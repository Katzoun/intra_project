
import os
import re
from dataclasses import dataclass
from typing import Dict, Tuple
import xacro
import numpy as np
from scipy.spatial.transform import Rotation as R

from intranodes_pkg.robot_controller_interface import RWSInterface

# ── Settings (pls edit me) ───────────────────────────────────────────────────
ROBOT_IP = "192.168.0.37"
USERNAME = "Admin"
PASSWORD = "robotics"
PORT = 443
MODULE = "CalibData"

TABLE_WOBJ = "wobjtabletop"
DOCK_WOBJS = ["wobjdock1", "wobjdock2", "wobjdock3"]

XACRO_PATH = "src/workcell_pkg/urdf/workcell.xacro"
OUT_URDF_PATH = "src/workcell_pkg/urdf/workcell.urdf"

USE_CAMERA_CALIBMAT = True
CALIBMAT_PATH = "calibration_scripts/calibmat.txt"

@dataclass(frozen=True)
class Pose:
    x_mm: float
    y_mm: float
    z_mm: float
    qw: float
    qx: float
    qy: float
    qz: float


def _numbers(raw: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", raw)]


def _pose_to_T(p: Pose) -> np.ndarray:
    rot = R.from_quat([p.qx, p.qy, p.qz, p.qw])  # scipy: [x,y,z,w]
    T = np.eye(4)
    T[:3, :3] = rot.as_matrix()
    T[:3, 3] = [p.x_mm, p.y_mm, p.z_mm]
    return T


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


def matrix_to_xyz_rpy(T: np.ndarray) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Convert homogeneous transform to xyz (m) + rpy (rad)."""
    t = T[:3, 3].astype(float)
    scale = infer_translation_scale_mm_to_m(t)
    t_m = t * scale
    roll, pitch, yaw = R.from_matrix(T[:3, :3]).as_euler("xyz", degrees=False)
    return (float(t_m[0]), float(t_m[1]), float(t_m[2])), (float(roll), float(pitch), float(yaw))


def _parse_wobjdata_uframe_oframe(raw: str) -> Tuple[Pose, Pose]:
    """Parse uframe and oframe from ABB RAPID wobjdata string.

    wobjdata = [robhold, ufprog, ufmec, uframe, oframe]
    uframe   = [[x,y,z], [qw,qx,qy,qz]]   (mm, ABB quat order)
    oframe   = [[x,y,z], [qw,qx,qy,qz]]

    Returns:
        (uframe_pose, oframe_pose)
    """
    vals = _numbers(raw)
    if len(vals) < 14:
        raise ValueError(
            f"wobjdata parse failed: expected >=14 numbers, got {len(vals)} from: {raw!r}"
        )

    u = Pose(vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6])
    o = Pose(vals[7], vals[8], vals[9], vals[10], vals[11], vals[12], vals[13])
    return u, o


def wobjdata_to_xyz_rpy(raw: str) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Convert wobjdata to xyz (m) and rpy (rad), as robot_base→object."""
    u, o = _parse_wobjdata_uframe_oframe(raw)
    T = _pose_to_T(u) @ _pose_to_T(o)
    x_m, y_m, z_m = (float(v) / 1000.0 for v in T[:3, 3])
    roll, pitch, yaw = R.from_matrix(T[:3, :3]).as_euler("xyz", degrees=False)
    return (x_m, y_m, z_m), (float(roll), float(pitch), float(yaw))


def _fmt_triplet(vals: Tuple[float, float, float], digits: int = 10) -> str:
    return " ".join(f"{v:.{digits}f}" for v in vals)

def build_workcell_urdf(
    *,
    xacro_path: str,
    out_urdf_path: str,
    xacro_args: Dict[str, str],
) -> None:
    doc = xacro.process_file(xacro_path, mappings=xacro_args)
    urdf_xml = doc.toxml()

    if out_urdf_path == "-":
        print(urdf_xml)
        return

    out_dir = os.path.dirname(out_urdf_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_urdf_path, "w", encoding="utf-8") as f:
        f.write(urdf_xml)


def main() -> int:
    rws = RWSInterface(ROBOT_IP, USERNAME, PASSWORD, PORT)
    try:
        rws.login()

        table_raw, _ = rws.get_rapid_symbol(TABLE_WOBJ, MODULE)
        docks_raw = []
        for wobj_name in DOCK_WOBJS:
            raw, _ = rws.get_rapid_symbol(wobj_name, MODULE)
            docks_raw.append((wobj_name, raw))

    finally:
        try:
            rws.logout()
        except Exception:
            pass

    table_xyz, table_rpy = wobjdata_to_xyz_rpy(table_raw)
    dock_xyz_rpy = [
        (name, *wobjdata_to_xyz_rpy(raw))
        for name, raw in docks_raw
    ]

    xacro_args: Dict[str, str] = {
        "table_top_xyz": _fmt_triplet(table_xyz),
        "table_top_rpy": _fmt_triplet(table_rpy),
    }
    for i, (_name, xyz, rpy) in enumerate(dock_xyz_rpy, start=1):
        xacro_args[f"stationdock{i}_xyz"] = _fmt_triplet(xyz)
        xacro_args[f"stationdock{i}_rpy"] = _fmt_triplet(rpy)

    if USE_CAMERA_CALIBMAT:
        T_cam = load_matrix(CALIBMAT_PATH)
        if float(np.max(np.abs(T_cam[3, :] - np.array([0.0, 0.0, 0.0, 1.0])))) > 1e-9:
            raise ValueError(f"Matrix last row is not [0 0 0 1]: {T_cam[3, :]}")
        cam_xyz, cam_rpy = matrix_to_xyz_rpy(T_cam)
        xacro_args["camera_xyz"] = _fmt_triplet(cam_xyz)
        xacro_args["camera_rpy"] = _fmt_triplet(cam_rpy)

    print("Parsed poses (robot_base/base_link object):")
    print(f"  table_top_xyz: {xacro_args['table_top_xyz']}")
    print(f"  table_top_rpy: {xacro_args['table_top_rpy']}")
    for i in range(1, 4):
        print(f"  stationdock{i}_xyz: {xacro_args[f'stationdock{i}_xyz']}")
        print(f"  stationdock{i}_rpy: {xacro_args[f'stationdock{i}_rpy']}")

    if USE_CAMERA_CALIBMAT:
        print(f"  camera_xyz: {xacro_args['camera_xyz']}")
        print(f"  camera_rpy: {xacro_args['camera_rpy']}")

    build_workcell_urdf(
        xacro_path=XACRO_PATH,
        out_urdf_path=OUT_URDF_PATH,
        xacro_args=xacro_args,
    )
    print(f"\nWrote URDF: {OUT_URDF_PATH}")
    return 0


if __name__ == "__main__":
    main()