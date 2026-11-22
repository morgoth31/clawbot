from setuptools import setup

setup(
    name="clawbot_common", version="0.1.0", packages=["clawbot_common"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/clawbot_common"]),
        ("share/clawbot_common", ["package.xml", "share/clawbot_common/errors.json"]),
        ("share/clawbot_common/schemas",
         ["share/clawbot_common/schemas/failure_report.schema.json"]),
    ],
)
