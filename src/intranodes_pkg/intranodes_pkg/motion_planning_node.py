"""Motion Planning Node.
"""

from __future__ import annotations

import json
import math

import rclpy
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState

import tf2_ros
from geometry_msgs.msg import Pose, PoseStamped, TransformStamped
from moveit_msgs.msg import (
    CollisionObject,
    Constraints,
    JointConstraint,
    OrientationConstraint,
    PlanningScene as PlanningSceneMsg,
    PlanningSceneComponents,
    PositionConstraint,
    RobotState,
    RobotTrajectory,
)
from moveit_msgs.srv import GetCartesianPath, GetMotionPlan, GetPlanningScene, GetPositionIK
from shape_msgs.msg import SolidPrimitive

from core_pkg.nodes_core import INTRANode, handle_operation_errors
from core_pkg.systemconstants import MotionPlanningConstants
from core_pkg.exceptions import NodeExceptionRecoverable, NodeExceptionNonRecoverable
from intranodes_pkg.parameters.motion_planning_parameters import (
    MotionPlanningParameters,
    MotionPlanningParametersKeys,
)
from interface_pkg.srv import PlanMotionSrv, TriggerServiceSrv


class MotionPlanningNode(INTRANode):
    """INTRANode wrapper around MoveIt move_group planning services."""

    def __init__(self):
        super().__init__(MotionPlanningConstants.NODE_NAME)

        self.default_ros_params = MotionPlanningParameters().to_ros_params()
        declared_params = self.declare_parameters(namespace='', parameters=self.default_ros_params)
        self.logger.info(f"Declared {len(declared_params)} parameters")

        # MoveIt service clients (calls to move_group node)
        self._plan_client = self.create_client(
            GetMotionPlan,
            MotionPlanningConstants.MoveGroupServiceNames.PLAN_KINEMATIC_PATH,
            callback_group=self.cb_group,
        )
        self._cartesian_client = self.create_client(
            GetCartesianPath,
            MotionPlanningConstants.MoveGroupServiceNames.COMPUTE_CARTESIAN_PATH,
            callback_group=self.cb_group,
        )
        self._get_scene_client = self.create_client(
            GetPlanningScene,
            MotionPlanningConstants.MoveGroupServiceNames.GET_PLANNING_SCENE,
            callback_group=self.cb_group,
        )
        self._ik_client = self.create_client(
            GetPositionIK,
            MotionPlanningConstants.MoveGroupServiceNames.COMPUTE_IK,
            callback_group=self.cb_group,
        )

        self._fake_obstacles_active = False
        self._scene_pub = self.create_publisher(PlanningSceneMsg, '/planning_scene', 10)

        self._latest_joint_state: JointState | None = None
        self.create_subscription(
            JointState,
            MotionPlanningConstants.TopicNames.JOINT_STATES,
            self._joint_state_cb,
            10,
            callback_group=self.cb_group,
        )


        self._tf_broadcaster = tf2_ros.StaticTransformBroadcaster(self)

        self._plan_service = self.create_service(
            PlanMotionSrv,
            f"{MotionPlanningConstants.NODE_NAME}/{MotionPlanningConstants.ServiceNames.PLAN_MOTION}",
            self.plan_motion_cb,
            callback_group=self.cb_group,
        )
        self.create_service(
            TriggerServiceSrv,
            f"{MotionPlanningConstants.NODE_NAME}/{MotionPlanningConstants.ServiceNames.TOGGLE_FAKE_OBSTACLES}",
            self._toggle_fake_obstacles_cb,
            callback_group=self.cb_group,
        )

        with self.sm_lock:
            self.lifecycle_sm.boot_complete(
                message=f"Boot of {self.NODE_NAME} complete, waiting for initialization"
            )

    def initialize_node(self):
        """Verify that MoveIt move_group services are reachable."""
        self.logger.info("Waiting for MoveIt move_group services...")

        if not self._plan_client.wait_for_service(timeout_sec=10.0):
            raise NodeExceptionNonRecoverable(
                f"MoveIt service {MotionPlanningConstants.MoveGroupServiceNames.PLAN_KINEMATIC_PATH} not available"
            )
        if not self._cartesian_client.wait_for_service(timeout_sec=10.0):
            raise NodeExceptionNonRecoverable(
                f"MoveIt service {MotionPlanningConstants.MoveGroupServiceNames.COMPUTE_CARTESIAN_PATH} not available"
            )
        if not self._get_scene_client.wait_for_service(timeout_sec=10.0):
            raise NodeExceptionNonRecoverable(
                f"MoveIt service {MotionPlanningConstants.MoveGroupServiceNames.GET_PLANNING_SCENE} not available"
            )
        if not self._ik_client.wait_for_service(timeout_sec=10.0):
            raise NodeExceptionNonRecoverable(
                f"MoveIt service {MotionPlanningConstants.MoveGroupServiceNames.COMPUTE_IK} not available"
            )
        self.logger.info("MoveIt move_group services available — node ready.")

    def apply_parameters(self):
        """Parameters are read from the ROS2 parameter server on each planning call."""
        pass

    def cleanup_resources(self):
        self._latest_joint_state = None

    def _publish_target_tf(self, pose: Pose) -> None:
        """Publish the planning goal pose as a TF frame so it's visible in RViz."""
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = MotionPlanningConstants.MoveItConfig.PLANNING_FRAME
        t.child_frame_id = "motion_planning_target"
        t.transform.translation.x = pose.position.x
        t.transform.translation.y = pose.position.y
        t.transform.translation.z = pose.position.z
        t.transform.rotation = pose.orientation
        self._tf_broadcaster.sendTransform(t)

    def _joint_state_cb(self, msg: JointState):
        self._latest_joint_state = msg

    def _get_attached_bodies(self) -> list:
        """
        Query move_group for currently attached collision objects.
        """
        req = GetPlanningScene.Request()
        req.components.components = (
            PlanningSceneComponents.ROBOT_STATE
            | PlanningSceneComponents.ROBOT_STATE_ATTACHED_OBJECTS
        )
        try:
            result = self.call_service_sync(self._get_scene_client, req, timeout_sec=2.0)
            bodies = list(result.scene.robot_state.attached_collision_objects)
            if bodies:
                self.logger.debug(f"Attached bodies for planning: {[b.object.id for b in bodies]}")
            return bodies
        except Exception as e:
            self.logger.warning(f"Could not fetch attached bodies from planning scene: {e}")
            return []

    def _current_robot_state(self) -> RobotState:
        rs = RobotState()
        rs.is_diff = True
        if self._latest_joint_state is not None:
            rs.joint_state = self._latest_joint_state
        attached = self._get_attached_bodies()
        if attached:
            rs.attached_collision_objects = attached
        return rs

    def _solve_ik(self, goal_pose: Pose) -> list[float] | None:
        """Solve IK for a Cartesian goal pose. Returns joint positions or None on failure."""
        req = GetPositionIK.Request()
        ik_req = req.ik_request
        ik_req.group_name = MotionPlanningConstants.MoveItConfig.PLANNING_GROUP
        ik_req.ik_link_name = MotionPlanningConstants.MoveItConfig.EE_LINK
        ik_req.robot_state = self._current_robot_state()
        ik_req.avoid_collisions = True
        ps = PoseStamped()
        ps.header.frame_id = MotionPlanningConstants.MoveItConfig.PLANNING_FRAME
        ps.header.stamp = self.get_clock().now().to_msg()
        ps.pose = goal_pose
        ik_req.pose_stamped = ps
        ik_req.timeout.sec = 5
        try:
            result = self.call_service_sync(self._ik_client, req, timeout_sec=10.0)
            if result.error_code.val != 1:  # MoveItErrorCodes.SUCCESS
                self.logger.warning(f"IK failed with error code {result.error_code.val}")
                return None
            js = result.solution.joint_state
            joint_map = dict(zip(js.name, js.position))
            positions = [
                joint_map[name]
                for name in MotionPlanningConstants.MoveItConfig.JOINT_NAMES
                if name in joint_map
            ]
            if len(positions) != len(MotionPlanningConstants.MoveItConfig.JOINT_NAMES):
                self.logger.warning("IK solution missing some joints")
                return None
            return positions
        except Exception as e:
            self.logger.warning(f"IK service call failed: {e}")
            return None


    _FAKE_OBSTACLE_DEFS = [
        {'id': 'fake_box_1', 'frame_id': 'table', 'dimensions': [0.05, 0.5, 0.5], 'position': [0.0, 0.0, 0.0]},
        {'id': 'fake_box_2', 'frame_id': 'table', 'dimensions': [0.05, 0.5, 0.25], 'position': [0.5, 0.0, 0.0]},
        {'id': 'fake_box_3', 'frame_id': 'table', 'dimensions': [0.05, 0.5, 0.5], 'position': [0.9,  0.0, 0.0]},
    ]

    def _toggle_fake_obstacles_cb(self, request, response: TriggerServiceSrv.Response):
        try:
            scene = PlanningSceneMsg()
            scene.is_diff = True
            if self._fake_obstacles_active:
                for ob in self._FAKE_OBSTACLE_DEFS:
                    co = CollisionObject()
                    co.header.frame_id = ob['frame_id']
                    co.id = ob['id']
                    co.operation = CollisionObject.REMOVE
                    scene.world.collision_objects.append(co)
                self._scene_pub.publish(scene)
                self._fake_obstacles_active = False
                response.status = True
                response.message = f'Removed {len(self._FAKE_OBSTACLE_DEFS)} fake obstacles'
            else:
                for ob in self._FAKE_OBSTACLE_DEFS:
                    co = self._make_box(
                        obj_id=ob['id'],
                        frame_id=ob['frame_id'],
                        dimensions=ob['dimensions'],
                        position=ob['position'],
                        anchor=('min', 'min', 'min'),
                    )
                    scene.world.collision_objects.append(co)
                self._scene_pub.publish(scene)
                self._fake_obstacles_active = True
                response.status = True
                response.message = f'Spawned {len(self._FAKE_OBSTACLE_DEFS)} fake obstacles'
            self.logger.info(response.message)
        except Exception as e:
            response.status = False
            response.message = f'Failed to toggle fake obstacles: {e}'
            self.logger.error(response.message)
        return response

    @handle_operation_errors
    def plan_motion_cb(self, request: PlanMotionSrv.Request, response: PlanMotionSrv.Response):
        """Plan a collision-free path to the requested goal pose.
        
        planning_mode:
          ``joint_space`` — free joint-space path via GetMotionPlan
          ``cartesian``   — straight Cartesian line via GetCartesianPath
        """
        with self.sm_lock:
            self.lifecycle_sm.start_operation(message="Planning motion path")

        self._publish_target_tf(request.goal_pose)
        mode = request.planning_mode.strip().lower()

        if mode == MotionPlanningConstants.PlanningMode.JOINT_SPACE:
            waypoints = self._plan_joint_space(request.goal_pose)
        elif mode == MotionPlanningConstants.PlanningMode.CARTESIAN:
            waypoints = self._plan_cartesian(request.goal_pose)
        else:
            raise NodeExceptionRecoverable(
                f"Unknown planning_mode '{mode}'. "
                f"Use '{MotionPlanningConstants.PlanningMode.JOINT_SPACE}' "
                f"or '{MotionPlanningConstants.PlanningMode.CARTESIAN}'."
            )

        if waypoints is None:
            response.status = False
            response.message = f"No path found for mode '{mode}'"
            self.logger.warning(response.message)
            with self.sm_lock:
                self.lifecycle_sm.complete(message=response.message)
            return

        response.status = True
        response.message = f"Planned {len(waypoints)} waypoints ({mode})"
        response.waypoints_json = json.dumps(waypoints)
        self.logger.info(response.message)

        with self.sm_lock:
            self.lifecycle_sm.complete(message=response.message)


    def _plan_joint_space(self, goal_pose: Pose) -> list[list[float]]:
        """Free joint-space path to a Cartesian goal pose (collision-aware)."""
        pos_tol = self.get_parameter(MotionPlanningParametersKeys.POSITION_TOLERANCE).value
        ori_tol = self.get_parameter(MotionPlanningParametersKeys.ORIENTATION_TOLERANCE).value

        req = GetMotionPlan.Request()
        mpr = req.motion_plan_request
        planner_id = self.get_parameter(MotionPlanningParametersKeys.PLANNER_ID).value
        pipeline_id = MotionPlanningConstants.Planners.PIPELINE_MAP.get(
            planner_id, MotionPlanningConstants.Planners.Pipelines.OMPL
        )
        mpr.group_name = MotionPlanningConstants.MoveItConfig.PLANNING_GROUP
        mpr.pipeline_id = pipeline_id
        mpr.planner_id = planner_id if pipeline_id == MotionPlanningConstants.Planners.Pipelines.OMPL else ""
        mpr.num_planning_attempts = self.get_parameter(MotionPlanningParametersKeys.NUM_PLANNING_ATTEMPTS).value
        mpr.allowed_planning_time = self.get_parameter(MotionPlanningParametersKeys.ALLOWED_PLANNING_TIME).value
        mpr.max_velocity_scaling_factor = self.get_parameter(MotionPlanningParametersKeys.VELOCITY_SCALING).value
        mpr.max_acceleration_scaling_factor = self.get_parameter(MotionPlanningParametersKeys.ACCELERATION_SCALING).value
        mpr.start_state = self._current_robot_state()

        self.logger.info(
            f"[MP] Planning request:"
            f"\n  pipeline={pipeline_id}  planner={planner_id}"
            f"\n  num_planning_attempts={mpr.num_planning_attempts}"
            f"\n  allowed_planning_time={mpr.allowed_planning_time}s"
            f"\n  vel_scale={mpr.max_velocity_scaling_factor}  acc_scale={mpr.max_acceleration_scaling_factor}"
            f"\n  group={mpr.group_name}  ee_link={MotionPlanningConstants.MoveItConfig.EE_LINK}"
            f"\n  start_state.is_diff={mpr.start_state.is_diff}"
            f"\n  start_state joints={list(zip(mpr.start_state.joint_state.name, [round(p,4) for p in mpr.start_state.joint_state.position]))}"
            f"\n  goal=[{goal_pose.position.x:.4f}, {goal_pose.position.y:.4f}, {goal_pose.position.z:.4f}]"
            f"  q=[{goal_pose.orientation.x:.4f}, {goal_pose.orientation.y:.4f}, {goal_pose.orientation.z:.4f}, {goal_pose.orientation.w:.4f}]"
        )

        gc = Constraints()
        if pipeline_id != MotionPlanningConstants.Planners.Pipelines.OMPL:
            # Non-OMPL planners (e.g. CHOMP) require joint-space goals — solve IK first
            joint_positions = self._solve_ik(goal_pose)
            if joint_positions is None:
                self.logger.warning(f"IK failed — cannot build joint goal for pipeline '{pipeline_id}'")
                return None
            for name, pos in zip(MotionPlanningConstants.MoveItConfig.JOINT_NAMES, joint_positions):
                jc = JointConstraint()
                jc.joint_name = name
                jc.position = pos
                jc.tolerance_above = ori_tol
                jc.tolerance_below = ori_tol
                jc.weight = 1.0
                gc.joint_constraints.append(jc)
        else:
            pc = PositionConstraint()
            pc.header.frame_id = MotionPlanningConstants.MoveItConfig.PLANNING_FRAME
            pc.link_name = MotionPlanningConstants.MoveItConfig.EE_LINK
            pc.target_point_offset.x = 0.0
            pc.target_point_offset.y = 0.0
            pc.target_point_offset.z = 0.0
            region = SolidPrimitive()
            region.type = SolidPrimitive.SPHERE
            region.dimensions = [pos_tol]
            pc.constraint_region.primitives.append(region)
            region_pose = Pose()
            region_pose.position = goal_pose.position
            region_pose.orientation.w = 1.0
            pc.constraint_region.primitive_poses.append(region_pose)
            pc.weight = 1.0
            gc.position_constraints.append(pc)

            oc = OrientationConstraint()
            oc.header.frame_id = MotionPlanningConstants.MoveItConfig.PLANNING_FRAME
            oc.link_name = MotionPlanningConstants.MoveItConfig.EE_LINK
            oc.orientation = goal_pose.orientation
            oc.absolute_x_axis_tolerance = ori_tol
            oc.absolute_y_axis_tolerance = ori_tol
            oc.absolute_z_axis_tolerance = ori_tol
            oc.weight = 1.0
            gc.orientation_constraints.append(oc)

        mpr.goal_constraints.append(gc)

        result = self.call_service_sync(self._plan_client, req, timeout_sec=30.0)
        resp = result.motion_plan_response

        traj_pts = len(resp.trajectory.joint_trajectory.points)
        traj_joints = resp.trajectory.joint_trajectory.joint_names
        self.logger.info(
            f"[MP] Planning response:"
            f"\n  error_code={resp.error_code.val}"
            f"\n  planning_time={resp.planning_time:.3f}s  (allowed={mpr.allowed_planning_time}s)"
            f"\n  trajectory_points={traj_pts}"
            f"\n  trajectory_joints={traj_joints}"
        )

        if resp.error_code.val != 1:  # MoveItErrorCodes.SUCCESS == 1
            self.logger.warning(
                f"[MP] Planning FAILED — error_code={resp.error_code.val} "
                f"planning_time={resp.planning_time:.3f}s "
                f"(time_used/allowed: {resp.planning_time:.3f}/{mpr.allowed_planning_time}s)"
            )
            return None

        waypoints = self._extract_waypoints(resp.trajectory)
        self.logger.info(f"[MP] Planning SUCCESS — {resp.planning_time:.3f}s — {len(waypoints)} waypoints")
        return waypoints

    def _plan_cartesian(self, goal_pose: Pose) -> list[list[float]]:
        """Straight Cartesian line to a goal pose."""
        req = GetCartesianPath.Request()
        req.header.frame_id = MotionPlanningConstants.MoveItConfig.PLANNING_FRAME
        req.group_name = MotionPlanningConstants.MoveItConfig.PLANNING_GROUP
        req.link_name = MotionPlanningConstants.MoveItConfig.EE_LINK
        req.max_step = self.get_parameter(MotionPlanningParametersKeys.CARTESIAN_MAX_STEP).value
        req.jump_threshold = self.get_parameter(MotionPlanningParametersKeys.CARTESIAN_JUMP_THRESHOLD).value
        req.avoid_collisions = self.get_parameter(MotionPlanningParametersKeys.CARTESIAN_AVOID_COLLISIONS).value
        req.start_state = self._current_robot_state()
        req.waypoints.append(goal_pose)

        result = self.call_service_sync(self._cartesian_client, req, timeout_sec=30.0)

        min_fraction = self.get_parameter(MotionPlanningParametersKeys.CARTESIAN_MIN_FRACTION).value
        if result.fraction < min_fraction:
            self.logger.warning(
                f"Cartesian path achieved only {result.fraction * 100:.1f}% "
                f"(minimum required: {min_fraction * 100:.1f}%)"
            )
            return None

        return self._extract_waypoints(result.solution)

    @staticmethod
    def _extract_waypoints(traj: RobotTrajectory) -> list[list[float]]:
        """Convert a RobotTrajectory to a list of joint-position waypoints in degrees."""
        return [
            [round(math.degrees(r), 4) for r in pt.positions]
            for pt in traj.joint_trajectory.points
        ]
    
    
    # ------------------------------------------------------------------
    @staticmethod
    def _anchored(value: float, dimension: float, anchor: str) -> float:
        if anchor == 'center':
            return value
        half = dimension / 2.0
        if anchor == 'min':
            return value + half
        if anchor == 'max':
            return value - half
        raise ValueError("anchor must be one of: 'min', 'center', 'max'")

    @staticmethod
    def _make_box(obj_id: str, frame_id: str,
                  dimensions: list[float], position: list[float],
                  orientation: list[float] | None = None,
                  anchor: tuple[str, str, str] = ('center', 'center', 'center')) -> CollisionObject:
        """Helper to create a BOX CollisionObject.

        `position` is interpreted according to `anchor` per axis:
        - 'center': position is the box center (MoveIt default)
        - 'min':    position is the minimum corner on that axis
        - 'max':    position is the maximum corner on that axis

        Example: bottom-left corner (ROS: x forward, y left, z up) often maps to
        `anchor=('min','max','min')` depending on how you define "left" in your scene.
        """
        co = CollisionObject()
        co.header.frame_id = frame_id
        co.id = obj_id

        prim = SolidPrimitive()
        prim.type = SolidPrimitive.BOX
        prim.dimensions = dimensions

        pose = Pose()
        pose.position.x = MotionPlanningNode._anchored(position[0], dimensions[0], anchor[0])
        pose.position.y = MotionPlanningNode._anchored(position[1], dimensions[1], anchor[1])
        pose.position.z = MotionPlanningNode._anchored(position[2], dimensions[2], anchor[2])
        if orientation:
            pose.orientation.x = orientation[0]
            pose.orientation.y = orientation[1]
            pose.orientation.z = orientation[2]
            pose.orientation.w = orientation[3]
        else:
            pose.orientation.w = 1.0

        co.primitives.append(prim)
        co.primitive_poses.append(pose)
        co.operation = CollisionObject.ADD
        return co


def main(args=None):
    rclpy.init(args=args)
    node = None
    executor = None
    try:
        node = MotionPlanningNode()
        executor = MultiThreadedExecutor(num_threads=2)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        if node:
            node.logger.info("Keyboard interrupt received")
    except Exception as e:
        if node:
            node.logger.error(f"Unexpected error: {e}")
        else:
            print(f"Error during node initialization: {e}")
    finally:
        if executor:
            executor.shutdown(timeout_sec=5)
        if node:
            with node.sm_lock:
                try:
                    node.lifecycle_sm.shutdown(message="Node shutting down")
                except Exception:
                    pass
        if node:
            try:
                node.cleanup_resources()
            except Exception as e:
                node.logger.error(f"Error during cleanup: {e}")
        if node:
            node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
