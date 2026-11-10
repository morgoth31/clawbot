"""Vues système factices : arbre de périphériques et graphe ROS 2 simulés.

Le test de santé lit le système par deux interfaces étroites (`DeviceView`, `GraphView`).
Les tests substituent ces vues : aucun accès au robot réel, aucun `rclpy`, aucune attente.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bridge_mcp.health import DeviceInfo, DeviceSnapshot, GraphSnapshot, Measurement


@dataclass
class FakeDeviceView:
    """Arbre de périphériques construit à la main."""

    usb: list[DeviceInfo] = field(default_factory=list)
    video: dict[str, str] = field(default_factory=dict)
    by_id: dict[str, str] = field(default_factory=dict)
    present: set[str] = field(default_factory=set)
    holders: dict[str, list[int]] = field(default_factory=dict)
    inputs: dict[str, str] = field(default_factory=dict)

    def snapshot(self) -> DeviceSnapshot:
        return DeviceSnapshot(
            usb=list(self.usb),
            video=dict(self.video),
            by_id=dict(self.by_id),
            present=set(self.present),
            holders={key: list(value) for key, value in self.holders.items()},
            inputs=dict(self.inputs),
        )


@dataclass
class FakeGraphView:
    """Graphe ROS 2 simulé : nœuds, cadences, TF."""

    nodes: list[str] = field(default_factory=list)
    topics: dict[str, Measurement] = field(default_factory=dict)
    tf_frames: set[str] = field(default_factory=set)
    calls: list[tuple[list[str], float]] = field(default_factory=list)

    def snapshot(self, topics: list[str], window_s: float) -> GraphSnapshot:
        self.calls.append((list(topics), window_s))
        return GraphSnapshot(
            nodes=list(self.nodes),
            topics={name: self.topics[name] for name in topics if name in self.topics},
            tf_frames=set(self.tf_frames),
            captured_at=1000.0,
        )


def measurement(**kwargs) -> Measurement:
    """Mesure ROS complète par défaut (topic vu, cadence et âge fournis)."""
    values = {"measured": True, "publishers": 1, "width": 640, "height": 480,
              "encoding": "rgb8", "frame_id": "camera_color_optical_frame"}
    values.update(kwargs)
    return Measurement(**values)


def healthy_robot() -> tuple[FakeDeviceView, FakeGraphView]:
    """Robot conforme aux mesures du 2026-11-10T08:06:06+08:00, lidar et manette absents."""
    device = FakeDeviceView(
        usb=[
            DeviceInfo(vid_pid="0c45:6340", product="USB 2.0 Camera", devpath="usb1/1-2.2.1"),
            DeviceInfo(vid_pid="2bc5:060f", product="ORBBEC Depth Sensor", devpath="usb1/1-2.2"),
            DeviceInfo(vid_pid="1a86:7523", product="CH340 serial converter", devpath="usb1/1-2.1"),
        ],
        video={"/dev/video0": "0c45:6340", "/dev/video1": "0c45:6340"},
        by_id={"usb-1a86_USB_Serial-if00-port0": "/dev/ttyUSB1"},
        present={"/dev/video0", "/dev/ttyUSB1", "/dev/myserial"},
        holders={"/dev/ttyUSB1": [5976]},
    )
    graph = FakeGraphView(
        nodes=["/camera/camera", "/driver_node", "/hardware_service_node"],
        topics={
            "/camera/color/image_raw": measurement(rate_hz=20.077, age_s=0.01),
            "/camera/depth/image_raw": measurement(rate_hz=30.007, age_s=0.02, encoding="16UC1"),
            "/imu/data_raw": measurement(rate_hz=9.999, age_s=0.03, width=None, height=None,
                                         encoding=None, frame_id="imu_link",
                                         sample={"quaternion_norm": 1.0}),
            "/voltage": measurement(rate_hz=9.999, age_s=0.04, width=None, height=None,
                                    encoding=None, frame_id=None, sample={"voltage_v": 11.9}),
            "/camera/detection_image": measurement(rate_hz=5.0, age_s=0.2),
        },
        tf_frames={"camera_link", "camera_color_frame", "base_link", "odom", "map"},
    )
    return device, graph
