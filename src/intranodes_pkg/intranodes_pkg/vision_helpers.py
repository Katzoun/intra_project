import mmap
import struct
import numpy as np
import matplotlib
from PIL import Image as PILImage
import open3d as o3d
from sensor_msgs.msg import PointCloud2, PointField
from sensor_msgs_py import point_cloud2
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation
from geometry_msgs.msg import Pose, PoseArray, Point, Quaternion
from std_msgs.msg import Header
from shapely.geometry import Polygon, LineString
import cv2


def o3d_to_pointcloud2(pcd: o3d.geometry.PointCloud, frame_id: str = "base_link") -> PointCloud2:
    """
    Convert an Open3D PointCloud to a sensor_msgs/PointCloud2 message
    using sensor_msgs_py.point_cloud2.create_cloud_xyz32.
    """
    header = Header()
    header.frame_id = frame_id
    pts = np.asarray(pcd.points, dtype=np.float32)
    return point_cloud2.create_cloud_xyz32(header, pts.tolist())


def largest_contour_from_mask(mask: np.ndarray, label: str):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError(f"{label} not found.")
    cnt = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(cnt)
    box = cv2.boxPoints(rect)
    box = np.int32(box)
    return box


def overlay_masks(image, masks):
    image = image.convert("RGBA")
    masks = 255 * masks.cpu().numpy().astype(np.uint8)
    
    n_masks = masks.shape[0]
    cmap = matplotlib.colormaps.get_cmap("rainbow").resampled(n_masks)
    colors = [
        tuple(int(c * 255) for c in cmap(i)[:3])
        for i in range(n_masks)
    ]

    for mask, color in zip(masks, colors):
        mask = PILImage.fromarray(mask)
        overlay = PILImage.new("RGBA", image.size, color + (0,))
        alpha = mask.point(lambda v: int(v * 0.5))
        overlay.putalpha(alpha)
        image = PILImage.alpha_composite(image, overlay)
    return image

def masked_pointcloud(cloud, mask):

    points = cloud[mask > 0]

    points = points[np.isfinite(points).all(axis=1)]
    points = points[~np.all(points == 0, axis=1)]  

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    return pcd

def ros_to_ndarray(msg: PointCloud2) -> np.ndarray:
        
    points = point_cloud2.read_points_numpy(
            msg,
            field_names=("x", "y", "z"),
            skip_nans=False,
            reshape_organized_cloud=True
    )

    print(f"Point cloud shape: {points.shape}")

    return points

def gamma_correct_texture(texture: NDArray[np.float32], gamma: float) -> PILImage.Image:

    print(f"Texture data shape: {texture.shape}")

    print(f"Value range: min={np.min(texture)}, max={np.max(texture)}")
    print(f"Non-zero values: {np.count_nonzero(texture)} / {len(texture)}")
    print(f"Mean: {np.mean(texture):.2f}, Std: {np.std(texture):.2f}")
    
    non_zero_mask = texture > 0
    normalized = texture.astype(float)
    if np.any(non_zero_mask):
        min_val = np.min(texture[non_zero_mask])
        max_val = np.max(texture[non_zero_mask])
        normalized[non_zero_mask] = (texture[non_zero_mask] - min_val) / (max_val - min_val)

    gamma_corrected = np.power(normalized, gamma)
    # Save gamma corrected image as PNG
    gamma_corrected_img = PILImage.fromarray((gamma_corrected*255).astype(np.uint8))
    return gamma_corrected_img
    # gamma_corrected_img.save("test.png")

def gamma_correct_texture_new(texture: NDArray[np.float32], gamma: float) -> PILImage.Image:

    print(f"Texture data shape: {texture.shape}")

    print(f"Value range: min={np.min(texture)}, max={np.max(texture)}")
    print(f"Non-zero values: {np.count_nonzero(texture)} / {len(texture)}")
    print(f"Mean: {np.mean(texture):.2f}, Std: {np.std(texture):.2f}")
    
    non_zero_mask = texture > 0
    normalized = texture.astype(float)

    non_zero_mask = texture > 0
    normalized_u8 = normalize_valid_to_uint8(texture, non_zero_mask)
    normalized = normalized_u8.astype(np.float32) / 255.0
    gamma_corrected = np.power(normalized, gamma)
    gamma_corrected_img = PILImage.fromarray((gamma_corrected*255).astype(np.uint8))
    return gamma_corrected_img



