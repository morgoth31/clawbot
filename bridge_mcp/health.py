"""Test de santé des périphériques (exigences HLT-01 à HLT-18).

Le contrôle est en lecture seule : il ouvre des nœuds de périphérique, lit sysfs, et mesure des
topics ROS 2 dans une fenêtre partagée. Il ne publie rien, n'écrit aucun fichier et ne redémarre
aucune unité. Son résultat est un rapport JSON, envoyé à l'humain par Telegram (D-20, D-23) au
démarrage et à chaque anomalie émise par S1 (D-22) : aucune action locale n'est déclenchée.

Seuils de cadence : D-21 n'a pas été tranchée ; les valeurs utilisées sont celles proposées et
portent `provisional: true` dans le rapport.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

HEALTH_VERSION = "1.0"
WINDOW_S = 5.0
WARMUP_S = 1.5
MAX_REPORT_BYTES = 64 * 1024

#: D-22 : au démarrage et à chaque anomalie, jamais périodiquement.
RUN_POLICY = {"at_startup": True, "on_anomaly": True, "periodic_s": None}

#: D-20 : le rapport part vers l'humain ; aucune action locale, aucune relance.
ACTIONS_ON_FAILURE: tuple[str, ...] = ()

#: D-21 non tranchée : ces seuils sont provisoires et signalés comme tels.
PROVISIONAL = ("cadence: D-21 (proposition, non validée)",)

OK_RATIO = 0.80
DEGRADED_RATIO = 0.50
AGE_OK_PERIODS = 3.0
AGE_FAILED_PERIODS = 10.0

VOLTAGE_MIN_V = 11.0
VOLTAGE_MAX_V = 13.0
VOLTAGE_PHYSICAL_MIN_V = 8.0


# ---------------------------------------------------------------- instantanés
@dataclass(frozen=True)
class DeviceInfo:
    vid_pid: str
    product: str
    devpath: str


@dataclass
class DeviceSnapshot:
    """État des périphériques physiques à un instant donné."""

    usb: list[DeviceInfo] = field(default_factory=list)
    video: dict[str, str] = field(default_factory=dict)
    by_id: dict[str, str] = field(default_factory=dict)
    present: set[str] = field(default_factory=set)
    holders: dict[str, list[int]] = field(default_factory=dict)
    inputs: dict[str, str] = field(default_factory=dict)


@dataclass
class Measurement:
    """Mesure d'un topic ROS 2 dans la fenêtre d'observation."""

    measured: bool = False
    rate_hz: float | None = None
    age_s: float | None = None
    publishers: int = 0
    qos_incompatible: bool = False
    width: int | None = None
    height: int | None = None
    encoding: str | None = None
    frame_id: str | None = None
    sample: dict[str, Any] | None = None


@dataclass
class GraphSnapshot:
    """État du graphe ROS 2 et mesures associées."""

    nodes: list[str] = field(default_factory=list)
    topics: dict[str, Measurement] = field(default_factory=dict)
    tf_frames: set[str] = field(default_factory=set)
    captured_at: float = 0.0


# ------------------------------------------------------------------ inventaire
@dataclass(frozen=True)
class Peripheral:
    """Description déclarée d'un périphérique et des sondes qui s'y appliquent."""

    id: str
    name: str
    required: bool
    levels: tuple[str, ...]
    usb: tuple[str, ...] = ()
    by_id: str | None = None
    devices: tuple[str, ...] = ()
    node: str | None = None
    topic: str | None = None
    nominal_rate_hz: float | None = None
    expected_encoding: str | None = None
    expected_resolution: tuple[int, int] | None = None
    expected_frames: tuple[str, ...] = ()
    input_class: str | None = None
    http_url: str | None = None
    not_installed: bool = False


INVENTORY: tuple[Peripheral, ...] = (
    Peripheral(
        "PER-01", "camera couleur", True, ("device", "ros", "functional"),
        usb=("0c45:6340",), devices=("/dev/video0",), node="/camera/camera",
        topic="/camera/color/image_raw", nominal_rate_hz=20.0,
        expected_resolution=(640, 480),
    ),
    Peripheral(
        "PER-02", "camera profondeur", True, ("device", "ros", "functional"),
        usb=("2bc5:060f",), node="/camera/camera",
        topic="/camera/depth/image_raw", nominal_rate_hz=30.0,
        expected_encoding="16UC1", expected_resolution=(640, 480),
    ),
    Peripheral(
        "PER-03", "centrale inertielle", True, ("ros", "functional"),
        node="/driver_node", topic="/imu/data_raw", nominal_rate_hz=10.0,
    ),
    Peripheral(
        "PER-04", "carte de commande", True, ("device", "ros"),
        usb=("1a86:7523",), by_id="usb-1a86_USB_Serial-if00-port0",
        devices=("/dev/myserial",), node="/driver_node",
    ),
    Peripheral(
        "PER-05", "batterie", True, ("ros", "functional"),
        node="/driver_node", topic="/voltage", nominal_rate_hz=10.0,
    ),
    Peripheral(
        "PER-06", "lidar", True, ("device", "ros"),
        usb=("10c4:ea60",),
        by_id="usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0",
        devices=("/dev/ydlidar", "/dev/ttyUSB0"),
        topic="/scan", nominal_rate_hz=10.0,
    ),
    Peripheral(
        "PER-07", "manette", False, ("device",), input_class="joystick",
    ),
    Peripheral(
        "PER-08", "chaine de detection", False, ("http",),
        http_url="http://127.0.0.1:8003/health",
    ),
    Peripheral(
        "PER-09", "arbre TF", True, ("ros",),
        expected_frames=("base_link", "odom", "map"),
    ),
)

INVENTORY_BY_ID: dict[str, Peripheral] = {item.id: item for item in INVENTORY}


# ---------------------------------------------------------------------- vues
class SystemDeviceView:
    """Lecture réelle de l'arbre des périphériques (sysfs, /dev, /proc)."""

    def snapshot(self) -> DeviceSnapshot:
        usb = self._usb_devices()
        video = self._video_nodes()
        by_id = self._by_id_links()
        inputs = self._input_nodes()
        present = self._present(set(video) | set(inputs) | {value for value in by_id.values()})
        holders = {
            device: self._holders(device)
            for device in {value for value in by_id.values()}
        }
        return DeviceSnapshot(usb=usb, video=video, by_id=by_id, present=present,
                              holders=holders, inputs=inputs)

    # ------------------------------------------------------------------ USB
    @staticmethod
    def _usb_devices() -> list[DeviceInfo]:
        devices: list[DeviceInfo] = []
        root = Path("/sys/bus/usb/devices")
        if not root.is_dir():
            return devices
        for entry in sorted(root.iterdir()):
            try:
                vendor = (entry / "idVendor").read_text().strip()
                product = (entry / "idProduct").read_text().strip()
                name = (entry / "product").read_text().strip()
            except OSError:
                continue
            devices.append(DeviceInfo(f"{vendor}:{product}", name, entry.name))
        return devices

    @staticmethod
    def _video_nodes() -> dict[str, str]:
        """Associe chaque nœud V4L au couple VID:PID de son interface USB."""
        nodes: dict[str, str] = {}
        for entry in sorted(Path("/sys/class/video4linux").glob("video*")):
            device_path = f"/dev/{entry.name}"
            if not os.path.exists(device_path):
                continue
            vid_pid = SystemDeviceView._usb_parent_identity(entry)
            if vid_pid:
                nodes[device_path] = vid_pid
        return nodes

    @staticmethod
    def _usb_parent_identity(node: Path) -> str | None:
        current = node.resolve()
        for _ in range(6):
            current = current.parent
            try:
                vendor = (current / "idVendor").read_text().strip()
                product = (current / "idProduct").read_text().strip()
                return f"{vendor}:{product}"
            except OSError:
                continue
        return None

    @staticmethod
    def _input_nodes() -> dict[str, str]:
        """Nœuds d'entrée par classe : un joypad est identifié comme manette, pas par son index."""
        nodes: dict[str, str] = {}
        for path in sorted(Path("/dev/input").glob("js*")):
            nodes[str(path)] = "joystick"
        return nodes

    @staticmethod
    def _by_id_links() -> dict[str, str]:
        links: dict[str, str] = {}
        root = Path("/dev/serial/by-id")
        if not root.is_dir():
            return links
        for entry in sorted(root.iterdir()):
            try:
                links[entry.name] = str(entry.resolve())
            except OSError:
                continue
        return links

    @staticmethod
    def _present(paths: Iterable[str]) -> set[str]:
        present: set[str] = set()
        for path in paths:
            if os.path.exists(path):
                present.add(path)
                try:
                    present.add(str(Path(path).resolve()))
                except OSError:
                    pass
        return present

    @staticmethod
    def _holders(device: str) -> list[int]:
        """Processus ayant le périphérique ouvert (lecture de /proc, sans sous-processus)."""
        try:
            target = str(Path(device).resolve())
        except OSError:
            return []
        holders: list[int] = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            fd_dir = entry / "fd"
            try:
                for fd in fd_dir.iterdir():
                    try:
                        if os.readlink(fd) == target:
                            holders.append(int(entry.name))
                            break
                    except OSError:
                        continue
            except OSError:
                continue
        return sorted(holders)


