from setuptools import setup

setup(name="clawbot_base_driver", version="0.1.0",
      packages=["clawbot_base_driver"],
      entry_points={"console_scripts": ["driver_node = clawbot_base_driver.base_driver:main"]})
