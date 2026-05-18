"""
Operations Page coordinator pipeline

ROS2 feedback callback runs on the rclpy spin thread,
NOT on the NiceGUI asyncio event loop. All UI mutations must happen
on the event loop. Feedback is buffered in a thread-safe queue and
drained with a ui.timer.
"""

from __future__ import annotations

import asyncio
import base64
import io
import math
import threading
from collections import deque
from typing import Optional, Dict, Any

import numpy as np
from nicegui import ui
from cv_bridge import CvBridge
from PIL import Image as PILImage
from sensor_msgs_py import point_cloud2

from scipy.spatial.transform import Rotation

from user_interface_pkg.constants import OPERATIONS_PAGE, CALL_TIMEOUT_SEC
from user_interface_pkg.pages.layout_page import create_main_layout
from user_interface_pkg.utils.jwtutils import get_valid_accessor
from interface_pkg.action import PerformOperation
from interface_pkg.srv import TriggerServiceSrv, NodeStateSrv
from rclpy.action.client import ClientGoalHandle
from core_pkg.nodes_async import AsyncINTRANode
from core_pkg.systemconstants import Operation1Phases, Operation2Phases, NodeStates

POINT_SIZE = 1.0
MAX_SCENE_POINTS = 20_000
CV_BRIDGE = CvBridge()

# ── Shared helpers ──────────────────────────────────────────────────

def _ros_image_to_data_url(ros_img) -> Optional[str]:
    """sensor_msgs/Image -> base64 PNG data-URL."""
    try:
        cv_img = CV_BRIDGE.imgmsg_to_cv2(ros_img, desired_encoding="rgb8")
        pil = PILImage.fromarray(cv_img)
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception as exc:
        print(f"[operations_page] image conversion error: {exc}")
        return None

def _ros_pcd_to_numpy(ros_pcd, max_pts: int = MAX_SCENE_POINTS) -> Optional[np.ndarray]:
    """sensor_msgs/PointCloud2 -> Nx3 float32 numpy array, or None."""
    try:
        from numpy.lib.recfunctions import structured_to_unstructured
        structured = point_cloud2.read_points(
            ros_pcd, field_names=("x", "y", "z"), skip_nans=True
        )
        xyz = structured_to_unstructured(structured).astype(np.float32)
        if xyz.ndim != 2 or xyz.shape[1] < 3:
            return None
        xyz = xyz[:, :3]
        xyz = xyz[np.isfinite(xyz).all(axis=1)]
        if len(xyz) == 0:
            return None
        if len(xyz) > max_pts:
            idx = np.random.choice(len(xyz), max_pts, replace=False)
            xyz = xyz[idx]
        return xyz
    except Exception as exc:
        print(f"[PCD] conversion error: {exc}")
        return None


def _render_coordinate_frame(origin: list, R: list, label_text: str, frame_len: float = 25.0):
    """Render a 3D coordinate frame (XYZ axes) at given origin with rotation matrix."""
    with ui.scene.group().move(*origin).rotate_R(R):
        for axis_label, color, rx, ry, rz in [
            ('x', '#ff0000', 0, 0, -math.pi / 2),
            ('y', '#00ff00', 0, 0, 0),
            ('z', '#0000ff', math.pi / 2, 0, 0),
        ]:
            with ui.scene.group().rotate(rx, ry, rz):
                ui.scene.cylinder(0.02 * frame_len, 0.02 * frame_len, 0.8 * frame_len) \
                    .move(y=0.4 * frame_len).material(color)
                ui.scene.cylinder(0, 0.1 * frame_len, 0.2 * frame_len) \
                    .move(y=0.9 * frame_len).material(color)
                ui.scene.text(axis_label, style=f'color: {color}') \
                    .move(y=1.1 * frame_len)
        ui.scene.text(label_text, style='color: #ffff00')


