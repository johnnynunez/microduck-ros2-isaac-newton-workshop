"""Transport-independent admission. HTTP test doubles are CPU fixtures only."""
import threading
import uuid
from microduck_workshop.contracts import ContractError, MotionCommand, identifier

MOTION_FIELDS = ('accepted', 'episode_id', 'request_id', 'generation', 'status', 'reason')


class Gateway:
    def __init__(self, transport):
        self.transport = transport
        self.lock = threading.RLock()
        self.episode_id = ''
        self.generation = 0
        self.token = None
        self.stopped = False
        self.pending = False
        self.seen = set()

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
        try:
            cmd = MotionCommand.from_dict(request)
        except ContractError as exc:
            return self._reject(request if isinstance(request, dict) else {}, str(exc))
        with self.lock:
            if self.stopped or not self.token or self.pending:
                return self._reject(request, 'stopped, unowned, or command pending')
            if cmd.episode_id != self.episode_id or cmd.expected_generation != self.generation:
                return self._reject(request, 'stale episode or generation')
            if cmd.request_id in self.seen:
                return self._reject(request, 'duplicate request ID')
            self.seen.add(cmd.request_id)
            self.pending = True
            token = self.token
        try:
            result = self.transport.post('/v1/command', cmd.as_dict(), token)
            if result['episode_id'] != cmd.episode_id or result['request_id'] != cmd.request_id:
                raise ContractError('mismatched command acknowledgment')
            with self.lock:
                self.generation = max(self.generation, result['generation'])
                if self.stopped:
                    return self._reject(request, 'priority stop superseded command', 'superseded_by_stop')
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

    def start_renewal(self, interval=.1):
        self.shutdown_event = threading.Event()
        def renew_loop():
            while not self.shutdown_event.wait(interval):
                with self.lock:
                    token, episode = self.token, self.episode_id
                if not token:
                    continue
                try:
                    self.transport.post('/v1/renew', {'episode_id': episode}, token)
                except Exception:
                    with self.lock:
                        self.token = None
                        self.stopped = True
        self.renew_thread = threading.Thread(target=renew_loop, daemon=True)
        self.renew_thread.start()

    def close(self):
        if hasattr(self, 'shutdown_event'):
            self.shutdown_event.set()
            self.renew_thread.join(timeout=1)
        self.stop()
