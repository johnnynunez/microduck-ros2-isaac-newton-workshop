"""Correlate real detector headers with original monotonic capture provenance."""
from collections import OrderedDict
import math
import threading
import time


def stamp_ns(seconds):
    return round(float(seconds) * 1_000_000_000)


class CaptureCache:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        # Optional local-state listener; runs under lock, never performs I/O.
        self.on_detection = None
        self.records = OrderedDict()
        self.latest = None
        self.episode = ''
        self.last_sim_time = -1.

    def clear(self):
        with self.lock:
            self.records.clear()
            self.latest = None

    def record(self, episode, sequence, sim_time, capture, frame):
        with self.lock:
            if episode != self.episode or sim_time < self.last_sim_time:
                self.clear()
            self.episode = episode
            self.last_sim_time = sim_time
            if not all(math.isfinite(x) for x in (sim_time, capture)):
                return
            key = (stamp_ns(sim_time), frame)
            # Duplicate reads cannot refresh the original capture age.
            if key not in self.records:
                self.records[key] = dict(episode_id=episode, frame_sequence=sequence,
                                         sim_time=sim_time, capture=capture, frame_id=frame)
            while len(self.records) > 64:
                self.records.popitem(last=False)

    def detect(self, sim_time, frame, tag_ids):
        with self.lock:
            record = self.records.get((stamp_ns(sim_time), frame))
            if record is None or not 0 <= self.clock() - record['capture'] <= .5:
                return False
            if self.latest and record['frame_sequence'] < self.latest['frame_sequence']:
                return False
            self.latest = dict(record, tag_ids=sorted(set(int(x) for x in tag_ids)))
            if self.on_detection is not None:
                self.on_detection(self.latest)
            return True

    def step_headers(self, episode):
        """Server-only proof, never a model observation or receipt-time restamp."""
        with self.lock:
            latest = self.latest
            if (latest is None or latest['episode_id'] != episode
                    or not 0 <= self.clock() - latest['capture'] < .5
                    or 0 not in latest['tag_ids'] or 1 in latest['tag_ids']
                    or type(latest['frame_sequence']) is not int
                    or latest['frame_sequence'] < 0):
                raise ValueError('step requires same-episode fresh GO without STOP')
            return {
                'X-Workshop-Observation-Episode': episode,
                'X-Workshop-Observation-Sequence': str(latest['frame_sequence']),
                'X-Workshop-Observation-Deadline': str(latest['capture'] + .5),
            }

    def observe(self, episode, generation):
        with self.lock:
            result = dict(fresh=False, episode_id=episode, generation=generation,
                          frame_sequence=0, sim_time=0., age_s=1e9,
                          frame_id='', tag_ids=[], reason='no fresh matched camera detection')
            if self.latest:
                age = self.clock() - self.latest['capture']
                if self.latest['episode_id'] == episode and 0 <= age <= .5:
                    result.update({k: self.latest[k] for k in ('frame_sequence', 'sim_time', 'frame_id', 'tag_ids')})
                    result.update(fresh=True, age_s=age, reason='matched original camera capture')
            return result