def normalize_valid_to_uint8(image: np.ndarray, mask: np.ndarray, lower_pct: float = 1.0, upper_pct: float = 99.0) -> np.ndarray:
    """
    Normalize valid pixels to uint8 using robust percentiles.

    Invalid pixels remain 0 so they do not pollute later histogram operations.
    """
    out = np.zeros(image.shape, dtype=np.uint8)
    valid_values = image[mask]

    if valid_values.size == 0:
        return out

    lo, hi = np.percentile(valid_values, [lower_pct, upper_pct])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo = float(np.min(valid_values))
        hi = float(np.max(valid_values))
        if hi <= lo:
            out[mask] = np.clip(valid_values, 0, 255).astype(np.uint8)
            return out

    clipped = np.clip(image[mask], lo, hi)
    scaled = ((clipped - lo) / (hi - lo) * 255.0).astype(np.uint8)
    out[mask] = scaled
    return out


def equalize_hist_masked_opencv(image_u8: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Histogram equalization using OpenCV, computed only from valid masked pixels.
    """
    result = np.zeros_like(image_u8)
    if not np.any(mask):
        return result

    mask_u8 = (mask.astype(np.uint8) * 255)
    hist = cv2.calcHist([image_u8], [0], mask_u8, [256], [0, 256]).ravel()

    nonzero = hist > 0
    if not np.any(nonzero):
        return result

    cdf = hist.cumsum()
    cdf_nonzero = cdf[nonzero]
    cdf_min = cdf_nonzero[0]
    cdf_max = cdf_nonzero[-1]

    lut = np.zeros(256, dtype=np.uint8)
    if cdf_max == cdf_min:
        lut[np.where(nonzero)[0]] = np.where(nonzero)[0].astype(np.uint8)
    else:
        lut_float = (cdf - cdf_min) * 255.0 / (cdf_max - cdf_min)
        lut = np.clip(lut_float, 0, 255).astype(np.uint8)

    equalized = cv2.LUT(image_u8, lut)
    result[mask] = equalized[mask]
    return result



def orient_normal_down(normal): 
    normal = normal / np.linalg.norm(normal)
    if np.dot(normal, [0, 0, -1]) < 0:
        normal = -normal
    return normal


def fit_plane(pcd_raw, label, nb_neighbors=100, std_ratio=2.0, distance_threshold=0.01, ransac_n=8, num_iterations=2000):

    # --- Outlier removal ---     
    cleaned, _ = pcd_raw.remove_statistical_outlier(nb_neighbors=nb_neighbors,
                                                     std_ratio=std_ratio)    
    n_before = len(pcd_raw.points)
    n_after  = len(cleaned.points)
    print(f"[{label}] Before: {n_before}  →  After: {n_after}  (removed {n_before - n_after})")

    # --- Plane fit ---
    pm, inl = cleaned.segment_plane(distance_threshold=distance_threshold, ransac_n=ransac_n,
                                     num_iterations=num_iterations)
    a_, b_, c_, d_ = pm
    nv = orient_normal_down(np.array([a_, b_, c_]))
    print(f"[{label}]  normal: {nv}")

    inlier_cloud = cleaned.select_by_index(inl)
    bbox   = inlier_cloud.get_axis_aligned_bounding_box()
    center = bbox.get_center()
    extent = bbox.get_extent()

    z_ = nv / np.linalg.norm(nv)
    h  = np.array([1, 0, 0]) if abs(z_[0]) < 0.9 else np.array([0, 1, 0])
    x_ = np.cross(h, z_);  x_ /= np.linalg.norm(x_)
    y_ = np.cross(z_, x_); y_ /= np.linalg.norm(y_)

    orig_n = np.array([a_, b_, c_])
    dist   = (np.dot(orig_n, center) + d_) / np.linalg.norm(orig_n)
    pc     = center - dist * (orig_n / np.linalg.norm(orig_n))

    half = max(extent) * 0.6
    g    = np.linspace(-half, half, 20)
    gx, gy = np.meshgrid(g, g)
    plane_pts = pc + gx.reshape(-1, 1) * x_ + gy.reshape(-1, 1) * y_

    plane_pcd = o3d.geometry.PointCloud()
    plane_pcd.points = o3d.utility.Vector3dVector(plane_pts)    

    return cleaned, pm, nv, plane_pcd, inlier_cloud


def estimate_grasp_pose_v2(
    cleaned_pcd,
    plane_model,
    plane_model_bg,
    normal_vector,
    box,
    cloud,
    masked_bg_pcd,
    H,
    W,
    plane_pcd_bg,
    label="Object",
    top_thresh=0.5,
    visualize=True,
):
    """
        ENHANCED GRASP POSE ESTIMATOR (v2)

        Inputs:
            cleaned_pcd       — cleaned object point cloud
            plane_model       — [a, b, c, d] plane of the object's top surface
            plane_model_bg    — [a, b, c, d] background/support plane
            normal_vector     — normal vector of the object's top surface
            box               — 2D minAreaRect corners (np.int32, shape (4,2))
            cloud             — organized point cloud (H, W, 3)
            H, W              — organized cloud dimensions
            plane_pcd_bg      — background plane point cloud (for visualization)
            label             — object name (for printed output)
            top_thresh        — threshold for top-surface inliers (mm)
            visualize         — whether to show Open3D visualization

        Returns:
            dict with keys: grasp_pose, center_3d, quat, obj_height,
                                            grasp_x, grasp_y, grasp_z, rot_matrix,
                                            edge0, edge1, top_pcd
    """

        # 1) Top surface — RANSAC plane inliers
    obj_pts = np.asarray(cleaned_pcd.points)
    [a_h, b_h, c_h, d_h] = plane_model

        # Distance of each point from the fitted plane
    n_obj       = np.array([a_h, b_h, c_h])
    n_obj_norm  = n_obj / np.linalg.norm(n_obj)
    distances   = np.abs(obj_pts @ n_obj + d_h) / np.linalg.norm(n_obj)

        # Inliers = points close to the top surface
    TOP_THRESH  = top_thresh  # mm
    top_mask    = distances < TOP_THRESH
    top_pts     = obj_pts[top_mask]

    top_pcd = o3d.geometry.PointCloud()
    top_pcd.points = o3d.utility.Vector3dVector(top_pts)
    top_pcd.paint_uniform_color([1.0, 0.0, 0.0])  # red = top-surface inliers

    outlier_pts = obj_pts[~top_mask]
    outlier_pcd = o3d.geometry.PointCloud()
    outlier_pcd.points = o3d.utility.Vector3dVector(outlier_pts)
    outlier_pcd.paint_uniform_color([0.5, 0.5, 0.5])  # gray = remaining points

    print(f"[{label}] Top surface: {len(top_pts)} inliers out of {len(obj_pts)} points")

        # 2) Object height = distance from top surface to background plane
    [a_b, b_b, c_b, d_b] = plane_model_bg
    n_bg      = np.array([a_b, b_b, c_b])
    n_bg_norm = n_bg / np.linalg.norm(n_bg)

        # Mean distance of top-surface inliers from the background plane
    dist_to_bg   = np.abs(top_pts @ n_bg + d_b) / np.linalg.norm(n_bg)
    obj_height_v2 = np.mean(dist_to_bg)

    print(f"[{label}] Object height (mean top→bg distance): {obj_height_v2:.2f} mm")
    print(f"  (min: {dist_to_bg.min():.2f}, max: {dist_to_bg.max():.2f}, std: {dist_to_bg.std():.2f})")

        # 3) Center = centroid of top-surface inliers
    center_3d_v2 = top_pts.mean(axis=0)
    print(f"\n[{label}] Center (centroid of top inliers): {center_3d_v2}")

        # 4) 3D dimensions from the bounding box
    corners_3d_v2 = []
    for (u, v) in box:
        u, v = int(round(u)), int(round(v))
        u = np.clip(u, 0, W - 1)
        v = np.clip(v, 0, H - 1)
        p = cloud[v, u]
        if np.isfinite(p).all() and not np.allclose(p, 0):
            corners_3d_v2.append(p)
    corners_3d_v2 = np.array(corners_3d_v2)

    edge0 = np.linalg.norm(corners_3d_v2[1] - corners_3d_v2[0])
    edge1 = np.linalg.norm(corners_3d_v2[2] - corners_3d_v2[1])
    print(f"[{label}] 3D box dimensions: {edge0:.2f} x {edge1:.2f} mm")

    # 5) Orientation — X parallel to a bounding-box edge
    # Z = top-surface normal (gripper approach direction)
    grasp_z_v2 = normal_vector / np.linalg.norm(normal_vector)

    # X = 3D box-edge direction, orthogonalized with respect to Z
    raw_x = (corners_3d_v2[1] - corners_3d_v2[0]).astype(float)
    raw_x /= np.linalg.norm(raw_x)

    # Remove the Z component so X lies in the plane perpendicular to Z
    grasp_x_v2 = raw_x - np.dot(raw_x, grasp_z_v2) * grasp_z_v2
    grasp_x_v2 /= np.linalg.norm(grasp_x_v2)

    # Y = Z × X  (right-handed coordinate system)
    grasp_y_v2 = np.cross(grasp_z_v2, grasp_x_v2)
    grasp_y_v2 /= np.linalg.norm(grasp_y_v2)

    # Final correction: X = Y × Z
    grasp_x_v2 = np.cross(grasp_y_v2, grasp_z_v2)
    grasp_x_v2 /= np.linalg.norm(grasp_x_v2)

    # Rotation matrix → quaternion
    rot_mat_v2 = np.column_stack([grasp_x_v2, grasp_y_v2, grasp_z_v2])
    quat_v2    = Rotation.from_matrix(rot_mat_v2).as_quat()  # [x, y, z, w]

    print(f"\n{'='*50}")
    print(f"[{label}] GRASP POSE v2:")
    print(f"  Position:    ({center_3d_v2[0]:.2f}, {center_3d_v2[1]:.2f}, {center_3d_v2[2]:.2f})")
    print(f"  Quaternion:  (x={quat_v2[0]:.4f}, y={quat_v2[1]:.4f}, z={quat_v2[2]:.4f}, w={quat_v2[3]:.4f})")
    print(f"  Object h.:   {obj_height_v2:.2f} mm")
    print(f"  X (edge):    {grasp_x_v2}")
    print(f"  Y (normal):  {grasp_y_v2}")
    print(f"  Z (surface): {grasp_z_v2}")
    print(f"{'='*50}")

    # ROS Pose message
    grasp_pose_v2 = Pose()
    grasp_pose_v2.position = Point(
        x=float(center_3d_v2[0]),
        y=float(center_3d_v2[1]),
        z=float(center_3d_v2[2])
    )
    grasp_pose_v2.orientation = Quaternion(
        x=float(quat_v2[0]), y=float(quat_v2[1]),
        z=float(quat_v2[2]), w=float(quat_v2[3])
    )

    # 6) Visualization
    if visualize:
        # Grasp frame
        ax_len = max(edge0, edge1) * 0.5
        frame_pts = [
            center_3d_v2,
            center_3d_v2 + grasp_x_v2 * ax_len,
            center_3d_v2 + grasp_y_v2 * ax_len,
            center_3d_v2 + grasp_z_v2 * ax_len,
        ]
        frame_ls_v2 = o3d.geometry.LineSet()
        frame_ls_v2.points = o3d.utility.Vector3dVector(np.array(frame_pts))
        frame_ls_v2.lines  = o3d.utility.Vector2iVector([[0,1],[0,2],[0,3]])
        frame_ls_v2.colors = o3d.utility.Vector3dVector([[1,0,0],[0,1,0],[0,0,1]])

        # Center point
        sphere_v2 = o3d.geometry.TriangleMesh.create_sphere(radius=1.5)
        sphere_v2.translate(center_3d_v2)
        sphere_v2.paint_uniform_color([1, 1, 0])

        # World frame
        coord = o3d.geometry.TriangleMesh.create_coordinate_frame(size=10, origin=[0,0,0])

        masked_bg_pcd.paint_uniform_color([0.7, 0.7, 0.7])

        print(f"\n[{label}] Visualization: red=top inliers, gray=rest, yellow=center, RGB=grasp frame")
        o3d.visualization.draw_geometries(
            [top_pcd, outlier_pcd, plane_pcd_bg, frame_ls_v2, sphere_v2, coord, masked_bg_pcd],
            window_name=f"Grasp Pose v2 — {label}"
        )

    return {
        "grasp_pose": grasp_pose_v2,
        "center_3d": center_3d_v2,
        "quat": quat_v2,
        "obj_height": obj_height_v2,
        "grasp_x": grasp_x_v2,
        "grasp_y": grasp_y_v2,
        "grasp_z": grasp_z_v2,
        "rot_matrix": rot_mat_v2,
        "edge0": edge0,
        "edge1": edge1,
        "top_pcd": top_pcd,
    }

def orient_normal_down(normal):

    normal = normal / np.linalg.norm(normal)

    down = np.array([0,0,-1])

    if np.dot(normal, down) < 0:
        normal = -normal

    return normal


def is_valid_point(p):
    if not np.isfinite(p).all():
        return False
    # (0,0,0) sometimes appears as invalid
    if np.allclose(p, 0):
        return False
    return True

def lookup_nearest_valid(cloud, u, v, r=3):
    H, W, _ = cloud.shape
    best = None
    best_d2 = 1e18
    for dv in range(-r, r+1):
        for du in range(-r, r+1):
            uu, vv = u + du, v + dv
            if 0 <= uu < W and 0 <= vv < H:
                p = cloud[vv, uu]
                if is_valid_point(p):
                    d2 = du*du + dv*dv
                    if d2 < best_d2:
                        best_d2 = d2
                        best = p
    if best is None:
        return np.array([np.nan, np.nan, np.nan], dtype=np.float32), False
    return best.astype(np.float32), True


def map_path_2d_to_3d_robust(path_2d, cloud, search_radius=3):
    H, W, _ = cloud.shape
    path3d = []
    valid = []
    for (u, v) in path_2d:
        u = int(round(u)); v = int(round(v))
        if not (0 <= u < W and 0 <= v < H):
            path3d.append([np.nan, np.nan, np.nan]); valid.append(False); continue

        p = cloud[v, u]
        if is_valid_point(p):
            path3d.append(p); valid.append(True)
        else:
            p2, ok = lookup_nearest_valid(cloud, u, v, r=search_radius)
            path3d.append(p2); valid.append(ok)

    return np.asarray(path3d, np.float32), np.asarray(valid, bool)


def pixel_to_3d(cloud, u, v, search_radius=3):
    H, W, _ = cloud.shape
    u = int(round(u)); v = int(round(v))
    if not (0 <= u < W and 0 <= v < H):
        return np.array([np.nan, np.nan, np.nan], dtype=np.float32), False

    p = cloud[v, u]
    if is_valid_point(p):
        return p.astype(np.float32), True

    return lookup_nearest_valid(cloud, u, v, r=search_radius)


def map_lines_2d_to_3d(lines_2d, cloud, search_radius=3):
    """
    lines_2d: list[((u0,v0),(u1,v1)), ...]
    returns:
      lines_3d: list[((X0,Y0,Z0),(X1,Y1,Z1)), ...] only valid pairs
      invalid:  list[index] indices that could not be mapped
    """
    lines_3d = []
    invalid = []

    for i, ((u0, v0), (u1, v1)) in enumerate(lines_2d):
        p0, ok0 = pixel_to_3d(cloud, u0, v0, search_radius)
        p1, ok1 = pixel_to_3d(cloud, u1, v1, search_radius)

        if ok0 and ok1:
            lines_3d.append((p0, p1))
        else:
            invalid.append(i)

    return lines_3d, invalid


def _normal_to_quaternion(normal: np.ndarray) -> np.ndarray:
    """
    Build a quaternion whose Z-axis aligns with *normal*.
    X and Y are chosen arbitrarily (but orthonormal).
    Returns [qx, qy, qz, qw].
    """
    z_axis = normal / np.linalg.norm(normal)

    helper = np.array([1.0, 0.0, 0.0]) if abs(z_axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    x_axis = np.cross(helper, z_axis)
    x_axis /= np.linalg.norm(x_axis)

    y_axis = np.cross(z_axis, x_axis)
    y_axis /= np.linalg.norm(y_axis)

    rot_matrix = np.column_stack([x_axis, y_axis, z_axis])
    return Rotation.from_matrix(rot_matrix).as_quat()  # [x, y, z, w]


def generate_zigzag_pose_array(
    box_2d: np.ndarray,
    cloud: np.ndarray,
    normal_vector: np.ndarray,
    spacing: float = 10.0,
    z_offset: float = 0.0,
    search_radius: int = 5,
    frame_id: str = "base_link",
) -> tuple[PoseArray, np.ndarray]:
    """
    Compute a 3D zigzag scan pattern inside a fitted 2D rectangle and
    return it as a ROS PoseArray (Z-axis aligned with *normal_vector*).

    Parameters
    ----------
    box_2d : np.ndarray, shape (4, 2)
        Corners of the fitted rectangle in pixel coords (from cv2.boxPoints).
    cloud : np.ndarray, shape (H, W, 3)
        Organized point cloud used for 2D → 3D back-projection.
    normal_vector : np.ndarray, shape (3,)
        Surface normal — becomes the Z-axis of every pose.
    spacing : float
        Pixel distance between zigzag rows.
    z_offset : float
        Offset along the normal vector (in cloud units, e.g. mm).
        Positive values move poses away from the surface.
    search_radius : int
        Neighbourhood radius for nearest-valid-point lookup.
    frame_id : str
        ROS frame_id for the PoseArray header.

    Returns
    -------
    pose_array : PoseArray
        Poses along the zigzag path (only finite points).
    path3d : np.ndarray, shape (N, 3)
        Raw 3D points (may contain NaN where lookup failed).
    """
    # --- 1) 2D zigzag inside the polygon ---
    poly = Polygon(box_2d)
    minx, miny, maxx, maxy = poly.bounds

    lines_clipped = []
    y = miny
    while y <= maxy:
        line = LineString([(minx - 100, y), (maxx + 100, y)])
        clipped = poly.intersection(line)
        if not clipped.is_empty:
            lines_clipped.append(clipped)
        y += spacing

    path_2d = []
    reverse = False
    for seg in lines_clipped:
        coords = list(seg.coords)
        if reverse:
            coords.reverse()
        path_2d.extend(coords)
        reverse = not reverse

    if len(path_2d) == 0:
        raise Exception("Zigzag path is empty — box may be degenerate.")

    # --- 2) Map to 3D ---
    path3d, valid = map_path_2d_to_3d_robust(path_2d, cloud, search_radius=search_radius)

    # --- 3) Build PoseArray ---
    quat = _normal_to_quaternion(normal_vector)
    n_unit = normal_vector / np.linalg.norm(normal_vector)
    offset_vec = n_unit * z_offset

    pose_array = PoseArray()
    pose_array.header = Header()
    pose_array.header.frame_id = frame_id

    for pt, ok in zip(path3d, valid):
        if not ok or not np.isfinite(pt).all():
            continue
        pt_off = pt + offset_vec
        pose = Pose()
        pose.position = Point(x=float(pt_off[0]), y=float(pt_off[1]), z=float(pt_off[2]))
        pose.orientation = Quaternion(
            x=float(quat[0]), y=float(quat[1]),
            z=float(quat[2]), w=float(quat[3]),
        )
        pose_array.poses.append(pose)

    print(f"[zigzag] {len(path_2d)} 2D pts → {valid.sum()} valid 3D pts → {len(pose_array.poses)} poses")

    return pose_array, path3d

def offset_pose_by_vector(pose: Pose, offset: np.ndarray) -> Pose:
    """
    Return a new Pose obtained by translating the input pose by *offset* in the pose's local frame.

    Parameters
    ----------
    pose : Pose
        Original pose to be offset.
    offset : np.ndarray, shape (3,)
        Translation vector in the local frame of the pose (e.g., [0, 0, 10] to move 10mm along Z).

    Returns
    -------
    Pose
        New Pose translated by the given offset.
    """
    q = [pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w]
    rot = Rotation.from_quat(q).as_matrix()
    offset_world = rot @ offset

    new_pose = Pose()
    new_pose.position.x = pose.position.x + offset_world[0]
    new_pose.position.y = pose.position.y + offset_world[1]
    new_pose.position.z = pose.position.z + offset_world[2]
    new_pose.orientation = Quaternion(
        x=pose.orientation.x, y=pose.orientation.y,
        z=pose.orientation.z, w=pose.orientation.w,
    )

    return new_pose


def generate_cone_poses(
    reference_pose: Pose,
    radius: float,
    n_poses: int = 3,
    cone_apex_z: float = 0.0,
    start_angle_deg: float = 0.0,
) -> list[Pose]:
    """
    Generate *n_poses* poses arranged on a circle in the local XY plane of
    *reference_pose*, with each pose's Z-axis pointing toward a common apex
    on the reference Z-axis — forming a cone.

    Parameters
    ----------
    reference_pose : Pose
        The central reference frame.  The circle lies in its local XY plane
        and the cone apex lies on its local Z-axis.
    radius : float
        Radius of the circle (same units as position, e.g. mm).
    n_poses : int
        Number of evenly-spaced poses on the circle (default 3 → 120° apart).
    cone_apex_z : float
        Distance along the reference local Z-axis where the cone apex is.
        * 0   → all Z-axes point at the reference origin (flat cone).
        * > 0 → apex is *above* the circle (steeper cone / more vertical).
        * < 0 → apex is *below* (inverted cone).
    start_angle_deg : float
        Starting angle in degrees (0 = local +X direction).

    Returns
    -------
    list[Pose]
        Poses on the circle, each with Z-axis aimed at the apex.
        X-axis is tangent to the circle (CCW), Y completes a right-handed frame.
    """
    # Reference frame
    q_ref = [
        reference_pose.orientation.x, reference_pose.orientation.y,
        reference_pose.orientation.z, reference_pose.orientation.w,
    ]
    R_ref = Rotation.from_quat(q_ref).as_matrix()
    p_ref = np.array([
        reference_pose.position.x,
        reference_pose.position.y,
        reference_pose.position.z,
    ])

    # Cone apex in world frame
    apex_local = np.array([0.0, 0.0, cone_apex_z])
    apex_world = p_ref + R_ref @ apex_local

    poses: list[Pose] = []
    for i in range(n_poses):
        theta = np.deg2rad(start_angle_deg + i * 360.0 / n_poses)

        # --- Position on the circle (local → world) ---
        local_pos = np.array([radius * np.cos(theta), radius * np.sin(theta), 0.0])
        world_pos = p_ref + R_ref @ local_pos

        # --- Z-axis: point from circle position toward the apex ---
        z_axis = apex_world - world_pos
        z_norm = np.linalg.norm(z_axis)
        if z_norm < 1e-12:
            # Degenerate (radius ≈ 0): fall back to reference Z
            z_axis = R_ref[:, 2].copy()
        else:
            z_axis /= z_norm

        # --- X-axis: tangent to the circle (CCW), orthogonalised to Z ---
        local_tangent = np.array([-np.sin(theta), np.cos(theta), 0.0])
        world_tangent = R_ref @ local_tangent
        x_axis = world_tangent - np.dot(world_tangent, z_axis) * z_axis
        x_norm = np.linalg.norm(x_axis)
        if x_norm < 1e-12:
            # Fallback: pick any vector perpendicular to Z
            helper = np.array([1.0, 0.0, 0.0]) if abs(z_axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
            x_axis = np.cross(helper, z_axis)
        x_axis /= np.linalg.norm(x_axis)

        # --- Y-axis: complete right-handed frame ---
        y_axis = np.cross(z_axis, x_axis)
        y_axis /= np.linalg.norm(y_axis)

        # Re-orthogonalise X for numerical safety
        x_axis = np.cross(y_axis, z_axis)
        x_axis /= np.linalg.norm(x_axis)

        # Rotate X and Y by 180° around Z (flip both)
        x_axis = -x_axis
        y_axis = -y_axis

        # --- Build Pose ---
        rot_mat = np.column_stack([x_axis, y_axis, z_axis])
        quat = Rotation.from_matrix(rot_mat).as_quat()  # [x, y, z, w]

        pose = Pose()
        pose.position = Point(x=float(world_pos[0]), y=float(world_pos[1]), z=float(world_pos[2]))
        pose.orientation = Quaternion(x=float(quat[0]), y=float(quat[1]), z=float(quat[2]), w=float(quat[3]))
        poses.append(pose)

    return poses


def visualize_zigzag_poses(
    pose_array: PoseArray,
    path3d: np.ndarray,
    pcd: o3d.geometry.PointCloud | None = None,
    axis_length: float = 5.0,
    every_n: int = 1,
    window_name: str = "Zigzag Pose Visualization",
):
    """
    Visualize a PoseArray as small RGB coordinate frames together with
    the zigzag trajectory and an optional background point cloud.

    Parameters
    ----------
    pose_array : PoseArray
        The poses to draw (output of generate_zigzag_pose_array).
    path3d : np.ndarray, shape (N, 3)
        Raw 3D zigzag path (used for the trajectory line).
    pcd : o3d.geometry.PointCloud, optional
        Background point cloud to render alongside.
    axis_length : float
        Length of each pose axis arrow (in cloud units, e.g. mm).
    every_n : int
        Show every n-th pose frame (1 = all).
    window_name : str
        Open3D window title.
    """
    # --- Build frame LineSet ---
    pts = []
    line_idx = []
    line_colors = []

    for i, pose in enumerate(pose_array.poses):
        if i % every_n != 0:
            continue

        pos = np.array([pose.position.x, pose.position.y, pose.position.z])
        q = [pose.orientation.x, pose.orientation.y,
             pose.orientation.z, pose.orientation.w]
        rot = Rotation.from_quat(q).as_matrix()

        base = len(pts)
        pts.append(pos)
        pts.append(pos + rot[:, 0] * axis_length)  # X
        pts.append(pos + rot[:, 1] * axis_length)  # Y
        pts.append(pos + rot[:, 2] * axis_length)  # Z

        line_idx  += [[base, base + 1], [base, base + 2], [base, base + 3]]
        line_colors += [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    frames_ls = o3d.geometry.LineSet()
    frames_ls.points = o3d.utility.Vector3dVector(np.array(pts))
    frames_ls.lines  = o3d.utility.Vector2iVector(np.array(line_idx))
    frames_ls.colors = o3d.utility.Vector3dVector(np.array(line_colors))

    # --- Trajectory line ---
    finite_mask = np.isfinite(path3d).all(axis=1)
    clean_pts = path3d[finite_mask]
    traj_lines = [[i, i + 1] for i in range(len(clean_pts) - 1)]

    traj_ls = o3d.geometry.LineSet()
    traj_ls.points = o3d.utility.Vector3dVector(clean_pts)
    traj_ls.lines  = o3d.utility.Vector2iVector(traj_lines)
    traj_ls.colors = o3d.utility.Vector3dVector([[1, 0.5, 0]] * len(traj_lines))  # orange

    # --- World frame ---
    world_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=30, origin=[0, 0, 0])

    geometries = [frames_ls, traj_ls, world_frame]
    if pcd is not None:
        pcd.paint_uniform_color([0.6, 0.6, 0.6])
        geometries.insert(0, pcd)

    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name=window_name)
    for g in geometries:
        vis.add_geometry(g)

    opt = vis.get_render_option()
    opt.point_size = 1
    opt.line_width = 5

    vis.run()
    vis.destroy_window()

    shown = sum(1 for i in range(len(pose_array.poses)) if i % every_n == 0)
    print(f"[zigzag-viz] Displayed {shown} pose frames, trajectory {len(clean_pts)} pts")




    
