from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('sim_url', default_value='http://127.0.0.1:8766'),
        DeclareLaunchArgument('tag_size', default_value='0.22'),
        Node(package='microduck_workshop_ros', executable='gateway', name='gateway',
             namespace='/workshop/microduck', output='screen',
             parameters=[{'sim_url': LaunchConfiguration('sim_url')}]),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(
            Path(get_package_share_directory('microduck_workshop_ros')) / 'launch/apriltag.launch.py')),
            launch_arguments={'tag_size': LaunchConfiguration('tag_size')}.items())])
