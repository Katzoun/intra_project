"""
Configuration Page
Allows administrators to configure robot and camera settings.
"""
from nicegui import ui, app
import asyncio
from functools import partial
from typing import Optional
from core_pkg.nodes_async import AsyncINTRANode
from user_interface_pkg.pages.layout_page import create_main_layout
from core_pkg.exceptions import ValidationError
from user_interface_pkg.constants import CONFIGURATION_PAGE
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from intranodes_pkg.parameters.camera_controller_parameters import CameraControllerParametersKeys, CameraControllerParameters
from intranodes_pkg.parameters.robot_controller_parameters import RobotParametersKeys, RobotParameters
from intranodes_pkg.parameters.coordinator_parameters import CoordinatorParametersKeys, CoordinatorParameters
from intranodes_pkg.parameters.vision_parameters import VisionParametersKeys, VisionParameters
from intranodes_pkg.parameters.tool_controller_parameters import ToolControllerParametersKeys, ToolControllerParameters
from intranodes_pkg.parameters.motion_planning_parameters import MotionPlanningParametersKeys, MotionPlanningParameters
from core_pkg.systemconstants import MotionPlanningConstants
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
from core_pkg.exceptions import ServiceCallException
from core_pkg.settings import ROBOT_CONFIG_YAML, CAMERA_CONFIG_YAML, COORDINATOR_CONFIG_YAML, VISION_PROCESSING_CONFIG_YAML, TOOL_CONTROLLER_CONFIG_YAML, MOTION_PLANNING_CONFIG_YAML
import numpy as np

