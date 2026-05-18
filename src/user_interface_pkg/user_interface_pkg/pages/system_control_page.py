"""
Robot Control Page - Hardware initialization and control
"""
from nicegui import ui
from typing import Optional, Callable, Dict, List, Tuple
from user_interface_pkg.constants import SYSTEM_CONTROL_PAGE, CALL_TIMEOUT_SEC
from user_interface_pkg.pages.layout_page import create_main_layout
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from core_pkg.nodes_async import AsyncINTRANode
from interface_pkg.srv import ScanAcquisitionSrv, RobotRequestSrv, ProcessVisionSrv, TriggerServiceSrv, PlanMotionSrv
from interface_pkg.action import ExecuteJointArray
from interface_pkg.msg import RobotJoints
from core_pkg.systemconstants import (StateKeys, NodeStates,
CameraControllerConstants, RobotControllerConstants, UserInterfaceConstants, VisionProcessingConstants, CoordinatorConstants, ToolControllerConstants, MotionPlanningConstants)
import asyncio
import json
import math
import yaml
import os
from geometry_msgs.msg import Pose, Quaternion
from rclpy.action.client import ClientGoalHandle
from rclpy.client import Client
from core_pkg.settings import MOTION_PLANNING_POSES_YAML
from functools import partial

def create_node_control_card(
    title: str,
    state_dict: Dict[str, str],
    initialize_callback: Callable,
    cleanup_callback: Callable,
    recover_callback: Callable,
    check_state_callback: Callable,
    custom_buttons: Optional[List[Tuple[str, str, Callable, str]]] = None
) -> Tuple[ui.label, ui.label]:
    """
    Create a reusable node control card with common and custom buttons.
    
    Args:
        title: Card title (e.g., 'Robot Controller')
        state_dict: Dictionary with 'state' and 'description' keys
        initialize_callback: Function to call for initialization
        cleanup_callback: Function to call for cleanup
        recover_callback: Function to call for recovery
        check_state_callback: Function to call to check state
        custom_buttons: Optional list of (label, icon, callback, color) tuples for custom buttons
        
    Returns:
        Tuple of (state_label, description_label) for updating the UI
    """
    with ui.card().classes('flex-1 p-6'):
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.label(title).classes('text-h6')
        
        with ui.column().classes('w-full gap-4'):
            # Status display
            with ui.card().classes('w-full bg-grey-2 shadow-0'):
                with ui.row().classes('w-full items-center gap-4'):
                    ui.label('State:').classes('text-subtitle2 text-grey-7')
                    state_label = ui.label(state_dict[StateKeys.STATE]).classes('text-body2 text-primary')
                with ui.row().classes('w-full items-center gap-4 mt-2'):
                    ui.label('Description:').classes('text-subtitle2 text-grey-7')
                    description_label = ui.label(state_dict[StateKeys.DESCRIPTION]).classes('text-body2')

            # Common control buttons
            with ui.row().classes('w-full gap-2 items-stretch'):
                ui.button('Initialize', icon='play_arrow', 
                         on_click=initialize_callback
                ).props('color=positive').classes('flex-1 self-stretch')
                ui.button('Cleanup', icon='stop',
                         on_click=cleanup_callback
                ).props('color=warning').classes('flex-1 self-stretch')
                ui.button('Recover from Error', icon='healing',
                         on_click=recover_callback
                ).props('color=orange').classes('flex-1 self-stretch')

            # Check state and custom buttons
            with ui.row().classes('w-full gap-2 items-stretch'):
                ui.button('Check State', icon='info',
                        on_click=check_state_callback
                ).props('outline color=primary').classes('flex-1')
                
                # Add custom buttons if provided
                if custom_buttons:
                    for label, icon, callback, color in custom_buttons:
                        ui.button(label, icon=icon,
                                 on_click=callback
                        ).props(f'color={color}').classes('flex-1')
    
    return state_label, description_label 


