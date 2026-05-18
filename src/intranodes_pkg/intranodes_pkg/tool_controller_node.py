import math
import os
import time
import yaml
import trimesh
import rclpy
from rclpy.executors import MultiThreadedExecutor

from geometry_msgs.msg import Pose, Point, Quaternion
from moveit_msgs.msg import (
    AttachedCollisionObject,
    CollisionObject,
    PlanningScene as PlanningSceneMsg,
)
from shape_msgs.msg import Mesh, MeshTriangle, SolidPrimitive

from core_pkg.nodes_core import INTRANode, handle_operation_errors
from core_pkg.systemconstants import ToolControllerConstants
from core_pkg.exceptions import NodeExceptionRecoverable, NodeExceptionNonRecoverable
from core_pkg.settings import TOOLS_CONFIG_YAML, TOOL_MESHES_DIR

from interface_pkg.srv import RobotRequestSrv, TriggerServiceSrv
from intranodes_pkg.parameters.tool_controller_parameters import ToolControllerParameters, ToolControllerParametersKeys


def _load_stl_mesh(stl_path: str, scale: list[float] | None = None, convex_hull: bool = True) -> Mesh:
    """Load a binary or ASCII STL file and return a shape_msgs/Mesh.

    Uses trimesh for robust STL parsing. Each STL triangle becomes a
    MeshTriangle referencing three vertices in the Mesh.vertices list.

    When convex_hull=True (default), the mesh is replaced by its convex hull.
    This is essential for collision detection. The convex hull fills in all openings.
    """

    tm = trimesh.load(stl_path, file_type='stl', force='mesh')

    if convex_hull:
        tm = tm.convex_hull

    sx, sy, sz = scale if scale else [1.0, 1.0, 1.0]

    mesh = Mesh()
    for v in tm.vertices:
        mesh.vertices.append(Point(
            x=float(v[0]) * sx,
            y=float(v[1]) * sy,
            z=float(v[2]) * sz,
        ))
    for face in tm.faces:
        tri = MeshTriangle()
        tri.vertex_indices = [int(face[0]), int(face[1]), int(face[2])]
        mesh.triangles.append(tri)

    return mesh


def _make_collision_geometry(cfg: dict, tool_id: str) -> dict:
    """YAML collision dict → dict with either 'mesh' or 'primitive' key."""
    ctype = cfg["type"]

    if ctype == "mesh":
        mesh_file = cfg.get("mesh_file")
        if not mesh_file:
            # fallback: look up default filename from constants
            mesh_file = ToolControllerConstants.TOOL_MESH_FILES.get(tool_id)
        if not mesh_file:
            raise ValueError(
                f"No mesh_file specified for tool '{tool_id}' and no default mapping found"
            )
        stl_path = os.path.join(TOOL_MESHES_DIR, mesh_file)
        if not os.path.isfile(stl_path):
            raise FileNotFoundError(f"STL file not found: {stl_path}")
        scale = cfg.get("scale", [1.0, 1.0, 1.0])
        use_convex = cfg.get("convex_hull", True)
        return {"mesh": _load_stl_mesh(stl_path, scale, convex_hull=use_convex)}

    elif ctype == "box":
        p = SolidPrimitive()
        p.type = SolidPrimitive.BOX
        p.dimensions = list(cfg["dimensions"])
        return {"primitive": p}

    elif ctype == "cylinder":
        p = SolidPrimitive()
        p.type = SolidPrimitive.CYLINDER
        p.dimensions = [float(cfg["height"]), float(cfg["radius"])]
        return {"primitive": p}

    else:
        raise ValueError(f"Unknown collision type: {ctype}")


def _pose(xyz, rpy=None) -> Pose:
    """[x,y,z] + optional [r,p,y] → Pose."""
    pose = Pose()
    pose.position = Point(x=float(xyz[0]), y=float(xyz[1]), z=float(xyz[2]))
    if rpy and any(abs(v) > 1e-9 for v in rpy):
        r, p, y = rpy
        cr, sr = math.cos(r / 2), math.sin(r / 2)
        cp, sp = math.cos(p / 2), math.sin(p / 2)
        cy, sy = math.cos(y / 2), math.sin(y / 2)
        pose.orientation = Quaternion(
            x=float(sr * cp * cy - cr * sp * sy),
            y=float(cr * sp * cy + sr * cp * sy),
            z=float(cr * cp * sy - sr * sp * cy),
            w=float(cr * cp * cy + sr * sp * sy),
        )
    else:
        pose.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    return pose


