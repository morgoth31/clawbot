from setuptools import setup

setup(name="clawbot_sentinel", version="0.1.0", packages=["clawbot_sentinel"],
      entry_points={"console_scripts": ["sentinel = clawbot_sentinel.sentinel_node:main"]})