def _render_images(images, image_labels, img_grid, img_card, open_enlarge_fn):
    """Render feedback images into the image grid."""
    lbls = image_labels if image_labels else [f"img_{i}" for i in range(len(images))]
    added = False
    with img_grid:
        for ros_img, lbl in zip(images, lbls):
            url = _ros_image_to_data_url(ros_img)
            if url:
                with ui.card().classes('shadow-sm cursor-pointer').style('width: 260px'):
                    img_el = ui.image(url).classes('w-full rounded')
                    ui.label(lbl).classes('text-caption text-grey-7 text-center w-full mt-1')
                    img_el.on('click', lambda _, u=url: open_enlarge_fn(u))
                added = True
    if added:
        img_card.set_visibility(True)


def _render_point_clouds(point_clouds, point_cloud_labels, pcd_container, scene_ref, pcd_colors: dict):
    """Render point clouds into a 3D scene, creating the scene lazily."""
    plbls = point_cloud_labels if point_cloud_labels else [f"cloud_{i}" for i in range(len(point_clouds))]

    all_arrays = []
    all_labels = []
    for pcd_msg, lbl in zip(point_clouds, plbls):
        arr = _ros_pcd_to_numpy(pcd_msg)
        if arr is not None:
            all_arrays.append(arr)
            all_labels.append(lbl)

    if not all_arrays:
        return

    all_pts = np.concatenate(all_arrays)
    centroid = all_pts.mean(axis=0)
    spread = float(np.max(np.abs(all_pts - centroid)))

    if scene_ref["scene"] is None:
        with pcd_container:
            card = ui.card().classes('w-full mb-4')
            with card:
                ui.label('Point Cloud').classes('text-h6 mb-2')
                cam = ui.scene.perspective_camera(far=2000)
                scene_ref["scene"] = ui.scene(width=1200, height=800, grid=False, camera=cam, fps=50).classes('rounded')
            scene_ref["card"] = card


    scene = scene_ref["scene"]
    try:
        scene.clear()
        with scene:
            for arr, lbl in zip(all_arrays, all_labels):
                centered = (arr - centroid).tolist()
                color = pcd_colors.get(lbl, [0.5, 0.5, 0.8])
                colors = [color] * len(centered)
                scene.point_cloud(centered, colors, point_size=POINT_SIZE)

        cam_dist = max(spread * 1.5, 10.0)
        scene.move_camera(x=0, y=0, z=cam_dist, look_at_x=0, look_at_y=0, look_at_z=0)
        scene_ref["centroid"] = centroid
    except Exception as exc:
        print(f"[PCD] scene render error: {exc}")


def _render_grasp_frames(grasp_results, scene_ref):
    """Render grasp results as coordinate frames in the 3D scene."""
    if not grasp_results or scene_ref["scene"] is None:
        return
    centroid = scene_ref["centroid"]
    scene = scene_ref["scene"]
    try:
        with scene:
            for gr in grasp_results:
                p = gr.grasp_pose.position
                q = gr.grasp_pose.orientation
                origin = (np.array([p.x, p.y, p.z]) - centroid).tolist()
                rot = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_matrix()
                _render_coordinate_frame(origin, rot.tolist(), gr.label)
    except Exception as exc:
        print(f"[PCD] grasp frame render error: {exc}")


def _render_pose_frames(poses, pose_labels, scene_ref):
    """Render individual poses as coordinate frames in the 3D scene."""
    if not poses or scene_ref["scene"] is None:
        return
    centroid = scene_ref["centroid"]
    scene = scene_ref["scene"]
    try:
        lbls = pose_labels if pose_labels else [f"pose_{i}" for i in range(len(poses))]
        with scene:
            for pose, lbl in zip(poses, lbls):
                p = pose.position
                q = pose.orientation
                origin = (np.array([p.x, p.y, p.z]) - centroid).tolist()
                rot = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_matrix()
                _render_coordinate_frame(origin, rot.tolist(), lbl)
    except Exception as exc:
        print(f"[PCD] pose frame render error: {exc}")


