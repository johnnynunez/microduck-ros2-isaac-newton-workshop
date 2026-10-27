"""Actual NVIDIA CUDA detector + official image bag, never a fake publisher.
Run inside ROS5 container with /workshop mounted to this checkout.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, CameraInfo
from isaac_ros_apriltag_interfaces.msg import AprilTagDetectionArray
from microduck_gateway.perception import CaptureCache

ROOT = Path(os.environ.get('WORKSHOP_ROOT', '/workshop'))
NS = '/workshop/microduck/'

def main():
    rclpy.init()
    node = rclpy.create_node('real_cuda_apriltag_gate')
    cache = CaptureCache()
    receipt = dict(evidence_scope='official_rosbag_not_live_microduck', backend='CUDA',
                   family='tag36h11', tag_size_m=.22, image_count=0, camera_info_count=0,
                   detection_messages=0, matched_detections=[], input_stopped_stale=False)
    def image(msg):
        receipt['image_count'] += 1
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        cache.record('bag_replay', receipt['image_count'], stamp, time.monotonic(), msg.header.frame_id)
    def info(msg):
        receipt['camera_info_count'] += 1
    def detection(msg):
        receipt['detection_messages'] += 1
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        ids = [d.id for d in msg.detections]
        if cache.detect(stamp, msg.header.frame_id, ids) and ids:
            receipt['matched_detections'].append(dict(stamp_sec=msg.header.stamp.sec,
                stamp_nanosec=msg.header.stamp.nanosec, frame_id=msg.header.frame_id, tag_ids=ids))
    subs = [node.create_subscription(Image, NS+'camera/image_rect', image, qos_profile_sensor_data),
            node.create_subscription(CameraInfo, NS+'camera/camera_info', info, qos_profile_sensor_data),
            node.create_subscription(AprilTagDetectionArray, NS+'tag_detections', detection, 10)]
    logs = ROOT/'.workshop/receipts'
    detector_log = open(logs/'apriltag-detector.log', 'w')
    bag_log = open(logs/'apriltag-player.log', 'w')
    detector = subprocess.Popen(['ros2', 'launch', str(ROOT/'ros_ws/src/microduck_gateway/launch/apriltag.launch.py')],
                                stdout=detector_log, stderr=subprocess.STDOUT, start_new_session=True)
    player = None
    try:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline and node.count_publishers(NS+'tag_detections') == 0:
            assert detector.poll() is None, 'CUDA component exited during startup'
            rclpy.spin_once(node, timeout_sec=.1)
        assert node.count_publishers(NS+'tag_detections') > 0, 'detector never appeared'
        player = subprocess.Popen(['ros2', 'bag', 'play', str(ROOT/'.workshop/apriltag/isaac_ros_apriltag/quickstart.bag'),
            '--rate', '0.5', '--delay', '2', '--remap', '/image:='+NS+'camera/image_rect',
            '/camera_info:='+NS+'camera/camera_info'], stdout=bag_log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and player.poll() is None:
            assert detector.poll() is None, 'CUDA component exited during playback'
            rclpy.spin_once(node, timeout_sec=.02)
        assert player.poll() == 0, 'bag playback failed or timed out'
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.05)
        receipt['input_stopped_stale'] = not cache.observe('bag_replay', 0)['fresh']
        assert receipt['image_count'] > 0 and receipt['camera_info_count'] > 0
        assert receipt['matched_detections'], 'no real CUDA detections matched actual images'
        assert receipt['input_stopped_stale']
        receipt['passed'] = True
    finally:
        for process in (player, detector):
            if process and process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        detector_log.close()
        bag_log.close()
        (logs/'apriltag-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print(json.dumps(receipt, indent=2))
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
