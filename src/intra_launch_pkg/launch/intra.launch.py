"""
INTRA Project Main Launch File
Launches all core services for the INTRA robotic inspection system.
"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration


def generate_launch_description():

    
    # Declare launch arguments
    log_level_arg = DeclareLaunchArgument(
        'log_level',
        default_value='info',
        description='Logging level (debug, info, warn, error, fatal)'
    )
    
    # Get launch configuration
    log_level = LaunchConfiguration('log_level')
    
    return LaunchDescription([
        # Launch arguments
        log_level_arg,
        
        # Startup message
        LogInfo(msg='========================================'),
        LogInfo(msg='Starting INTRA Project Nodes'),
        LogInfo(msg='========================================'),
        
        # Frontend Node
        Node(
            package='user_interface_pkg',
            executable='user_interface_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        ),
        
        # Robot Controller Node
        Node(
            package='intranodes_pkg',
            executable='robot_controller_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            remappings=[('/robot_controller/joint_states', '/joint_states')],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        ),
        
        # Photoneo Camera Node
        Node(
            package='intranodes_pkg',
            executable='camera_controller_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        ),
        # Vision Processing Node
        Node(
            package='intranodes_pkg',
            executable='vision_processing_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        ),

        # Coordinator Node
        Node(
            package='intranodes_pkg',
            executable='coordinator_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        ),

            # Motion Planning Node
        Node(
            package='intranodes_pkg',
            executable='motion_planning_node_exec',
            output='screen',
            parameters=[{
                'log_level': log_level,
            }],
            emulate_tty=True,
            respawn=True,
            respawn_delay=5.0,
        ),

        
        # Completion message
        LogInfo(msg='========================================'),
        LogInfo(msg='All INTRA Nodes started successfully'),
        LogInfo(msg='========================================'),
    ])
