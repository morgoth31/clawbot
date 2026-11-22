from setuptools import setup

setup(
    name="clawbot_health", version="0.1.0", packages=["clawbot_health"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/clawbot_health"]),
        ("share/clawbot_health", ["package.xml"]),
        ("share/clawbot_health/config", ["config/expected_flows.yaml"]),
    ],
    entry_points={"console_scripts": ["health_monitor = clawbot_health.health_monitor:main"]},
)
