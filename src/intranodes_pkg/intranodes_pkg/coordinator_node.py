
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.action.client import ClientGoalHandle
import copy
from core_pkg.nodes_core import INTRANode
from intranodes_pkg.client_factory import ClientFactory
from core_pkg.systemconstants import (
    CoordinatorConstants,
    VisionProcessingConstants, ToolControllerConstants, CALL_TIMEOUT_SEC
)
from core_pkg.systemconstants import  RobotControllerConstants as RCC
from intranodes_pkg.robot_controller_interface import RWSInterface
from rclpy.action import ActionClient
from action_msgs.msg import GoalStatus
from rclpy.client import Client
from core_pkg.exceptions import NodeExceptionRecoverable, NodeExceptionNonRecoverable, ServiceCallException
from intranodes_pkg.parameters.coordinator_parameters import CoordinatorParameters, CoordinatorParametersKeys
from sensor_msgs.msg import PointCloud2, Image
import numpy as np
from cv_bridge import CvBridge
from statemachine.exceptions import TransitionNotAllowed
from interface_pkg.srv import TriggerServiceSrv, ScanAcquisitionSrv, ProcessVisionSrv, ProcessVisionSrv2
from interface_pkg.action import PerformOperation
import intranodes_pkg.vision_helpers as vh

from core_pkg.systemconstants import Operation1Phases, Operation2Phases

from geometry_msgs.msg import Pose, PoseArray
from interface_pkg.action import ExecutePoseArray
from interface_pkg.srv import RobotRequestSrv
import time

class _CancelledError(Exception):
    """Raised inside helper functions (wait_for_user_input, wait_for_rapid_idle) when a
    cancel is detected and processed, so the outer execute callback can exit immediately."""
    pass


