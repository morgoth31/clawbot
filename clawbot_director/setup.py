from setuptools import setup

setup(name="clawbot_director", version="0.1.0", packages=["clawbot_director"],
      entry_points={"console_scripts": ["director_node = clawbot_director.director_node:main"]})
