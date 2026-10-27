"""Transport-independent admission. HTTP test doubles are CPU fixtures only."""
import threading
import uuid
from microduck_workshop.contracts import ContractError, MotionCommand, identifier

MOTION_FIELDS = ('accepted', 'episode_id', 'request_id', 'generation', 'status', 'reason')


class Gateway:
    def __init__(self, transport, *, captures=None):
        self.transport = transport
        self.captures = captures
        self.step_request = None
        # Admission and accepted detections share a lock: a STOP cannot slip
        # between acquiring GO proof and marking the step active. No I/O here.
        self.lock = captures.lock if captures is not None else threading.RLock()
        self.episode_id = ''
        self.generation = 0
        self.token = None
        self.stopped = False
        self.pending = False
        self.seen = set()
        self.perception_stop_pending = False
        self._renewal_wakeup = threading.Event()
        if captures is not None:
            captures.on_detection = self._accepted_detection

    def _accepted_detection(self, detection):
        # Called under the shared capture/admission lock. Retain revocation
        # separately from latest perception, which must remain truthful.
        if (self.step_request is not None and not self.stopped
                and detection['episode_id'] == self.episode_id):
            if 1 in detection['tag_ids'] or 0 not in detection['tag_ids']:
                self.stopped = True
                self.token = None
                self.perception_stop_pending = True
            # A healthy lease does not extend the installed capture deadline.
            # Wake the sole renewer now; its periodic sleep can outlast that
            # deadline even while newer matched GO evidence is already here.
            # Only signal under this lock: never perform network I/O here.
            self._renewal_wakeup.set()

    def detect(self, sim_time, frame, tag_ids):
        if self.captures is None:
            return False
        accepted = self.captures.detect(sim_time, frame, tag_ids)
        self._stop_for_perception()
        return accepted

    def _stop_for_perception(self):
        with self.lock:
            stop_pending = self.perception_stop_pending
            self.perception_stop_pending = False
        if stop_pending:
            self.stop()
        return stop_pending

    def claim(self):
        health = self.transport.get('/v1/health')
        if health.get('protocol_version') != 1 or health.get('physics') != 'newton' or not health.get('ready'):
            raise ContractError('requires ready simulation-only Newton protocol v1')
        result = self.transport.post('/v1/claim', {'owner_id': 'ros5-' + uuid.uuid4().hex})
        with self.lock:
            self.episode_id = result['episode_id']
            self.generation = result['generation']
            self.token = result['lease_token']

    def _reject(self, request, reason, status='rejected'):
        return dict(accepted=False, episode_id=self.episode_id,
                    request_id=str(request.get('request_id', ''))[:64],
                    generation=self.generation, status=status, reason=reason)

    def command(self, request):
        """Legacy operator diagnostic; not autonomous signal-game acceptance."""
        return self._command(request, step=False)

    def step_forward(self, request):
        return self._command(request, step=True)

    def _step_headers(self):
        if self.captures is None:
            raise ContractError('no server-side capture source')
        return self.captures.step_headers(self.episode_id)

    def _command(self, request, *, step):
        try:
            cmd = MotionCommand.from_dict(request)
            if step and (cmd.vx, cmd.vy, cmd.wz, cmd.duration_s) != (.1, 0., 0., 2.):
                raise ContractError('step-forward-v1 requires fixed .10/0/0/2.0')
        except ContractError as exc:
            return self._reject(request if isinstance(request, dict) else {}, str(exc))
        with self.lock:
            if self.stopped or not self.token or self.pending:
                return self._reject(request, 'stopped, unowned, or command pending')
            if cmd.episode_id != self.episode_id or cmd.expected_generation != self.generation:
                return self._reject(request, 'stale episode or generation')
            if cmd.request_id in self.seen:
                return self._reject(request, 'duplicate request ID')
            try:
                proof = self._step_headers() if step else None
            except (ValueError, KeyError, TypeError):
                return self._reject(request, 'fresh same-episode GO proof unavailable')
            self.seen.add(cmd.request_id)
            self.pending = True
            if step:
                # Require fresh renewal proof even while the command ACK is in flight.
                self.step_request = cmd.request_id
            token = self.token
        try:
            if step:
                result = self.transport.post('/v1/step', cmd.as_dict(), token,
                                             observation_headers=proof)
            else:
                result = self.transport.post('/v1/command', cmd.as_dict(), token)
            if result['episode_id'] != cmd.episode_id or result['request_id'] != cmd.request_id:
                raise ContractError('mismatched command acknowledgment')
            with self.lock:
                self.generation = max(self.generation, result['generation'])
                if self.stopped:
                    return self._reject(request, 'priority stop superseded command', 'superseded_by_stop')
                if step and result['accepted'] is not True:
                    self.step_request = None
                return {k: result[k] for k in MOTION_FIELDS}
        except Exception:
            with self.lock:
                self.token = None
                self.stopped = True
            return self._reject(request, 'delivery uncertain; do not retry; lease will expire', 'delivery_unknown')
        finally:
            with self.lock:
                self.pending = False

    def status(self, episode, request_id):
        result = dict(known=False, completed=False, verification_available=False,
                      verified=False, status='unknown', reason='unavailable or stale epoch',
                      generation=self.generation)
        try:
            identifier(request_id, 'request_id')
            if episode != self.episode_id:
                return result
            raw = self.transport.get('/v1/status/' + request_id)
            if raw.get('episode_id') != episode:
                return result
            result = {key: raw[key] for key in result}
            result['verified'] = bool(result['verification_available'] and result['verified'])
            with self.lock:
                if (self.step_request == request_id and not self.pending
                        and raw.get('request_id') == request_id and raw.get('completed') is True):
                    self.step_request = None
        except Exception:
            pass
        return result

    def stop(self):
        # Do not hold the command lock across any network call. Each HTTP call
        # uses its own connection; stop cannot queue behind a blocked send.
        with self.lock:
            self.stopped = True
            self.token = None
            episode = self.episode_id
        try:
            result = self.transport.post('/v1/stop', {'episode_id': episode, 'latch': True})
            with self.lock:
                self.generation = max(self.generation, result.get('generation', self.generation))
            return {'success': True, 'message': 'stop acknowledged; not proof of physical rest'}
        except Exception:
            return {'success': False, 'message': 'stop delivery unknown; lease renewal disabled'}

    def renew_once(self):
        if self._stop_for_perception():
            return
        try:
            with self.lock:
                token, episode = self.token, self.episode_id
                if not token or self.stopped:
                    return
                proof = self._step_headers() if self.step_request is not None else None
            if proof is not None:
                self.transport.post('/v1/renew', {'episode_id': episode}, token,
                                    observation_headers=proof)
            else:
                self.transport.post('/v1/renew', {'episode_id': episode}, token)
        except Exception:
            # Disable authority BEFORE priority-stop IO. Missing/STOP/stale proof
            # cannot be papered over by a healthy actuator lease or a new claim.
            self.stop()

    def start_renewal(self, interval=.1):
        self.shutdown_event = threading.Event()
        def renew_loop():
            while not self.shutdown_event.is_set():
                self._renewal_wakeup.wait(interval)
                self._renewal_wakeup.clear()
                if self.shutdown_event.is_set():
                    break
                self.renew_once()
        self.renew_thread = threading.Thread(target=renew_loop, daemon=True)
        self.renew_thread.start()

    def close(self):
        if hasattr(self, 'shutdown_event'):
            self.shutdown_event.set()
            self._renewal_wakeup.set()
            self.renew_thread.join(timeout=1)
        self.stop()