def _render_pose_array_paths(pose_arrays, pose_array_labels, scene_ref):
    """Render pose arrays as connected line segments in the 3D scene."""
    if not pose_arrays or scene_ref["scene"] is None:
        return
    centroid = scene_ref["centroid"]
    scene = scene_ref["scene"]
    PATH_COLORS = {"zigzag": "#ff00ff"}
    try:
        labels = pose_array_labels if pose_array_labels else [f"path_{i}" for i in range(len(pose_arrays))]
        with scene:
            for pa, lbl in zip(pose_arrays, labels):
                pa_poses = pa.poses
                if len(pa_poses) < 2:
                    continue
                color = PATH_COLORS.get(lbl, "#ffffff")
                for i in range(len(pa_poses) - 1):
                    p0 = pa_poses[i].position
                    p1 = pa_poses[i + 1].position
                    s = np.array([p0.x, p0.y, p0.z]) - centroid
                    e = np.array([p1.x, p1.y, p1.z]) - centroid
                    scene.line(s.tolist(), e.tolist()).material(color)
    except Exception as exc:
        print(f"[PCD] pose path render error: {exc}")


def _parse_feedback(feedback_msg) -> dict:
    """Extract feedback fields from ROS feedback message into a plain dict."""
    fb = feedback_msg.feedback
    return {
        "phase": fb.phase,
        "progress": fb.progress,
        "message": fb.status_message,
        "images": list(fb.images) if fb.images else [],
        "image_labels": list(fb.image_labels) if fb.image_labels else [],
        "point_clouds": list(fb.point_clouds) if fb.point_clouds else [],
        "point_cloud_labels": list(fb.point_cloud_labels) if fb.point_cloud_labels else [],
        "grasp_results": list(fb.grasp_results) if fb.grasp_results else [],
        "poses": list(fb.poses) if fb.poses else [],
        "pose_labels": list(fb.pose_labels) if fb.pose_labels else [],
        "pose_arrays": list(fb.pose_arrays) if fb.pose_arrays else [],
        "pose_array_labels": list(fb.pose_array_labels) if fb.pose_array_labels else [],
    }


