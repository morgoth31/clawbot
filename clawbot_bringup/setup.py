from glob import glob

from setuptools import setup

package_name = "clawbot_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
        ("share/" + package_name + "/urdf", glob("urdf/*.urdf")),
        ("share/" + package_name + "/maps", glob("maps/*")),
        ("share/" + package_name + "/scripts", glob("scripts/*.sh")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Clawbot",
    maintainer_email="jetson@clawbot.local",
    description="Point d'entree unique du robot : un fichier de lancement par unite (P14)",
    license="Proprietary",
    tests_require=["pytest"],
)
