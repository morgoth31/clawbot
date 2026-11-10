from setuptools import setup

package_name = 'clawbot_arm_controller'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/arm_controller.launch.py']),
        ('share/' + package_name + '/config', ['config/arm_controller.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Clawbot',
    maintainer_email='jetson@clawbot.local',
    description='Serveur d action FollowJointTrajectory du bras Clawbot X3 Plus',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'arm_trajectory_server = clawbot_arm_controller.arm_trajectory_server:main',
        ],
    },
)
