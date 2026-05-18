import pandas as pd
import numpy as np

if __name__ == "__main__":
    # Load the two files into pandas DataFrames
    df1 = pd.read_csv("calib_poses1.txt", delim_whitespace=True, header=None)
    df2 = pd.read_csv("campoints6.txt", delim_whitespace=True, header=None)

    # Convert DataFrames to numpy arrays
    poses = df1.to_numpy()
    campoints = df2.to_numpy()
    
    # from calib poses take first 7 columns and from camerapoints take columns 8 to 10
    poses1 = poses[:, :7]
    campoints = campoints[:, 7:10]

    # Merge the two arrays (stack them horizontally)
    merged_poses = np.hstack((poses1, campoints))

    # Save the merged array to a new text file
    np.savetxt("merged_calib_poses.txt", merged_poses, fmt="%.6f")

