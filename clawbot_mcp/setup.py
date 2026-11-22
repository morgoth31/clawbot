from setuptools import setup

package_name = "clawbot_mcp"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Clawbot",
    maintainer_email="jetson@clawbot.local",
    description="Serveur MCP du Clawbot : facade de l'executif (P10)",
    license="Proprietary",
    tests_require=["pytest"],
    entry_points={"console_scripts": ["server = clawbot_mcp.serveur:main"]},
)
