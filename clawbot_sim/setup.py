from setuptools import setup

setup(
    name="clawbot_sim", version="0.1.0", packages=["clawbot_sim"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/clawbot_sim"]),
        ("share/clawbot_sim", ["package.xml"]),
    ],
    entry_points={"console_scripts": ["fake_inputs = clawbot_sim.fake_inputs:main"]},
)