class ToolControllerNode(INTRANode):

    def __init__(self):
        super().__init__(ToolControllerConstants.NODE_NAME)

        # Initialize default parameters from config YAML
        self.default_ros_params = ToolControllerParameters().to_ros_params()

        # Declare ROS2 parameters
        declared_params = self.declare_parameters(
            namespace='',
            parameters=self.default_ros_params,
        )
        self.logger.info(f"Declared {len(declared_params)} parameters")

        self._tools: dict[str, dict] = {}
        self._active: str | None = None
        self._scene_pub = None

        # Declare services
        self.create_service(
            RobotRequestSrv,
            f"{ToolControllerConstants.NODE_NAME}/{ToolControllerConstants.ServiceNames.SWAP_TOOL}",
            self._swap_cb,
            callback_group=self.cb_group,
        )
        self.create_service(
            TriggerServiceSrv,
            f"{ToolControllerConstants.NODE_NAME}/{ToolControllerConstants.ServiceNames.RELOAD_TOOLS}",
            self._reload_tools_cb,
            callback_group=self.cb_group,
        )

        with self.sm_lock:
            self.lifecycle_sm.boot_complete(
                message=f"Boot of {self.NODE_NAME} complete, waiting for initialization"
            )


    def _load_tools(self):
        """Parse tools.yaml and build collision geometry for each tool."""
        try:
            with open(TOOLS_CONFIG_YAML) as f:
                cfg = yaml.safe_load(f)
        except FileNotFoundError as e:
            raise NodeExceptionNonRecoverable(
                f"Tools config not found: {TOOLS_CONFIG_YAML}"
            ) from e

        tools = {}
        for t in cfg["tools"]:
            col_cfg = t.get("collision_pose_in_flange", {})
            geometry = _make_collision_geometry(t["collision"], t["id"])
            tools[t["id"]] = {
                **geometry,  # either {"mesh": Mesh} or {"primitive": SolidPrimitive}
                "pose": _pose(
                    col_cfg.get("translation", [0, 0, 0]),
                    col_cfg.get("rpy", [0, 0, 0]),
                ),
            }
        return tools

    def initialize_node(self):
        """Load tools from YAML and create MoveIt scene publisher."""
        if self._scene_pub is not None:
            raise NodeExceptionRecoverable(
                "Node already initialized, cleanup before re-initialization"
            )

        self._tools = self._load_tools()
        self._active = None
        # Publish PlanningScene diffs to /planning_scene.
        # This is the standard MoveIt2 approach for updating the planning scene
        # and is more reliable than the dedicated /attached_collision_object topic
        # for registering collision geometry with the FCL collision checker.
        self._scene_pub = self.create_publisher(
            PlanningSceneMsg, "/planning_scene", 10
        )

        self.logger.info(
            f"Tools loaded: {list(self._tools)} | flange: {self.get_parameter(ToolControllerParametersKeys.FLANGE_LINK).value}"
        )

    def cleanup_resources(self):
        """Release publishers and clear tool state."""
        if self._scene_pub is not None:
            self.destroy_publisher(self._scene_pub)
            self._scene_pub = None
        self._tools = {}
        self._active = None
        self.logger.info("Tool controller resources cleaned up")

    def apply_parameters(self):
        """Re-read parameters from ROS2 parameter server."""
        self.logger.info(
            f"Parameters applied: flange_link={self.get_parameter(ToolControllerParametersKeys.FLANGE_LINK).value}, "
            f"publish_count={self.get_parameter(ToolControllerParametersKeys.PUBLISH_COUNT).value}, "
            f"publish_delay={self.get_parameter(ToolControllerParametersKeys.PUBLISH_DELAY).value}"
        )

    def _reload_tools_cb(self, request, response: TriggerServiceSrv.Response):
        """Reload tool definitions from tools.yaml (re-parse config + STL meshes)."""
        try:
            self._detach()
            self._tools = self._load_tools()
            response.status = True
            response.message = f"Tools reloaded: {list(self._tools)}"
            self.logger.info(response.message)
        except Exception as e:
            response.status = False
            response.message = f"Failed to reload tools: {e}"
            self.logger.error(response.message)
        return response


    def _publish_scene(self, scene: PlanningSceneMsg, label: str = ""):
        """Publish a PlanningScene diff on /planning_scene."""
        publish_count = self.get_parameter(ToolControllerParametersKeys.PUBLISH_COUNT).value
        publish_delay = self.get_parameter(ToolControllerParametersKeys.PUBLISH_DELAY).value
        scene.is_diff = True
        for _ in range(publish_count):
            self._scene_pub.publish(scene)
            time.sleep(publish_delay)
        if label:
            self.logger.info(f"[scene] {label} ({publish_count}x on /planning_scene)")


    def _detach(self):
        if not self._active:
            return
        tid = self._active
        flange = self.get_parameter(ToolControllerParametersKeys.FLANGE_LINK).value

        # 1) detach from robot (MoveIt moves shapes back to world)
        scene1 = PlanningSceneMsg()
        aco = AttachedCollisionObject()
        aco.link_name = flange
        aco.object.id = tid
        aco.object.operation = CollisionObject.REMOVE
        scene1.robot_state.attached_collision_objects.append(aco)
        scene1.robot_state.is_diff = True
        self._publish_scene(scene1, f"detach '{tid}' from {flange}")

        # 2) remove from world so it doesn't linger
        scene2 = PlanningSceneMsg()
        
        rm = CollisionObject()
        rm.header.frame_id = "world"
        rm.id = tid
        rm.operation = CollisionObject.REMOVE
        scene2.world.collision_objects.append(rm)
        self._publish_scene(scene2, f"remove '{tid}' from world")

        self._active = None


    def _attach(self, tid: str):
        tool = self._tools[tid]
        flange = self.get_parameter(ToolControllerParametersKeys.FLANGE_LINK).value
        scene = PlanningSceneMsg()

        # Remove from world in case it was left there from a previous session.
        rm = CollisionObject()
        rm.header.frame_id = "world"
        rm.id = tid
        rm.operation = CollisionObject.REMOVE
        scene.world.collision_objects.append(rm)

        # Build CollisionObject with geometry in the flange frame.
        co = CollisionObject()
        co.header.frame_id = flange
        co.id = tid
        co.operation = CollisionObject.ADD

        if "mesh" in tool:
            co.meshes.append(tool["mesh"])
            co.mesh_poses.append(tool["pose"])
        else:
            co.primitives.append(tool["primitive"])
            co.primitive_poses.append(tool["pose"])

        # Wrap in AttachedCollisionObject and include in the same diff so
        # MoveIt2 processes the remove + attach atomically.
        aco = AttachedCollisionObject()
        aco.link_name = flange
        aco.object = co
        aco.touch_links = [flange]
        scene.robot_state.attached_collision_objects.append(aco)
        scene.robot_state.is_diff = True

        self._publish_scene(scene, f"attach '{tid}' on {flange}")
        self._active = tid


    @handle_operation_errors
    def _swap_cb(self, req: RobotRequestSrv.Request, resp: RobotRequestSrv.Response):
        tid = req.command.strip()
        self.logger.info(f"swap_tool → '{tid}'")

        with self.sm_lock:
            self.lifecycle_sm.start_operation(message=f"Swapping tool to '{tid}'")

        if tid == ToolControllerConstants.ToolNames.DETACH:
            self._detach()
            resp.status = True
            resp.message = "Tool detached" if self._active is None else f"Detached '{self._active}'"
            with self.sm_lock:
                self.lifecycle_sm.complete(message=resp.message)
            return

        if tid not in self._tools:
            raise NodeExceptionRecoverable(
                f"Unknown tool '{tid}'. Available: {list(self._tools)}"
            )

        if tid == self._active:
            resp.status = True
            resp.message = f"'{tid}' already attached"
            with self.sm_lock:
                self.lifecycle_sm.complete(message=resp.message)
            return

        self._detach()
        time.sleep(0.3)
        self._attach(tid)

        resp.status = True
        resp.message = f"Attached '{tid}'"
        with self.sm_lock:
            self.lifecycle_sm.complete(message=resp.message)


