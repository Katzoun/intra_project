from setuptools import find_packages, setup

package_name = 'intranodes_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tomas Janousek',
    maintainer_email='tomas.janousek02@gmail.com',
    description='INTRANodes for INTRA robotic application',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            f'camera_controller_node_exec = {package_name}.camera_controller_node:main',
            f'robot_controller_node_exec = {package_name}.robot_controller_node:main',
            f'vision_processing_node_exec = {package_name}.vision_processing_node:main',
            f'motion_planning_node_exec = {package_name}.motion_planning_node:main',
            f'tool_controller_node_exec = {package_name}.tool_controller_node:main',
            f'test_robot_action_exec = {package_name}.test_robot_action_client:main',
            f'coordinator_node_exec = {package_name}.coordinator_node:main',
        ],
    },
)
