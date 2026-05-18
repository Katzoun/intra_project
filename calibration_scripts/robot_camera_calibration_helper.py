import struct
import time
import json
from intranodes_pkg.robot_controller_interface import RWSInterface
import numpy as np
import os
import ament_index_python.packages
from ament_index_python.packages import get_package_share_directory


robotIP = "192.168.0.37"
username = "Admin"
password = "robotics"
port = 443 # real robot 443
directory = "calibration_scripts"

if __name__ == "__main__":

    try:
        print("Current Working Directory:", os.getcwd())
        os.makedirs(directory, exist_ok=True)
        iter = 0
        rwsInterface = RWSInterface(robotIP, username, password, port)
        rwsInterface.login()


        print("Logged in:", rwsInterface.get_login_state())

        clock = rwsInterface.get_clock()

        print("Mastership edit:", rwsInterface.is_master("edit"))

        input("Press enter to scan first pose")


        while True:
            #get robot position
            raw_json, _ = rwsInterface.get_robot_cartesian()
            raw = json.loads(raw_json)
            if isinstance(raw, list):
                raw = raw[0]
            pose = [float(raw[k]) for k in ('x', 'y', 'z', 'q1', 'q2', 'q3', 'q4')]
            print("Robot Cartesian Pose:", pose)
            
            #open or create new file and append last pose to file
            with open(os.path.join(directory, "calib_poses1.txt"), "a") as f:
                f.write(" ".join(f"{x:.6f}" for x in pose) + "\n")
    
            iter += 1
            print(f"Iteration: {iter}")

            input("Press Enter to continue...")
            print("Continuing...")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        rwsInterface.logout()