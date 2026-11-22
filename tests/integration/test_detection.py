"""Intégration : images fixes → détections publiées (domaine 99, backend factice)."""
from __future__ import annotations

import time

import numpy as np
import pytest
import rclpy
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray

pytestmark = pytest.mark.integration


@pytest.mark.req("REQ-PERC-010")
def test_images_fixes_produisent_des_detections():
    from yolo_node.backend import BackendFactice
    from yolo_node.noeud import YoloNode

    if not rclpy.ok():
        rclpy.init()
    noeud = YoloNode(backend=BackendFactice())
    receptions = []

    espion = rclpy.create_node("espion_detections_p12")
    espion.create_subscription(Detection2DArray, "/perception/detections",
                               lambda message: receptions.append(message), 10)
    editeur = espion.create_publisher(Image, "/wrist_camera/image_raw", 2)
    try:
        for _ in range(40):
            rclpy.spin_once(espion, timeout_sec=0.05)
            image = Image()
            image.width, image.height = 640, 480
            image.encoding = "rgb8"
            image.step = 640 * 3
            image.data = np.zeros((480, 640, 3), dtype=np.uint8).tobytes()
            editeur.publish(image)
            rclpy.spin_once(noeud, timeout_sec=0.05)
            if receptions:
                break
            time.sleep(0.02)
        assert receptions, "aucune Detection2DArray publiée"
        detection = receptions[-1].detections[0]
        assert detection.results[0].hypothesis.class_id == "bottle"
        assert detection.results[0].hypothesis.score > 0.5
    finally:
        espion.destroy_node()
        noeud.destroy_node()
