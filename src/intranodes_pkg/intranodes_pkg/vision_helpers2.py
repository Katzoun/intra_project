import time
from pathlib import Path
import numpy as np
import open3d as o3d
import trimesh
from geometry_msgs.msg import Pose
from scipy.spatial.transform import Rotation


def load_cad(path: str, num_samples: int = 30_000) -> o3d.geometry.PointCloud:
    """Load a CAD mesh (.stl/.obj) and uniformly sample it into a point cloud."""
    mesh = trimesh.load(str(path), force="mesh")
    samples, face_ids = trimesh.sample.sample_surface_even(mesh, count=num_samples)
    normals = mesh.face_normals[face_ids]
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(samples.astype(np.float64))
    pcd.normals = o3d.utility.Vector3dVector(normals.astype(np.float64))
    print(f"CAD loaded: {Path(path).name} -> {len(pcd.points)} points")
    return pcd


def preprocess(pcd: o3d.geometry.PointCloud, voxel_size: float, label: str = "") -> o3d.geometry.PointCloud:
    """Voxel downsample, remove outliers, estimate normals."""
    down = pcd.voxel_down_sample(voxel_size)
    print(f"[{label}] Voxel downsample ({voxel_size:.1f} mm): {len(pcd.points)} -> {len(down.points)} pts")
    down, _ = down.remove_statistical_outlier(nb_neighbors=40, std_ratio=2.0)
    print(f"[{label}] After outlier removal: {len(down.points)} pts")
    down.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 2, max_nn=30))
    down.orient_normals_towards_camera_location()
    return down

def compute_fpfh(pcd: o3d.geometry.PointCloud, voxel_size: float) -> o3d.pipelines.registration.Feature:
    """Compute Fast Point Feature Histograms."""
    radius = voxel_size * 5
    fpfh = o3d.pipelines.registration.compute_fpfh_feature(
        pcd, o3d.geometry.KDTreeSearchParamHybrid(radius=radius, max_nn=100))
    print(f"FPFH: {fpfh.num()} descriptors x {fpfh.dimension()} dims")
    return fpfh


def global_registration(src, tgt, src_fpfh, tgt_fpfh, voxel_size):
    """RANSAC-based global registration using FPFH features."""
    distance = voxel_size * 1.5
    result = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        src, tgt, src_fpfh, tgt_fpfh,
        mutual_filter=True,
        max_correspondence_distance=distance,
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
        ransac_n=3,
        checkers=[
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(distance),
        ],
        criteria=o3d.pipelines.registration.RANSACConvergenceCriteria(4_000_000, 0.999),
    )
    print(f"RANSAC: fitness={result.fitness:.4f}  RMSE={result.inlier_rmse:.4f} mm  corr={len(result.correspondence_set)}")
    return result


def refine_icp(src, tgt, init_transform, voxel_size):
    """Multi-stage ICP refinement at decreasing distance thresholds."""
    current = init_transform.copy()
    distances = [voxel_size * 2, voxel_size, voxel_size * 0.5]
    best_result = None
    best_rmse = float("inf")

    for i, dist in enumerate(distances):
        result = o3d.pipelines.registration.registration_icp(
            src, tgt, dist, current,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=100),
        )
        print(f"ICP [{i + 1}/{len(distances)}] dist={dist:.1f} mm -> fitness={result.fitness:.4f}  RMSE={result.inlier_rmse:.4f} mm")
        if result.inlier_rmse > 0 and result.inlier_rmse < best_rmse:
            best_rmse = result.inlier_rmse
            best_result = result
        current = np.array(result.transformation)

    ransac_eval = o3d.pipelines.registration.evaluate_registration(
        src, tgt, distances[-1], init_transform)
    if best_result is None or (ransac_eval.inlier_rmse > 0 and ransac_eval.inlier_rmse < best_result.inlier_rmse):
        print(f"ICP degraded RMSE ({ransac_eval.inlier_rmse:.4f} -> {best_result.inlier_rmse if best_result else float('inf'):.4f}), using RANSAC result")
        return ransac_eval
    return best_result


def transformation_to_pose(T: np.ndarray) -> Pose:
    """Convert a 4x4 homogeneous transformation matrix to a ROS2 Pose message (mm)."""
    pose = Pose()
    pose.position.x = float(T[0, 3])
    pose.position.y = float(T[1, 3])
    pose.position.z = float(T[2, 3])

    quat = Rotation.from_matrix(T[:3, :3]).as_quat()  # [x, y, z, w]
    pose.orientation.x = float(quat[0])
    pose.orientation.y = float(quat[1])
    pose.orientation.z = float(quat[2])
    pose.orientation.w = float(quat[3])
    return pose

