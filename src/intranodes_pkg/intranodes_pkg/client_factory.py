from dataclasses import dataclass
from rclpy.node import Node
from rclpy.client import Client

from rcl_interfaces.srv import SetParameters, GetParameters

from interface_pkg.srv import (
    NodeStateSrv,
    ScanAcquisitionSrv,
    RobotRequestSrv,
    TriggerServiceSrv,
    ProcessVisionSrv,
    ProcessVisionSrv2,
    PlanMotionSrv,
)
from core_pkg.systemconstants import (
    RobotControllerConstants,
    CameraControllerConstants,
    GeneralNodeConstants,
    UserInterfaceConstants,
    VisionProcessingConstants,
    CoordinatorConstants,
    ToolControllerConstants,
    MotionPlanningConstants,
)


@dataclass
class GenericClients:
    get_state_cli: Client
    set_parameters_cli: Client
    initialize_node_cli: Client
    cleanup_resources_cli: Client
    get_parameters_cli: Client
    apply_parameters_cli: Client
    recover_from_error_cli: Client

@dataclass
class VisionProcessingClients(GenericClients):
    vision_processing_op1_cli: Client
    vision_processing_op2_cli: Client

@dataclass
class UserInterfaceClients(GenericClients):
    pass

@dataclass
class CameraControllerClients(GenericClients):
    camera_controller_capture_cli: Client

@dataclass
class RobotControllerClients(GenericClients):
    robot_controller_request_cli: Client

@dataclass
class ToolControllerClients(GenericClients):
    swap_tool_cli: Client
    reload_tools_cli: Client

@dataclass
class CoordinatorClients(GenericClients):
    pass

@dataclass
class MotionPlanningClients(GenericClients):
    plan_motion_cli: Client


