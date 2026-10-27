from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('tag_size', default_value='0.22'),
        ComposableNodeContainer(
            name='apriltag_container', namespace='/workshop/microduck',
            package='rclcpp_components', executable='component_container_mt',
            composable_node_descriptions=[ComposableNode(
                package='isaac_ros_apriltag',
                plugin='nvidia::isaac_ros::apriltag::AprilTagNode',
                name='apriltag', namespace='/workshop/microduck',
                parameters=[{'size': ParameterValue(LaunchConfiguration('tag_size'), value_type=float),
                             'tag_family': 'tag36h11', 'backends': 'CUDA', 'max_tags': 64}],
                remappings=[('image', 'camera/image_rect'), ('camera_info', 'camera/camera_info')])],
            output='screen')])
