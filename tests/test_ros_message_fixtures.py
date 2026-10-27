"""ROS message-conversion unit fixtures only. NOT live sensor acceptance."""
import io
import sys
import time
from pathlib import Path
import pytest
pytest.importorskip('rclpy')
import rclpy
from PIL import Image
sys.path.insert(0, str(Path(__file__).parents[1] / 'ros_ws/src/microduck_gateway'))
from microduck_gateway.node import GatewayNode


class Sink:
    def __init__(self): self.messages = []
    def publish(self, message): self.messages.append(message)


def test_ros_image_and_camera_info_preserve_atomic_stamp_and_validate_calibration():
    rclpy.init(args=['--ros-args', '-p', 'sim_url:=http://127.0.0.1:18766'])
    node = GatewayNode()
    node.gateway.episode_id = 'fixture'
    node.images, node.infos = Sink(), Sink()
    data = io.BytesIO()
    Image.new('RGB', (2, 2), (255, 255, 255)).save(data, format='JPEG')
    calibration = dict(width=2, height=2, frame_id='fixture_camera', encoding='rgb8',
                       distortion_model='plumb_bob', k=[1.,0.,1.,0.,1.,1.,0.,0.,1.],
                       d=[0.]*5, r=[1.,0.,0.,0.,1.,0.,0.,0.,1.],
                       p=[1.,0.,1.,0.,0.,1.,1.,0.,0.,0.,1.,0.])
    class Fixture:
        sequence = 1
        def camera(self):
            return data.getvalue(), dict(episode='fixture', sequence=self.sequence, sim_time=1.25, capture=time.monotonic())
        def get(self, path): return calibration
    fixture = Fixture()
    node.transport = fixture
    try:
        node.poll_camera()
        assert len(node.images.messages) == 1
        image, info = node.images.messages[0], node.infos.messages[0]
        assert image.header == info.header
        assert image.header.stamp.sec == 1 and image.header.stamp.nanosec == 250000000
        assert image.header.frame_id == 'fixture_camera'
        assert image.encoding == 'rgb8' and len(image.data) == 12
        fixture.sequence = 2
        node.calibration = None
        calibration['k'][0] = float('nan')
        node.poll_camera()
        assert len(node.images.messages) == 1  # must reject nonfinite calibration
    finally:
        node.destroy_node()
        rclpy.shutdown()
