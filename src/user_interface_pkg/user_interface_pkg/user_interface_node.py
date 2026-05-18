from __future__ import annotations
import os
import time
import threading
from typing import Optional

import rclpy
from rclpy.executors import ExternalShutdownException

from fastapi import Request
from fastapi.responses import RedirectResponse
from nicegui import ui, app, Client, ui_run

from rclpy.action import ActionClient

from core_pkg.nodes_async import AsyncINTRANode
from intranodes_pkg.client_factory import ClientFactory
from core_pkg.systemconstants import UserInterfaceConstants, RobotControllerConstants, CoordinatorConstants
from core_pkg.settings import UI_STORAGE_SECRET, APP_TITLE
from user_interface_pkg.utils.jwtutils import is_session_active, touch_session

# Import page factories
from user_interface_pkg.pages.login_page import login_page_factory
from user_interface_pkg.pages.dashboard_page import dashboard_page_factory
from user_interface_pkg.pages.settings_page import settings_page_factory
from user_interface_pkg.pages.user_management_page import user_management_page_factory
from user_interface_pkg.pages.configuration_page import configuration_page_factory
from user_interface_pkg.pages.system_control_page import system_control_page_factory
from user_interface_pkg.pages.operations_page import operations_page_factory
from user_interface_pkg.pages.robot_shadow_page import robot_shadow_page_factory
from user_interface_pkg.pages.tool_control_page import tool_controller_page_factory
# Import permission decorators
from user_interface_pkg.utils.permissions import require_permission

from user_interface_pkg.constants import LOGIN_PAGE, DASHBOARD_PAGE, SETTINGS_PAGE, USER_MANAGEMENT_PAGE, CONFIGURATION_PAGE, SYSTEM_CONTROL_PAGE, OPERATIONS_PAGE, ROBOT_PAGE, TOOL_CONTROLLER_PAGE
from core_pkg.systemconstants import NodeStates
from core_pkg.exceptions import NodeException
from user_interface_pkg.constants import StorageConstants
from core_pkg.dbmodels.schemas import PermissionsKeys
from interface_pkg.srv import TriggerServiceSrv
from interface_pkg.action import PerformOperation, ExecuteJointArray

from sensor_msgs.msg import JointState



unrestricted_page_routes = {LOGIN_PAGE.route}



@app.middleware('http')
async def auth_middleware(request: Request, call_next):
    """
    Redirects an unauthenticated user to /login
    if they are trying to access any NiceGUI page outside `unrestricted_page_routes`.
    Adds Authorization: Bearer <token> to request.headers.
    Clears stale session data when a token has expired.
    """
    path = request.url.path
    
    # Skip auth for unrestricted routes, internal NiceGUI routes, and static files
    if (path in unrestricted_page_routes or 
        path.startswith('/_nicegui') or 
        path.startswith('/static') or 
        path == '/favicon.ico'):
        return await call_next(request)
    
    # Try to get token from storage (requires UI context)
    try:
        active = is_session_active()
    except RuntimeError:
        # UI context not available yet (first request from client)
        # Allow the request to proceed - NiceGUI will create the context
        return await call_next(request)

    # Redirect to login if session is inactive / expired
    if (not active
        and path in Client.page_routes.values()
        and path not in unrestricted_page_routes):
        # Clear stale session data so no leftover artifacts remain
        try:
            app.storage.user.clear()
        except RuntimeError:
            pass
        try:
            app.storage.user[StorageConstants.REFERRER_PATH] = path
        except RuntimeError:
            pass  # Can't set referrer if no UI context
        return RedirectResponse(LOGIN_PAGE.route)

    # Session is valid — refresh the inactivity timer
    if active:
        try:
            touch_session()
        except RuntimeError:
            pass

    # Inject Authorization header
    token = None
    try:
        token = app.storage.user.get(StorageConstants.AUTH_TOKEN, None)
    except RuntimeError:
        pass
    headers = [
        (k, v)
        for (k, v) in request.scope.get('headers', [])
        if k != b'authorization'
    ]
    if token:
        headers.append((b'authorization', f'Bearer {token}'.encode()))
    request.scope['headers'] = headers

    return await call_next(request)



