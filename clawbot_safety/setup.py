from setuptools import setup
setup(name="clawbot_safety", version="0.1.0", packages=["clawbot_safety"],
      entry_points={"console_scripts": ["arbitrator = clawbot_safety.arbitrator:main"]})
