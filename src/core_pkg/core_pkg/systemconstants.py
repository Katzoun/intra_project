from enum import Enum
from dataclasses import dataclass
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

@dataclass(frozen=True)
class StateKeys:
    STATE: str = 'state'
    DESCRIPTION: str = 'description'

TOPIC_QOS = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.SYSTEM_DEFAULT)

CALL_TIMEOUT_SEC = 30.0

class DatabaseConstants:
    BLOB_ID_LENGTH = 10
    MAX_TITLE_LENGTH = 30
    MAX_DESCRIPTION_LENGTH = 255
    MAX_NAME_LENGTH = 32
    MIN_NAME_LENGTH = 3
    MAX_LOGIN_LENGTH = 32
    MIN_LOGIN_LENGTH = 5
    MAX_PASSWORD_LENGTH = 64
    MIN_PASSWORD_LENGTH = 8

class Operation1Phases:
    SCANNING = "scanning"
    VISION_PROCESSING = "vision_processing"
    GRASP_READY = "grasp_ready"
    EXECUTING_MOTION = "executing_motion"
    COMPLETED = "completed"

class Operation2Phases:
    SCANNING = "scanning"
    VISION_PROCESSING = "vision_processing"
    POSE_READY = "pose_ready"
    EXECUTING_MOTION = "executing_motion"
    COMPLETED = "completed"





class GeneralNodeConstants:
    class ServiceNames:
        GET_STATE = "get_state"
        SET_PARAMETERS = "set_parameters"
        GET_PARAMETERS = "get_parameters"
        APPLY_PARAMETERS = "apply_parameters"
        INITIALIZE_NODE = "initialize_node"
        CLEANUP_RESOURCES = "cleanup_resources"
        RECOVER_FROM_ERROR = "recover_from_error"

class CameraControllerConstants:
    NODE_NAME = "camera_controller"
    class ServiceNames:
        EXECUTE_SCAN = "execute_scan"
    class TopicNames:
        TEXTURE_TOPIC = "texture"
        DEPTH_MAP_TOPIC = "depth_map"
        POINT_CLOUD_TOPIC = "points"
        POINT_CLOUD_FULL_TOPIC = "pointsfull"
        POINT_CLOUD_FULL_TOPIC_ROS = "pointsfull_ros"
        NORMAL_MAP_TOPIC = "normal_map"
        CONFIDENCE_MAP_TOPIC = "confidence_map"

class VisionProcessingConstants:
    NODE_NAME = "vision_processing"
    class ServiceNames:
        PROCESS_VISION_OP1 = "process_vision_op1"
        PROCESS_VISION_OP2 = "process_vision_op2"
        
class RobotControllerConstants:
    NODE_NAME = "robot_controller"
    class ServiceNames:
        CONTROLLER_REQUEST = "controller_request"
    class TopicNames:
        JOINT_STATES_TOPIC = "joint_states"
    class ActionNames:
        ROBOT_ROBTARGET_MOVE_ACTION = "robot_robtarget_move"
        ROBOT_JOINTTARGET_MOVE_ACTION = "robot_jointtarget_move"
        
    class MotionCommands:
        MOVE_L     = "MoveL"
        MOVE_J     = "MoveJ"
        MOVE_ABS_J = "MoveAbsJ"
        MOVE_ABS_L = "MoveAbsL"

    class Modules:
        RAPID = "TRobRAPID"
        USER  = "TRobUser"
        MAIN  = "TRobMain"
    class Symbols:
        ROUTINE_NAME       = "routine_name_input"
        SPEED              = "speednum"
        CURRENT_STATE      = "current_state"
        RECEIVED_ROBTARGET = "received_robtarget"
    class States:
        EXECUTE = "2"
        IDLE   = "0"
    class Routines:
        MOVE_L        = "run_routine_buffer_moveL"
        MOVE_J        = "run_routine_buffer_moveJ"
        MOVE_ABS_J    = "run_routine_buffer_moveabsJ"
        MOVE_ABS_L    = "run_routine_buffer_moveabsL"
        SINGLE_MOVE_L = "run_single_moveL"
        SINGLE_MOVE_J = "run_single_moveJ"
        SINGLE_MOVE_C = "run_single_moveC"

