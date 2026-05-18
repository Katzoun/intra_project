"""
Tests for the pure-Python helpers on MotionPlanningNode.
"""

import math

import pytest
from moveit_msgs.msg import CollisionObject, RobotTrajectory
from shape_msgs.msg import SolidPrimitive
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from intranodes_pkg.motion_planning_node import MotionPlanningNode


# ---- _anchored --------------------------------------------------------------

def test_anchored_center_returns_value_unchanged():
    assert MotionPlanningNode._anchored(1.0, 0.4, 'center') == 1.0


def test_anchored_min_shifts_by_half_dimension_positive():
    # 'min' means the given value is the minimum corner - center sits half a
    # dimension further along the axis.
    assert MotionPlanningNode._anchored(1.0, 0.4, 'min') == pytest.approx(1.2)


def test_anchored_max_shifts_by_half_dimension_negative():
    assert MotionPlanningNode._anchored(1.0, 0.4, 'max') == pytest.approx(0.8)


def test_anchored_rejects_unknown_anchor():
    with pytest.raises(ValueError):
        MotionPlanningNode._anchored(1.0, 0.4, 'middle')


# ---- _make_box --------------------------------------------------------------

def test_make_box_defaults_to_center_anchor_and_add_operation():
    co = MotionPlanningNode._make_box(
        obj_id='unit_box',
        frame_id='world',
        dimensions=[0.2, 0.4, 0.6],
        position=[1.0, 2.0, 3.0],
    )

    assert isinstance(co, CollisionObject)
    assert co.id == 'unit_box'
    assert co.header.frame_id == 'world'
    assert co.operation == CollisionObject.ADD

    assert len(co.primitives) == 1
    prim = co.primitives[0]
    assert prim.type == SolidPrimitive.BOX
    assert list(prim.dimensions) == [0.2, 0.4, 0.6]

    pose = co.primitive_poses[0]
    assert (pose.position.x, pose.position.y, pose.position.z) == (1.0, 2.0, 3.0)
    # Default orientation is identity quaternion.
    assert pose.orientation.w == 1.0


def test_make_box_min_anchor_shifts_pose_to_box_center():
    co = MotionPlanningNode._make_box(
        obj_id='corner_box',
        frame_id='table',
        dimensions=[0.2, 0.4, 0.6],
        position=[0.0, 0.0, 0.0],
        anchor=('min', 'min', 'min'),
    )
    pose = co.primitive_poses[0]
    assert pose.position.x == pytest.approx(0.1)
    assert pose.position.y == pytest.approx(0.2)
    assert pose.position.z == pytest.approx(0.3)


def test_make_box_custom_orientation_is_applied():
    co = MotionPlanningNode._make_box(
        obj_id='rotated',
        frame_id='world',
        dimensions=[0.1, 0.1, 0.1],
        position=[0.0, 0.0, 0.0],
        orientation=[0.0, 0.0, 0.7071, 0.7071],
    )
    pose = co.primitive_poses[0]
    assert pose.orientation.z == pytest.approx(0.7071)
    assert pose.orientation.w == pytest.approx(0.7071)


# ---- _extract_waypoints -----------------------------------------------------

def _trajectory_from(points_rad: list[list[float]]) -> RobotTrajectory:
    traj = RobotTrajectory()
    jt = JointTrajectory()
    for pos in points_rad:
        pt = JointTrajectoryPoint()
        pt.positions = pos
        jt.points.append(pt)
    traj.joint_trajectory = jt
    return traj


def test_extract_waypoints_converts_radians_to_degrees():
    traj = _trajectory_from([[0.0, math.pi / 2, math.pi]])
    wps = MotionPlanningNode._extract_waypoints(traj)
    assert wps == [[0.0, 90.0, 180.0]]


def test_extract_waypoints_preserves_order_and_handles_empty():
    traj = _trajectory_from([[0.0], [math.pi]])
    assert MotionPlanningNode._extract_waypoints(traj) == [[0.0], [180.0]]

    assert MotionPlanningNode._extract_waypoints(_trajectory_from([])) == []
