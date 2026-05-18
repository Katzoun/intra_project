"""
Tests for helpers in vision_helpers.
"""

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from intranodes_pkg.vision_helpers import (
    _normal_to_quaternion,
    is_valid_point,
    orient_normal_down,
)

def test_orient_normal_down_flips_upward_normal():
    # An upward-pointing normal must be flipped so the gripper approaches from above.
    result = orient_normal_down(np.array([0.0, 0.0, 1.0]))
    np.testing.assert_allclose(result, [0.0, 0.0, -1.0])


def test_orient_normal_down_leaves_downward_normal_alone():
    result = orient_normal_down(np.array([0.0, 0.0, -1.0]))
    np.testing.assert_allclose(result, [0.0, 0.0, -1.0])


def test_orient_normal_down_normalises_input():
    # Caller may pass an unnormalised normal - output must still be unit length.
    result = orient_normal_down(np.array([0.0, 0.0, -5.0]))
    assert np.linalg.norm(result) == pytest.approx(1.0)


def test_is_valid_point_accepts_regular_point():
    assert is_valid_point(np.array([1.0, 2.0, 3.0])) is True


def test_is_valid_point_rejects_nan_and_inf():
    assert is_valid_point(np.array([1.0, np.nan, 3.0])) is False
    assert is_valid_point(np.array([np.inf, 0.0, 0.0])) is False


def test_is_valid_point_rejects_zero_point():
    # (0,0,0) shows up as a sentinel for missing depth in the raw cloud.
    assert is_valid_point(np.array([0.0, 0.0, 0.0])) is False

def test_normal_to_quaternion_aligns_z_axis_with_normal():
    # The returned quaternion should rotate the canonical Z axis onto the input normal.
    normal = np.array([0.3, -0.4, 0.866])
    normal /= np.linalg.norm(normal)

    quat = _normal_to_quaternion(normal)
    rotated_z = Rotation.from_quat(quat).apply([0.0, 0.0, 1.0])

    np.testing.assert_allclose(rotated_z, normal, atol=1e-9)

def test_normal_to_quaternion_returns_unit_quaternion():
    quat = _normal_to_quaternion(np.array([1.0, 1.0, 1.0]))
    assert np.linalg.norm(quat) == pytest.approx(1.0)