class RosGraphView:
    """Mesure réelle du graphe ROS 2 dans une fenêtre unique, sans publication."""

    IMAGE_TOPICS = {"/camera/color/image_raw", "/camera/depth/image_raw", "/camera/detection_image"}

    def __init__(self, window_s: float = WINDOW_S) -> None:
        self._window_s = window_s

    def snapshot(self, topics: Sequence[str], window_s: float) -> GraphSnapshot:
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import Image, Imu, LaserScan
        from std_msgs.msg import Float32

        created = not rclpy.ok()
        if created:
            rclpy.init(args=None)
        counters: dict[str, int] = {name: 0 for name in topics}
        latest: dict[str, Any] = {}
        arrivals: dict[str, float] = {}
        stamps: dict[str, list[float]] = {name: [] for name in topics}
        frames: set[str] = set()

        node = Node("bridge_health_probe")
        try:
            for name in topics:
                callback = self._counter(counters, latest, arrivals, stamps, name)
                if name in self.IMAGE_TOPICS:
                    node.create_subscription(Image, name, callback, qos_profile_sensor_data)
                elif name == "/imu/data_raw":
                    node.create_subscription(Imu, name, callback, qos_profile_sensor_data)
                elif name == "/voltage":
                    node.create_subscription(Float32, name, callback, qos_profile_sensor_data)
                elif name == "/scan":
                    node.create_subscription(LaserScan, name, callback, qos_profile_sensor_data)

            from tf2_msgs.msg import TFMessage

            node.create_subscription(
                TFMessage, "/tf", lambda message: frames.update(
                    transform.child_frame_id for transform in message.transforms
                ), 50
            )
            if "/tf_static" in dict(node.get_topic_names_and_types()):
                node.create_subscription(
                    TFMessage, "/tf_static", lambda message: frames.update(
                        transform.child_frame_id for transform in message.transforms
                    ), 50
                )

            # Découverte DDS : les premiers messages ne comptent pas, sinon la cadence
            # mesurée reflète le délai d'appairage et non le débit du topic.
            discovery_deadline = time.monotonic() + min(WARMUP_S, window_s / 2)
            while time.monotonic() < discovery_deadline:
                rclpy.spin_once(node, timeout_sec=0.05)
            for name in topics:
                counters[name] = 0
                stamps[name].clear()
            latest.clear()
            arrivals.clear()

            start = time.monotonic()
            while time.monotonic() - start < window_s:
                rclpy.spin_once(node, timeout_sec=0.05)
            elapsed = max(1e-6, time.monotonic() - start)
            nodes = node.get_node_names()
            publishers = {
                name: len(node.get_publishers_info_by_topic(name)) for name in topics
            }
        finally:
            node.destroy_node()
            if created:
                rclpy.shutdown()

        measurements: dict[str, Measurement] = {}
        for name in topics:
            message = latest.get(name)
            if message is None:
                measurements[name] = Measurement(measured=False, publishers=publishers.get(name, 0))
                continue
            arrival_age = (
                None if name not in arrivals else max(0.0, time.time() - arrivals[name])
            )
            # Cadence sur l'intervalle réellement couvert par les messages reçus : immunisée
            # contre le retard d'appairage DDS et contre la fin de fenêtre.
            series = stamps[name]
            if len(series) >= 2 and series[-1] > series[0]:
                rate = (len(series) - 1) / (series[-1] - series[0])
            else:
                rate = counters[name] / elapsed
            measurements[name] = self._measurement(
                message, rate, publishers.get(name, 0), name, arrival_age
            )
        return GraphSnapshot(nodes=list(nodes), topics=measurements, tf_frames=frames,
                             captured_at=time.time())

    @staticmethod
    def _counter(counters: dict[str, int], latest: dict[str, Any],
                 arrivals: dict[str, float], stamps: dict[str, list[float]], name: str):
        def callback(message: Any) -> None:
            counters[name] += 1
            latest[name] = message
            now = time.time()
            arrivals[name] = now
            stamps[name].append(now)

        return callback

    @staticmethod
    def _measurement(message: Any, rate_hz: float, publishers: int, name: str,
                     arrival_age: float | None = None) -> Measurement:
        stamp = getattr(getattr(message, "header", None), "stamp", None)
        age_s = arrival_age
        if stamp is not None:
            age_s = max(0.0, time.time() - (stamp.sec + stamp.nanosec / 1e9))
        sample: dict[str, Any] = {}
        if name == "/voltage":
            sample = {"voltage_v": float(message.data)}
        elif name == "/imu/data_raw":
            orientation = message.orientation
            norm = (orientation.x ** 2 + orientation.y ** 2 + orientation.z ** 2 + orientation.w ** 2) ** 0.5
            sample = {"quaternion_norm": round(norm, 4)}
        return Measurement(
            measured=True,
            rate_hz=round(rate_hz, 3),
            age_s=None if age_s is None else round(age_s, 3),
            publishers=publishers,
            width=getattr(message, "width", None),
            height=getattr(message, "height", None),
            encoding=getattr(message, "encoding", None),
            frame_id=getattr(getattr(message, "header", None), "frame_id", None),
            sample=sample or None,
        )


