from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="arms_detection",
            executable="arms_detection_node",
            name="arms_detection_node",
            output="screen",
        ),
    ])