@app.on_connect
async def on_client_connect():
    """
    Called every time a browser tab (re)connects via WebSocket.
    If the session has been inactive too long, clear the stale storage
    so the next navigation / middleware check redirects to login cleanly.
    """
    try:
        token = app.storage.user.get(StorageConstants.AUTH_TOKEN, None)
        if token and not is_session_active():
            app.storage.user.clear()
    except RuntimeError:
        pass  # storage not available yet — middleware will handle it


class UserInterfaceNode(AsyncINTRANode):
    """User Interface Node with NiceGUI and ROS2 integration."""

    def __init__(self) -> None:
        super().__init__(UserInterfaceConstants.NODE_NAME)

        self.coordinator_clients = ClientFactory.create_coordinator_clients(self, self.cb_group)
        self.robot_clients = ClientFactory.create_robot_clients(self, self.cb_group)
        self.camera_clients = ClientFactory.create_camera_clients(self, self.cb_group)
        self.vision_clients = ClientFactory.create_vision_clients(self, self.cb_group)
        self.tool_clients = ClientFactory.create_tool_clients(self, self.cb_group)
        self.ui_clients = ClientFactory.create_ui_clients(self, self.cb_group)
        self.motion_planning_clients = ClientFactory.create_motion_planning_clients(self, self.cb_group)

        self.get_logger().info('User Interface Node started')

        # Action client for coordinator pipeline (operation 1)
        self.perform_operation_action_client = ActionClient(
            self,
            PerformOperation,
            f"{CoordinatorConstants.NODE_NAME}/{CoordinatorConstants.ActionNames.PERFORM_OPERATION}",
            callback_group=self.cb_group,
        )

        self.robot_joint_array_action_client = ActionClient(
            self,
            ExecuteJointArray,
            f"{RobotControllerConstants.NODE_NAME}/{RobotControllerConstants.ActionNames.ROBOT_JOINTTARGET_MOVE_ACTION}",
            callback_group=self.cb_group,
        )

        # Action client for coordinator pipeline (operation 2)
        self.perform_operation2_action_client = ActionClient(
            self,
            PerformOperation,
            f"{CoordinatorConstants.NODE_NAME}/{CoordinatorConstants.ActionNames.PERFORM_OPERATION_2}",
            callback_group=self.cb_group,
        )

        # Service client for user input trigger
        self.user_input_client = self.create_client(
            TriggerServiceSrv,
            f"{CoordinatorConstants.NODE_NAME}/{CoordinatorConstants.ServiceNames.USER_INPUT}",
            callback_group=self.cb_group,
        )

        # Joint state subscription
        self.joint_state_subscriber = None
        self.latest_joint_state: Optional[JointState] = None

        with self.sm_lock:
            self.lifecycle_sm.boot_complete(message=f"Boot of {self.NODE_NAME} complete, waiting for initialization")
        self.setup_ui_pages()

        with self.sm_lock:
            self.lifecycle_sm.start_initialization(message="Starting node initialization")


        # Services
        # self.service_one = self.create_service(...

        with self.sm_lock:
            self.lifecycle_sm.complete(message="Node initialization complete, ready for operation")


    def start_joint_state_subscription(self) -> None:
        """ JointState subscription."""
        if self.joint_state_subscriber is not None:
            return

        topic = f"{RobotControllerConstants.TopicNames.JOINT_STATES_TOPIC}"
        self.get_logger().info(f"Subscribing to JointState: {topic}")

        self.joint_state_subscriber = self.create_subscription(
            JointState,
            topic,
            self.handle_joint_state,
            10,
        )

    def stop_joint_state_subscription(self) -> None:
        """ JointState subscription."""
        if self.joint_state_subscriber is None:
            return

        self.get_logger().info("Unsubscribing from JointState")
        self.destroy_subscription(self.joint_state_subscriber)
        self.joint_state_subscriber = None

    def handle_joint_state(self, msg: JointState) -> None:
        """Callback JointState."""
        self.latest_joint_state = msg

    
    def apply_parameters(self) -> None:
        """Handle apply parameters service call"""
        pass

    def cleanup_resources(self) -> None:
        """Cleanup resources before shutdown."""
        pass
    def initialize_node(self) -> None:
        """Initialize node resources."""
        pass

    def setup_ui_pages(self):
        """
        Page registration with permission-based access control.
        
        Access levels:
        - Login: Public (no auth required)
        - Dashboard: All authenticated users
        - Settings: All authenticated users (some sections require permissions)
        - Other pages: Permission-specific decorators
        """
        
        ui.page(LOGIN_PAGE.route, title=f'{LOGIN_PAGE.name} | {APP_TITLE}')(
            login_page_factory(self)
        )
        
        # Dashboard - accessible to all authenticated users
        ui.page(DASHBOARD_PAGE.route, title=f'{DASHBOARD_PAGE.name} | {APP_TITLE}')(
            dashboard_page_factory(self)
        )
        
        # Settings - accessible to all authenticated users
        # (Internal sections use conditional rendering based on permissions)
        ui.page(SETTINGS_PAGE.route, title=f'{SETTINGS_PAGE.name} | {APP_TITLE}')(
            settings_page_factory(self)
        )

        # User Management - requires user management permission
        ui.page(USER_MANAGEMENT_PAGE.route, title=f'{USER_MANAGEMENT_PAGE.name} | {APP_TITLE}')(
            require_permission(PermissionsKeys.ALLOW_USER_MANAGEMENT)(
                user_management_page_factory(self)
            )
        )

        # Configuration - requires system config permission
        ui.page(CONFIGURATION_PAGE.route, title=f'{CONFIGURATION_PAGE.name} | {APP_TITLE}')(
            require_permission(PermissionsKeys.ALLOW_SYSTEM_CONFIG)(
                configuration_page_factory(self)
            )
        )

        # System Control - requires system control permission
        ui.page(SYSTEM_CONTROL_PAGE.route, title=f'{SYSTEM_CONTROL_PAGE.name} | {APP_TITLE}')(
            require_permission(PermissionsKeys.ALLOW_SYSTEM_CONTROL)(
                system_control_page_factory(self)
            )
        )

        # Operations - requires manage operations permission
        ui.page(OPERATIONS_PAGE.route, title=f'{OPERATIONS_PAGE.name} | {APP_TITLE}')(
            require_permission(PermissionsKeys.ALLOW_MANAGE_OPERATIONS)(
                operations_page_factory(self)
            )
        )

        ui.page(ROBOT_PAGE.route, title=f'{ROBOT_PAGE.name} | {APP_TITLE}')(
            require_permission(PermissionsKeys.ALLOW_ROBOT_PREVIEW)(
                robot_shadow_page_factory(self)
            )
        )
        ui.page(TOOL_CONTROLLER_PAGE.route, title=f'{TOOL_CONTROLLER_PAGE.name} | {APP_TITLE}')(
            require_permission(PermissionsKeys.ALLOW_SYSTEM_CONTROL)(
                tool_controller_page_factory(self)
            )
        )

       