def visualize_result(src, tgt, ransac_T, icp_T, title="Pose Estimation"):
    """Shows three side-by-side views: before alignment, RANSAC, and ICP.
    Colors: Blue = CAD (before), Orange = scene, Green = RANSAC-aligned CAD,
    Red = ICP-aligned CAD.
    """
    tgt_pts = np.asarray(tgt.points)
    x_span = tgt_pts[:, 0].ptp()
    offset = x_span * 1.2
    geometries = []

    # Stage 1: before alignment
    tgt1 = o3d.geometry.PointCloud(tgt)
    tgt1.paint_uniform_color([0.9, 0.5, 0.1])
    src1 = o3d.geometry.PointCloud(src)
    src1.paint_uniform_color([0.2, 0.4, 0.9])
    frame1 = o3d.geometry.TriangleMesh.create_coordinate_frame(size=x_span * 0.08)
    geometries += [tgt1, src1, frame1]

    # Stage 2: RANSAC
    tgt2 = o3d.geometry.PointCloud(tgt)
    tgt2.paint_uniform_color([0.9, 0.5, 0.1])
    tgt2.translate([offset, 0, 0])
    src2 = o3d.geometry.PointCloud(src)
    src2.transform(ransac_T)
    src2.paint_uniform_color([0.1, 0.8, 0.2])
    src2.translate([offset, 0, 0])
    geometries += [tgt2, src2]

    # Stage 3: ICP
    tgt3 = o3d.geometry.PointCloud(tgt)
    tgt3.paint_uniform_color([0.9, 0.5, 0.1])
    tgt3.translate([2 * offset, 0, 0])
    src3 = o3d.geometry.PointCloud(src)
    src3.transform(icp_T)
    src3.paint_uniform_color([0.9, 0.1, 0.15])
    src3.translate([2 * offset, 0, 0])
    geometries += [tgt3, src3]

    o3d.visualization.draw_geometries(
        geometries,
        window_name=f"{title}  |  Blue=before  Green=RANSAC  Red=ICP  Orange=scene",
        width=1920, height=800,
    )


def estimate_pose(
    cad_path: str,
    scene_pcd: o3d.geometry.PointCloud,
    voxel_size: float = 2.0,
    nb_neighbors: int = 20,
    visualize: bool = False,
) -> tuple[Pose, np.ndarray, np.ndarray, dict]:
    """Run the full pose estimation pipeline.
    Args:
        cad_path: Path to CAD mesh file (.stl / .obj).
        scene_pcd: Scene point cloud (Open3D), already loaded and SAM3-filtered.
        voxel_size: Voxel size in mm for downsampling.
        visualize: If True, show Open3D window with alignment stages.

    Returns:
        pose: ROS2 Pose of the detected object in world frame (mm).
        icp_T: 4x4 ICP transformation matrix.
        ransac_T: 4x4 RANSAC transformation (before ICP refinement).
        info: Dict with fitness, rmse, elapsed time, and point clouds.
    """
    t0 = time.perf_counter()

    src_raw = load_cad(cad_path)
    src = preprocess(src_raw, voxel_size, label="CAD")

    tgt_clean, _ = scene_pcd.remove_statistical_outlier(nb_neighbors=nb_neighbors, std_ratio=2.0)
    print(f"[scene] After outlier removal: {len(tgt_clean.points)} pts")
    tgt = tgt_clean.voxel_down_sample(voxel_size)
    print(f"[scene] Voxel downsample ({voxel_size:.1f} mm): {len(tgt_clean.points)} -> {len(tgt.points)} pts")
    tgt.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 2, max_nn=30))
    tgt.orient_normals_towards_camera_location()

    src_fpfh = compute_fpfh(src, voxel_size)
    tgt_fpfh = compute_fpfh(tgt, voxel_size)

    ransac_result = global_registration(src, tgt, src_fpfh, tgt_fpfh, voxel_size)
    ransac_T = np.array(ransac_result.transformation)

    icp_result = refine_icp(src, tgt, ransac_T, voxel_size)
    icp_T = np.array(icp_result.transformation)

    pose = transformation_to_pose(icp_T)
    elapsed = time.perf_counter() - t0

    t = icp_T[:3, 3]
    euler = Rotation.from_matrix(icp_T[:3, :3]).as_euler("xyz", degrees=True)
    print("=" * 55)
    print("RESULT")
    print(f"  Fitness:     {icp_result.fitness:.4f}")
    print(f"  RMSE:        {icp_result.inlier_rmse:.4f} mm")
    print(f"  Position:    [{t[0]:.2f}, {t[1]:.2f}, {t[2]:.2f}] mm")
    print(f"  Euler (deg): [{euler[0]:.2f}, {euler[1]:.2f}, {euler[2]:.2f}]")
    print(f"  Quaternion:  [{pose.orientation.x:.4f}, {pose.orientation.y:.4f}, {pose.orientation.z:.4f}, {pose.orientation.w:.4f}]")
    print(f"  Time:        {elapsed:.2f} s")
    print("=" * 55)

    if visualize:
        visualize_result(src, tgt, ransac_T, icp_T,
                         title=f"Pose Estimation – {Path(cad_path).stem}")

    info = {
        "fitness": icp_result.fitness,
        "rmse": icp_result.inlier_rmse,
        "elapsed": elapsed,
        "src": src,
        "tgt": tgt,
    }
    return pose, icp_T, ransac_T, info