def configuration_page_factory(node: AsyncINTRANode):
    """
    Factory function to create configuration page view.
    Returns a function with access to ROS2 node via closure.
    
    Args:
        node: ROS2 AsyncINTRANode node instance
    
    Returns:
        async configuration page view function
    """

    async def create_configuration_page() -> None:
        """
        Configuration page for robot and camera settings.
        Only accessible to users with 'allow_system_config' permission.
        """
        try:
            accessor_dto = await get_valid_accessor()
            if accessor_dto is None:
                return
            
            # Create layout (header + sidebar) and get content area
            with create_main_layout(accessor=accessor_dto, active_page=CONFIGURATION_PAGE.page):
                # Page header
                with ui.row().classes('w-full items-center mb-6'):
                    ui.icon(CONFIGURATION_PAGE.icon).classes('text-4xl text-primary mr-3')
                    with ui.column().classes('gap-0'):
                        ui.label(CONFIGURATION_PAGE.name).classes('text-h4 mt-4')
                        ui.label('Configure node parameters').classes('text-subtitle2 text-grey-7')
                with ui.card().classes('w-full p-6 mb-4'):
                    # Header with refresh button
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Robot Configuration').classes('text-h6')
                    
                    # Connection Parameters
                    ui.label('Connection').classes('text-subtitle1 font-bold mb-3')
                    
                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        robot_ip = ui.input(
                            RobotParametersKeys.IP_ADDRESS,
                            placeholder='192.168.1.156'
                        ).props('outlined dense').classes('w-full')
                        
                        robot_port = ui.number(
                            RobotParametersKeys.PORT,
                            value=80,
                            min=1,
                            max=65535
                        ).props('outlined dense').classes('w-full')
                        
                        robot_username = ui.input(
                            RobotParametersKeys.USERNAME,
                            placeholder='admin'
                        ).props('outlined dense').classes('w-full')
                        
                        robot_password = ui.input(
                            RobotParametersKeys.PASSWORD,
                            password=True,
                            password_toggle_button=True
                        ).props('outlined dense').classes('w-full')
                    
                    # Utility Parameters
                    ui.label('Utility').classes('text-subtitle1 font-bold mb-3 mt-4')
                    
                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        robot_keepalive = ui.switch(
                            RobotParametersKeys.SEND_KEEPALIVE,
                            value=True
                        ).classes('w-full')
                        
                        robot_keepalive_interval = ui.number(
                            RobotParametersKeys.KEEPALIVE_INTERVAL,
                            value=60.0,
                            min=1.0,
                            step=1.0,
                            suffix=' seconds'
                        ).props('outlined dense').classes('w-full')

                        robot_send_joint_states = ui.switch(
                            RobotParametersKeys.SEND_JOINT_STATES,
                            value=True
                        ).classes('w-full')

                        robot_joint_states_hz = ui.number(
                            RobotParametersKeys.JOINT_STATES_HZ,
                            value=5.0,
                            min=0.1,
                            step=0.5,
                            suffix=' Hz'
                        ).props('outlined dense').classes('w-full')

                    # DIPC Parameters
                    ui.label('DIPC').classes('text-subtitle1 font-bold mb-3 mt-4')

                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        robot_dipc_retry_max = ui.number(
                            'Max Retries',
                            value=100,
                            min=1,
                            step=1
                        ).props('outlined dense').classes('w-full')

                        robot_dipc_retry_delay = ui.number(
                            'Retry Delay',
                            value=0.25,
                            min=0.01,
                            step=0.05,
                            suffix=' seconds'
                        ).props('outlined dense').classes('w-full')

                    ui.separator().classes('my-4')
                    
                    # Action buttons
                    with ui.row().classes('w-full justify-end gap-2'):
                        robot_load_yaml_button = ui.button('Load YAML', icon='file_upload').props('flat color=secondary')
                        robot_save_yaml_button = ui.button('Save YAML', icon='file_download').props('flat color=secondary')
                        robot_get_live_param_button = ui.button('Get Node Parameters', icon='download').props('color=primary')
                        robot_apply_param_button = ui.button('Apply Node Parameters', icon='save').props('color=primary')
                with ui.card().classes('w-full p-6 mb-4'):
                    # Header
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Camera Configuration').classes('text-h6')
                    
                    # Device Settings
                    ui.label('Device').classes('text-subtitle1 font-bold mb-3')
                    
                    with ui.grid(columns=1).classes('w-full gap-4 mb-4'):
                        camera_device_id = ui.input(
                            'Device ID',
                            placeholder='PhotoneoTL_DEV_2019-06-011-LC3',
                            value='PhotoneoTL_DEV_2019-06-011-LC3'
                        ).props('outlined dense').classes('w-full')
                    
                    # Output Settings
                    ui.label('Output').classes('text-subtitle1 font-bold mb-3 mt-4')    
                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        camera_publish_topics = ui.switch('Publish to Topics', value=True).classes('w-full')
                        camera_save_to_file = ui.switch('Save to File', value=True).classes('w-full')
                        camera_save_mesh = ui.switch('Save Mesh', value=True).classes('w-full')
                        camera_save_depth_map = ui.switch('Save Depth Map', value=True).classes('w-full')
                        camera_save_point_cloud = ui.switch('Save Point Cloud', value=True).classes('w-full')
                        camera_save_normal_map = ui.switch('Save Normal Map', value=True).classes('w-full')
                    
                    # Capture Settings
                    ui.label('Capture').classes('text-subtitle1 font-bold mb-3 mt-4')
                    
                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        camera_coding_strategy = ui.select(
                            options=['Normal', 'Interreflections'],
                            value='Interreflections',
                            label='Coding Strategy'
                        ).props('outlined dense').classes('w-full')
                        camera_ambient_light_suppression = ui.switch('Ambient Light Suppression', value=True).classes('w-full')
                    
                    # Point Cloud Settings
                    ui.label('Point Cloud Output').classes('text-subtitle1 font-bold mb-3 mt-4')
                    
                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        camera_send_texture = ui.switch('Send Texture', value=True).classes('w-full')
                        camera_send_point_cloud = ui.switch('Send Point Cloud', value=True).classes('w-full')
                        camera_send_normal_map = ui.switch('Send Normal Map', value=True).classes('w-full')
                        camera_send_depth_map = ui.switch('Send Depth Map', value=True).classes('w-full')
                        camera_send_confidence_map = ui.switch('Send Confidence Map', value=True).classes('w-full')
                    
                    ui.label('Point Cloud Transformation').classes('text-subtitle1 font-bold mb-3 mt-4')
                    with ui.grid(columns=1).classes('w-full gap-4 mb-4'):
                        camera_coordinate_space = ui.select(
                            options=['CameraSpace', 'RobotSpace'],
                            value='RobotSpace',
                            label='Coordinate Space Selector'
                        ).props('outlined dense').classes('w-full')
                        camera_use_transform = ui.switch('Use Transform', value=True).classes('w-full')
                        camera_frame_id = ui.input('TF Frame ID', value='camera_link').classes('w-full')

                    ui.label('Calibration Transform (4x4)').classes('text-subtitle1 font-bold mb-3 mt-4')
                    camera_transform_display = ui.code('No transform loaded', language='text').classes('w-full')
                    with ui.row().classes('w-full gap-2 mt-2'):
                        camera_reload_transform_yaml_btn = ui.button(
                            'Reload from YAML', icon='file_upload'
                        ).props('outline color=secondary')
                        camera_get_transform_node_btn = ui.button(
                            'Get from Node', icon='download'
                        ).props('outline color=primary')
                        camera_apply_transform_node_btn = ui.button(
                            'Apply to Node', icon='save'
                        ).props('color=primary')

                    ui.separator().classes('my-4')

                    # Action buttons
                    with ui.row().classes('w-full justify-end gap-2'):
                        camera_load_yaml_button = ui.button('Load YAML', icon='file_upload').props('flat color=secondary')
                        camera_save_yaml_button = ui.button('Save YAML', icon='file_download').props('flat color=secondary')
                        camera_get_live_param_button = ui.button('Get Node Parameters', icon='download').props('color=primary')
                        camera_apply_param_button = ui.button('Apply Node Parameters', icon='save').props('color=primary')

                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Coordinator Configuration').classes('text-h6')

                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        coord_wait_for_user_input = ui.switch(
                            'Wait for User Input',
                            value=True
                        ).classes('w-full')

                        coord_enable_rviz_tool_swap = ui.switch(
                            'Enable RViz Tool Swap',
                            value=False
                        ).classes('w-full')

                    ui.separator().classes('my-4')

                    with ui.row().classes('w-full justify-end gap-2'):
                        coord_load_yaml_button = ui.button('Load YAML', icon='file_upload').props('flat color=secondary')
                        coord_save_yaml_button = ui.button('Save YAML', icon='file_download').props('flat color=secondary')
                        coord_get_live_param_button = ui.button('Get Node Parameters', icon='download').props('color=primary')
                        coord_apply_param_button = ui.button('Apply Node Parameters', icon='save').props('color=primary')

                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Vision Processing Configuration').classes('text-h6')

                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        vision_debug_image_output = ui.switch(
                            'Debug Image Output',
                            value=False
                        ).classes('w-full')

                        vision_vizualize_o3d = ui.switch(
                            'Visualize Open3D',
                            value=False
                        ).classes('w-full')

                        vision_use_sim_height = ui.switch(
                            'Use Simulated Height',
                            value=False
                        ).classes('w-full')

                    ui.label('Pose Estimation').classes('text-subtitle1 font-bold mb-3 mt-4')

                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        vision_cad_model_path = ui.input(
                            'CAD Model Path',
                            placeholder='/path/to/model.stl'
                        ).props('outlined dense').classes('w-full')

                        vision_voxel_size = ui.number(
                            'Voxel Size (mm)',
                            value=2.0,
                            min=0.1,
                            step=0.5,
                            suffix=' mm'
                        ).props('outlined dense').classes('w-full')

                        vision_nb_neighbors = ui.number(
                            'NB Neighbors (outlier removal)',
                            value=30,
                            min=1,
                            step=1,
                        ).props('outlined dense').classes('w-full')

                    ui.separator().classes('my-4')

                    with ui.row().classes('w-full justify-end gap-2'):
                        vision_load_yaml_button = ui.button('Load YAML', icon='file_upload').props('flat color=secondary')
                        vision_save_yaml_button = ui.button('Save YAML', icon='file_download').props('flat color=secondary')
                        vision_get_live_param_button = ui.button('Get Node Parameters', icon='download').props('color=primary')
                        vision_apply_param_button = ui.button('Apply Node Parameters', icon='save').props('color=primary')

                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Tool Controller Configuration').classes('text-h6')

                    ui.label('Scene').classes('text-subtitle1 font-bold mb-3')

                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        tool_flange_link = ui.input(
                            'Flange Link',
                            placeholder='tool0'
                        ).props('outlined dense').classes('w-full')

                        tool_publish_count = ui.number(
                            'Publish Count',
                            value=5,
                            min=1,
                            step=1
                        ).props('outlined dense').classes('w-full')

                        tool_publish_delay = ui.number(
                            'Publish Delay',
                            value=0.1,
                            min=0.0,
                            step=0.01,
                            suffix=' seconds'
                        ).props('outlined dense').classes('w-full')

                    ui.separator().classes('my-4')

                    with ui.row().classes('w-full justify-end gap-2'):
                        tool_load_yaml_button = ui.button('Load YAML', icon='file_upload').props('flat color=secondary')
                        tool_save_yaml_button = ui.button('Save YAML', icon='file_download').props('flat color=secondary')
                        tool_get_live_param_button = ui.button('Get Node Parameters', icon='download').props('color=primary')
                        tool_apply_param_button = ui.button('Apply Node Parameters', icon='save').props('color=primary')

                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Motion Planning Configuration').classes('text-h6')

                    ui.label('Planning').classes('text-subtitle1 font-bold mb-3')

                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        mp_num_attempts = ui.number(
                            'Planning Attempts',
                            value=10,
                            min=1,
                            step=1
                        ).props('outlined dense').classes('w-full')

                        mp_allowed_time = ui.number(
                            'Allowed Planning Time',
                            value=5.0,
                            min=0.1,
                            step=0.5,
                            suffix=' s'
                        ).props('outlined dense').classes('w-full')

                        mp_planner_id = ui.select(
                            options=MotionPlanningConstants.Planners.ALL,
                            value=MotionPlanningConstants.Planners.RRT_CONNECT,
                            label='Planner'
                        ).props('outlined dense').classes('w-full')

                    ui.label('Goal Tolerances (joint_space only)').classes('text-subtitle1 font-bold mb-3 mt-4')

                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        mp_position_tolerance = ui.number(
                            'Position Tolerance',
                            value=0.001,
                            min=0.0001,
                            step=0.0005,
                            suffix=' m'
                        ).props('outlined dense').classes('w-full')

                        mp_orientation_tolerance = ui.number(
                            'Orientation Tolerance',
                            value=0.001,
                            min=0.0001,
                            step=0.0005,
                            suffix=' rad'
                        ).props('outlined dense').classes('w-full')

                    ui.label('Cartesian Path').classes('text-subtitle1 font-bold mb-3 mt-4')

                    with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
                        mp_max_step = ui.number(
                            'Max Step',
                            value=0.01,
                            min=0.001,
                            step=0.005,
                            suffix=' m'
                        ).props('outlined dense').classes('w-full')

                        mp_jump_threshold = ui.number(
                            'Jump Threshold',
                            value=0.0,
                            min=0.0,
                            step=0.1,
                        ).props('outlined dense').classes('w-full')

                        mp_avoid_collisions = ui.switch(
                            'Avoid Collisions',
                            value=True
                        ).classes('w-full')

                        mp_min_fraction = ui.number(
                            'Min Achieved Fraction',
                            value=0.99,
                            min=0.0,
                            max=1.0,
                            step=0.01,
                        ).props('outlined dense').classes('w-full')

                    ui.separator().classes('my-4')

                    with ui.row().classes('w-full justify-end gap-2'):
                        mp_load_yaml_button = ui.button('Load YAML', icon='file_upload').props('flat color=secondary')
                        mp_save_yaml_button = ui.button('Save YAML', icon='file_download').props('flat color=secondary')
                        mp_get_live_param_button = ui.button('Get Node Parameters', icon='download').props('color=primary')
                        mp_apply_param_button = ui.button('Apply Node Parameters', icon='save').props('color=primary')

            async def refresh_robot_parameters():
                """Refresh robot parameters from ROS2"""
                try:
                    ui.notify('Loading robot parameters...', color='info')
                    
                    # Get parameters from robot controller
                    response = await node.get_node_parameters_async(
                        node.robot_clients.get_parameters_cli,
                        parameter_names=[
                            RobotParametersKeys.IP_ADDRESS,
                            RobotParametersKeys.PORT,
                            RobotParametersKeys.USERNAME,
                            RobotParametersKeys.PASSWORD,
                            RobotParametersKeys.SEND_KEEPALIVE,
                            RobotParametersKeys.KEEPALIVE_INTERVAL,
                            RobotParametersKeys.SEND_JOINT_STATES,
                            RobotParametersKeys.JOINT_STATES_HZ,
                            RobotParametersKeys.DIPC_RETRY_MAX,
                            RobotParametersKeys.DIPC_RETRY_DELAY_S,
                        ]
                    )
                    
                    # Parse and update UI using list index (parameters returned in same order)
                    if len(response.values) >= 10:
                        robot_ip.value = response.values[0].string_value
                        robot_port.value = response.values[1].integer_value
                        robot_username.value = response.values[2].string_value
                        robot_password.value = response.values[3].string_value
                        robot_keepalive.value = response.values[4].bool_value
                        robot_keepalive_interval.value = response.values[5].double_value
                        robot_send_joint_states.value = response.values[6].bool_value
                        robot_joint_states_hz.value = response.values[7].double_value
                        robot_dipc_retry_max.value = response.values[8].integer_value
                        robot_dipc_retry_delay.value = response.values[9].double_value
                    
                    ui.notify('Robot parameters loaded successfully', color='positive')
                    
                except Exception as e:
                    node.logger.error(f'Failed to refresh robot parameters: {e}')
                    ui.notify(f'Failed to load parameters: {e}', color='negative')
            
            async def apply_robot_parameters():
                """Apply robot parameters to ROS2"""
                try:
                    ui.notify('Applying robot parameters...', color='info')
                    
                    parameters = [
                        Parameter(
                            name=RobotParametersKeys.IP_ADDRESS,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(robot_ip.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.PORT,
                            value=ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=int(robot_port.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.USERNAME,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(robot_username.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.PASSWORD,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(robot_password.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.SEND_KEEPALIVE,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(robot_keepalive.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.KEEPALIVE_INTERVAL,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(robot_keepalive_interval.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.SEND_JOINT_STATES,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(robot_send_joint_states.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.JOINT_STATES_HZ,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(robot_joint_states_hz.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.DIPC_RETRY_MAX,
                            value=ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=int(robot_dipc_retry_max.value))
                        ),
                        Parameter(
                            name=RobotParametersKeys.DIPC_RETRY_DELAY_S,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(robot_dipc_retry_delay.value))
                        ),
                    ]
                    
                    # Set parameters on robot controller with 15s timeout
                    response = await node.set_node_parameters_async(
                        node.robot_clients.set_parameters_cli,
                        parameters,
                    )
                    
                    # Check results
                    if all(result.successful for result in response.results):
                        # ui.notify('Robot parameters applied successfully', color='positive')
                        response = await node.apply_parameters_async(
                            node.robot_clients.apply_parameters_cli,
                        )
                        if response.status:
                            ui.notify(f"{response.message}", color='positive')
                        else:
                            ui.notify(f"{response.message}", color='negative')
                        
                    else:
                        failed = [param.name for i, (param, result) in enumerate(zip(parameters, response.results)) if not result.successful]
                        ui.notify(f'Some parameters failed: {", ".join(failed)}', color='warning')
                    
                except Exception as e:
                    node.logger.error(f'Failed to apply robot parameters: {e}')
                    ui.notify(f'Failed to apply parameters: {e}', color='negative')

            async def save_robot_yaml():
                """Save current robot UI values to YAML file"""
                try:
                    params = RobotParameters(
                        ip_address=str(robot_ip.value),
                        port=int(robot_port.value),
                        username=str(robot_username.value),
                        password=str(robot_password.value),
                        send_keepalive=bool(robot_keepalive.value),
                        keepalive_interval=float(robot_keepalive_interval.value),
                        send_joint_states=bool(robot_send_joint_states.value),
                        joint_states_hz=float(robot_joint_states_hz.value),
                        dipc_retry_max=int(robot_dipc_retry_max.value),
                        dipc_retry_delay_s=float(robot_dipc_retry_delay.value),
                    )
                    params.save_yaml(ROBOT_CONFIG_YAML)
                    ui.notify(f'Robot parameters saved to {ROBOT_CONFIG_YAML}', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to save robot YAML: {e}')
                    ui.notify(f'Failed to save YAML: {e}', color='negative')

            async def load_robot_yaml():
                """Load robot parameters from YAML file into UI"""
                try:
                    params = RobotParameters.load_yaml(ROBOT_CONFIG_YAML)
                    robot_ip.value = params.ip_address
                    robot_port.value = params.port
                    robot_username.value = params.username
                    robot_password.value = params.password
                    robot_keepalive.value = params.send_keepalive
                    robot_keepalive_interval.value = params.keepalive_interval
                    robot_send_joint_states.value = params.send_joint_states
                    robot_joint_states_hz.value = params.joint_states_hz
                    robot_dipc_retry_max.value = params.dipc_retry_max
                    robot_dipc_retry_delay.value = params.dipc_retry_delay_s
                    ui.notify(f'Robot parameters loaded from {ROBOT_CONFIG_YAML}', color='positive')
                except FileNotFoundError:
                    ui.notify(f'YAML file not found: {ROBOT_CONFIG_YAML}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to load robot YAML: {e}')
                    ui.notify(f'Failed to load YAML: {e}', color='negative')

            async def save_camera_yaml():
                """Save current camera UI values to YAML file"""
                try:
                    params = CameraControllerParameters(
                        device_id=str(camera_device_id.value),
                        publish_topics=bool(camera_publish_topics.value),
                        save_to_file=bool(camera_save_to_file.value),
                        save_mesh=bool(camera_save_mesh.value),
                        save_depth_map=bool(camera_save_depth_map.value),
                        save_point_cloud=bool(camera_save_point_cloud.value),
                        save_normal_map=bool(camera_save_normal_map.value),
                        ambient_light_suppression=bool(camera_ambient_light_suppression.value),
                        coding_strategy=str(camera_coding_strategy.value),
                        send_texture=bool(camera_send_texture.value),
                        send_point_cloud=bool(camera_send_point_cloud.value),
                        send_normal_map=bool(camera_send_normal_map.value),
                        send_depth_map=bool(camera_send_depth_map.value),
                        send_confidence_map=bool(camera_send_confidence_map.value),
                        coordinate_space=str(camera_coordinate_space.value),
                        use_transform=bool(camera_use_transform.value),
                        tf_frame_id=str(camera_frame_id.value)
                    )
                    params.save_yaml(CAMERA_CONFIG_YAML)
                    ui.notify(f'Camera parameters saved to {CAMERA_CONFIG_YAML}', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to save camera YAML: {e}')
                    ui.notify(f'Failed to save YAML: {e}', color='negative')

            async def load_camera_yaml():
                """Load camera parameters from YAML file into UI"""
                try:
                    params = CameraControllerParameters.load_yaml(CAMERA_CONFIG_YAML)
                    camera_device_id.value = params.device_id
                    camera_publish_topics.value = params.publish_topics
                    camera_save_to_file.value = params.save_to_file
                    camera_save_mesh.value = params.save_mesh
                    camera_save_depth_map.value = params.save_depth_map
                    camera_save_point_cloud.value = params.save_point_cloud
                    camera_save_normal_map.value = params.save_normal_map
                    camera_ambient_light_suppression.value = params.ambient_light_suppression
                    camera_coding_strategy.value = params.coding_strategy
                    camera_send_texture.value = params.send_texture
                    camera_send_point_cloud.value = params.send_point_cloud
                    camera_send_normal_map.value = params.send_normal_map
                    camera_send_depth_map.value = params.send_depth_map
                    camera_send_confidence_map.value = params.send_confidence_map
                    camera_coordinate_space.value = params.coordinate_space
                    camera_use_transform.value = params.use_transform
                    camera_frame_id.value = params.tf_frame_id

                    ui.notify(f'Camera parameters loaded from {CAMERA_CONFIG_YAML}', color='positive')
                except FileNotFoundError:
                    ui.notify(f'YAML file not found: {CAMERA_CONFIG_YAML}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to load camera YAML: {e}')
                    ui.notify(f'Failed to load YAML: {e}', color='negative')

            async def refresh_camera_parameters():
                """Refresh camera parameters from ROS2"""
                try:
                    ui.notify('Loading camera parameters...', color='info')
                    
                    # Get parameters from camera controller node
                    response = await node.get_node_parameters_async(
                        node.camera_clients.get_parameters_cli,
                        parameter_names=[
                            CameraControllerParametersKeys.DEVICE_ID,
                            CameraControllerParametersKeys.PUBLISH_TOPICS,
                            CameraControllerParametersKeys.SAVE_TO_FILE,
                            CameraControllerParametersKeys.SAVE_MESH,
                            CameraControllerParametersKeys.SAVE_DEPTH_MAP,
                            CameraControllerParametersKeys.SAVE_POINT_CLOUD,
                            CameraControllerParametersKeys.SAVE_NORMAL_MAP,
                            CameraControllerParametersKeys.AMBIENT_LIGHT_SUPPRESSION,
                            CameraControllerParametersKeys.CODING_STRATEGY,
                            CameraControllerParametersKeys.SEND_TEXTURE,
                            CameraControllerParametersKeys.SEND_POINT_CLOUD,
                            CameraControllerParametersKeys.SEND_NORMAL_MAP,
                            CameraControllerParametersKeys.SEND_DEPTH_MAP,
                            CameraControllerParametersKeys.SEND_CONFIDENCE_MAP,
                            CameraControllerParametersKeys.COORDINATE_SPACE,
                            CameraControllerParametersKeys.USE_TRANSFORM,
                            CameraControllerParametersKeys.TF_FRAME_ID
                        ]
                    )
                    
                    # Parse and update UI using list index (parameters returned in same order)
                    if len(response.values) >= 17:
                        camera_device_id.value = response.values[0].string_value
                        camera_publish_topics.value = response.values[1].bool_value
                        camera_save_to_file.value = response.values[2].bool_value
                        camera_save_mesh.value = response.values[3].bool_value
                        camera_save_depth_map.value = response.values[4].bool_value
                        camera_save_point_cloud.value = response.values[5].bool_value
                        camera_save_normal_map.value = response.values[6].bool_value
                        camera_ambient_light_suppression.value = response.values[7].bool_value
                        camera_coding_strategy.value = response.values[8].string_value
                        camera_send_texture.value = response.values[9].bool_value
                        camera_send_point_cloud.value = response.values[10].bool_value
                        camera_send_normal_map.value = response.values[11].bool_value
                        camera_send_depth_map.value = response.values[12].bool_value
                        camera_send_confidence_map.value = response.values[13].bool_value
                        camera_coordinate_space.value = response.values[14].string_value
                        camera_use_transform.value = response.values[15].bool_value
                        camera_frame_id.value = response.values[16].string_value
                    
                    ui.notify('Camera parameters loaded successfully', color='positive')
                    
                except Exception as e:
                    node.logger.error(f'Failed to refresh camera parameters: {e}')
                    ui.notify(f'Failed to load camera parameters: {e}', color='negative')
            
            async def apply_camera_parameters():
                """Apply camera parameters to ROS2"""
                try:
                    ui.notify('Applying camera parameters', color='info')
                    
                    parameters = [
                        Parameter(
                            name=CameraControllerParametersKeys.DEVICE_ID,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(camera_device_id.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.PUBLISH_TOPICS,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_publish_topics.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SAVE_TO_FILE,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_save_to_file.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SAVE_MESH,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_save_mesh.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SAVE_DEPTH_MAP,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_save_depth_map.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SAVE_POINT_CLOUD,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_save_point_cloud.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SAVE_NORMAL_MAP,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_save_normal_map.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.AMBIENT_LIGHT_SUPPRESSION,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_ambient_light_suppression.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.CODING_STRATEGY,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(camera_coding_strategy.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SEND_TEXTURE,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_send_texture.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SEND_POINT_CLOUD,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_send_point_cloud.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SEND_NORMAL_MAP,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_send_normal_map.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SEND_DEPTH_MAP,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_send_depth_map.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.SEND_CONFIDENCE_MAP,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_send_confidence_map.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.COORDINATE_SPACE,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(camera_coordinate_space.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.USE_TRANSFORM,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(camera_use_transform.value))
                        ),
                        Parameter(
                            name=CameraControllerParametersKeys.TF_FRAME_ID,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(camera_frame_id.value))
                        )

                    ]
                    
                    # Set parameters on camera controller node with 15s timeout
                    response = await node.set_node_parameters_async(
                        node.camera_clients.set_parameters_cli,
                        parameters,
                        timeout_sec=15.0
                    )
                    
                    # Check results
                    if all(result.successful for result in response.results):
                        # ui.notify('Camera parameters sent successfully, applying changes...', color='positive')
                        response = await node.apply_parameters_async(
                            node.camera_clients.apply_parameters_cli,
                        )
                        if response.status:
                            ui.notify(f"{response.message}", color='positive')
                        else:
                            ui.notify(f"{response.message}", color='negative')

                    else:
                        failed = [param.name for param, result in zip(parameters, response.results) if not result.successful]
                        ui.notify(f'Some parameters failed: {", ".join(failed)}', color='warning')
                    
                except Exception as e:
                    node.logger.error(f'Failed to apply camera parameters: {e}')
                    ui.notify(f'Failed to apply camera parameters: {e}', color='negative')
            

            # --- Calibration transform helpers ---
            _current_transform: list = []  # flat 16 floats

            def _format_transform_4x4(flat: list) -> str:
                """Format a flat 16-element list as a readable 4x4 matrix string."""
                m = np.array(flat).reshape(4, 4)
                lines = []
                for row in m:
                    lines.append('  '.join(f'{v: .6f}' for v in row))
                return '\n'.join(lines)

            async def reload_transform_from_yaml():
                """Load calibration transform from camera YAML and display it."""
                nonlocal _current_transform
                try:
                    params = CameraControllerParameters.load_yaml(CAMERA_CONFIG_YAML)
                    _current_transform = list(params.default_transform)
                    camera_transform_display.set_content(_format_transform_4x4(_current_transform))
                    ui.notify('Transform loaded from YAML', color='positive')
                except FileNotFoundError:
                    ui.notify(f'YAML file not found: {CAMERA_CONFIG_YAML}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to load transform from YAML: {e}')
                    ui.notify(f'Failed to load transform: {e}', color='negative')

            async def get_transform_from_node():
                """Fetch the current calibration transform parameter from the camera node."""
                nonlocal _current_transform
                try:
                    response = await node.get_node_parameters_async(
                        node.camera_clients.get_parameters_cli,
                        parameter_names=[CameraControllerParametersKeys.DEFAULT_TRANSFORM],
                    )
                    if response.values:
                        _current_transform = list(response.values[0].double_array_value)
                        camera_transform_display.set_content(_format_transform_4x4(_current_transform))
                        ui.notify('Transform retrieved from node', color='positive')
                    else:
                        ui.notify('No transform parameter returned', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to get transform from node: {e}')
                    ui.notify(f'Failed to get transform: {e}', color='negative')

            async def apply_transform_to_node():
                """Push the currently displayed transform to the camera node parameter."""
                if not _current_transform or len(_current_transform) != 16:
                    ui.notify('No valid transform loaded — reload from YAML or get from node first', color='warning')
                    return
                try:
                    parameters = [
                        Parameter(
                            name=CameraControllerParametersKeys.DEFAULT_TRANSFORM,
                            value=ParameterValue(
                                type=ParameterType.PARAMETER_DOUBLE_ARRAY,
                                double_array_value=_current_transform,
                            ),
                        ),
                    ]
                    response = await node.set_node_parameters_async(
                        node.camera_clients.set_parameters_cli,
                        parameters,
                    )
                    if all(r.successful for r in response.results):
                        ui.notify('Transform applied to node', color='positive')
                    else:
                        ui.notify('Failed to set transform parameter', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to apply transform to node: {e}')
                    ui.notify(f'Failed to apply transform: {e}', color='negative')

            camera_reload_transform_yaml_btn.on('click', reload_transform_from_yaml)
            camera_get_transform_node_btn.on('click', get_transform_from_node)
            camera_apply_transform_node_btn.on('click', apply_transform_to_node)

            # --- Coordinator handlers ---
            async def refresh_coordinator_parameters():
                try:
                    ui.notify('Loading coordinator parameters...', color='info')
                    response = await node.get_node_parameters_async(
                        node.coordinator_clients.get_parameters_cli,
                        parameter_names=[
                            CoordinatorParametersKeys.WAIT_FOR_USER_INPUT,
                            CoordinatorParametersKeys.ENABLE_RVIZ_TOOL_SWAP,
                        ]
                    )
                    if len(response.values) >= 2:
                        coord_wait_for_user_input.value = response.values[0].bool_value
                        coord_enable_rviz_tool_swap.value = response.values[1].bool_value
                    ui.notify('Coordinator parameters loaded successfully', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to refresh coordinator parameters: {e}')
                    ui.notify(f'Failed to load parameters: {e}', color='negative')

            async def apply_coordinator_parameters():
                try:
                    ui.notify('Applying coordinator parameters...', color='info')
                    parameters = [
                        Parameter(
                            name=CoordinatorParametersKeys.WAIT_FOR_USER_INPUT,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(coord_wait_for_user_input.value))
                        ),
                        Parameter(
                            name=CoordinatorParametersKeys.ENABLE_RVIZ_TOOL_SWAP,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(coord_enable_rviz_tool_swap.value))
                        ),
                    ]
                    response = await node.set_node_parameters_async(
                        node.coordinator_clients.set_parameters_cli,
                        parameters,
                    )
                    if all(result.successful for result in response.results):
                        response = await node.apply_parameters_async(
                            node.coordinator_clients.apply_parameters_cli,
                        )
                        if response.status:
                            ui.notify(f"{response.message}", color='positive')
                        else:
                            ui.notify(f"{response.message}", color='negative')
                    else:
                        failed = [param.name for param, result in zip(parameters, response.results) if not result.successful]
                        ui.notify(f'Some parameters failed: {", ".join(failed)}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to apply coordinator parameters: {e}')
                    ui.notify(f'Failed to apply parameters: {e}', color='negative')

            async def save_coordinator_yaml():
                try:
                    params = CoordinatorParameters(
                        wait_for_user_input=bool(coord_wait_for_user_input.value),
                        enable_rviz_tool_swap=bool(coord_enable_rviz_tool_swap.value),
                    )
                    params.save_yaml(COORDINATOR_CONFIG_YAML)
                    ui.notify(f'Coordinator parameters saved to {COORDINATOR_CONFIG_YAML}', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to save coordinator YAML: {e}')
                    ui.notify(f'Failed to save YAML: {e}', color='negative')

            async def load_coordinator_yaml():
                try:
                    params = CoordinatorParameters.load_yaml(COORDINATOR_CONFIG_YAML)
                    coord_wait_for_user_input.value = params.wait_for_user_input
                    coord_enable_rviz_tool_swap.value = params.enable_rviz_tool_swap
                    ui.notify(f'Coordinator parameters loaded from {COORDINATOR_CONFIG_YAML}', color='positive')
                except FileNotFoundError:
                    ui.notify(f'YAML file not found: {COORDINATOR_CONFIG_YAML}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to load coordinator YAML: {e}')
                    ui.notify(f'Failed to load YAML: {e}', color='negative')

            # --- Vision handlers ---
            async def refresh_vision_parameters():
                try:
                    ui.notify('Loading vision parameters...', color='info')
                    response = await node.get_node_parameters_async(
                        node.vision_clients.get_parameters_cli,
                        parameter_names=[
                            VisionParametersKeys.DEBUG_IMAGE_OUTPUT,
                            VisionParametersKeys.VIZUALIZE_O3D,
                            VisionParametersKeys.USE_SIM_HEIGHT,
                            VisionParametersKeys.CAD_MODEL_PATH,
                            VisionParametersKeys.POSE_ESTIMATION_VOXEL_SIZE,
                            VisionParametersKeys.POSE_ESTIMATION_NB_NEIGHBORS,
                        ]
                    )
                    if len(response.values) >= 6:
                        vision_debug_image_output.value = response.values[0].bool_value
                        vision_vizualize_o3d.value = response.values[1].bool_value
                        vision_use_sim_height.value = response.values[2].bool_value
                        vision_cad_model_path.value = response.values[3].string_value
                        vision_voxel_size.value = response.values[4].double_value
                        vision_nb_neighbors.value = response.values[5].integer_value
                    ui.notify('Vision parameters loaded successfully', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to refresh vision parameters: {e}')
                    ui.notify(f'Failed to load parameters: {e}', color='negative')

            async def apply_vision_parameters():
                try:
                    ui.notify('Applying vision parameters...', color='info')
                    parameters = [
                        Parameter(
                            name=VisionParametersKeys.DEBUG_IMAGE_OUTPUT,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(vision_debug_image_output.value))
                        ),
                        Parameter(
                            name=VisionParametersKeys.VIZUALIZE_O3D,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(vision_vizualize_o3d.value))
                        ),
                        Parameter(
                            name=VisionParametersKeys.USE_SIM_HEIGHT,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(vision_use_sim_height.value))
                        ),
                        Parameter(
                            name=VisionParametersKeys.CAD_MODEL_PATH,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(vision_cad_model_path.value or ''))
                        ),
                        Parameter(
                            name=VisionParametersKeys.POSE_ESTIMATION_VOXEL_SIZE,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(vision_voxel_size.value))
                        ),
                        Parameter(
                            name=VisionParametersKeys.POSE_ESTIMATION_NB_NEIGHBORS,
                            value=ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=int(vision_nb_neighbors.value))
                        ),
                    ]
                    response = await node.set_node_parameters_async(
                        node.vision_clients.set_parameters_cli,
                        parameters,
                    )
                    if all(result.successful for result in response.results):
                        response = await node.apply_parameters_async(
                            node.vision_clients.apply_parameters_cli,
                        )
                        if response.status:
                            ui.notify(f"{response.message}", color='positive')
                        else:
                            ui.notify(f"{response.message}", color='negative')
                    else:
                        failed = [param.name for param, result in zip(parameters, response.results) if not result.successful]
                        ui.notify(f'Some parameters failed: {", ".join(failed)}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to apply vision parameters: {e}')
                    ui.notify(f'Failed to apply parameters: {e}', color='negative')

            async def save_vision_yaml():
                try:
                    params = VisionParameters(
                        debug_image_output=bool(vision_debug_image_output.value),
                        vizualize_o3d=bool(vision_vizualize_o3d.value),
                        use_sim_height=bool(vision_use_sim_height.value),
                        cad_model_path=str(vision_cad_model_path.value or ''),
                        pose_estimation_voxel_size=float(vision_voxel_size.value),
                        pose_estimation_nb_neighbors=int(vision_nb_neighbors.value),
                    )
                    params.save_yaml(VISION_PROCESSING_CONFIG_YAML)
                    ui.notify(f'Vision parameters saved to {VISION_PROCESSING_CONFIG_YAML}', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to save vision YAML: {e}')
                    ui.notify(f'Failed to save YAML: {e}', color='negative')

            async def load_vision_yaml():
                try:
                    params = VisionParameters.load_yaml(VISION_PROCESSING_CONFIG_YAML)
                    vision_debug_image_output.value = params.debug_image_output
                    vision_vizualize_o3d.value = params.vizualize_o3d
                    vision_use_sim_height.value = params.use_sim_height
                    vision_cad_model_path.value = params.cad_model_path
                    vision_voxel_size.value = params.pose_estimation_voxel_size
                    vision_nb_neighbors.value = params.pose_estimation_nb_neighbors
                    ui.notify(f'Vision parameters loaded from {VISION_PROCESSING_CONFIG_YAML}', color='positive')
                except FileNotFoundError:
                    ui.notify(f'YAML file not found: {VISION_PROCESSING_CONFIG_YAML}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to load vision YAML: {e}')
                    ui.notify(f'Failed to load YAML: {e}', color='negative')

            # --- Tool controller handlers ---
            async def refresh_tool_parameters():
                try:
                    ui.notify('Loading tool parameters...', color='info')
                    response = await node.get_node_parameters_async(
                        node.tool_clients.get_parameters_cli,
                        parameter_names=[
                            ToolControllerParametersKeys.FLANGE_LINK,
                            ToolControllerParametersKeys.PUBLISH_COUNT,
                            ToolControllerParametersKeys.PUBLISH_DELAY,
                        ]
                    )
                    if len(response.values) >= 3:
                        tool_flange_link.value = response.values[0].string_value
                        tool_publish_count.value = response.values[1].integer_value
                        tool_publish_delay.value = response.values[2].double_value
                    ui.notify('Tool parameters loaded successfully', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to refresh tool parameters: {e}')
                    ui.notify(f'Failed to load parameters: {e}', color='negative')

            async def apply_tool_parameters():
                try:
                    ui.notify('Applying tool parameters...', color='info')
                    parameters = [
                        Parameter(
                            name=ToolControllerParametersKeys.FLANGE_LINK,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(tool_flange_link.value))
                        ),
                        Parameter(
                            name=ToolControllerParametersKeys.PUBLISH_COUNT,
                            value=ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=int(tool_publish_count.value))
                        ),
                        Parameter(
                            name=ToolControllerParametersKeys.PUBLISH_DELAY,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(tool_publish_delay.value))
                        ),
                    ]
                    response = await node.set_node_parameters_async(
                        node.tool_clients.set_parameters_cli,
                        parameters,
                    )
                    if all(result.successful for result in response.results):
                        response = await node.apply_parameters_async(
                            node.tool_clients.apply_parameters_cli,
                        )
                        if response.status:
                            ui.notify(f"{response.message}", color='positive')
                        else:
                            ui.notify(f"{response.message}", color='negative')
                    else:
                        failed = [param.name for param, result in zip(parameters, response.results) if not result.successful]
                        ui.notify(f'Some parameters failed: {", ".join(failed)}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to apply tool parameters: {e}')
                    ui.notify(f'Failed to apply parameters: {e}', color='negative')

            async def save_tool_parameters_yaml():
                try:
                    params = ToolControllerParameters(
                        flange_link=str(tool_flange_link.value),
                        publish_count=int(tool_publish_count.value),
                        publish_delay=float(tool_publish_delay.value),
                    )
                    params.save_yaml(TOOL_CONTROLLER_CONFIG_YAML)
                    ui.notify(f'Tool parameters saved to {TOOL_CONTROLLER_CONFIG_YAML}', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to save tool parameters YAML: {e}')
                    ui.notify(f'Failed to save YAML: {e}', color='negative')

            async def load_tools_yaml():
                try:
                    params = ToolControllerParameters.load_yaml(TOOL_CONTROLLER_CONFIG_YAML)
                    tool_flange_link.value = params.flange_link
                    tool_publish_count.value = params.publish_count
                    tool_publish_delay.value = params.publish_delay
                    ui.notify(f'Tool controller parameters loaded from {TOOL_CONTROLLER_CONFIG_YAML}', color='positive')
                except FileNotFoundError:
                    ui.notify(f'YAML file not found: {TOOL_CONTROLLER_CONFIG_YAML}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to load tool controller YAML: {e}')
                    ui.notify(f'Failed to load YAML: {e}', color='negative')

            async def refresh_motion_planning_parameters():
                try:
                    ui.notify('Loading motion planning parameters...', color='info')
                    response = await node.get_node_parameters_async(
                        node.motion_planning_clients.get_parameters_cli,
                        parameter_names=[
                            MotionPlanningParametersKeys.NUM_PLANNING_ATTEMPTS,
                            MotionPlanningParametersKeys.ALLOWED_PLANNING_TIME,
                            MotionPlanningParametersKeys.PLANNER_ID,
                            MotionPlanningParametersKeys.POSITION_TOLERANCE,
                            MotionPlanningParametersKeys.ORIENTATION_TOLERANCE,
                            MotionPlanningParametersKeys.CARTESIAN_MAX_STEP,
                            MotionPlanningParametersKeys.CARTESIAN_JUMP_THRESHOLD,
                            MotionPlanningParametersKeys.CARTESIAN_AVOID_COLLISIONS,
                            MotionPlanningParametersKeys.CARTESIAN_MIN_FRACTION,
                        ]
                    )
                    if len(response.values) >= 9:
                        mp_num_attempts.value = response.values[0].integer_value
                        mp_allowed_time.value = response.values[1].double_value
                        mp_planner_id.value = response.values[2].string_value
                        mp_position_tolerance.value = response.values[3].double_value
                        mp_orientation_tolerance.value = response.values[4].double_value
                        mp_max_step.value = response.values[5].double_value
                        mp_jump_threshold.value = response.values[6].double_value
                        mp_avoid_collisions.value = response.values[7].bool_value
                        mp_min_fraction.value = response.values[8].double_value
                    ui.notify('Motion planning parameters loaded successfully', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to refresh motion planning parameters: {e}')
                    ui.notify(f'Failed to load parameters: {e}', color='negative')

            async def apply_motion_planning_parameters():
                try:
                    ui.notify('Applying motion planning parameters...', color='info')
                    parameters = [
                        Parameter(
                            name=MotionPlanningParametersKeys.NUM_PLANNING_ATTEMPTS,
                            value=ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=int(mp_num_attempts.value))
                        ),
                        Parameter(
                            name=MotionPlanningParametersKeys.ALLOWED_PLANNING_TIME,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(mp_allowed_time.value))
                        ),
                        Parameter(
                            name=MotionPlanningParametersKeys.PLANNER_ID,
                            value=ParameterValue(type=ParameterType.PARAMETER_STRING, string_value=str(mp_planner_id.value))
                        ),
                        Parameter(
                            name=MotionPlanningParametersKeys.POSITION_TOLERANCE,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(mp_position_tolerance.value))
                        ),
                        Parameter(
                            name=MotionPlanningParametersKeys.ORIENTATION_TOLERANCE,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(mp_orientation_tolerance.value))
                        ),
                        Parameter(
                            name=MotionPlanningParametersKeys.CARTESIAN_MAX_STEP,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(mp_max_step.value))
                        ),
                        Parameter(
                            name=MotionPlanningParametersKeys.CARTESIAN_JUMP_THRESHOLD,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(mp_jump_threshold.value))
                        ),
                        Parameter(
                            name=MotionPlanningParametersKeys.CARTESIAN_AVOID_COLLISIONS,
                            value=ParameterValue(type=ParameterType.PARAMETER_BOOL, bool_value=bool(mp_avoid_collisions.value))
                        ),
                        Parameter(
                            name=MotionPlanningParametersKeys.CARTESIAN_MIN_FRACTION,
                            value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(mp_min_fraction.value))
                        ),
                    ]
                    response = await node.set_node_parameters_async(
                        node.motion_planning_clients.set_parameters_cli,
                        parameters,
                    )
                    if all(result.successful for result in response.results):
                        response = await node.apply_parameters_async(
                            node.motion_planning_clients.apply_parameters_cli,
                        )
                        if response.status:
                            ui.notify(f"{response.message}", color='positive')
                        else:
                            ui.notify(f"{response.message}", color='negative')
                    else:
                        failed = [param.name for param, result in zip(parameters, response.results) if not result.successful]
                        ui.notify(f'Some parameters failed: {", ".join(failed)}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to apply motion planning parameters: {e}')
                    ui.notify(f'Failed to apply parameters: {e}', color='negative')

            async def save_motion_planning_yaml():
                try:
                    params = MotionPlanningParameters(
                        num_planning_attempts=int(mp_num_attempts.value),
                        allowed_planning_time=float(mp_allowed_time.value),
                        planner_id=str(mp_planner_id.value),
                        position_tolerance=float(mp_position_tolerance.value),
                        orientation_tolerance=float(mp_orientation_tolerance.value),
                        cartesian_max_step=float(mp_max_step.value),
                        cartesian_jump_threshold=float(mp_jump_threshold.value),
                        cartesian_avoid_collisions=bool(mp_avoid_collisions.value),
                        cartesian_min_fraction=float(mp_min_fraction.value),
                    )
                    params.save_yaml(MOTION_PLANNING_CONFIG_YAML)
                    ui.notify(f'Motion planning parameters saved to {MOTION_PLANNING_CONFIG_YAML}', color='positive')
                except Exception as e:
                    node.logger.error(f'Failed to save motion planning YAML: {e}')
                    ui.notify(f'Failed to save YAML: {e}', color='negative')

            async def load_motion_planning_yaml():
                try:
                    params = MotionPlanningParameters.load_yaml(MOTION_PLANNING_CONFIG_YAML)
                    mp_num_attempts.value = params.num_planning_attempts
                    mp_allowed_time.value = params.allowed_planning_time
                    mp_planner_id.value = params.planner_id
                    mp_position_tolerance.value = params.position_tolerance
                    mp_orientation_tolerance.value = params.orientation_tolerance
                    mp_max_step.value = params.cartesian_max_step
                    mp_jump_threshold.value = params.cartesian_jump_threshold
                    mp_avoid_collisions.value = params.cartesian_avoid_collisions
                    mp_min_fraction.value = params.cartesian_min_fraction
                    ui.notify(f'Motion planning parameters loaded from {MOTION_PLANNING_CONFIG_YAML}', color='positive')
                except FileNotFoundError:
                    ui.notify(f'YAML file not found: {MOTION_PLANNING_CONFIG_YAML}', color='warning')
                except Exception as e:
                    node.logger.error(f'Failed to load motion planning YAML: {e}')
                    ui.notify(f'Failed to load YAML: {e}', color='negative')

            robot_get_live_param_button.on('click', refresh_robot_parameters)
            robot_apply_param_button.on('click', apply_robot_parameters)
            robot_save_yaml_button.on('click', save_robot_yaml)
            robot_load_yaml_button.on('click', load_robot_yaml)
            
            camera_get_live_param_button.on('click', refresh_camera_parameters)
            camera_apply_param_button.on('click', apply_camera_parameters)
            camera_save_yaml_button.on('click', save_camera_yaml)
            camera_load_yaml_button.on('click', load_camera_yaml)

            coord_get_live_param_button.on('click', refresh_coordinator_parameters)
            coord_apply_param_button.on('click', apply_coordinator_parameters)
            coord_save_yaml_button.on('click', save_coordinator_yaml)
            coord_load_yaml_button.on('click', load_coordinator_yaml)

            vision_get_live_param_button.on('click', refresh_vision_parameters)
            vision_apply_param_button.on('click', apply_vision_parameters)
            vision_save_yaml_button.on('click', save_vision_yaml)
            vision_load_yaml_button.on('click', load_vision_yaml)

            tool_get_live_param_button.on('click', refresh_tool_parameters)
            tool_apply_param_button.on('click', apply_tool_parameters)
            tool_save_yaml_button.on('click', save_tool_parameters_yaml)
            tool_load_yaml_button.on('click', load_tools_yaml)

            mp_get_live_param_button.on('click', refresh_motion_planning_parameters)
            mp_apply_param_button.on('click', apply_motion_planning_parameters)
            mp_save_yaml_button.on('click', save_motion_planning_yaml)
            mp_load_yaml_button.on('click', load_motion_planning_yaml)
                
        except Exception as e:
            node.logger.error(f'Configuration page error: {e}')
            ui.notify('Failed to load configuration page', color='negative')
    
    return create_configuration_page
