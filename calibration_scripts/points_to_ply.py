"""Reads points from calib_poses1.txt (first 3 columns: x, y, z) and writes a PLY file."""

import sys
import os

def txt_to_ply(input_path, output_path):
    points = []
    with open(input_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3:
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                points.append((x, y, z))

    with open(output_path, "w") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("property uchar red\n")
        f.write("property uchar green\n")
        f.write("property uchar blue\n")
        f.write("end_header\n")
        for x, y, z in points:
            f.write(f"{x} {y} {z} 255 0 0\n")

    print(f"Wrote {len(points)} vertices to {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "calib_poses1.txt")
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.rsplit(".", 1)[0] + ".ply"
    txt_to_ply(input_file, output_file)