def main(args=None):

    rclpy.init(args=args)
    node = None
    executor = None

    try:
        # Initialize the Robot Controller node
        node = ToolControllerNode()
        
        # Create multithreaded executor with 2 threads
        executor = MultiThreadedExecutor(num_threads=2)
        executor.add_node(node)
        
        # Spin the executor
        executor.spin()
        
    except KeyboardInterrupt:
        if node:
            node.logger.info("Keyboard interrupt received")
            
    except Exception as e:
        if node:
            node.logger.error(f"Unexpected error: {e}")
        else:
            print(f'Error during node initialization: {e}')
            
    finally:
        # Shutdown executor (stops spinning and waits for callbacks to finish)
        if executor:
            executor.shutdown(timeout_sec=5)
        
        # Update lifecycle state
        if node:
            with node.sm_lock:
                try:
                    node.lifecycle_sm.shutdown(
                        message="Node shutting down"
                    )
                except Exception as e:
                    node.logger.warning(
                        f"State transition failed during shutdown: {e}"
                    )
        
        # Cleanup node-specific resources
        if node:
            try:
                node.cleanup_resources()
            except Exception as e:
                node.logger.error(
                    f"Error during cleanup: {e}"
                )
        
        # Destroy the node
        if node:
            node.destroy_node()
        
        # Shutdown rclpy
        try:
            rclpy.shutdown()
        except Exception:
            pass  # rclpy may already be shut down

if __name__ == '__main__':
    main()