# ------------------------------------------------------------------ contrôle
def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(epoch))


def _rate_verdict(rate_hz: float | None, nominal: float | None) -> tuple[str, str | None]:
    if rate_hz is None or nominal is None:
        return "failed", "HLT-E-TOPIC-SILENT"
    if rate_hz < DEGRADED_RATIO * nominal:
        return "failed", "HLT-E-RATE-LOW"
    if rate_hz < OK_RATIO * nominal:
        return "degraded", "HLT-E-RATE-LOW"
    return "ok", None


def _age_verdict(age_s: float | None, period_s: float) -> tuple[str, str | None]:
    if age_s is None:
        return "failed", "HLT-E-TOPIC-SILENT"
    if age_s > AGE_FAILED_PERIODS * period_s:
        return "failed", "HLT-E-TOPIC-SILENT"
    if age_s > AGE_OK_PERIODS * period_s:
        return "degraded", "HLT-E-TOPIC-SILENT"
    return "ok", None


def _worst(statuses: Iterable[str]) -> str:
    order = ["failed", "degraded", "unavailable", "skipped", "ok"]
    present = [status for status in statuses if status in order]
    if not present:
        return "unavailable"
    return min(present, key=order.index)


class HealthChecker:
    """Exécute les sondes de l'inventaire et produit le rapport."""

    def __init__(self, *, device_view: Any, graph_view: Any, now: Any = time.time,
                 inventory: Sequence[Peripheral] = INVENTORY) -> None:
        self._device_view = device_view
        self._graph_view = graph_view
        self._now = now
        self._inventory = tuple(inventory)

    def run(self, **extra: Any) -> dict[str, Any]:
        started = time.monotonic()
        devices: DeviceSnapshot = self._device_view.snapshot()
        topics = [item.topic for item in self._inventory if item.topic]
        graph: GraphSnapshot = self._graph_view.snapshot(topics, WINDOW_S)
        checked_at = _iso(self._now())

        peripherals = [self._evaluate(item, devices, graph, checked_at) for item in self._inventory]
        required = [item for item in peripherals if item["required"]]
        verdict = _worst(item["verdict"] for item in required)

        report: dict[str, Any] = {
            "health_version": HEALTH_VERSION,
            "checked_at": checked_at,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "verdict": verdict,
            "ros": {"domain_id": os.environ.get("ROS_DOMAIN_ID", "inconnu"),
                    "node_count": len(graph.nodes)},
            "peripherals": peripherals,
            "unavailable": [
                f"{item['id']} {item['name']}: HLT-E-NOT-INSTALLED"
                for item in peripherals
                if item["verdict"] == "unavailable"
            ],
            "provisional": list(PROVISIONAL),
            "actions_taken": list(ACTIONS_ON_FAILURE),
            "spec_refs": ["HLT-01", "HLT-03", "HLT-04", "HLT-09"],
        }
        report.update(extra)
        return self._bound(report)

    # ------------------------------------------------------------ évaluation
    def _evaluate(self, peripheral: Peripheral, devices: DeviceSnapshot,
                  graph: GraphSnapshot, checked_at: str) -> dict[str, Any]:
        if peripheral.not_installed:
            probes = [self._probe(f"{peripheral.id}/device", "device", "unavailable", {},
                                  {"installed": False}, checked_at, "HLT-E-NOT-INSTALLED",
                                  "périphérique déclaré non installé sur ce robot")]
        else:
            probes = []
            if peripheral.http_url:
                probes.append(self._http_probe(peripheral, checked_at))
            if "device" in peripheral.levels:
                probes.append(self._device_probe(peripheral, devices, checked_at))
            if "ros" in peripheral.levels:
                probes.append(self._ros_probe(peripheral, graph, checked_at))
            if "functional" in peripheral.levels:
                functional = self._functional_probe(peripheral, graph, checked_at)
                if functional is not None:
                    probes.append(functional)

        return {
            "id": peripheral.id,
            "name": peripheral.name,
            "required": peripheral.required,
            "verdict": _worst(probe["status"] for probe in probes),
            "identity": self._identity(peripheral, devices),
            "probes": probes,
        }

    @staticmethod
    def _probe(identifier: str, level: str, status: str, observed: dict[str, Any],
               threshold: dict[str, Any], measured_at: str, error_code: str | None = None,
               detail: str = "") -> dict[str, Any]:
        return {
            "probe": identifier,
            "level": level,
            "status": status,
            "observed": observed,
            "threshold": threshold,
            "measured_at": measured_at,
            "error_code": error_code,
            "detail": detail,
        }

    @staticmethod
    def _identity(peripheral: Peripheral, devices: DeviceSnapshot) -> dict[str, Any]:
        device: str | None = None
        if peripheral.input_class:
            found = sorted(path for path, kind in devices.inputs.items() if kind == peripheral.input_class)
            return {"usb": None, "device": found[0] if found else None}
        if peripheral.by_id and peripheral.by_id in devices.by_id:
            device = devices.by_id[peripheral.by_id]
        if device is None and peripheral.devices:
            resolved = HealthChecker._resolve_video(peripheral, devices)
            device = resolved[0][0] if resolved else next(
                (path for path in peripheral.devices if path in devices.present), None
            )
        return {"usb": peripheral.usb[0] if peripheral.usb else None, "device": device}

    @staticmethod
    def _resolve_video(peripheral: Peripheral, devices: DeviceSnapshot) -> list[tuple[str, str]]:
        return sorted(
            (path, vid_pid) for path, vid_pid in devices.video.items() if vid_pid in peripheral.usb
        )

    def _device_probe(self, peripheral: Peripheral, devices: DeviceSnapshot,
                      checked_at: str) -> dict[str, Any]:
        identifier = f"{peripheral.id}/device"

        if peripheral.input_class:
            found = sorted(
                path for path, kind in devices.inputs.items() if kind == peripheral.input_class
            )
            return self._probe(identifier, "device", "ok" if found else "failed",
                               {"devices": found}, {"class": peripheral.input_class}, checked_at,
                               None if found else "HLT-E-DEVICE-ABSENT",
                               "" if found else "aucune manette presente sur le bus d'entree")

        if peripheral.devices and not peripheral.usb and not peripheral.by_id:
            present = any(path in devices.present for path in peripheral.devices)
            detail = "" if present else "aucun périphérique d'entrée déclaré"
            return self._probe(identifier, "device", "ok" if present else "failed",
                               {"present": present}, {"present": True}, checked_at,
                               None if present else "HLT-E-DEVICE-ABSENT", detail)

        if peripheral.by_id:
            resolved = devices.by_id.get(peripheral.by_id)
            present = resolved is not None and resolved in devices.present
            if not present:
                return self._probe(identifier, "device", "failed", {"present": False},
                                   {"by_id": peripheral.by_id}, checked_at,
                                   "HLT-E-DEVICE-ABSENT", "lien by-id non résolu")
            holders = devices.holders.get(resolved, [])
            identity_ok = any(info.vid_pid in peripheral.usb for info in devices.usb) if peripheral.usb else True
            if not identity_ok:
                return self._probe(identifier, "device", "failed",
                                   {"device": resolved, "holders": holders},
                                   {"usb": list(peripheral.usb)}, checked_at,
                                   "HLT-E-IDENTITY-MISMATCH", "identité USB de la carte non conforme")
            if len(holders) > 1:
                return self._probe(identifier, "device", "failed",
                                   {"device": resolved, "holders": holders},
                                   {"max_holders": 1}, checked_at,
                                   "HLT-E-USED-BY-OTHER", "port tenu par plusieurs processus")
            status = "ok" if holders else "degraded"
            return self._probe(identifier, "device", status,
                               {"device": resolved, "holders": holders}, {"min_holders": 1},
                               checked_at, None,
                               "" if holders else "port présent mais ouvert par aucun processus")

        if peripheral.usb and not peripheral.devices:
            found = [info for info in devices.usb if info.vid_pid in peripheral.usb]
            return self._probe(identifier, "device", "ok" if found else "failed",
                               {"usb_present": [info.vid_pid for info in found]},
                               {"usb": list(peripheral.usb)}, checked_at,
                               None if found else "HLT-E-DEVICE-ABSENT",
                               "" if found else "aucune interface USB de cette identité")

        resolved = self._resolve_video(peripheral, devices)
        if resolved:
            return self._probe(identifier, "device", "ok",
                               {"device": resolved[0][0], "usb": resolved[0][1]},
                               {"usb": list(peripheral.usb)}, checked_at)

        for path in peripheral.devices:
            if path in devices.video:
                return self._probe(identifier, "device", "failed",
                                   {"device": path, "usb": devices.video[path]},
                                   {"usb": list(peripheral.usb)}, checked_at,
                                   "HLT-E-IDENTITY-MISMATCH",
                                   f"{path} porte une autre identité")
        return self._probe(identifier, "device", "failed", {"device": None},
                           {"usb": list(peripheral.usb)}, checked_at,
                           "HLT-E-DEVICE-ABSENT", "aucun nœud ne correspond à l'identité déclarée")

    def _http_probe(self, peripheral: Peripheral, checked_at: str) -> dict[str, Any]:
        """Point d'entrée HTTP : la chaîne de détection expose son état hors ROS."""
        import urllib.error
        import urllib.request

        identifier = f"{peripheral.id}/http"
        url = peripheral.http_url or ""
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            return self._probe(identifier, "http", "failed", {"http_status": error.code},
                               {"http_status": 200}, checked_at, "HLT-E-UNAVAILABLE",
                               f"le point d'entrée répond {error.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            return self._probe(identifier, "http", "failed", {"http_status": None},
                               {"http_status": 200}, checked_at, "HLT-E-UNAVAILABLE",
                               f"point d'entrée injoignable ({type(error).__name__})")
        return self._probe(identifier, "http", "ok" if status == 200 else "failed",
                           {"http_status": status}, {"http_status": 200}, checked_at,
                           None if status == 200 else "HLT-E-UNAVAILABLE")

    def _ros_probe(self, peripheral: Peripheral, graph: GraphSnapshot,
                   checked_at: str) -> dict[str, Any]:
        identifier = f"{peripheral.id}/ros"

        if peripheral.expected_frames:
            missing = [frame for frame in peripheral.expected_frames if frame not in graph.tf_frames]
            status = "failed" if missing else "ok"
            return self._probe(identifier, "ros", status,
                               {"frames_present": sorted(graph.tf_frames), "missing": missing},
                               {"required_frames": list(peripheral.expected_frames)}, checked_at,
                               "HLT-E-NODE-ABSENT" if missing else None,
                               f"cadres absents : {', '.join(missing)}" if missing else "")

        if peripheral.node and peripheral.topic is None:
            known = {name.lstrip("/") for name in graph.nodes}
            present = peripheral.node.lstrip("/") in known
            return self._probe(identifier, "ros", "ok" if present else "failed",
                               {"node": peripheral.node, "present": present},
                               {"present": True}, checked_at,
                               None if present else "HLT-E-NODE-ABSENT",
                               "" if present else f"{peripheral.node} absent du graphe")

        measurement = graph.topics.get(peripheral.topic or "")
        if measurement is None or not measurement.measured:
            return self._probe(identifier, "ros", "failed",
                               {"rate_hz": None, "age_s": None, "publishers": 0},
                               {"min_rate_hz": (peripheral.nominal_rate_hz or 0) * OK_RATIO},
                               checked_at, "HLT-E-TOPIC-SILENT",
                               f"aucun message sur {peripheral.topic} dans la fenêtre")

        period = 1.0 / peripheral.nominal_rate_hz if peripheral.nominal_rate_hz else 0.0
        rate_status, rate_code = _rate_verdict(measurement.rate_hz, peripheral.nominal_rate_hz)
        age_status, age_code = _age_verdict(measurement.age_s, period) if period else ("ok", None)
        status = _worst([rate_status, age_status])
        threshold = {"min_rate_hz": round((peripheral.nominal_rate_hz or 0) * OK_RATIO, 3),
                     "max_age_s": round(AGE_OK_PERIODS * period, 3)}
        return self._probe(identifier, "ros", status,
                           {"rate_hz": measurement.rate_hz, "age_s": measurement.age_s,
                            "publishers": measurement.publishers},
                           threshold, checked_at, rate_code or age_code)

    def _functional_probe(self, peripheral: Peripheral, graph: GraphSnapshot,
                          checked_at: str) -> dict[str, Any] | None:
        topic_name = peripheral.topic or ""
        measurement = graph.topics.get(topic_name)
        if measurement is None or not measurement.measured:
            return None  # déjà déclaré par la sonde ROS : pas de doublon

        identifier = f"{peripheral.id}/functional"
        observed: dict[str, Any] = {}
        threshold: dict[str, Any] = {}

        if peripheral.expected_resolution:
            observed["resolution"] = (
                [measurement.width, measurement.height]
                if measurement.width is not None else None
            )
            threshold["resolution"] = list(peripheral.expected_resolution)
        if peripheral.expected_encoding:
            observed["encoding"] = measurement.encoding
            threshold["encoding"] = peripheral.expected_encoding
        if peripheral.id == "PER-03":
            norm = (measurement.sample or {}).get("quaternion_norm")
            observed["quaternion_norm"] = norm
            threshold["quaternion_norm"] = [0.95, 1.05]
        if peripheral.id == "PER-05":
            volt = (measurement.sample or {}).get("voltage_v")
            observed["voltage_v"] = volt
            threshold["voltage_v"] = [VOLTAGE_MIN_V, VOLTAGE_MAX_V]

        status, code, detail = "ok", None, ""
        if peripheral.expected_resolution and list(peripheral.expected_resolution) != observed.get("resolution"):
            status, code = "failed", "HLT-E-FRAME-INVALID"
            detail = "résolution inattendue"
        if peripheral.expected_encoding and peripheral.expected_encoding != observed.get("encoding"):
            status, code = "failed", "HLT-E-FRAME-INVALID"
            detail = "encodage inattendu"
        if peripheral.id == "PER-03":
            norm = observed.get("quaternion_norm")
            if norm is None or not 0.95 <= norm <= 1.05:
                status, code, detail = "failed", "HLT-E-FRAME-INVALID", "quaternion non normalisé"
        if peripheral.id == "PER-05":
            volt = observed.get("voltage_v")
            if volt is None or not VOLTAGE_PHYSICAL_MIN_V <= volt <= VOLTAGE_MAX_V:
                status, code, detail = "failed", "HLT-E-FRAME-INVALID", "tension hors plage physique"
            elif volt < VOLTAGE_MIN_V:
                status, code, detail = "degraded", None, "tension sous le seuil (D-06 provisoire)"

        return self._probe(identifier, "functional", status, observed, threshold, checked_at, code, detail)

    @staticmethod
    def _bound(report: dict[str, Any]) -> dict[str, Any]:
        rendered = json.dumps(report, ensure_ascii=False)
        if len(rendered.encode()) <= MAX_REPORT_BYTES:
            return report
        report["peripherals"] = report["peripherals"][:5]
        report["unavailable"].append(f"rapport tronque: {len(rendered)} octets")
        return report