class UserInterfaceConstants:
    NODE_NAME = "user_interface"

class ToolControllerConstants:
    NODE_NAME = "tool_controller"
    class ServiceNames:
        SWAP_TOOL = "swap_tool"
        RELOAD_TOOLS = "reload_tools"
    class ToolNames:
        TOOL_1 = "gripper_1"
        TOOL_2 = "gripper_2"
        TOOL_3 = "gripper_3"
        DETACH = "detach"

    TOOL_MESH_FILES: dict[str, str] = {
        ToolNames.TOOL_1: "gripper_1.stl",
        ToolNames.TOOL_2: "gripper_2.stl",
        ToolNames.TOOL_3: "gripper_3.stl",
    }

class MotionPlanningConstants:
    NODE_NAME = "motion_planning"

    class ServiceNames:
        PLAN_MOTION = "plan_motion"
        TOGGLE_FAKE_OBSTACLES = "toggle_fake_obstacles"

    class MoveGroupServiceNames:
        PLAN_KINEMATIC_PATH    = "/plan_kinematic_path"
        COMPUTE_CARTESIAN_PATH = "/compute_cartesian_path"
        GET_PLANNING_SCENE     = "/get_planning_scene"
        COMPUTE_IK             = "/compute_ik"

    class TopicNames:
        JOINT_STATES = "/joint_states"

    class PlanningMode:
        JOINT_SPACE = "joint_space"
        CARTESIAN = "cartesian"

    class Planners:
        """MoveIt2 planners available in move_group"""
        # OMPL planners
        RRT_CONNECT  = "RRTConnect"
        RRT          = "RRT"
        # Asymptotically optimal (finds shorter paths over time)
        RRT_STAR     = "RRTstar"
        LBTRRT       = "LBTRRT"
        # Probabilistic Roadmap, good for repeated queries in same scene
        PRM          = "PRM"
        PRM_STAR     = "PRMstar"
        # Meta-planner: runs multiple planners and continuously shortens the path
        ANYTIME_PATH_SHORTENING = "AnytimePathShortening"
        # Gradient-based trajectory optimizer
        CHOMP        = "CHOMP"

        class Pipelines:
            OMPL  = "ompl"
            CHOMP = "chomp"

        PIPELINE_MAP = {
            RRT_CONNECT:            "ompl",
            RRT:                    "ompl",
            RRT_STAR:               "ompl",
            LBTRRT:                 "ompl",
            PRM:                    "ompl",
            PRM_STAR:               "ompl",
            ANYTIME_PATH_SHORTENING: "ompl",
            CHOMP:                  "chomp",
        }

        ALL = [
            RRT_CONNECT, RRT, RRT_STAR, LBTRRT,
            PRM, PRM_STAR, ANYTIME_PATH_SHORTENING,
            CHOMP,
        ]

    class MoveItConfig:
        PLANNING_GROUP = "gofa_arm"
        EE_LINK = "tool0"
        PLANNING_FRAME = "base_link"
        JOINT_NAMES = [
            "Revolute 1",
            "Revolute 2",
            "Revolute 3",
            "Revolute 4",
            "Revolute 5",
            "Revolute 6",
        ]

class CoordinatorConstants:
    NODE_NAME = "coordinator_node"
    class ServiceNames:
        USER_INPUT = "user_input"
    class ActionNames:
        PERFORM_OPERATION = "perform_operation"
        PERFORM_OPERATION_2 = "perform_operation_2"

class NodeStates(Enum):
    BOOT = "boot"
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    ERROR_RECOVERABLE = "error_recoverable"
    CLEANING_UP = "cleaning_up"
    SHUTTING_DOWN = "shutting_down"

