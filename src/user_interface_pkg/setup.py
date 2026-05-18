from setuptools import find_packages, setup

package_name = 'user_interface_pkg'

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
    description='user_interface_pkg_desc',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'user_interface_node_exec = user_interface_pkg.user_interface_node:main',
        ],
    },
)