# ROS main entry point

def ros_main() -> None:
    """Main ROS2 entry point, runs in a separate thread."""
    rclpy.init()
    node: Optional[UserInterfaceNode] = None

    try:
        node = UserInterfaceNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        
        if node:
            node.lifecycle_sm.shutdown(message=f"Shutdown requested, stopping {node.NODE_NAME}")
        else:
            print('Shutdown signal received during initialization')
    except Exception as e:
        if node:
            node.lifecycle_sm.shutdown(message=f"Unexpected error: {e}")
        else:
            print(f'Error during node initialization: {e}')
    finally:
        if node:
            try:
                node.cleanup_resources()
                node.destroy_node()
            except Exception as e:
                print(f'Error during cleanup: {e}')
        rclpy.shutdown()


def main() -> None:
    pass

# NiceGUI app start

# Start ROS2 in a separate thread before starting NiceGUI
app.on_startup(lambda: threading.Thread(target=ros_main, daemon=True).start())

ui_run.APP_IMPORT_STRING = f'{__name__}:app'


ui.run(
    show=True,
    favicon='src/user_interface_pkg/user_interface_pkg/static/favicon.svg',
    title=APP_TITLE,
    storage_secret=UI_STORAGE_SECRET,
    uvicorn_logging_level='info',
    host='0.0.0.0',
    port=8080,
    reload=False,  # Disable auto-reload to prevent multiple ROS nodes from starting
)