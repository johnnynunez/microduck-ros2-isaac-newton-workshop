"""Read-only ROS 2 JointState observer; ROS imports happen only in run()."""


import math


def select_positions(names, positions, requested):
    """Map finite positions by unique names; malformed/missing data raises ValueError."""
    for group in (names, requested):
        if any(not isinstance(name, str) or not name for name in group):
            raise ValueError("joint names must be nonempty strings")
        if len(set(group)) != len(group):
            raise ValueError("joint names must be unique")
    if len(names) != len(positions):
        raise ValueError("name and position arrays must have equal lengths")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in positions):
        raise ValueError("joint positions must be finite numbers, not bools or strings")
    by_name = dict(zip(names, positions, strict=True))
    if any(name not in by_name for name in requested):
        raise ValueError("a requested joint is missing from this message")
    return {name: by_name[name] for name in requested}


def stamp_status(stamp_ns, now_ns, max_age_ns=500_000_000):
    """Classify simulation-time age. This is NOT a wall-clock safety watchdog."""
    if any(type(value) is not int for value in (stamp_ns, now_ns, max_age_ns)):
        raise ValueError("timestamps and limit must be integer nanoseconds")
    if stamp_ns < 0 or now_ns < 0 or max_age_ns <= 0:
        raise ValueError("timestamps must be nonnegative and age limit positive")
    if now_ns == 0:
        return "waiting_for_clock"
    if stamp_ns > now_ns:
        return "future_stamp"
    if now_ns - stamp_ns > max_age_ns:
        return "stale_sim_age"
    return "within_sim_age"


def run(select_fn=select_positions, stamp_fn=stamp_status, args=None):
    """Run a real subscriber in the prepared Lyrical shell; never publish motion.

    Passing the two helpers lets the student exercise use the same ROS wiring.
    The simulation-age label is diagnostic only, not a command authorization.
    """
    import time

    import rclpy
    from rclpy.executors import ExternalShutdownException
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import JointState

    class JointWatch(Node):
        def __init__(self):
            super().__init__("joint_watch")
            self.joint = self.declare_parameter("joint_name", "left_knee").value
            self.last_log = float("-inf")
            self.subscription = self.create_subscription(
                JointState, "/workshop/microduck/joint_states", self.on_message,
                qos_profile_sensor_data,
            )
            self.get_logger().info("Read-only joint observer; Ctrl+C exits. No motion tools.")

        def on_message(self, msg):
            # Wall time limits logging even if /clock is paused or rewound.
            wall_now = time.monotonic()
            if wall_now - self.last_log < 1.0:
                return
            self.last_log = wall_now
            try:
                selected = select_fn(msg.name, msg.position, [self.joint])
                stamp_ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
                status = stamp_fn(stamp_ns, self.get_clock().now().nanoseconds)
            except ValueError as error:
                self.get_logger().warning(f"Sample discarded: {error}")
                return
            self.get_logger().info(
                f"{self.joint}={selected[self.joint]:.4f} rad; {status}; stamp_ns={stamp_ns}"
            )

    rclpy.init(args=args)
    node = None
    try:
        node = JointWatch()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    run()
