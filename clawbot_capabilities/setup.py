from glob import glob

from setuptools import setup

package_name = "clawbot_capabilities"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Clawbot",
    maintainer_email="jetson@clawbot.local",
    description="Gestionnaire de capacites : liste blanche, conflits, etats (P07)",
    license="Proprietary",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "gestionnaire = clawbot_capabilities.gestionnaire:main",
        ],
    },
)