def operations_page_factory(node: AsyncINTRANode):

    async def create_operations_page() -> None:
        try:
            accessor_dto = await get_valid_accessor()
            if accessor_dto is None:
                return

            with create_main_layout(accessor=accessor_dto, active_page=OPERATIONS_PAGE.page):

                with ui.row().classes('w-full items-center justify-between mb-6'):
                    with ui.row().classes('items-center'):
                        ui.icon(OPERATIONS_PAGE.icon).classes('text-4xl text-primary mr-3')
                        with ui.column().classes('gap-0'):
                            ui.label(OPERATIONS_PAGE.name).classes('text-h4 mt-4')

                # Coordinator state card
                coordinator_idle = False
                op1_buttons: list = []
                op2_buttons: list = []

                async def check_coordinator_state() -> bool:
                    nonlocal coordinator_idle
                    try:
                        response: NodeStateSrv.Response = await node.call_service_async(
                            node.coordinator_clients.get_state_cli,
                            NodeStateSrv.Request(),
                            timeout_sec=CALL_TIMEOUT_SEC,
                        )
                        coordinator_idle = response.state == NodeStates.IDLE.value
                        state_label.set_text(response.state)
                        state_desc_label.set_text(response.description)
                    except Exception as exc:
                        coordinator_idle = False
                        state_label.set_text("unreachable")
                        state_desc_label.set_text(str(exc))
                        node.logger.error(f"Failed to check coordinator state: {exc}")

                    for btn in op1_buttons + op2_buttons:
                        if coordinator_idle:
                            btn.enable()
                        else:
                            btn.disable()
                    return coordinator_idle

                with ui.card().classes('w-full p-6 mb-4'):
                    with ui.row().classes('w-full items-center justify-between mb-4'):
                        ui.label('Coordinator State').classes('text-h6')
                        ui.button('Refresh', icon='refresh',
                                  on_click=check_coordinator_state
                        ).props('outline color=primary')
                    with ui.row().classes('w-full items-center gap-4'):
                        ui.label('State:').classes('text-subtitle2 text-grey-7')
                        state_label = ui.label('Unknown').classes('text-body2 text-primary')
                    with ui.row().classes('w-full items-center gap-4 mt-2'):
                        ui.label('Description:').classes('text-subtitle2 text-grey-7')
                        state_desc_label = ui.label('').classes('text-body2')

                # Shared enlarge dialog
                enlarge_dialog = ui.dialog().props('maximized')
                with enlarge_dialog, ui.card().classes('w-full h-full items-center justify-center bg-black'):
                    enlarge_img = ui.image('').classes('max-w-full max-h-full')
                    ui.button(icon='close', on_click=enlarge_dialog.close).props(
                        'flat round color=white').classes('absolute-top-right ma-2')

                def _open_enlarge(url: str):
                    enlarge_img.set_source(url)
                    enlarge_dialog.open()

                # OPERATION 1 — Object Segmentation + Pick-and-Place

                op1_state: Dict[str, Any] = {"running": False, "goal_handle": None}
                op1_feedback_queue: deque = deque()
                op1_feedback_lock = threading.Lock()

                with ui.card().classes('w-full mb-4'):
                    ui.label('Operation 1 — Object Segmentation & Pick-and-Place').classes('text-h6')
                    with ui.row().classes('w-full items-center gap-4'):
                        op1_start_btn = ui.button('Start', icon='play_arrow', color='positive')
                        op1_start_btn.disable()
                        op1_cancel_btn = ui.button('Cancel', icon='stop', color='negative').props('outline')
                        op1_cancel_btn.set_visibility(False)
                        op1_user_input_btn = ui.button('Proceed', icon='arrow_forward', color='primary').props('outline')
                        op1_user_input_btn.set_visibility(False)
                    op1_status_label = ui.label('Idle').classes('text-body2 text-grey-8 mt-2')
                    op1_progress_bar = ui.linear_progress(0, show_value=False, size='12px').classes('w-full rounded mt-1')
                op1_buttons.append(op1_start_btn)

                op1_img_card = ui.card().classes('w-full mb-4')
                op1_img_card.set_visibility(False)
                with op1_img_card:
                    ui.label('Images').classes('text-h6 mb-2')
                    op1_img_grid = ui.row().classes('w-full gap-3 flex-wrap')

                op1_pcd_container = ui.column().classes('w-full')
                op1_scene_ref: Dict[str, Any] = {"scene": None, "card": None, "centroid": np.zeros(3)}

                # OPERATION 2 — CAD pose estimation

                op2_state: Dict[str, Any] = {"running": False, "goal_handle": None}
                op2_feedback_queue: deque = deque()
                op2_feedback_lock = threading.Lock()

                with ui.card().classes('w-full mb-4'):
                    ui.label('Operation 2 — CAD Pose Estimation + Welding').classes('text-h6')
                    with ui.row().classes('w-full items-center gap-4'):
                        op2_start_btn = ui.button('Start', icon='play_arrow', color='positive')
                        op2_start_btn.disable()
                        op2_cancel_btn = ui.button('Cancel', icon='stop', color='negative').props('outline')
                        op2_cancel_btn.set_visibility(False)
                        op2_user_input_btn = ui.button('Proceed', icon='arrow_forward', color='primary').props('outline')
                        op2_user_input_btn.set_visibility(False)
                    op2_status_label = ui.label('Idle').classes('text-body2 text-grey-8 mt-2')
                    op2_progress_bar = ui.linear_progress(0, show_value=False, size='12px').classes('w-full rounded mt-1')
                op2_buttons.append(op2_start_btn)

                op2_img_card = ui.card().classes('w-full mb-4')
                op2_img_card.set_visibility(False)
                with op2_img_card:
                    ui.label('Images').classes('text-h6 mb-2')
                    op2_img_grid = ui.row().classes('w-full gap-3 flex-wrap')

                op2_pcd_container = ui.column().classes('w-full')
                op2_scene_ref: Dict[str, Any] = {"scene": None, "card": None, "centroid": np.zeros(3)}

            # ── Point cloud color maps ──────────────────────────

            OP1_PCD_COLORS = {
                "inlier_hexagon":    [0.9, 0.5, 0.1],
                "inlier_circle":     [0.1, 0.6, 0.9],
                "inlier_background": [0.4, 0.8, 0.4],
            }

            OP2_PCD_COLORS = {
                "cad_pcd":         [0.9, 0.2, 0.2],
                "scene_pcd":       [0.2, 0.7, 0.9],
                "aligned_cad_pcd": [0.2, 0.9, 0.3],
            }


            def _op1_drain_feedback():
                with op1_feedback_lock:
                    items = list(op1_feedback_queue)
                    op1_feedback_queue.clear()

                for fb_data in items:
                    phase = fb_data["phase"]

                    op1_status_label.set_text(f'[{phase}] {fb_data["message"]}')
                    op1_progress_bar.set_value(fb_data["progress"])

                    if phase == Operation1Phases.GRASP_READY:
                        op1_user_input_btn.set_visibility(True)
                    elif phase in (Operation1Phases.EXECUTING_MOTION, Operation1Phases.COMPLETED):
                        op1_user_input_btn.set_visibility(False)

                    if fb_data["images"]:
                        _render_images(fb_data["images"], fb_data["image_labels"],
                                       op1_img_grid, op1_img_card, _open_enlarge)

                    if fb_data["point_clouds"]:
                        _render_point_clouds(fb_data["point_clouds"], fb_data["point_cloud_labels"],
                                             op1_pcd_container, op1_scene_ref, OP1_PCD_COLORS)

                    _render_grasp_frames(fb_data["grasp_results"], op1_scene_ref)
                    _render_pose_frames(fb_data["poses"], fb_data["pose_labels"], op1_scene_ref)
                    _render_pose_array_paths(fb_data["pose_arrays"], fb_data["pose_array_labels"], op1_scene_ref)

            ui.timer(0.2, _op1_drain_feedback)

            def _op1_on_feedback(feedback_msg):
                data = _parse_feedback(feedback_msg)
                with op1_feedback_lock:
                    op1_feedback_queue.append(data)

            def _op1_reset_ui():
                op1_state.update({"running": False, "goal_handle": None})
                op1_progress_bar.set_value(0)
                op1_status_label.set_text('Idle')
                op1_start_btn.enable()
                op1_cancel_btn.set_visibility(False)
                op1_user_input_btn.set_visibility(False)
                op1_img_card.set_visibility(False)
                op1_img_grid.clear()
                if op1_scene_ref["scene"] is not None:
                    op1_scene_ref["scene"].clear()

            async def _op1_send_goal():
                _op1_reset_ui()
                op1_state["running"] = True
                op1_start_btn.disable()
                op1_cancel_btn.set_visibility(True)
                op1_status_label.set_text('Connecting to coordinator...')

                action_client = node.perform_operation_action_client
                ready = action_client.wait_for_server(timeout_sec=5.0)
                if not ready:
                    ui.notify('Coordinator not available', type='negative')
                    _op1_reset_ui()
                    return

                goal_msg = PerformOperation.Goal()
                goal_msg.operation_name = 'operation1_pipeline'

                op1_status_label.set_text('Sending goal...')
                send_goal_future = action_client.send_goal_async(
                    goal_msg, feedback_callback=_op1_on_feedback
                )

                start = asyncio.get_event_loop().time()
                while not send_goal_future.done():
                    if asyncio.get_event_loop().time() - start > 10.0:
                        ui.notify('Goal send timed out', type='negative')
                        _op1_reset_ui()
                        return
                    await asyncio.sleep(0.05)

                goal_handle: ClientGoalHandle = send_goal_future.result()
                if not goal_handle.accepted:
                    ui.notify('Goal rejected', type='warning')
                    _op1_reset_ui()
                    return

                op1_state["goal_handle"] = goal_handle
                op1_status_label.set_text('Pipeline running...')

                result_future = goal_handle.get_result_async()
                while not result_future.done():
                    await asyncio.sleep(0.1)

                ros_result = result_future.result().result
                if ros_result.success:
                    op1_status_label.set_text(f'Done: {ros_result.message}')
                    ui.notify(ros_result.message, type='positive')
                else:
                    op1_status_label.set_text(f'Failed: {ros_result.message}')
                    ui.notify(ros_result.message, type='negative')

                op1_progress_bar.set_value(1.0 if ros_result.success else 0.0)
                op1_state["running"] = False
                op1_start_btn.enable()
                op1_cancel_btn.set_visibility(False)

            async def _op1_cancel_goal():
                gh: Optional[ClientGoalHandle] = op1_state.get("goal_handle")
                if gh is None:
                    return
                op1_status_label.set_text('Cancelling...')
                cancel_future = gh.cancel_goal_async()
                start = asyncio.get_event_loop().time()
                while not cancel_future.done():
                    if asyncio.get_event_loop().time() - start > 5.0:
                        ui.notify('Cancel timed out', type='warning')
                        return
                    await asyncio.sleep(0.05)
                ui.notify('Cancel requested', type='info')

            async def _op1_send_user_input():
                op1_user_input_btn.disable()
                srv_client = node.user_input_client
                if not srv_client.wait_for_service(timeout_sec=3.0):
                    ui.notify('User input service not available', type='negative')
                    op1_user_input_btn.enable()
                    return
                future = srv_client.call_async(TriggerServiceSrv.Request())
                start = asyncio.get_event_loop().time()
                while not future.done():
                    if asyncio.get_event_loop().time() - start > 10.0:
                        ui.notify('User input call timed out', type='warning')
                        op1_user_input_btn.enable()
                        return
                    await asyncio.sleep(0.05)
                resp = future.result()
                if resp.status:
                    ui.notify(resp.message, type='positive')
                else:
                    ui.notify(resp.message or 'User input failed', type='negative')
                op1_user_input_btn.enable()

            op1_start_btn.on_click(_op1_send_goal)
            op1_cancel_btn.on_click(_op1_cancel_goal)
            op1_user_input_btn.on_click(_op1_send_user_input)
            

            def _op2_drain_feedback():
                with op2_feedback_lock:
                    items = list(op2_feedback_queue)
                    op2_feedback_queue.clear()

                for fb_data in items:
                    phase = fb_data["phase"]

                    op2_status_label.set_text(f'[{phase}] {fb_data["message"]}')
                    op2_progress_bar.set_value(fb_data["progress"])

                    if phase == Operation2Phases.POSE_READY:
                        op2_user_input_btn.set_visibility(True)
                    elif phase in (Operation2Phases.EXECUTING_MOTION, Operation2Phases.COMPLETED):
                        op2_user_input_btn.set_visibility(False)

                    if fb_data["images"]:
                        _render_images(fb_data["images"], fb_data["image_labels"],
                                       op2_img_grid, op2_img_card, _open_enlarge)

                    if fb_data["point_clouds"]:
                        _render_point_clouds(fb_data["point_clouds"], fb_data["point_cloud_labels"],
                                             op2_pcd_container, op2_scene_ref, OP2_PCD_COLORS)

                    _render_grasp_frames(fb_data["grasp_results"], op2_scene_ref)
                    _render_pose_frames(fb_data["poses"], fb_data["pose_labels"], op2_scene_ref)
                    _render_pose_array_paths(fb_data["pose_arrays"], fb_data["pose_array_labels"], op2_scene_ref)

            ui.timer(0.2, _op2_drain_feedback)

            def _op2_on_feedback(feedback_msg):
                data = _parse_feedback(feedback_msg)
                with op2_feedback_lock:
                    op2_feedback_queue.append(data)

            def _op2_reset_ui():
                op2_state.update({"running": False, "goal_handle": None})
                op2_progress_bar.set_value(0)
                op2_status_label.set_text('Idle')
                op2_start_btn.enable()
                op2_cancel_btn.set_visibility(False)
                op2_user_input_btn.set_visibility(False)
                op2_img_card.set_visibility(False)
                op2_img_grid.clear()
                if op2_scene_ref["scene"] is not None:
                    op2_scene_ref["scene"].clear()

            async def _op2_send_goal():
                _op2_reset_ui()
                op2_state["running"] = True
                op2_start_btn.disable()
                op2_cancel_btn.set_visibility(True)
                op2_status_label.set_text('Connecting to coordinator...')

                action_client = node.perform_operation2_action_client
                ready = action_client.wait_for_server(timeout_sec=5.0)
                if not ready:
                    ui.notify('Coordinator not available (op2)', type='negative')
                    _op2_reset_ui()
                    return

                goal_msg = PerformOperation.Goal()
                goal_msg.operation_name = 'operation2_pipeline'

                op2_status_label.set_text('Sending goal...')
                send_goal_future = action_client.send_goal_async(
                    goal_msg, feedback_callback=_op2_on_feedback
                )

                start = asyncio.get_event_loop().time()
                while not send_goal_future.done():
                    if asyncio.get_event_loop().time() - start > 10.0:
                        ui.notify('Goal send timed out', type='negative')
                        _op2_reset_ui()
                        return
                    await asyncio.sleep(0.05)

                goal_handle: ClientGoalHandle = send_goal_future.result()
                if not goal_handle.accepted:
                    ui.notify('Goal rejected', type='warning')
                    _op2_reset_ui()
                    return

                op2_state["goal_handle"] = goal_handle
                op2_status_label.set_text('Pipeline running...')

                result_future = goal_handle.get_result_async()
                while not result_future.done():
                    await asyncio.sleep(0.1)

                ros_result = result_future.result().result
                if ros_result.success:
                    op2_status_label.set_text(f'Done: {ros_result.message}')
                    ui.notify(ros_result.message, type='positive')
                else:
                    op2_status_label.set_text(f'Failed: {ros_result.message}')
                    ui.notify(ros_result.message, type='negative')

                op2_progress_bar.set_value(1.0 if ros_result.success else 0.0)
                op2_state["running"] = False
                op2_start_btn.enable()
                op2_cancel_btn.set_visibility(False)

            async def _op2_cancel_goal():
                gh: Optional[ClientGoalHandle] = op2_state.get("goal_handle")
                if gh is None:
                    return
                op2_status_label.set_text('Cancelling...')
                cancel_future = gh.cancel_goal_async()
                start = asyncio.get_event_loop().time()
                while not cancel_future.done():
                    if asyncio.get_event_loop().time() - start > 5.0:
                        ui.notify('Cancel timed out', type='warning')
                        return
                    await asyncio.sleep(0.05)
                ui.notify('Cancel requested', type='info')

            async def _op2_send_user_input():
                op2_user_input_btn.disable()
                srv_client = node.user_input_client
                if not srv_client.wait_for_service(timeout_sec=3.0):
                    ui.notify('User input service not available', type='negative')
                    op2_user_input_btn.enable()
                    return
                future = srv_client.call_async(TriggerServiceSrv.Request())
                start = asyncio.get_event_loop().time()
                while not future.done():
                    if asyncio.get_event_loop().time() - start > 10.0:
                        ui.notify('User input call timed out', type='warning')
                        op2_user_input_btn.enable()
                        return
                    await asyncio.sleep(0.05)
                resp = future.result()
                if resp.status:
                    ui.notify(resp.message, type='positive')
                else:
                    ui.notify(resp.message or 'User input failed', type='negative')
                op2_user_input_btn.enable()

            op2_start_btn.on_click(_op2_send_goal)
            op2_cancel_btn.on_click(_op2_cancel_goal)
            op2_user_input_btn.on_click(_op2_send_user_input)

            # Initial state check
            await check_coordinator_state()

        except Exception as e:
            ui.notify(f'Error: {str(e)}', type='negative')
            node.logger.error(f"Operations page error: {e}")

    return create_operations_page
