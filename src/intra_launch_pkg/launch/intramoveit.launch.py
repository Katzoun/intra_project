"""INTRA MoveIt + workcell visualization (no application nodes).
Starts:
    1) static TF   world → robot_base  (Z offset default: -0.6 m)
    2) RSP         workcell scene       (publishes TF + URDF on /workcell_description)
    3) MoveIt      minimal bringup      (virtual joint TFs, rsp, move_group, RViz)
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command, LaunchConfiguration, PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    workcell_pkg = FindPackageShare('workcell_pkg')
    moveit_pkg = FindPackageShare('robotarm_moveit_pkg')

    default_urdf = PathJoinSubstitution([workcell_pkg, 'urdf', 'workcell.urdf'])


    world_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='world_to_robot_base',
        arguments=[
            '--x', '0.0',
            '--y', '0.0',
            '--z', LaunchConfiguration('world_to_robot_base_z'),
            '--roll', '0.0',
            '--pitch', '0.0',
            '--yaw', '0.0',
            '--frame-id', 'world',
            '--child-frame-id', 'robot_base',
        ],
    )

    workcell_rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='workcell_state_publisher',
        parameters=[{
            'robot_description': ParameterValue(
                Command(['cat ', LaunchConfiguration('workcell_urdf')]),
                value_type=str,
            ),
        }],
        remappings=[('robot_description', 'workcell_description')],
    )

    static_virtual_joint_tfs = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([moveit_pkg, 'launch', 'static_virtual_joint_tfs.launch.py'])
        ),
    )

    moveit_rsp = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([moveit_pkg, 'launch', 'rsp.launch.py'])
        ),
        launch_arguments={
            'debug': LaunchConfiguration('debug'),
            'publish_frequency': LaunchConfiguration('rsp_publish_frequency'),
        }.items(),
    )

    move_group = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([moveit_pkg, 'launch', 'move_group.launch.py'])
        ),
        launch_arguments={
            'debug': LaunchConfiguration('debug'),
        }.items(),
    )

    moveit_rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([moveit_pkg, 'launch', 'moveit_rviz.launch.py'])
        ),
        condition=IfCondition(LaunchConfiguration('use_rviz')),
        launch_arguments={
            'debug': LaunchConfiguration('debug'),
        }.items(),
    )

    spawn_collision_objects = Node(
        package='workcell_pkg',
        executable='spawn_collision_objects',
        name='spawn_collision_objects',
        output='screen',
    )

    spawn_collision_objects_delayed = TimerAction(
        period=LaunchConfiguration('collision_spawn_delay'),
        actions=[spawn_collision_objects],
    )


    return LaunchDescription([
        DeclareLaunchArgument('workcell_urdf', default_value=default_urdf,
                              description='Path to pre-built workcell URDF'),
        DeclareLaunchArgument('world_to_robot_base_z', default_value='0.6',
                              description='world → robot_base translation in Z (m)'),
        DeclareLaunchArgument('use_rviz', default_value='true'),
        DeclareLaunchArgument('debug',    default_value='false'),
        DeclareLaunchArgument('rsp_publish_frequency', default_value='100.0',
                              description='Robot state publisher TF publish rate (Hz)'),
        DeclareLaunchArgument(
            'collision_spawn_delay',
            default_value='10.0',
            description='Delay (s) before spawning workcell collision objects',
        ),

        LogInfo(msg='═══════════════════════════════════════════'),
        LogInfo(msg='  INTRA MoveIt + RViz (no app nodes)      '),
        LogInfo(msg=['  Workcell URDF: ', LaunchConfiguration('workcell_urdf')]),
        LogInfo(msg='═══════════════════════════════════════════'),

        world_tf,
        workcell_rsp,
        static_virtual_joint_tfs,
        moveit_rsp,
        move_group,
        spawn_collision_objects_delayed,
        moveit_rviz,
    ])