def system_control_page_factory(node: AsyncINTRANode):
    """
    Factory function to create system control page view.
    Returns a function with access to ROS2 node via closure.
    
    Args:
        node: ROS2 AsyncINTRANode instance
        
    Returns:
        async robot control page view function
    """
    
    async def create_system_control_page() -> None:
        """
        System control page with hardware initialization and management.
        Only accessible to users with 'allow_system_control' permission.
        """
        try:
            accessor_dto = await get_valid_accessor()
            if accessor_dto is None:
                return
            
            # State tracking - labels auto-populated during UI build
            node_labels = {}  # key -> {'state': label, 'desc': label, 'overview': label}

            def update_status_ui():
                """Update all status indicators from node states"""
                for key, labels in node_labels.items():
                    state = node_configs[key]['state']
                    for lbl_key, lbl in labels.items():
                        if lbl_key in ('state', 'overview'):
                            lbl.set_text(state[StateKeys.STATE])
                        elif lbl_key == 'desc':
                            lbl.set_text(state[StateKeys.DESCRIPTION])


                
            async def get_robot_pos():
                """Get current robot cartesian position"""
                try:
                    node.logger.info('Getting robot cartesian position via UI')
                    request = RobotRequestSrv.Request()
                    request.command = 'get_robot_cartesian'

                    response: RobotRequestSrv.Response = await node.call_service_async(
                        node.robot_clients.robot_controller_request_cli,
                        request,
                        timeout_sec=CALL_TIMEOUT_SEC
                    )
                    
                    if response.status:
                        ui.notify(f'Robot position: {response.message}', type='positive')
                        node.logger.info(f'Robot cartesian position retrieved: {response.message}')
                    else:
                        ui.notify(f'Failed to get robot position: {response.message}', type='negative')
                        node.logger.error(f'Failed to get robot position: {response.message}')
                    
                except Exception as e:
                    ui.notify(f'Error getting robot position: {e}', type='negative')
                    node.logger.error(f'Error getting robot position: {e}')

            async def initialize_async(nodename: str, timeout_sec: float, client: Client):
                """Initialize node"""
                try:
                    ui.notify(f'Initializing {nodename}...', type='info')
                    node.logger.info(f'Initializing {nodename} via UI')
                    
                    response = await node.initialize_node_async(
                        client,
                        timeout_sec=timeout_sec
                    )
                    
                    if response.status:
                        ui.notify(f'{nodename} initialized successfully', type='positive')
                        node.logger.info(f'{nodename} initialized successfully')
                    else:
                        ui.notify(f'Failed to initialize {nodename}: {response.message}', type='negative')
                        node.logger.error(f'Failed to initialize {nodename}: {response.message}')
   
                except Exception as e:
                    ui.notify(f'Error initializing {nodename}: {e}', type='negative')
                    node.logger.error(f'Error initializing {nodename}: {e}')
            async def cleanup_async(nodename: str, timeout_sec: float, client: Client):
                """Cleanup node resources"""
                try:
                    ui.notify(f'Cleaning up {nodename}...', type='info')
                    node.logger.info(f'Cleaning up {nodename} via UI')
                    
                    response = await node.cleanup_resources_async(
                        client,
                        timeout_sec=timeout_sec
                    )
                    
                    if response.status:
                        ui.notify(f'{nodename} resources cleaned up', type='positive')
                        node.logger.info(f'{nodename} resources cleaned up successfully')
                    else:
                        ui.notify(f'Failed to cleanup {nodename}: {response.message}', type='negative')
                        node.logger.error(f'Failed to cleanup {nodename}: {response.message}')
                except Exception as e:
                    ui.notify(f'Error cleaning up {nodename}: {e}', type='negative')
                    node.logger.error(f'Error cleaning up {nodename}: {e}')
            
            async def get_state_async(nodename: str, timeout_sec: float, client: Client, state_dict: Dict[str, str]):
                """Get current node state"""
                try:
                    ui.notify(f'Checking {nodename} state...', type='info')
                    
                    response = await node.get_node_state_async(
                        client,
                        timeout_sec=timeout_sec
                    )
                    
                    state_dict[StateKeys.STATE] = response.state
                    state_dict[StateKeys.DESCRIPTION] = response.description
     
                except Exception as e:
                    state_dict[StateKeys.STATE] = NodeStates.ERROR
                    state_dict[StateKeys.DESCRIPTION] = str(e)
                    
                    ui.notify(f'Error getting {nodename} state: {e}', type='negative')
                    node.logger.error(f'Error getting {nodename} state: {e}')
                finally:
                    update_status_ui()
            
            async def recover_async(nodename: str, timeout_sec: float, client: Client):
                """Recover node from error state"""
                try:
                    ui.notify(f'Recovering {nodename} from error...', type='info')
                    node.logger.info(f'Recovering {nodename} from error via UI')
                    
                    response = await node.recover_from_error_async(
                        client,
                        timeout_sec=timeout_sec
                    )
                    
                    if response.status:
                        ui.notify(f'{nodename} recovered successfully', type='positive')
                        node.logger.info(f'{nodename} recovered from error successfully')
                    else:
                        ui.notify(f'Failed to recover {nodename}: {response.message}', type='negative')
                        node.logger.error(f'Failed to recover {nodename}: {response.message}')
                    
                except Exception as e:
                    ui.notify(f'Error recovering {nodename}: {e}', type='negative')
                    node.logger.error(f'Error recovering {nodename}: {e}')
            
            async def trigger_scan():
                """Trigger a single scan capture"""
                try:

                    ui.notify('Triggering scan...', type='info')
                    node.logger.info('Triggering scan via UI')
                    response: ScanAcquisitionSrv.Response = await node.call_service_async(
                        node.camera_clients.camera_controller_capture_cli,
                        ScanAcquisitionSrv.Request(),
                        timeout_sec=CALL_TIMEOUT_SEC
                    )
                    
                    if response.status:
                        ui.notify(f'Scan completed: {response.file_path}', type='positive')
                        node.logger.info(f'Scan completed successfully: {response.file_path}')
                    else:
                        ui.notify(f'Scan failed: {response.message}', type='negative')
                        node.logger.error(f'Scan failed: {response.message}')
                    
                except Exception as e:
                    ui.notify(f'Error triggering scan: {e}', type='negative')
                    node.logger.error(f'Error triggering scan: {e}')


            async def trigger_processing():
                try:
                    ui.notify('Triggering scan processing...', type='info')
                    node.logger.info("Triggering scan processing.")
                    response: ProcessVisionSrv.Response = await node.call_service_async(
                        node.vision_clients.vision_processing_op1_cli,
                        ProcessVisionSrv.Request(),
                        timeout_sec=CALL_TIMEOUT_SEC*3
                    )
                    
                    if response.status:
                        ui.notify(f'Scan processing completed successfully', type='positive')
                        node.logger.info(f'Scan processing completed successfully')
                    else:
                        ui.notify(f'Scan processing failed: {response.message}', type='negative')
                        node.logger.error(f'Scan processing failed: {response.message}')
                    
                except Exception as e:
                    ui.notify(f'Error triggering scan processing: {e}', type='negative')
                    node.logger.error(f'Error triggering scan processing: {e}')

            # To add a new node, add an entry here. Everything else is automatic.




            # Motion planning test — UI element refs populated when test card is built
            mp_test_refs: Dict = {'last_waypoints': None, 'poses': {}, 'pose_select': None}

            def load_poses_yaml():
                """Load predefined poses from YAML file."""
                try:
                    with open(MOTION_PLANNING_POSES_YAML, 'r') as f:
                        data = yaml.safe_load(f)
                    poses = {}
                    for p in data.get('poses', []):
                        poses[p['name']] = p
                    mp_test_refs['poses'] = poses
                    if mp_test_refs.get('pose_select'):
                        mp_test_refs['pose_select'].options = [''] + list(poses.keys())
                        mp_test_refs['pose_select'].update()
                    node.logger.info(f'Loaded {len(poses)} poses from {MOTION_PLANNING_POSES_YAML}')
                    ui.notify(f'Loaded {len(poses)} poses', type='positive')
                except Exception as e:
                    ui.notify(f'Failed to load poses: {e}', type='negative')
                    node.logger.error(f'Failed to load poses YAML: {e}')

            def apply_selected_pose(e):
                """Fill input fields with the selected predefined pose."""
                name = e.value
                if not name or name not in mp_test_refs['poses']:
                    return
                p = mp_test_refs['poses'][name]
                mp_test_refs['x'].value = p.get('x', 0.0)
                mp_test_refs['y'].value = p.get('y', 0.0)
                mp_test_refs['z'].value = p.get('z', 0.0)
                mp_test_refs['roll'].value = p.get('roll', 0.0)
                mp_test_refs['pitch'].value = p.get('pitch', 0.0)
                mp_test_refs['yaw'].value = p.get('yaw', 0.0)
                mp_test_refs['pose_name'].value = name

            def save_pose_yaml():
                """Save current input fields as a named pose to the YAML file."""
                try:
                    name = (mp_test_refs['pose_name'].value or '').strip()
                    if not name:
                        ui.notify('Enter a pose name first', type='warning')
                        return
                    new_pose = {
                        'name': name,
                        'x': round(float(mp_test_refs['x'].value or 0.0), 4),
                        'y': round(float(mp_test_refs['y'].value or 0.0), 4),
                        'z': round(float(mp_test_refs['z'].value or 0.0), 4),
                        'roll': round(float(mp_test_refs['roll'].value or 0.0), 2),
                        'pitch': round(float(mp_test_refs['pitch'].value or 0.0), 2),
                        'yaw': round(float(mp_test_refs['yaw'].value or 0.0), 2),
                    }
                    # Load existing file or start fresh
                    if os.path.exists(MOTION_PLANNING_POSES_YAML):
                        with open(MOTION_PLANNING_POSES_YAML, 'r') as f:
                            data = yaml.safe_load(f) or {}
                    else:
                        data = {}
                    poses_list = data.get('poses', [])
                    # Replace if name exists, otherwise append
                    replaced = False
                    for i, p in enumerate(poses_list):
                        if p.get('name') == name:
                            poses_list[i] = new_pose
                            replaced = True
                            break
                    if not replaced:
                        poses_list.append(new_pose)
                    data['poses'] = poses_list
                    with open(MOTION_PLANNING_POSES_YAML, 'w') as f:
                        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                    # Reload into UI
                    load_poses_yaml()
                    node.logger.info(f"Saved pose '{name}' to {MOTION_PLANNING_POSES_YAML}")
                except Exception as e:
                    ui.notify(f'Failed to save pose: {e}', type='negative')
                    node.logger.error(f'Failed to save pose: {e}')

            async def test_motion_plan():
                """Call PlanMotionSrv to a user-defined pose and log waypoints to terminal."""
                try:
                    ui.notify('Planning motion...', type='info')
                    x    = float(mp_test_refs['x'].value     or 0.0)
                    y    = float(mp_test_refs['y'].value     or 0.0)
                    z    = float(mp_test_refs['z'].value     or 0.0)
                    roll  = math.radians(float(mp_test_refs['roll'].value  or 0.0))
                    pitch = math.radians(float(mp_test_refs['pitch'].value or 0.0))
                    yaw   = math.radians(float(mp_test_refs['yaw'].value   or 0.0))
                    mode = mp_test_refs['mode'].value

                    cr, sr = math.cos(roll / 2),  math.sin(roll / 2)
                    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
                    cy, sy = math.cos(yaw / 2),   math.sin(yaw / 2)
                    quat = Quaternion(
                        x=float(sr * cp * cy - cr * sp * sy),
                        y=float(cr * sp * cy + sr * cp * sy),
                        z=float(cr * cp * sy - sr * sp * cy),
                        w=float(cr * cp * cy + sr * sp * sy),
                    )

                    node.logger.info(
                        f'Test motion plan: pos=({x:.4f}, {y:.4f}, {z:.4f}) '
                        f'rpy=({math.degrees(roll):.2f}°, {math.degrees(pitch):.2f}°, {math.degrees(yaw):.2f}°) '
                        f'mode={mode}'
                    )

                    request = PlanMotionSrv.Request()
                    request.goal_pose = Pose()
                    request.goal_pose.position.x = x
                    request.goal_pose.position.y = y
                    request.goal_pose.position.z = z
                    request.goal_pose.orientation = quat
                    request.planning_mode = mode

                    response: PlanMotionSrv.Response = await node.call_service_async(
                        node.motion_planning_clients.plan_motion_cli,
                        request,
                        timeout_sec=CALL_TIMEOUT_SEC * 12  # 120s — planning can take much longer than standard calls
                    )

                    if response.status:
                        waypoints = json.loads(response.waypoints_json)
                        mp_test_refs['last_waypoints'] = waypoints
                        mp_test_refs['execute_btn'].enable()
                        node.logger.info(f'Motion plan OK — {len(waypoints)} waypoints:')
                        for i, wp in enumerate(waypoints):
                            node.logger.info(f'  WP[{i:3d}]: {[round(v, 2) for v in wp]}')
                        ui.notify(f'Plan OK: {len(waypoints)} waypoints (see terminal)', type='positive')
                    else:
                        mp_test_refs['last_waypoints'] = None
                        mp_test_refs['execute_btn'].disable()
                        ui.notify(f'Planning failed: {response.message}', type='negative')
                        node.logger.error(f'Motion plan failed: {response.message}')

                except Exception as e:
                    ui.notify(f'Error: {e}', type='negative')
                    node.logger.error(f'Error testing motion plan: {e}')

            async def execute_motion_plan():
                """Execute the last planned trajectory via ExecuteJointArray action (DIPC)."""
                try:
                    waypoints = mp_test_refs.get('last_waypoints')
                    if not waypoints:
                        ui.notify('No planned path — run planning first', type='warning')
                        return

                    # Check coordinator state
                    coord_response = await node.get_node_state_async(
                        node.coordinator_clients.get_state_cli,
                        timeout_sec=CALL_TIMEOUT_SEC
                    )
                    if coord_response.state != NodeStates.IDLE.value:
                        ui.notify(f'Coordinator not idle (state: {coord_response.state})', type='warning')
                        return

                    # Check robot controller state
                    robot_response = await node.get_node_state_async(
                        node.robot_clients.get_state_cli,
                        timeout_sec=CALL_TIMEOUT_SEC
                    )
                    if robot_response.state != NodeStates.IDLE.value:
                        ui.notify(f'Robot controller not idle (state: {robot_response.state})', type='warning')
                        return
                    
                    #make robot ready
                    robot_response: RobotRequestSrv.Response = node.call_service_sync(
                        node.robot_clients.robot_controller_request_cli,
                        RobotRequestSrv.Request(command="make_robot_ready", params=[]))
                    
                    node.logger.info(f"Controller request response: status={robot_response.status}  message='{robot_response.message}'  status_code={robot_response.status_code}")


                    speed = str(mp_test_refs['exec_speed'].value or '50')
                    motion_command = str(mp_test_refs['exec_motion_command'].value or RobotControllerConstants.MotionCommands.MOVE_ABS_J)
                    node.logger.info(f'Executing joint trajectory: {len(waypoints)} waypoints, speed={speed}, command={motion_command}')

                    action_client = node.robot_joint_array_action_client
                    if not action_client.wait_for_server(timeout_sec=5.0):
                        ui.notify('Joint trajectory action server not available', type='negative')
                        return

                    goal_msg = ExecuteJointArray.Goal()
                    goal_msg.motion_command = motion_command
                    goal_msg.waypoints = [
                        RobotJoints(j1=wp[0], j2=wp[1], j3=wp[2], j4=wp[3], j5=wp[4], j6=wp[5])
                        for wp in waypoints
                    ]
                    goal_msg.speed = speed

                    mp_test_refs['execute_btn'].disable()
                    ui.notify(f'Sending {len(waypoints)} waypoints (speed={speed})...', type='info')

                    send_goal_future = action_client.send_goal_async(goal_msg)
                    start = asyncio.get_event_loop().time()
                    while not send_goal_future.done():
                        if asyncio.get_event_loop().time() - start > 10.0:
                            ui.notify('Goal send timed out', type='negative')
                            mp_test_refs['execute_btn'].enable()
                            return
                        await asyncio.sleep(0.05)

                    goal_handle: ClientGoalHandle = send_goal_future.result()
                    if not goal_handle.accepted:
                        ui.notify('Goal rejected by robot controller', type='warning')
                        mp_test_refs['execute_btn'].enable()
                        return

                    ui.notify('Executing...', type='info')
                    result_future = goal_handle.get_result_async()
                    while not result_future.done():
                        await asyncio.sleep(0.1)

                    ros_result = result_future.result().result
                    if ros_result.success:
                        ui.notify(f'Done: {ros_result.message}', type='positive')
                        node.logger.info(f'Joint trajectory done: {ros_result.message}')
                    else:
                        ui.notify(f'Failed: {ros_result.message}', type='negative')
                        node.logger.error(f'Joint trajectory failed: {ros_result.message}')

                    mp_test_refs['execute_btn'].enable()

                except Exception as e:
                    ui.notify(f'Error: {e}', type='negative')
                    node.logger.error(f'Error executing motion plan: {e}')
                    mp_test_refs['execute_btn'].enable()

            async def reload_tools_config():
                """Reload tool definitions from YAML (re-parse config + STL meshes)."""
                try:
                    ui.notify('Reloading tools config...', type='info')
                    node.logger.info('Reloading tools config via UI')
                    response: TriggerServiceSrv.Response = await node.call_service_async(
                        node.tool_clients.reload_tools_cli,
                        TriggerServiceSrv.Request(),
                        timeout_sec=CALL_TIMEOUT_SEC
                    )
                    if response.status:
                        ui.notify(f'Tools reloaded: {response.message}', type='positive')
                        node.logger.info(f'Tools reloaded: {response.message}')
                    else:
                        ui.notify(f'Reload failed: {response.message}', type='negative')
                        node.logger.error(f'Reload failed: {response.message}')
                except Exception as e:
                    ui.notify(f'Error reloading tools: {e}', type='negative')
                    node.logger.error(f'Error reloading tools: {e}')

            node_configs = {
                'robot': {
                    'title': 'Robot Controller',
                    'node_name': RobotControllerConstants.NODE_NAME,
                    'state': {StateKeys.STATE: 'Unknown', StateKeys.DESCRIPTION: ''},
                    'clients': node.robot_clients,
                    'timeout': CALL_TIMEOUT_SEC,
                    'has_card': True,
                    'custom_buttons': [('Get cartesian', 'gps_fixed', get_robot_pos, 'primary')],
                    'init_timeout': CALL_TIMEOUT_SEC,
                },
                'camera': {
                    'title': 'Camera Controller',
                    'node_name': CameraControllerConstants.NODE_NAME,
                    'state': {StateKeys.STATE: 'Unknown', StateKeys.DESCRIPTION: ''},
                    'clients': node.camera_clients,
                    'timeout': CALL_TIMEOUT_SEC,
                    'has_card': True,
                    'custom_buttons': [('Trigger Scan', 'camera', trigger_scan, 'primary')],
                    'init_timeout': CALL_TIMEOUT_SEC,
                },
                'vision': {
                    'title': 'Vision Node',
                    'node_name': VisionProcessingConstants.NODE_NAME,
                    'state': {StateKeys.STATE: 'Unknown', StateKeys.DESCRIPTION: ''},
                    'clients': node.vision_clients,
                    'timeout': CALL_TIMEOUT_SEC,
                    'has_card': True,
                    'custom_buttons': [('Process Scan', 'build', trigger_processing, 'primary')],
                    'init_timeout': CALL_TIMEOUT_SEC * 30,
                },
                'ui': {
                    'title': 'User Interface',
                    'node_name': UserInterfaceConstants.NODE_NAME,
                    'state': {StateKeys.STATE: 'Unknown', StateKeys.DESCRIPTION: ''},
                    'clients': node.ui_clients,
                    'timeout': CALL_TIMEOUT_SEC,
                    'has_card': False,
                    'custom_buttons': None,
                    'init_timeout': None,
                },
                'coordinator': {
                    'title': 'Coordinator',
                    'node_name': CoordinatorConstants.NODE_NAME,
                    'state': {StateKeys.STATE: 'Unknown', StateKeys.DESCRIPTION: ''},
                    'clients': node.coordinator_clients,
                    'timeout': CALL_TIMEOUT_SEC,
                    'has_card': True,
                    'custom_buttons': None,
                    'init_timeout': CALL_TIMEOUT_SEC,
                },
                'tool_controller': {
                    'title': 'Tool Controller',
                    'node_name': ToolControllerConstants.NODE_NAME,
                    'state': {StateKeys.STATE: 'Unknown', StateKeys.DESCRIPTION: ''},
                    'clients': node.tool_clients,
                    'timeout': CALL_TIMEOUT_SEC,
                    'has_card': True,
                    'custom_buttons': [('Reload Tools Config', 'refresh', reload_tools_config, 'primary')],
                    'init_timeout': CALL_TIMEOUT_SEC,
                },
                'motion_planning': {
                    'title': 'Motion Planning',
                    'node_name': MotionPlanningConstants.NODE_NAME,
                    'state': {StateKeys.STATE: 'Unknown', StateKeys.DESCRIPTION: ''},
                    'clients': node.motion_planning_clients,
                    'timeout': CALL_TIMEOUT_SEC,
                    'has_card': True,
                    'custom_buttons': None,
                    'init_timeout': CALL_TIMEOUT_SEC,
                },

            }

            async def initialize_all():
                """Initialize all nodes that have a control card"""
                try:
                    ui.notify('Initializing all nodes...', type='info')
                    node.logger.info('Initializing all nodes via UI')
                    
                    for cfg in node_configs.values():
                        if cfg['has_card'] and cfg.get('init_timeout'):
                            await initialize_async(
                                cfg['node_name'], cfg['init_timeout'],
                                cfg['clients'].initialize_node_cli
                            )
                    
                    ui.notify('All nodes initialized', type='positive')
                    
                except Exception as e:
                    ui.notify(f'Error during initialization: {e}', type='negative')
                    node.logger.error(f'Error during initialization: {e}')
            
            async def get_all_states():
                """Get states for all registered nodes"""
                for cfg in node_configs.values():
                    await get_state_async(
                        cfg['node_name'], cfg['timeout'],
                        cfg['clients'].get_state_cli, cfg['state']
                    )
            
            # Create layout (header + sidebar) and get content area
            with create_main_layout(accessor=accessor_dto, active_page=SYSTEM_CONTROL_PAGE.page):
                
                # Page header
                with ui.row().classes('w-full items-center justify-between mb-6'):
                    with ui.row().classes('items-center'):
                        ui.icon(SYSTEM_CONTROL_PAGE.icon).classes('text-4xl text-primary mr-3')
                        with ui.column().classes('gap-0'):
                            ui.label(SYSTEM_CONTROL_PAGE.name).classes('text-h4 mt-4')
                            ui.label('Initialize and manage nodes').classes('text-subtitle2 text-grey-7')
                
                # Quick Actions
                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Quick Actions').classes('text-h6')
                    with ui.row().classes('gap-4'):
                        ui.button('Initialize All', icon='power_settings_new', 
                                 on_click=initialize_all
                        ).props('color=positive')
                        ui.button('Refresh service states', icon='refresh',
                                 on_click=get_all_states
                        ).props('outline color=primary')
                
                # Node control cards (auto-generated from node_configs)
                with ui.grid(columns=2).classes('w-full gap-4'):
                    for key, cfg in node_configs.items():
                        if not cfg['has_card']:
                            continue
                        state_label, desc_label = create_node_control_card(
                            title=cfg['title'],
                            state_dict=cfg['state'],
                            initialize_callback=partial(initialize_async, cfg['node_name'], cfg['timeout'], cfg['clients'].initialize_node_cli),
                            cleanup_callback=partial(cleanup_async, cfg['node_name'], cfg['timeout'], cfg['clients'].cleanup_resources_cli),
                            recover_callback=partial(recover_async, cfg['node_name'], cfg['timeout'], cfg['clients'].recover_from_error_cli),
                            check_state_callback=partial(get_state_async, cfg['node_name'], cfg['timeout'], cfg['clients'].get_state_cli, cfg['state']),
                            custom_buttons=cfg['custom_buttons'],
                        )
                        node_labels[key] = {'state': state_label, 'desc': desc_label}

                # Motion Planning Test Card
                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Motion Planning Test').classes('text-h6')
                    with ui.row().classes('w-full gap-4 mb-2'):
                        mp_test_refs['pose_select'] = ui.select(
                            [''], label='Predefined Pose', value='',
                            on_change=apply_selected_pose,
                        ).classes('flex-1')
                        mp_test_refs['pose_name'] = ui.input(label='Pose Name', value='').classes('flex-1')
                        ui.button('Load', icon='upload_file',
                                  on_click=load_poses_yaml).props('outline color=primary')
                        ui.button('Save', icon='save',
                                  on_click=save_pose_yaml).props('outline color=positive')
                    with ui.row().classes('w-full gap-4 mb-2'):
                        mp_test_refs['x'] = ui.number(label='X (m)', value=0.6, format='%.4f').classes('flex-1')
                        mp_test_refs['y'] = ui.number(label='Y (m)', value=0.0, format='%.4f').classes('flex-1')
                        mp_test_refs['z'] = ui.number(label='Z (m)', value=0.8, format='%.4f').classes('flex-1')
                    with ui.row().classes('w-full gap-4 mb-2'):
                        mp_test_refs['roll']  = ui.number(label='Roll (°)',  value=0.0, format='%.2f').classes('flex-1')
                        mp_test_refs['pitch'] = ui.number(label='Pitch (°)', value=180.0, format='%.2f').classes('flex-1')
                        mp_test_refs['yaw']   = ui.number(label='Yaw (°)',   value=0.0, format='%.2f').classes('flex-1')
                    with ui.row().classes('w-full gap-4 mb-4'):
                        mp_test_refs['mode'] = ui.select(
                            [MotionPlanningConstants.PlanningMode.JOINT_SPACE,
                             MotionPlanningConstants.PlanningMode.CARTESIAN],
                            label='Planning Mode',
                            value=MotionPlanningConstants.PlanningMode.JOINT_SPACE,
                        ).classes('flex-1')
                        mp_test_refs['exec_speed'] = ui.select(
                            ['10', '20', '50', '100', '200'],
                            label='Execute Speed',
                            value='50',
                        ).classes('flex-1')
                        mp_test_refs['exec_motion_command'] = ui.select(
                            [RobotControllerConstants.MotionCommands.MOVE_ABS_J, RobotControllerConstants.MotionCommands.MOVE_ABS_L],
                            label='Motion Command',
                            value=RobotControllerConstants.MotionCommands.MOVE_ABS_J,
                        ).classes('flex-1')
                    with ui.row().classes('w-full gap-2'):
                        ui.button('Plan', icon='route',
                                  on_click=test_motion_plan).props('color=primary')
                        execute_btn = ui.button('Execute', icon='play_arrow',
                                  on_click=execute_motion_plan).props('color=positive')
                        execute_btn.disable()
                        mp_test_refs['execute_btn'] = execute_btn

                # System Information Card (auto-generated from node_configs)
                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('System Information').classes('text-h6')
                    with ui.grid(columns=2).classes('w-full gap-4'):
                        with ui.column().classes('gap-1'):
                            ui.label('ROS2 Node').classes('text-subtitle2 text-grey-7')
                            for cfg in node_configs.values():
                                ui.label(cfg['node_name']).classes('text-body2')
                        with ui.column().classes('gap-1'):
                            ui.label('State').classes('text-subtitle2 text-grey-7')
                            for key, cfg in node_configs.items():
                                overview_label = ui.label(cfg['state'][StateKeys.STATE]).classes('text-body2')
                                node_labels.setdefault(key, {})['overview'] = overview_label
                
                # Help Card
                with ui.card().classes('w-full p-6 bg-blue-1'):
                    with ui.row().classes('items-start gap-3'):
                        ui.icon('info').classes('text-primary text-2xl')
                        with ui.column().classes('gap-2'):
                            ui.label('Hardware Control Guide').classes('text-subtitle1 font-bold')
                            ui.label('1. Initialize hardware before performing operations').classes('text-body2')
                            ui.label('2. Use "Check State" to verify node status').classes('text-body2')
                            ui.label('3. If errors occur, use "Recover from Error" or "Cleanup Resources"').classes('text-body2')

                # Initial state check (deferred — don't block page render)
                ui.timer(0.3, get_all_states, once=True)

        except Exception as e:
            node.logger.error(f'Robot control page error: {e}')
            ui.notify('Failed to load system control page', color='negative')
    
    return create_system_control_page
