from setuptools import setup

PACKAGE = "yolo_node"

setup(
    name=PACKAGE,
    version="1.0.0",
    packages=[PACKAGE],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE}"]),
        (f"share/{PACKAGE}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    entry_points={"console_scripts": [
        "yolo_node = yolo_node.noeud:main",
    ]},
)