class ClientFactory:
    @staticmethod
    def create_camera_clients(node: Node, cb_group) -> CameraControllerClients:
        base = CameraControllerConstants.NODE_NAME
        return CameraControllerClients(
            get_state_cli=node.create_client(NodeStateSrv, f"{base}/{GeneralNodeConstants.ServiceNames.GET_STATE}", callback_group=cb_group),
            set_parameters_cli=node.create_client(SetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.SET_PARAMETERS}", callback_group=cb_group),
            initialize_node_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.INITIALIZE_NODE}", callback_group=cb_group),
            cleanup_resources_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.CLEANUP_RESOURCES}", callback_group=cb_group),
            get_parameters_cli=node.create_client(GetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.GET_PARAMETERS}", callback_group=cb_group),
            apply_parameters_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.APPLY_PARAMETERS}", callback_group=cb_group),
            recover_from_error_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.RECOVER_FROM_ERROR}", callback_group=cb_group),
            camera_controller_capture_cli=node.create_client(ScanAcquisitionSrv, f"{base}/{CameraControllerConstants.ServiceNames.EXECUTE_SCAN}", callback_group=cb_group),
        )

    @staticmethod
    def create_robot_clients(node: Node, cb_group) -> RobotControllerClients:
        base = RobotControllerConstants.NODE_NAME
        return RobotControllerClients(
            get_state_cli=node.create_client(NodeStateSrv, f"{base}/{GeneralNodeConstants.ServiceNames.GET_STATE}", callback_group=cb_group),
            set_parameters_cli=node.create_client(SetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.SET_PARAMETERS}", callback_group=cb_group),
            initialize_node_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.INITIALIZE_NODE}", callback_group=cb_group),
            cleanup_resources_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.CLEANUP_RESOURCES}", callback_group=cb_group),
            get_parameters_cli=node.create_client(GetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.GET_PARAMETERS}", callback_group=cb_group),
            apply_parameters_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.APPLY_PARAMETERS}", callback_group=cb_group),
            recover_from_error_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.RECOVER_FROM_ERROR}", callback_group=cb_group),
            robot_controller_request_cli=node.create_client(RobotRequestSrv, f"{base}/{RobotControllerConstants.ServiceNames.CONTROLLER_REQUEST}", callback_group=cb_group),
        )

    @staticmethod
    def create_ui_clients(node: Node, cb_group) -> UserInterfaceClients:
        base = UserInterfaceConstants.NODE_NAME
        return UserInterfaceClients(
            get_state_cli=node.create_client(NodeStateSrv, f"{base}/{GeneralNodeConstants.ServiceNames.GET_STATE}", callback_group=cb_group),
            set_parameters_cli=node.create_client(SetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.SET_PARAMETERS}", callback_group=cb_group),
            initialize_node_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.INITIALIZE_NODE}", callback_group=cb_group),
            cleanup_resources_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.CLEANUP_RESOURCES}", callback_group=cb_group),
            get_parameters_cli=node.create_client(GetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.GET_PARAMETERS}", callback_group=cb_group),
            apply_parameters_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.APPLY_PARAMETERS}", callback_group=cb_group),
            recover_from_error_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.RECOVER_FROM_ERROR}", callback_group=cb_group),
        )

    @staticmethod
    def create_vision_clients(node: Node, cb_group) -> VisionProcessingClients:
        base = VisionProcessingConstants.NODE_NAME
        return VisionProcessingClients(
            get_state_cli=node.create_client(NodeStateSrv, f"{base}/{GeneralNodeConstants.ServiceNames.GET_STATE}", callback_group=cb_group),
            set_parameters_cli=node.create_client(SetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.SET_PARAMETERS}", callback_group=cb_group),
            initialize_node_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.INITIALIZE_NODE}", callback_group=cb_group),
            cleanup_resources_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.CLEANUP_RESOURCES}", callback_group=cb_group),
            get_parameters_cli=node.create_client(GetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.GET_PARAMETERS}", callback_group=cb_group),
            apply_parameters_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.APPLY_PARAMETERS}", callback_group=cb_group),
            recover_from_error_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.RECOVER_FROM_ERROR}", callback_group=cb_group),
            vision_processing_op1_cli=node.create_client(ProcessVisionSrv, f"{base}/{VisionProcessingConstants.ServiceNames.PROCESS_VISION_OP1}", callback_group=cb_group),
            vision_processing_op2_cli=node.create_client(ProcessVisionSrv2, f"{base}/{VisionProcessingConstants.ServiceNames.PROCESS_VISION_OP2}", callback_group=cb_group),
        )

    @staticmethod
    def create_tool_clients(node: Node, cb_group) -> ToolControllerClients:
        base = ToolControllerConstants.NODE_NAME
        return ToolControllerClients(
            get_state_cli=node.create_client(NodeStateSrv, f"{base}/{GeneralNodeConstants.ServiceNames.GET_STATE}", callback_group=cb_group),
            set_parameters_cli=node.create_client(SetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.SET_PARAMETERS}", callback_group=cb_group),
            initialize_node_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.INITIALIZE_NODE}", callback_group=cb_group),
            cleanup_resources_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.CLEANUP_RESOURCES}", callback_group=cb_group),
            get_parameters_cli=node.create_client(GetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.GET_PARAMETERS}", callback_group=cb_group),
            apply_parameters_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.APPLY_PARAMETERS}", callback_group=cb_group),
            recover_from_error_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.RECOVER_FROM_ERROR}", callback_group=cb_group),
            swap_tool_cli=node.create_client(RobotRequestSrv, f"{base}/{ToolControllerConstants.ServiceNames.SWAP_TOOL}", callback_group=cb_group),
            reload_tools_cli=node.create_client(TriggerServiceSrv, f"{base}/{ToolControllerConstants.ServiceNames.RELOAD_TOOLS}", callback_group=cb_group),
        )

    @staticmethod
    def create_motion_planning_clients(node: Node, cb_group) -> MotionPlanningClients:
        base = MotionPlanningConstants.NODE_NAME
        return MotionPlanningClients(
            get_state_cli=node.create_client(NodeStateSrv, f"{base}/{GeneralNodeConstants.ServiceNames.GET_STATE}", callback_group=cb_group),
            set_parameters_cli=node.create_client(SetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.SET_PARAMETERS}", callback_group=cb_group),
            initialize_node_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.INITIALIZE_NODE}", callback_group=cb_group),
            cleanup_resources_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.CLEANUP_RESOURCES}", callback_group=cb_group),
            get_parameters_cli=node.create_client(GetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.GET_PARAMETERS}", callback_group=cb_group),
            apply_parameters_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.APPLY_PARAMETERS}", callback_group=cb_group),
            recover_from_error_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.RECOVER_FROM_ERROR}", callback_group=cb_group),
            plan_motion_cli=node.create_client(PlanMotionSrv, f"{base}/{MotionPlanningConstants.ServiceNames.PLAN_MOTION}", callback_group=cb_group),
        )

    @staticmethod
    def create_coordinator_clients(node: Node, cb_group) -> CoordinatorClients:
        base = CoordinatorConstants.NODE_NAME
        return CoordinatorClients(
            get_state_cli=node.create_client(NodeStateSrv, f"{base}/{GeneralNodeConstants.ServiceNames.GET_STATE}", callback_group=cb_group),
            set_parameters_cli=node.create_client(SetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.SET_PARAMETERS}", callback_group=cb_group),
            initialize_node_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.INITIALIZE_NODE}", callback_group=cb_group),
            cleanup_resources_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.CLEANUP_RESOURCES}", callback_group=cb_group),
            get_parameters_cli=node.create_client(GetParameters, f"{base}/{GeneralNodeConstants.ServiceNames.GET_PARAMETERS}", callback_group=cb_group),
            apply_parameters_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.APPLY_PARAMETERS}", callback_group=cb_group),
            recover_from_error_cli=node.create_client(TriggerServiceSrv, f"{base}/{GeneralNodeConstants.ServiceNames.RECOVER_FROM_ERROR}", callback_group=cb_group),
        )