def exit_code_for(report: dict[str, Any]) -> int:
    """HLT-12 : code de sortie correspondant au verdict."""
    return {"ok": 0, "degraded": 1, "failed": 2}.get(str(report.get("verdict")), 0)


def build_default_checker() -> HealthChecker:
    """Contrôleur sur le robot réel : périphériques, graphe ROS 2, horloge système."""
    return HealthChecker(device_view=SystemDeviceView(), graph_view=RosGraphView())


def run_and_notify(notifier: Any, *, reason: str, device_view: Any | None = None,
                   graph_view: Any | None = None, now: Any = time.time) -> dict[str, Any]:
    """Exécute le contrôle et envoie le statut à l'humain (D-20, D-22, D-23)."""
    checker = (
        HealthChecker(device_view=device_view, graph_view=graph_view, now=now)
        if device_view is not None and graph_view is not None
        else build_default_checker()
    )
    report = checker.run(reason=reason)
    notifier.send_report(report, reason=reason)
    return report


def main(argv: Sequence[str] | None = None, *, device_view: Any | None = None,
         graph_view: Any | None = None, now: Any = time.time,
         notifier: Any | None = None) -> int:
    """Interface ligne de commande du test de santé (HLT-12)."""
    parser = argparse.ArgumentParser(prog="bridge_mcp.health", description="Test de santé des périphériques")
    parser.add_argument("--json", action="store_true", help="écrit le rapport JSON sur la sortie standard")
    parser.add_argument("--notify", dest="notify", action="store_true", help="envoie le statut par Telegram")
    parser.add_argument("--no-notify", dest="notify", action="store_false", help="n'envoie rien")
    parser.add_argument("--reason", default="demarrage", help="motif de l'exécution")
    parser.add_argument(
        "--service-mode",
        action="store_true",
        help="sort 0 si le contrôle a pu être exécuté, même si le verdict est `failed` "
             "(pour ne pas marquer l'unité systemd en échec à chaque démarrage)",
    )
    parser.set_defaults(notify=False)
    args = parser.parse_args(list(argv) if argv is not None else None)

    checker = (
        HealthChecker(device_view=device_view, graph_view=graph_view, now=now)
        if device_view is not None and graph_view is not None
        else build_default_checker()
    )
    report = checker.run(reason=args.reason)

    if args.notify:
        from bridge_mcp import notify as notify_module

        sender = notifier if notifier is not None else notify_module.TelegramNotifier()
        delivery = sender.send_report(report, reason=args.reason)
        report["notification"] = {"delivered": delivery.delivered, "status": delivery.status}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_human_summary(report))

    if args.service_mode:
        return 0
    return exit_code_for(report)


def _human_summary(report: dict[str, Any]) -> str:
    lines = [f"verdict {report['verdict']} — {len(report['peripherals'])} périphériques"]
    for item in report["peripherals"]:
        lines.append(f"  {item['id']} {item['name']:<24} {item['verdict']}")
    notification = report.get("notification")
    if notification:
        lines.append(f"notification: {notification['status']} (livre={notification['delivered']})")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
