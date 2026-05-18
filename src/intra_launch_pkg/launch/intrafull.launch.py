"""INTRA Robotic Application – full bringup.

Starts:
  1) static TF   world → robot_base
  2) RSP         workcell scene on /workcell_description
  3) MoveIt      minimal bringup (virtual joint TFs, rsp, move_group, RViz)
  4) Application nodes (user interface, robot controller, camera controller, vision)
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, ThisLaunchFileDir
from launch_ros.actions import Node

def generate_launch_description():

    log_level = LaunchConfiguration('log_level')

    # ── MoveIt + Workcell
    intra_moveit = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([ThisLaunchFileDir(), 'intramoveit.launch.py'])
        ),
    )

    user_interface = Node(
        package='user_interface_pkg',
        executable='user_interface_node_exec',
        output='screen',
        parameters=[{'log_level': log_level}],
        emulate_tty=True, respawn=True, respawn_delay=5.0,
    )

    robot_controller = Node(
        package='intranodes_pkg',
        executable='robot_controller_node_exec',
        output='screen',
        parameters=[{'log_level': log_level}],
        remappings=[('/robot_controller/joint_states', '/joint_states')],
        emulate_tty=True, respawn=True, respawn_delay=5.0,
    )

    camera_controller = Node(
        package='intranodes_pkg',
        executable='camera_controller_node_exec',
        output='screen',
        parameters=[{'log_level': log_level}],
        emulate_tty=True, respawn=True, respawn_delay=5.0,
    )

    vision = Node(
        package='intranodes_pkg',
        executable='vision_processing_node_exec',
        output='screen',
        parameters=[{'log_level': log_level}],
        emulate_tty=True, respawn=True, respawn_delay=5.0,
    )

    # Coordinator Node
    coordinator = Node(
            package='intranodes_pkg',
            executable='coordinator_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        )

    # Tool Controller Node
    tool_controller = Node(
            package='intranodes_pkg',
            executable='tool_controller_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        )

    # Motion Planning Node
    motion_planning = Node(
            package='intranodes_pkg',
            executable='motion_planning_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        )


    return LaunchDescription([
        DeclareLaunchArgument('log_level', default_value='info'),

        LogInfo(msg='═══════════════════════════════════════════'),
        LogInfo(msg='  INTRA full bringup                      '),
        LogInfo(msg='═══════════════════════════════════════════'),

        intra_moveit,
        user_interface,
        robot_controller,
        camera_controller,
        vision,
        coordinator,
        tool_controller,
        motion_planning,
    ])
