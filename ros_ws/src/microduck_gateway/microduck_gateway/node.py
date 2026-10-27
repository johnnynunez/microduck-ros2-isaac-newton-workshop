"""Real ROS 2 Lyrical sidecar. No fake publishers, ROS ABI mixing or robot I/O."""
import io
import time
from PIL import Image as PILImage
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import qos_profile_sensor_data
from builtin_interfaces.msg import Time
from sensor_msgs.msg import CameraInfo, Image, Imu, JointState
from rosgraph_msgs.msg import Clock
from std_srvs.srv import Trigger
from isaac_ros_apriltag_interfaces.msg import AprilTagDetectionArray
from microduck_workshop_interfaces.srv import BoundedMotion, MotionStatus, Observe
from microduck_gateway.core import Gateway
from microduck_gateway.perception import CaptureCache, stamp_ns
from microduck_gateway.sensors import checked_state, checked_calibration
from microduck_gateway.transport import SimHTTP


def ros_stamp(seconds):
    nanoseconds = stamp_ns(seconds)
    return Time(sec=nanoseconds // 1_000_000_000, nanosec=nanoseconds % 1_000_000_000)


def assign(response, values):
    for key, value in values.items():
        setattr(response, key, value)
    return response


class GatewayNode(Node):
    def __init__(self):
        super().__init__('gateway', namespace='/workshop/microduck')
        self.declare_parameter('sim_url', 'http://127.0.0.1:8766')
        self.transport = SimHTTP(self.get_parameter('sim_url').value)
        self.captures = CaptureCache()
        self.gateway = Gateway(self.transport, captures=self.captures)
        self.last_state = None
        self.last_camera = None
        self.calibration = None
        try:
            self.gateway.claim()
        except Exception:
            self.get_logger().error('Simulator unavailable or lease refused. No command authority; start simulator then explicitly restart gateway.')
        self.gateway.start_renewal()
        self.groups = [MutuallyExclusiveCallbackGroup() for _ in range(7)]
        self.create_service(BoundedMotion, 'bounded_motion', self.motion, callback_group=self.groups[0])
        self.create_service(BoundedMotion, 'step_forward', self.step_forward, callback_group=self.groups[0])
        self.create_service(MotionStatus, 'motion_status', self.status, callback_group=self.groups[1])
        self.create_service(Observe, 'observe', self.observe, callback_group=self.groups[2])
        self.create_service(Trigger, 'emergency_stop', self.stop, callback_group=self.groups[3])
        self.joints = self.create_publisher(JointState, 'joint_states', qos_profile_sensor_data)
        self.imu = self.create_publisher(Imu, 'imu', qos_profile_sensor_data)
        self.clock_pub = self.create_publisher(Clock, '/clock', 10)
        self.images = self.create_publisher(Image, 'camera/image_rect', qos_profile_sensor_data)
        self.infos = self.create_publisher(CameraInfo, 'camera/camera_info', qos_profile_sensor_data)
        self.create_subscription(AprilTagDetectionArray, 'tag_detections', self.detection, 10, callback_group=self.groups[4])
        self.create_timer(.02, self.poll_state, callback_group=self.groups[5])
        self.create_timer(.1, self.poll_camera, callback_group=self.groups[6])

    def motion(self, request, response):
        body = {name: getattr(request, name) for name in request.get_fields_and_field_types()}
        return assign(response, self.gateway.command(body))

    def step_forward(self, request, response):
        body = {name: getattr(request, name) for name in request.get_fields_and_field_types()}
        return assign(response, self.gateway.step_forward(body))

    def status(self, request, response):
        return assign(response, self.gateway.status(request.episode_id, request.request_id))

    def observe(self, request, response):
        with self.gateway.lock:
            return assign(response, self.captures.observe(self.gateway.episode_id, self.gateway.generation))

    def stop(self, request, response):
        return assign(response, self.gateway.stop())

    def detection(self, message):
        stamp = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        self.captures.detect(stamp, message.header.frame_id, [tag.id for tag in message.detections])

    def poll_state(self):
        if not self.gateway.episode_id:
            return
        try:
            raw = self.transport.get('/v1/state')
            if raw['episode_id'] != self.gateway.episode_id:
                self.captures.clear()
                with self.gateway.lock:
                    self.gateway.token = None
                    self.gateway.stopped = True
                return
            state = checked_state(raw, self.gateway.episode_id)
            identity = (state['episode_id'], state['sequence'])
            if identity == self.last_state:
                return
            self.last_state = identity
            if raw.get('stop_latched'):
                with self.gateway.lock:
                    self.gateway.token = None
                    self.gateway.stopped = True
            stamp = ros_stamp(state['sim_time'])
            joint = JointState()
            joint.header.stamp = stamp
            joint.name = state['joint_names']
            joint.position = [float(x) for x in state['joint_position']]
            joint.velocity = [float(x) for x in state['joint_velocity']]
            imu = Imu()
            imu.header.stamp = stamp
            imu.header.frame_id = 'imu_link'
            imu.orientation_covariance[0] = -1.0  # no GT orientation
            for key in ('angular_velocity', 'linear_acceleration'):
                target = getattr(imu, key)
                target.x, target.y, target.z = map(float, state['imu'][key])
            self.joints.publish(joint)
            self.imu.publish(imu)
            self.clock_pub.publish(Clock(clock=stamp))
        except Exception:
            self.get_logger().warning('State unavailable, stale or invalid; no replacement telemetry published.', throttle_duration_sec=5.)

    def poll_camera(self):
        if not self.gateway.episode_id:
            return
        try:
            payload, meta = self.transport.camera()
            if meta['episode'] != self.gateway.episode_id:
                self.captures.clear()
                return
            if not 0 <= time.monotonic() - meta['capture'] <= .5:
                return
            identity = (meta['episode'], meta['sequence'])
            if identity == self.last_camera:
                return
            if self.calibration is None:
                self.calibration = checked_calibration(self.transport.get('/v1/camera_info'))
            calibration = self.calibration
            with PILImage.open(io.BytesIO(payload)) as decoded:
                rgb = decoded.convert('RGB')
                if rgb.size != (calibration['width'], calibration['height']):
                    raise ValueError('image calibration dimensions mismatch')
                data = rgb.tobytes()
            stamp = ros_stamp(meta['sim_time'])
            frame = calibration['frame_id']
            image = Image()
            image.header.stamp, image.header.frame_id = stamp, frame
            image.width, image.height = calibration['width'], calibration['height']
            image.encoding, image.step = 'rgb8', image.width * 3
            image.data = data
            info = CameraInfo()
            info.header = image.header
            for field in ('width', 'height', 'distortion_model', 'k', 'd', 'r', 'p'):
                setattr(info, field, calibration[field])
            self.captures.record(meta['episode'], meta['sequence'], meta['sim_time'], meta['capture'], frame)
            self.infos.publish(info)
            self.images.publish(image)
            self.last_camera = identity
        except Exception:
            self.get_logger().warning('Camera unavailable, stale or invalid; no placeholder image published.', throttle_duration_sec=5.)

    def destroy_node(self):
        self.gateway.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GatewayNode()
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    except Exception:
        # Lyrical can race SIGTERM shutdown against WaitSet construction.
        # Suppress only after the ROS context has actually shut down.
        if rclpy.ok():
            raise
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
