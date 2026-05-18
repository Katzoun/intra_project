#!/bin/bash

echo "Starting build process..."

source /opt/ros/humble/setup.bash
source .venv/bin/activate
echo '=== CURRENT PYTHON PATH ==='
which python
echo '=== BUILDING ROS2 PACKAGES ==='

python -m colcon build --packages-select interface_pkg 
python -m colcon build --packages-select core_pkg --symlink-install
python -m colcon build --packages-select intranodes_pkg --symlink-install 
python -m colcon build --packages-select user_interface_pkg --symlink-install 
python -m colcon build --packages-select robotarm_pkg --symlink-install
python -m colcon build --packages-select robotarm_moveit_pkg
python -m colcon build --packages-select workcell_pkg --symlink-install 
python -m colcon build --packages-select intra_launch_pkg --symlink-install 



# Source the workspace setup script
source install/setup.bash

echo "ROS 2 packages built and workspace setup complete."