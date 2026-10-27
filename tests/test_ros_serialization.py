"""Real generated ROS CDR, not DDS/physics. Run directly inside the ROS image.

Each case uses a child because the broken float64 ABI aborts rather than raises.
The ordinary host suite skips when generated ROS types are not installed.
"""
import importlib.util
import json
import subprocess
import sys
import unittest

CODE = '''
import json, resource, sys
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from microduck_workshop.contracts import MotionCommand
from microduck_workshop.agent.gateway import service_request
from microduck_workshop_interfaces.srv import BoundedMotion
from rclpy.serialization import serialize_message, deserialize_message
cmd = MotionCommand("serialization", "request", 7, **json.loads(sys.argv[1]))
req = service_request(BoundedMotion.Request, cmd.as_dict())
blob = serialize_message(req)
back = deserialize_message(blob, BoundedMotion.Request)
for field in ("vx", "vy", "wz", "duration_s"):
    assert type(getattr(back, field)) is float
    assert getattr(back, field) == getattr(cmd, field)
assert back.episode_id == cmd.episode_id
assert back.request_id == cmd.request_id
assert type(back.expected_generation) is int and back.expected_generation == 7
print("CDR roundtrip", len(blob))
'''


@unittest.skipUnless(importlib.util.find_spec("rclpy"), "requires real ROS image")
class GeneratedSerialization(unittest.TestCase):
    def test_validated_integer_numbers_roundtrip(self):
        base = dict(vx=.05, vy=0., wz=0., duration_s=.5)
        for fields in (base, dict(base, vy=0, wz=0), dict(base, duration_s=1),
                       dict(base, vx=0), dict(vx=.1, vy=0, wz=0, duration_s=2)):
            with self.subTest(fields=fields):
                child = subprocess.run([sys.executable, '-c', CODE, json.dumps(fields)],
                                       capture_output=True, text=True, timeout=15)
                self.assertEqual(child.returncode, 0, child.stderr)
                self.assertIn('CDR roundtrip', child.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
