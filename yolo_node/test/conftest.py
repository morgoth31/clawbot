"""Un seul contexte rclpy pour toute la session de tests (leçon P08)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))          # pour importer le paquet `yolo_node`
os.environ.setdefault("ROS_DOMAIN_ID", "98")


@pytest.fixture(scope="session", autouse=True)
def contexte_ros():
    import rclpy

    if not rclpy.ok():
        rclpy.init()
    yield
