"""Nœud `yolo_node` : détection dans le graphe, sur GPU, à la demande (P12).

Abonnement `/wrist_camera/image_raw` en profondeur 1 et BEST_EFFORT (REQ-PERC-014),
publication `vision_msgs/Detection2DArray` sur `/perception/detections`, JSON de
compatibilité sur `/detections` (REQ-PERC-012), image annotée seulement s'il y a un
abonné (REQ-PERC-013). La façade HTTP 8003 tourne dans un thread du même processus.
"""
from __future__ import annotations

import json
import threading
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import (HistoryPolicy, QoSProfile, ReliabilityPolicy,
                       qos_profile_sensor_data)
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from .backend import charger_backend
from .posttraitement import DerniereImage, json_detections, nms, vers_detection2d_array

QOS_IMAGE = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                       history=HistoryPolicy.KEEP_LAST)


class YoloNode(Node):
    def __init__(self, backend=None) -> None:
        """`backend` permet d'injecter un backend factice en test (paramètre `backend`
        sinon). Sans cette injection, un test unitaire chargerait torch et échouerait sur
        l'environnement, pas sur le code."""
        super().__init__("yolo_node")
        self.declare_parameter("max_rate_hz", 5.0)
        self.declare_parameter("conf_min", 0.25)
        self.declare_parameter("backend", "torch")
        self.declare_parameter("modele", "/home/jetson/software/yolov5-7.0/yolov5s.pt")
        self.declare_parameter("http_port", 0)

        self.max_rate_hz = float(self.get_parameter("max_rate_hz").value)
        self.backend = backend if backend is not None else charger_backend(
            self.get_parameter("backend").value, self.get_parameter("modele").value)
        self.tampon = DerniereImage()
        self._derniere_inference_ms = 0
        self._inferences = 0

        self.pub_detections = self.create_publisher(Detection2DArray,
                                                    "/perception/detections", 10)
        self.pub_json = self.create_publisher(String, "/detections", 10)
        self.pub_image = self.create_publisher(CompressedImage,
                                               "/camera/detection_image", 2)

        self.sub_image = self.create_subscription(Image, "/wrist_camera/image_raw",
                                                  self._sur_image, QOS_IMAGE)
        periode = 1.0 / max(self.max_rate_hz, 0.1)
        self.timer = self.create_timer(periode, self._tick)

        port = int(self.get_parameter("http_port").value)
        if port:
            self._demarrer_http(port)
        self.get_logger().info(
            f"yolo_node pret : backend={self.backend.nom} max_rate_hz={self.max_rate_hz}")

    # ── image ────────────────────────────────────────────────────────────────
    def _sur_image(self, message: Image) -> None:
        image = vers_bgr(message.data, message.height, message.width, message.encoding)
        if image is None:
            return
        self.tampon.deposer((image, message.header), time.monotonic())

    # ── inférence ────────────────────────────────────────────────────────────
    def infere(self, image) -> list:
        debut = time.monotonic()
        detections = nms(self.backend.inferer(image))
        self._derniere_inference_ms = round((time.monotonic() - debut) * 1000)
        self._inferences += 1
        return detections

    def _tick(self) -> None:
        if not self.tampon.a_traiter():
            return
        couple, _ = self.tampon.prendre()
        image, entete = couple
        detections = self.infere(image)

        self.pub_json.publish(String(data=json_detections(detections)))
        self.pub_detections.publish(
            vers_detection2d_array(detections, entete, image.shape[1], image.shape[0]))

        if doit_encoder(self.pub_image.get_subscription_count()):     # REQ-PERC-013
            from .serveur_http import annoter
            ok, tampon = cv2.imencode(".jpg", annoter(image, detections),
                                      [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                message = CompressedImage()
                message.header = entete
                message.format = "jpeg"
                message.data = tampon.tobytes()
                self.pub_image.publish(message)

    # ── HTTP ─────────────────────────────────────────────────────────────────
    def derniere_image(self):
        if self.tampon._image is None:      # noqa: SLF001 — état partagé du tampon
            return None
        return self.tampon._image[0]

    def _demarrer_http(self, port: int) -> None:
        from .serveur_http import creer_application, servir

        application = creer_application(self.infere, self.derniere_image)
        fil = threading.Thread(target=servir, args=(application, port), daemon=True)
        fil.start()
        self.get_logger().info(f"façade HTTP sur le port {port}")


def vers_bgr(donnees, hauteur: int, largeur: int, encodage: str):
    """Convertit un message Image en BGR 8 bits à 3 canaux, quel que soit son encodage.

    La caméra du poignet publie en `yuv422` (2 octets par pixel) : un simple
    `reshape(h, w, -1)` donne 2 canaux et l'inférence lève « expected input[1, 2,
    480, 640] to have 3 channels » (constaté au déploiement du 2026-11-22).
    """
    if not hauteur or not largeur:
        return None
    tampon = np.frombuffer(donnees, dtype=np.uint8)
    if encodage in ("rgb8", "bgr8"):
        try:
            image = tampon.reshape(hauteur, largeur, 3)
        except ValueError:
            return None
        return image if encodage == "bgr8" else cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if encodage in ("mono8",):
        try:
            gris = tampon.reshape(hauteur, largeur)
        except ValueError:
            return None
        return cv2.cvtColor(gris, cv2.COLOR_GRAY2BGR)
    if encodage in ("mono16", "16UC1", "rgb16"):
        try:
            gris16 = tampon.view(np.uint16).reshape(hauteur, largeur)
        except ValueError:
            return None
        return cv2.cvtColor(cv2.convertScaleAbs(gris16, alpha=255.0 / 65535.0),
                            cv2.COLOR_GRAY2BGR)
    if encodage in ("yuv422", "yuyv", "yuv422_yuy2"):
        try:
            yuyv = tampon.reshape(hauteur, largeur, 2)
        except ValueError:
            return None
        return cv2.cvtColor(yuyv, cv2.COLOR_YUV2BGR_YUYV)
    # dernier recours : 2 octets par pixel supposé YUYV
    try:
        return cv2.cvtColor(tampon.reshape(hauteur, largeur, 2), cv2.COLOR_YUV2BGR_YUYV)
    except ValueError:
        return None


def doit_encoder(n_abonnes: int) -> bool:
    """L'image annotée n'est encodée que s'il y a un abonné (REQ-PERC-013)."""
    return n_abonnes > 0


def main() -> int:
    """Point d'entrée ; tout se règle par paramètres ROS (`--ros-args -p http_port:=8003`)."""
    rclpy.init()
    noeud = YoloNode()
    try:
        rclpy.spin(noeud)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        noeud.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
