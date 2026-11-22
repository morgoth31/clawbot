from setuptools import setup
import os
from glob import glob
package_name = 'yahboomcar_description'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share',package_name,'launch'),glob(os.path.join('launch','*launch.py'))),
        (os.path.join('share',package_name,'urdf'),glob(os.path.join('urdf','*.*'))),
        # P13 : les maillages sont dans des sous-dossiers (X3plus/visual, X3plus/collision,
        # mecanum, sensor) et le glob de premier niveau n'en installait AUCUN. MoveIt
        # chargeait donc un modele sans geometrie de collision : il planifiait dans un
        # monde vide et ne pouvait rien proteger. Une entree par dossier, sans glob
        # recursif (setup.py n'en connait pas).
        (os.path.join('share',package_name,'meshes'),glob(os.path.join('meshes','*.*'))),
        (os.path.join('share',package_name,'meshes/mecanum'),glob(os.path.join('meshes/mecanum','*.*'))),
        (os.path.join('share',package_name,'meshes/sensor'),glob(os.path.join('meshes/sensor','*.*'))),
        (os.path.join('share',package_name,'meshes/X3plus/visual'),glob(os.path.join('meshes/X3plus/visual','*.*'))),
        (os.path.join('share',package_name,'meshes/X3plus/collision'),glob(os.path.join('meshes/X3plus/collision','*.*'))),
        (os.path.join('share',package_name,'rviz'),glob(os.path.join('rviz','*.rviz*'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='nx-ros2',
    maintainer_email='nx-ros2@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        "test": ["pytest"],
    },
    entry_points={
        'console_scripts': [
        ],
    },
)