class CoordinatorNode(INTRANode):

    def __init__(self):
        super().__init__(CoordinatorConstants.NODE_NAME)

        self.camera_clients = ClientFactory.create_camera_clients(self, self.cb_group)
        self.robot_clients = ClientFactory.create_robot_clients(self, self.cb_group)
        self.vision_clients = ClientFactory.create_vision_clients(self, self.cb_group)
        self.tool_clients = ClientFactory.create_tool_clients(self, self.cb_group)
        self.motion_planning_clients = ClientFactory.create_motion_planning_clients(self, self.cb_group)

        # Initialize default parameters

        self.default_ros_params = CoordinatorParameters().to_ros_params()

        self.bridge = CvBridge()
        self._user_input_received = False
        # Declare ROS2 parameters
        declared_params = self.declare_parameters(
            namespace='',  
            parameters=self.default_ros_params
        )
        self.logger.info(f"Declared {len(declared_params)} parameters")
        
        # Action server for operation 1
        self.perform_operation_action_server = ActionServer(
            self,
            PerformOperation,
            f"{CoordinatorConstants.NODE_NAME}/{CoordinatorConstants.ActionNames.PERFORM_OPERATION}",
            execute_callback=self.execute_operation1_cb,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group
        )

        # Action server for operation 2
        self.perform_operation2_action_server = ActionServer(
            self,
            PerformOperation,
            f"{CoordinatorConstants.NODE_NAME}/{CoordinatorConstants.ActionNames.PERFORM_OPERATION_2}",
            execute_callback=self.execute_operation2_cb,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group
        )

        # Action client for robot controller
        self.robot_motion_action_client = ActionClient(
            self,
            ExecutePoseArray,
            f"{RCC.NODE_NAME}/{RCC.ActionNames.ROBOT_ROBTARGET_MOVE_ACTION}",
            callback_group=self.cb_group
        )

        #service servers
        self.user_input_service = self.create_service(
            TriggerServiceSrv,
            f"{CoordinatorConstants.NODE_NAME}/{CoordinatorConstants.ServiceNames.USER_INPUT}",
            self._user_input_cb,
            callback_group=self.cb_group
        )


        with self.sm_lock:
            self.lifecycle_sm.boot_complete(message=f"Boot of {self.NODE_NAME} complete, waiting for initialization")

    def _user_input_cb(self, request: TriggerServiceSrv.Request, response: TriggerServiceSrv.Response) -> TriggerServiceSrv.Response:
        """Service callback to receive user input trigger."""
        self.logger.info("Received user input trigger via service call")
        self._user_input_received = True
        response.status = True
        response.message = "User input received, proceeding with operation"
        return response

   # ============= ACTION SERVER CALLBACKS =============

    def goal_callback(self, goal_request: PerformOperation.Goal) -> GoalResponse:
        """Accept or reject incoming operation goals."""
        try:
            with self.sm_lock:
                self.lifecycle_sm.start_operation(
                    message=f"Received operation goal: {goal_request.operation_name}"
                )
            self.logger.info(f"Goal accepted: operation_name='{goal_request.operation_name}'")
            return GoalResponse.ACCEPT
        except TransitionNotAllowed as e:
            self.logger.error(f"Goal rejected, state machine transition not allowed: {e}")
            return GoalResponse.REJECT

    def cancel_callback(self, goal_handle: ServerGoalHandle) -> CancelResponse:
        """Accept cancel requests."""
        self.logger.info("Cancel requested for operation")
        return CancelResponse.ACCEPT

    def _publish_feedback(self, goal_handle: ServerGoalHandle, phase: str, progress: float, message: str, **kwargs):
        """
        Build a PerformOperation.Feedback message and publish it.
        Any extra keyword arguments whose names match Feedback fields
        (images, point clouds etc..) are set automatically.
        """
        fb = PerformOperation.Feedback()
        fb.phase = phase
        fb.progress = float(progress)
        fb.status_message = message

        for field, value in kwargs.items():
            if hasattr(fb, field):
                setattr(fb, field, value)

        goal_handle.publish_feedback(fb)
        self.logger.info(f"[{phase}] {message}  (progress={progress:.0%})")
 
    def _handle_cancel(self, goal_handle: ServerGoalHandle, result: PerformOperation.Result, message: str) -> PerformOperation.Result:
        """Shared cancel handling."""
        self.logger.info(message)
        goal_handle.canceled()
        result.success = False
        result.message = message
        with self.sm_lock:
            self.lifecycle_sm.complete(message=message)
        return result

    @staticmethod
    def _make_origin_pose() -> Pose:
        """Create a Pose at the world coordinate system origin (0,0,0) with identity orientation."""
        p = Pose()
        p.position.x = 0.0
        p.position.y = 0.0
        p.position.z = 0.0
        p.orientation.x = 0.0
        p.orientation.y = 0.0
        p.orientation.z = 0.0
        p.orientation.w = 1.0
        return p

    # ============= ACTION CLIENT =============

    def send_motion_goal(self,pose_array: PoseArray, motion_command: str, speed: float) -> ExecutePoseArray.Result:
        """
        Send a PoseArray goal to the robot controller and block until the action completes.
        Timeout logic uses a heartbeat approach - As long as feedback keeps arriving the action
        will never time out.
        """
        if not self.robot_motion_action_client.wait_for_server(timeout_sec=CALL_TIMEOUT_SEC):
            raise NodeExceptionRecoverable(
                f"Robot motion action server not available after {CALL_TIMEOUT_SEC} s"
            )

        self.logger.info(f"Sending motion goal with {len(pose_array.poses)} poses")

        goal_msg = ExecutePoseArray.Goal()
        goal_msg.path = PoseArray()
        goal_msg.path.poses = pose_array.poses
        goal_msg.motion_command = motion_command
        goal_msg.speed = str(speed)

        # Heartbeat timestamp – updated on every feedback message
        self._last_motion_heartbeat = time.monotonic()

        send_goal_future = self.robot_motion_action_client.send_goal_async(
            goal_msg,
            feedback_callback=self._motion_feedback_cb,
        )

        # wait for goal acceptance 
        while not send_goal_future.done():
            if time.monotonic() - self._last_motion_heartbeat > CALL_TIMEOUT_SEC:
                raise NodeExceptionRecoverable("Timed out waiting for goal acceptance")
            time.sleep(0.05)

        goal_handle: ClientGoalHandle = send_goal_future.result()
        if not goal_handle.accepted:
            raise NodeExceptionRecoverable("Motion goal was REJECTED by the action server")

        self.logger.info("Motion goal was ACCEPTED waiting for result")
        self._last_motion_heartbeat = time.monotonic()

        # wait for result (heartbeat-based timeout)
        result_future = goal_handle.get_result_async()
        while not result_future.done():
            silence = time.monotonic() - self._last_motion_heartbeat
            if silence > CALL_TIMEOUT_SEC:
                self.logger.warning(
                    f"No motion feedback for {silence:.1f} sec - cancelling goal"
                )
                goal_handle.cancel_goal_async()
                raise NodeExceptionRecoverable(
                    f"Motion timed out - no feedback for {CALL_TIMEOUT_SEC} sec"
                )
            time.sleep(0.05)

        wrapper = result_future.result()
        status = wrapper.status
        print(f"Motion action completed with status {status}")
        res: ExecutePoseArray.Result = wrapper.result

        if status == GoalStatus.STATUS_SUCCEEDED:
            self.logger.info(
                f"Motion SUCCEEDED - {res.message}  (executed {res.executed_count} poses)"
            )
            return res
        elif status == GoalStatus.STATUS_CANCELED:
            raise NodeExceptionRecoverable(
                f"Motion CANCELED - {res.message}  (executed {res.executed_count} poses)"
            )
        else:
            raise NodeExceptionRecoverable(
                f"Motion FAILED (status={status}) - {res.message}  (executed {res.executed_count} poses)"
            )

    def _motion_feedback_cb(self, feedback_msg):
        """Called by the action client on every feedback – refreshes heartbeat."""
        self._last_motion_heartbeat = time.monotonic()
        fb = feedback_msg.feedback
        self.logger.info(
            f"  Motion feedback: index={fb.current_index}  state=\"{fb.state}\""
        )

    def _swap_rviz_tool(self, tool_id: str):
        """Call tool controller node to attach/detach a collision gripper in RViz.
        tool_id: gripper id from tools.yaml (e.g. 'gripper_1') or 'detach'.
        """
        if not self.get_parameter(CoordinatorParametersKeys.ENABLE_RVIZ_TOOL_SWAP).value:
            return
        try:
            resp: RobotRequestSrv.Response = self.call_service_sync(
                self.tool_clients.swap_tool_cli,
                RobotRequestSrv.Request(command=tool_id),
            )
            if resp.status:
                self.logger.info(f"RViz tool swap OK: {resp.message}")
            else:
                self.logger.warning(f"RViz tool swap failed: {resp.message}")
        except Exception as e:
            self.logger.warning(f"RViz tool swap error (non-fatal): {e}")
    
    def execute_operation1_cb(self, goal_handle: ServerGoalHandle):
        """Main pipeline"""

        def wait_for_user_input():
            self.logger.info("Waiting for user input to proceed with operation...")
            while not self._user_input_received:
                if goal_handle.is_cancel_requested:
                    self._handle_cancel(goal_handle, result, "Cancelled while waiting for user input")
                    raise _CancelledError()
                time.sleep(0.1)
            self._user_input_received = False  # reset for next time
            self.logger.info("User input received, proceeding with operation")

        def wait_for_rapid_idle():
            time.sleep(1.0)  # initial delay before checking
            while True:
                if goal_handle.is_cancel_requested:
                    self._handle_cancel(goal_handle, result, "Cancelled while waiting for robot to be ready")
                    raise _CancelledError()
                robot_response: RobotRequestSrv.Response = self.call_service_sync(
                    self.robot_clients.robot_controller_request_cli,
                    RobotRequestSrv.Request(command="get_rapid_symbol",
                                            params=[RCC.Symbols.CURRENT_STATE, RCC.Modules.MAIN]
                                            ))
                if robot_response.status and robot_response.message == "0":
                    self.logger.info("Robot is in RAPID idle state, proceeding with motion execution")
                    break
                else:
                    self.logger.info("Waiting for robot to be in RAPID idle state...")
                    time.sleep(0.5)

        result = PerformOperation.Result()

        try:
            operation_name = goal_handle.request.operation_name
            self.logger.info(f"Executing operation: {operation_name}")



            # stage 1: scanning

            self._publish_feedback(goal_handle, Operation1Phases.SCANNING, 0.05,
                                   "Triggering scan acquisition...")

            scan_response: ScanAcquisitionSrv.Response = self.call_service_sync(
                self.camera_clients.camera_controller_capture_cli,
                ScanAcquisitionSrv.Request(),
                timeout_sec=CALL_TIMEOUT_SEC
            )

            if not scan_response.status:
                raise NodeExceptionRecoverable(f"Scan acquisition failed: {scan_response.message}")

            self._publish_feedback(goal_handle, Operation1Phases.SCANNING, 0.20,
                                   f"Scan captured: {scan_response.file_path}")

            # Check for cancellation
            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled after scanning")
            
            time.sleep(3.0)

            # stage 2: vision processing
            self._publish_feedback(goal_handle, Operation1Phases.VISION_PROCESSING, 0.25,
                                   "Starting vision processing (segmentation + grasp estimation)...")

            vision_request = ProcessVisionSrv.Request()
            vision_response: ProcessVisionSrv.Response = self.call_service_sync(
                self.vision_clients.vision_processing_op1_cli,
                vision_request,
                timeout_sec=CALL_TIMEOUT_SEC*2
            )

            if not vision_response.status:
                raise NodeExceptionRecoverable(f"Vision processing failed: {vision_response.message}")

            # Publish vision results as feedback (images + point clouds + grasps)
            self._publish_feedback(
                goal_handle, Operation1Phases.VISION_PROCESSING, 0.35,
                "Vision processing complete segmentation masks ready",
                images=[
                    vision_response.img_masks_all,
                    vision_response.img_hexagon,
                    vision_response.img_circle,
                    vision_response.img_background,
                    vision_response.img_drawn_rectangle,
                ],
                image_labels=["overlay", "mask_hexagon", "mask_circle", "background"],
                point_clouds=[
                    vision_response.inlier_pcd_hexagon,
                    vision_response.inlier_pcd_background,
                    vision_response.inlier_pcd_circle,
                    vision_response.inlier_pcd_drawn,
                ],
                point_cloud_labels=["inlier_hexagon", "inlier_background", "inlier_circle", "inlier_drawn"],
                plane_data=(
                    list(vision_response.plane_model_hexagon)
                    + list(vision_response.plane_model_background)
                    + list(vision_response.plane_model_circle)
                    + list(vision_response.plane_model_drawn)
                ),
                plane_labels=["hexagon", "background", "circle", "drawn_rectangle"],
            )

            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled after vision processing")

            # stage 3: motion execution
            self.logger.info("First pose array from vision results:" + str(vision_response.zigzag_poses.poses[:3]) + " ...")

            self._publish_feedback(
                goal_handle, Operation1Phases.GRASP_READY, 0.40,
                "Grasp poses estimated",
                grasp_results=[
                    vision_response.grasp_hexagon,
                    vision_response.grasp_circle,
                    vision_response.pose_rectangle
                ],
                pose_arrays=[vision_response.zigzag_poses],
                pose_array_labels=["zigzag"],
                poses = vision_response.cone_poses,
                pose_labels = ["cone_pose1", "cone_pose2", "cone_pose3", "cone_pose4"]
            )
            time.sleep(5.0)

            wait_for_user_input()

            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled before motion execution")
            

            self._publish_feedback(goal_handle, Operation1Phases.EXECUTING_MOTION, 0.45,
                                   "Executing motion plan on robot controller")
            
            # motion pipeline starts here
            self.logger.info("Calling controller_request service to prepare robot …")

            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="make_robot_ready", params=[]))
            
            self.logger.info(f"Controller request response: status={robot_response.status}  message='{robot_response.message}'  status_code={robot_response.status_code}")

            # take tool1
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["take_tool1"]
                                        ))
            self._swap_rviz_tool(ToolControllerConstants.ToolNames.TOOL_1)

            wait_for_rapid_idle()

            zigzag_init_pose: Pose = copy.deepcopy(vision_response.zigzag_poses.poses[0])
            zigzag_init_pose.position.z += 150.0

            robtarget = RWSInterface.pose_to_robtarget(zigzag_init_pose)

            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_move_command",
                                        params=[RCC.MotionCommands.MOVE_J, robtarget, "150"]
                                        ))
            
            wait_for_rapid_idle()
            #perfrom dipc action to execute motion – this will block until motion is complete and return the result
            motion_result: ExecutePoseArray.Result = self.send_motion_goal(vision_response.zigzag_poses, motion_command=RCC.MotionCommands.MOVE_L, speed=50.0)
            print(f"Motion result: status={motion_result.success}  message='{motion_result.message}'  executed_count={motion_result.executed_count}")
            

            wait_for_rapid_idle()


            zigzag_last_pose: Pose = copy.deepcopy(vision_response.zigzag_poses.poses[-1])
            zigzag_last_pose.position.z += 150.0

            robtarget = RWSInterface.pose_to_robtarget(zigzag_last_pose)

            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_move_command",
                                        params=[RCC.MotionCommands.MOVE_J, robtarget, "150"]
                                        ))
            
            
            
            cur_height = (vision_response.grasp_hexagon.obj_height*1.05)
            hex_robt =  RWSInterface.pose_to_robtarget(vision_response.grasp_hexagon.grasp_pose)
            release_pose = vh.offset_pose_by_vector(vision_response.pose_rectangle.grasp_pose, [0, 0, -cur_height])
            release_robt = RWSInterface.pose_to_robtarget(release_pose)

            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="set_rapid_symbol_raw",
                                        params=[hex_robt, "grasp_pose", RCC.Modules.USER]
                                        ))
            
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="set_rapid_symbol_raw",
                                        params=[release_robt, "release_pose", RCC.Modules.USER]
                                        ))
            

            wait_for_rapid_idle()

            # dock tool1
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["dock_tool1"]
                                        ))
            self._swap_rviz_tool(ToolControllerConstants.ToolNames.DETACH)

            wait_for_rapid_idle()

            # take tool2
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["take_tool2"]
                                        ))
            self._swap_rviz_tool(ToolControllerConstants.ToolNames.TOOL_2)

            wait_for_rapid_idle()
            
            # grasp with tool2
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["perform_pick_place"]
                                        ))
            
            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled during motion execution")
            
            self._publish_feedback(goal_handle, Operation1Phases.EXECUTING_MOTION, 0.60,"Grasping hexagon with tool2 …")
        
            cur_height +=  (vision_response.grasp_circle.obj_height*1.05)
            circ_robt = RWSInterface.pose_to_robtarget(vision_response.grasp_circle.grasp_pose)
            release_pose = vh.offset_pose_by_vector(vision_response.pose_rectangle.grasp_pose, [0, 0, -cur_height])

            release_robt = RWSInterface.pose_to_robtarget(release_pose)

            cone_robtargets = RWSInterface.pose_list_to_robtargets(vision_response.cone_poses)

            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="set_rapid_symbol_raw",
                                        params=[cone_robtargets, "circle_poses", RCC.Modules.USER]
                                        ))



            wait_for_rapid_idle()


            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="set_rapid_symbol_raw",
                                        params=[circ_robt, "grasp_pose", RCC.Modules.USER]
                                        ))
            
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="set_rapid_symbol_raw",
                                        params=[release_robt, "release_pose", RCC.Modules.USER]
                                        ))
            
            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled during motion execution")
            
            time.sleep(1.0)
            # grasp circle with tool2
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["perform_pick_place"]
                                        ))

            
            self._publish_feedback(goal_handle, Operation1Phases.EXECUTING_MOTION, 0.70,"Grasping circle with tool2 …")
            wait_for_rapid_idle()


            # dock tool2
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["dock_tool2"]
                                        ))
            self._swap_rviz_tool(ToolControllerConstants.ToolNames.DETACH)

            wait_for_rapid_idle()


            # take tool3
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["take_tool3"]
                                        ))
            self._swap_rviz_tool(ToolControllerConstants.ToolNames.TOOL_3)

            wait_for_rapid_idle()


            # run circular motion with tool3
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=[RCC.Routines.SINGLE_MOVE_C]
                                        ))

            wait_for_rapid_idle()
            # dock tool3
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["dock_tool3"]
                                        ))
            self._swap_rviz_tool(ToolControllerConstants.ToolNames.DETACH)

            wait_for_rapid_idle()

            robpose = Pose()
            robpose.position.x = 1040.0
            robpose.position.y = 470.0
            robpose.position.z = 600.0

            robpose.orientation.x = 0.0
            robpose.orientation.y = 1.0
            robpose.orientation.z = 0.0
            robpose.orientation.w = 0.0


            robtarget = RWSInterface.pose_to_robtarget(robpose)

            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_move_command",
                                        params=[RCC.MotionCommands.MOVE_J, robtarget, "200"]
                                        ))
            wait_for_rapid_idle()


            self._publish_feedback(goal_handle, Operation1Phases.COMPLETED, 1.0,
                                   "Operation completed successfully")

            goal_handle.succeed()
            result.success = True
            result.message = "Operation completed successfully"

            with self.sm_lock:
                self.lifecycle_sm.complete(message=result.message)

            return result

        except _CancelledError:
            return result  # result already set by _handle_cancel

        except NodeExceptionRecoverable as e:
            self.logger.error(f"Recoverable error during operation: {e}")
            goal_handle.abort()
            result.success = False
            result.message = str(e)
            with self.sm_lock:
                self.lifecycle_sm.fail_recoverable(message=str(e))
            return result

        except Exception as e:
            self.logger.error(f"Unexpected error during operation: {e}")
            goal_handle.abort()
            result.success = False
            result.message = str(e)
            with self.sm_lock:
                self.lifecycle_sm.fail_non_recoverable(message=str(e))
            return result

    def execute_operation2_cb(self, goal_handle: ServerGoalHandle):
        """Operation 2 pipeline"""

        def wait_for_user_input():
            self.logger.info("Waiting for user input to proceed with operation...")
            while not self._user_input_received:
                if goal_handle.is_cancel_requested:
                    self._handle_cancel(goal_handle, result, "Cancelled while waiting for user input")
                    raise _CancelledError()
                time.sleep(0.1)
            self._user_input_received = False  # reset for next time
            self.logger.info("User input received, proceeding with operation")

        def wait_for_rapid_idle():
            time.sleep(1.0)  # initial delay before checking
            while True:
                if goal_handle.is_cancel_requested:
                    self._handle_cancel(goal_handle, result, "Cancelled while waiting for robot to be ready")
                    raise _CancelledError()
                robot_response: RobotRequestSrv.Response = self.call_service_sync(
                    self.robot_clients.robot_controller_request_cli,
                    RobotRequestSrv.Request(command="get_rapid_symbol",
                                            params=[RCC.Symbols.CURRENT_STATE, RCC.Modules.MAIN]
                                            ))
                if robot_response.status and robot_response.message == "0":
                    self.logger.info("Robot is in RAPID idle state, proceeding with motion execution")
                    break
                else:
                    self.logger.info("Waiting for robot to be in RAPID idle state...")
                    time.sleep(0.5)

        result = PerformOperation.Result()

        try:
            operation_name = goal_handle.request.operation_name
            self.logger.info(f"Executing operation 2: {operation_name}")

            # stage 1 - scanning
            self._publish_feedback(goal_handle, Operation2Phases.SCANNING, 0.05,
                                   "Triggering scan acquisition...")

            scan_response: ScanAcquisitionSrv.Response = self.call_service_sync(
                self.camera_clients.camera_controller_capture_cli,
                ScanAcquisitionSrv.Request(),
                timeout_sec=CALL_TIMEOUT_SEC
            )

            if not scan_response.status:
                raise NodeExceptionRecoverable(f"Scan acquisition failed: {scan_response.message}")

            self._publish_feedback(goal_handle, Operation2Phases.SCANNING, 0.20,
                                   f"Scan captured: {scan_response.file_path}")

            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled after scanning")
            time.sleep(3.0)

            # stage 2 - vision processing
            self._publish_feedback(goal_handle, Operation2Phases.VISION_PROCESSING, 0.25,
                                   "Starting vision processing for operation 2...")

            vision_response: ProcessVisionSrv2.Response = self.call_service_sync(
                self.vision_clients.vision_processing_op2_cli,
                ProcessVisionSrv2.Request(),
                timeout_sec=CALL_TIMEOUT_SEC * 2
            )

            if not vision_response.status:
                raise NodeExceptionRecoverable(f"Vision processing failed: {vision_response.message}")

            self._publish_feedback(
                goal_handle, Operation2Phases.VISION_PROCESSING, 0.40,
                f"Pose estimation complete (fitness={vision_response.fitness:.4f}, rmse={vision_response.rmse:.4f})",
                images=[vision_response.bg_mask_image],
                image_labels=["bg_mask"],
                point_clouds=[
                    vision_response.cad_pcd,
                    vision_response.scene_pcd,
                    vision_response.aligned_cad_pcd,
                ],
                point_cloud_labels=["cad_pcd", "scene_pcd", "aligned_cad_pcd"],
                poses=[vision_response.estimated_pose, self._make_origin_pose()],
                pose_labels=["estimated_pose", "world_origin"],
            )

            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled after vision processing")

            # stage 3: wait for user confirmation before motion execution
            self._publish_feedback(
                goal_handle, Operation2Phases.POSE_READY, 0.45,
                f"Pose estimation ready (fitness={vision_response.fitness:.4f}, RMSE={vision_response.rmse:.4f}), waiting for user confirmation...",
            )

            wait_for_user_input()

            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled before motion execution")

            # stage 4: motion execution
            self._publish_feedback(goal_handle, Operation2Phases.EXECUTING_MOTION, 0.50, "Executing motion plan on robot controller")

            self.logger.info("Calling controller_request service to prepare robot …")

            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="make_robot_ready", params=[]))

            self.logger.info(f"Controller request response: status={robot_response.status}  message='{robot_response.message}'")

            wait_for_rapid_idle()

            estimated_robtarget = RWSInterface.pose_to_robtarget(vision_response.estimated_pose)

            # Set estimated pose as target
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="set_rapid_symbol_raw",
                                        params=[estimated_robtarget, "weld_pseudowobj_robtarget", RCC.Modules.USER]
                                        ))
            
            self._publish_feedback(goal_handle, Operation2Phases.EXECUTING_MOTION, 0.60,
                                   "Taking tool 3")
            
            # take tool3
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["take_tool3"]
                                        ))
            self._swap_rviz_tool(ToolControllerConstants.ToolNames.TOOL_3)

            wait_for_rapid_idle()

            # run weld routine with tool3
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", params=["weld_routine"]))
            
            self._publish_feedback(goal_handle, Operation2Phases.EXECUTING_MOTION, 0.70,
                                   "Running weld routine with tool 3")
            
            wait_for_rapid_idle()

            #dock tool3
            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_rapid_routine", 
                                        params=["dock_tool3"]
                                        ))
            self._swap_rviz_tool(ToolControllerConstants.ToolNames.DETACH)

            self._publish_feedback(goal_handle, Operation2Phases.EXECUTING_MOTION, 0.80,
                                   "Docking tool 3")

            wait_for_rapid_idle()

            #go home
            self._publish_feedback(goal_handle, Operation2Phases.EXECUTING_MOTION, 0.90,
                                   "Going home")

            robpose = Pose()
            robpose.position.x = 1040.0
            robpose.position.y = 470.0
            robpose.position.z = 600.0

            robpose.orientation.x = 0.0
            robpose.orientation.y = 1.0
            robpose.orientation.z = 0.0
            robpose.orientation.w = 0.0


            robtarget = RWSInterface.pose_to_robtarget(robpose)

            robot_response: RobotRequestSrv.Response = self.call_service_sync(
                self.robot_clients.robot_controller_request_cli,
                RobotRequestSrv.Request(command="run_move_command",
                                        params=[RCC.MotionCommands.MOVE_J, robtarget, "200"]
                                        ))
            
            wait_for_rapid_idle()

            if goal_handle.is_cancel_requested:
                return self._handle_cancel(goal_handle, result, "Cancelled during motion execution")


            # complete
            self._publish_feedback(goal_handle, Operation2Phases.COMPLETED, 1.0,
                                   "Operation 2 completed successfully")

            goal_handle.succeed()
            result.success = True
            result.message = "Operation 2 completed successfully"

            with self.sm_lock:
                self.lifecycle_sm.complete(message=result.message)

            return result

        except _CancelledError:
            return result  # result already set by _handle_cancel

        except NodeExceptionRecoverable as e:
            self.logger.error(f"Recoverable error during operation 2: {e}")
            goal_handle.abort()
            result.success = False
            result.message = str(e)
            with self.sm_lock:
                self.lifecycle_sm.fail_recoverable(message=str(e))
            return result

        except Exception as e:
            self.logger.error(f"Unexpected error during operation 2: {e}")
            goal_handle.abort()
            result.success = False
            result.message = str(e)
            with self.sm_lock:
                self.lifecycle_sm.fail_non_recoverable(message=str(e))
            return result

    def apply_parameters(self):
        """Apply parameters to hardware"""
        pass

    def cleanup_resources(self):
        """Cleanup resources"""
        pass

    def initialize_node(self):
        pass


def main(args=None):
    """Main entry point for node"""

    rclpy.init(args=args)
    executor = MultiThreadedExecutor(num_threads=3)
    coordinator_node = None

    try:
        coordinator_node = CoordinatorNode()
        executor.add_node(coordinator_node)
        executor.spin()
    except KeyboardInterrupt:
        if coordinator_node:
            coordinator_node.logger.info('Keyboard interrupt received, shutting down')
        else:
            print('Shutdown signal received during initialization')
            
    except Exception as e:
        # Handle unexpected errors
        if coordinator_node:
            coordinator_node.logger.error(f'Unexpected error: {e}')
        else:
            print(f'Error during node initialization: {e}')
            
    finally:
        # Always cleanup resources
        if coordinator_node:
            coordinator_node.cleanup_resources()
            coordinator_node.destroy_node()
        executor.shutdown()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
