from setuptools import setup
import os
from glob import glob

package_name = 'workcell_pkg'


setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'urdf'), glob('urdf/*')),
        (os.path.join('share', package_name, 'meshes'), glob('meshes/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tomas Janousek',
    maintainer_email='tomas.janousek02@gmail.com',
    description='Workcell description (camera/table/etc.)',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'spawn_collision_objects = workcell_pkg.spawn_collision_objects:main',
        ],
    },
)
