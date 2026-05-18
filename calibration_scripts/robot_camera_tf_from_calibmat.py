import os
import yaml
import numpy as np
from scipy.spatial.transform import Rotation as R


CALIBMAT_PATH = "calibmat.txt"
OUTPUT_YAML = "base_link_to_camera_link.yaml"


def load_matrix(path: str) -> np.ndarray:
    """Load a 4x4 matrix from a text file (tabs/spaces, 4 rows)."""
    mat = np.loadtxt(path, dtype=float)
    if mat.shape != (4, 4):
        raise ValueError(f"Expected 4x4 matrix in {path}, got shape {mat.shape}")
    return mat


def infer_translation_scale_mm_to_m(t_xyz: np.ndarray) -> float:
    """Heuristic: if translation looks like millimetres, return 0.001 else 1.0."""
    if float(np.max(np.abs(t_xyz))) > 10.0:
        return 0.001
    return 1.0


def matrix_to_yaml_transform(T: np.ndarray, parent_frame: str, child_frame: str, key: str) -> dict:
    rot = R.from_matrix(T[:3, :3])
    qx, qy, qz, qw = rot.as_quat()  # scipy: [x,y,z,w]

    t = T[:3, 3].astype(float)
    scale = infer_translation_scale_mm_to_m(t)
    t_m = t * scale

    return {
        key: {
            "parent_frame": parent_frame,
            "child_frame": child_frame,
            "x": float(round(t_m[0], 10)),
            "y": float(round(t_m[1], 10)),
            "z": float(round(t_m[2], 10)),
            "qx": float(round(qx, 10)),
            "qy": float(round(qy, 10)),
            "qz": float(round(qz, 10)),
            "qw": float(round(qw, 10)),
        }
    }

def matrix_to_rpy_transform(T: np.ndarray, parent_frame: str, child_frame: str, key: str) -> dict:
    rot = R.from_matrix(T[:3, :3])
    rpy = rot.as_euler('xyz', degrees=False)  # Roll, Pitch, Yaw

    t = T[:3, 3].astype(float)
    scale = infer_translation_scale_mm_to_m(t)
    t_m = t * scale

    return {
        key: {
            "parent_frame": parent_frame,
            "child_frame": child_frame,
            "x": float(round(t_m[0], 10)),
            "y": float(round(t_m[1], 10)),
            "z": float(round(t_m[2], 10)),
            "roll": float(round(rpy[0], 10)),
            "pitch": float(round(rpy[1], 10)),
            "yaw": float(round(rpy[2], 10)),
        }
    }



def max_abs_err(A: np.ndarray, B: np.ndarray) -> float:
    return float(np.max(np.abs(A - B)))


if __name__ == "__main__":
    T = load_matrix(CALIBMAT_PATH)

    # Quick sanity: rigid transform should have last row [0 0 0 1]
    if max_abs_err(T[3, :], np.array([0.0, 0.0, 0.0, 1.0])) > 1e-9:
        raise ValueError(f"Matrix last row is not [0 0 0 1]: {T[3, :]}")

    # Consistency check for inversion
    I = np.eye(4)
    invT = np.linalg.inv(T)
    err1 = max_abs_err(T @ invT, I)
    err2 = max_abs_err(invT @ T, I)

    print("calibmat.txt → transform")
    print(f"  max|T*inv(T)-I|: {err1:.3e}")
    print(f"  max|inv(T)*T-I|: {err2:.3e}")

    tf = matrix_to_rpy_transform(
        T,
        parent_frame="base_link",
        child_frame="camera_link",
        key="base_link_to_camera_link",
    )

    out_dir = os.path.dirname(os.path.abspath(OUTPUT_YAML))
    os.makedirs(out_dir, exist_ok=True)
    with open(OUTPUT_YAML, "w") as f:
        yaml.safe_dump(tf, f, default_flow_style=False, sort_keys=False)

    print(f"Saved: {os.path.normpath(OUTPUT_YAML)}")
