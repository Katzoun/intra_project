# Grasp pose estimation result for a single detected object

string label

# Grasp pose (position + orientation quaternion)
geometry_msgs/Pose grasp_pose

# 3D center of the object's top surface (centroid of inliers) [mm]
float64[3] center_3d

# Orientation quaternion [x, y, z, w]
float64[4] quaternion

# Object height above the background plane [mm]
float64 obj_height

# Grasp frame axes (unit vectors)
float64[3] grasp_x
float64[3] grasp_y
float64[3] grasp_z

# Rotation matrix (3x3, row-major)
float64[9] rot_matrix

# 3D bounding box edge lengths [mm]
float64 edge0
float64 edge1
