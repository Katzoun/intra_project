import os

from moveit_configs_utils import MoveItConfigsBuilder
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    moveit_config = MoveItConfigsBuilder("robotarm", package_name="robotarm_moveit_pkg").to_moveit_configs()

    move_group_configuration = {
        "publish_robot_description_semantic": True,
        "allow_trajectory_execution": True,
        "publish_monitored_planning_scene": True,
        "capabilities": moveit_config.move_group_capabilities.get("capabilities", ""),
        "disable_capabilities": moveit_config.move_group_capabilities.get("disable_capabilities", ""),
        "publish_planning_scene": True,
        "publish_geometry_updates": True,
        "publish_state_updates": True,
        "publish_transforms_updates": True,
        "monitor_dynamics": False,
    }

    move_group_params = [
        moveit_config.to_dict(),
        move_group_configuration,
    ]

    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=move_group_params,
        # ros_arguments go into the --ros-args section the launch system already creates
        ros_arguments=["--log-level", LaunchConfiguration("log_level")],
        # --debug is a move_group binary flag that enables OMPL native verbose logging
        arguments=["--debug"],
        additional_env={"DISPLAY": os.environ.get("DISPLAY", "")},
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            "log_level",
            default_value="DEBUG",
            description="ROS2 log level for move_group (DEBUG / INFO / WARN / ERROR)",
        ),
        move_group_node,
    ])
