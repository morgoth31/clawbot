from setuptools import setup

setup(
    name="clawbot_safety", version="0.1.0", packages=["clawbot_safety"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/clawbot_safety"]),
        ("share/clawbot_safety", ["package.xml"]),
        ("share/clawbot_safety/config", ["config/arbitrator.yaml"]),
    ],
    entry_points={"console_scripts": ["arbitrator = clawbot_safety.arbitrator:main"]},
)
