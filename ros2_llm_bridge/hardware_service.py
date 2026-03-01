#!/usr/bin/env python3
"""
Clawbot Hardware Service — runs on the Jetson host (port 8001).

All hardware control goes through ROS 2 topics (domain 28) so that the
driver_node (Mcnamu_driver_X3) keeps EXCLUSIVE access to /dev/myserial.
This is the only way to have working odometry.

  Motion   → /cmd_vel          (geometry_msgs/Twist)
  Servos   → /servo_ctrl       (std_msgs/Int32MultiArray)
  Buzzer   → /Buzzer           (std_msgs/Bool)
  LEDs     → /RGBLight         (std_msgs/Int32)
  Battery  ← /voltage          (std_msgs/Float32)
  Camera   → OpenCV direct     (/dev/video0, /dev/video2)
"""

import asyncio
import base64
import json
import subprocess
import logging
import os
import threading
import time

import cv2
import numpy as np
import uvicorn
import yaml as _yaml
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# ROS 2
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import CompressedImage, Imu
from std_msgs.msg import Bool, Float32, Int32, Int32MultiArray, String

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [hardware_service] %(levelname)s %(message)s",
)
logger = logging.getLogger("hardware_service")

# ── Safety limits ───────────────────────────────────────────────────────────
MAX_LINEAR_MS  = float(os.getenv("MAX_LINEAR_MS",  "0.5"))
MAX_ANGULAR_RS = float(os.getenv("MAX_ANGULAR_RS", "1.5"))
MOTION_WATCHDOG_S = float(os.getenv("MOTION_WATCHDOG_S", "1.5"))

SAFETY_FILE     = "/tmp/lidar_safety.json"
SAFETY_MAX_AGE  = 2.0
LIDAR_REQUIRED  = os.getenv("LIDAR_SAFETY_REQUIRED", "true").lower() != "false"

# ── ROS 2 domain ────────────────────────────────────────────────────────────
ROS_DOMAIN_ID = int(os.getenv("ROS_DOMAIN_ID", "28"))

# ── Camera devices ──────────────────────────────────────────────────────────
CAMERA_DEVICES = {
    "front": int(os.getenv("CAMERA_FRONT_INDEX", "0")),
    "claw":  int(os.getenv("CAMERA_CLAW_INDEX",  "2")),
}
WORKSPACE = os.getenv("WORKSPACE_PATH", "/home/jetson/.openclaw/workspace")


# ── ROS 2 node ──────────────────────────────────────────────────────────────

class HardwareNode(Node):
    """ROS2 node for hardware control and sensor data aggregation.

    Publishers:
        /cmd_vel       — robot velocity commands
        /servo_ctrl    — arm servo angle commands
        /Buzzer        — buzzer on/off
        /RGBLight      — LED colour

    Subscribers:
        /voltage       — battery voltage (V)
        /imu/data_raw  — accelerometer + gyroscope
        /vel_raw       — current measured velocity (vx, vy, angular)
    """

    def __init__(self):
        super().__init__("hardware_service_node")
        best_effort = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        # ── Publishers ────────────────────────────────────────────────────
        self.cmd_vel_pub = self.create_publisher(Twist,          "/cmd_vel",    10)
        self.servo_pub   = self.create_publisher(Int32MultiArray, "/servo_ctrl", 10)
        self.buzzer_pub  = self.create_publisher(Bool,            "/Buzzer",     10)
        self.rgb_pub     = self.create_publisher(Int32,           "/RGBLight",   10)

        # ── Sensor state ──────────────────────────────────────────────────
        self.battery_volt = 0.0

        # IMU — real accelerometer + gyroscope data from driver
        self.imu_accel   = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.imu_gyro    = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.imu_stamp   = 0.0

        # Velocity — measured by wheel encoders (Rosmaster internal)
        self.vel_vx      = 0.0
        self.vel_vy      = 0.0
        self.vel_angular = 0.0
        self.vel_stamp   = 0.0

        # Servo angles — last commanded value per ID (1-indexed, IDs 1-6)
        # Actual read-back requires direct serial access (conflicts with driver)
        # so we track the last commanded angle as an approximation.
        self.servo_angles: dict[int, int] = {i: -1 for i in range(1, 7)}

        # ── Subscriptions ─────────────────────────────────────────────────
        self.create_subscription(Float32, "/voltage",      self._bat_cb,  best_effort)
        self.create_subscription(Imu,     "/imu/data_raw", self._imu_cb,  best_effort)
        self.create_subscription(Twist,   "/vel_raw",      self._vel_cb,  best_effort)

        # SLAM map — transient-local so we get the last published map on connect
        map_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.map_data: OccupancyGrid | None = None
        self.map_stamp: float = 0.0
        self.create_subscription(OccupancyGrid, "/map", self._map_cb, map_qos)

        # YOLO detection feed — optional, only active when yolo-detector is running
        self.yolo_frame_bytes: bytes | None = None
        self.yolo_detections: list = []
        self.yolo_stamp: float = 0.0
        self.create_subscription(
            CompressedImage, "/camera/detection_image", self._yolo_img_cb, best_effort
        )
        self.create_subscription(
            String, "/detections", self._yolo_det_cb, best_effort
        )

        self.get_logger().info(f"HardwareNode ready on domain {ROS_DOMAIN_ID}")

    def _bat_cb(self, msg: Float32) -> None:
        """Update battery voltage from /voltage topic."""
        self.battery_volt = msg.data

    def _imu_cb(self, msg: Imu) -> None:
        """Update IMU state from /imu/data_raw topic."""
        a = msg.linear_acceleration
        g = msg.angular_velocity
        self.imu_accel = {"x": round(a.x, 3), "y": round(a.y, 3), "z": round(a.z, 3)}
        self.imu_gyro  = {"x": round(g.x, 4), "y": round(g.y, 4), "z": round(g.z, 4)}
        self.imu_stamp = time.time()

    def _vel_cb(self, msg: Twist) -> None:
        """Update measured velocity from /vel_raw topic."""
        self.vel_vx      = round(msg.linear.x,  4)
        self.vel_vy      = round(msg.linear.y,  4)
        self.vel_angular = round(msg.angular.z, 4)
        self.vel_stamp   = time.time()

    def _map_cb(self, msg: OccupancyGrid) -> None:
        """Store latest occupancy grid from /map topic."""
        self.map_data  = msg
        self.map_stamp = time.time()

    def _yolo_img_cb(self, msg: CompressedImage) -> None:
        """Cache latest YOLO annotated image from /camera/detection_image."""
        self.yolo_frame_bytes = bytes(msg.data)
        self.yolo_stamp = time.time()

    def _yolo_det_cb(self, msg: String) -> None:
        """Cache latest YOLO detections JSON from /detections."""
        try:
            import json as _json
            self.yolo_detections = _json.loads(msg.data)
        except Exception:
            self.yolo_detections = []


ros_node: HardwareNode | None = None
_last_motion_t: float = 0.0


def _watchdog_thread():
    while True:
        time.sleep(0.3)
        if ros_node is None:
            continue
        if _last_motion_t > 0 and (time.time() - _last_motion_t) > MOTION_WATCHDOG_S:
            try:
                ros_node.cmd_vel_pub.publish(Twist())
            except Exception:
                pass


def _ros_spin():
    rclpy.spin(ros_node)


# ── FastAPI ──────────────────────────────────────────────────────────────────

app = FastAPI(title="Clawbot Hardware Service", version="2.0.0")


@app.on_event("startup")
async def startup():
    global ros_node
    os.environ["ROS_DOMAIN_ID"] = str(ROS_DOMAIN_ID)
    rclpy.init()
    ros_node = HardwareNode()
    threading.Thread(target=_ros_spin, daemon=True).start()
    threading.Thread(target=_watchdog_thread, daemon=True).start()
    logger.info("ROS 2 node spinning (domain %d)", ROS_DOMAIN_ID)


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "ros2": ros_node is not None,
        "domain_id": ROS_DOMAIN_ID,
        "cameras": CAMERA_DEVICES,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clamp(v: float, lim: float) -> float:
    return max(-lim, min(lim, v))


def _lidar_ok(vx: float, vy: float) -> tuple[bool, str]:
    if not LIDAR_REQUIRED:
        return True, "safety disabled (LIDAR_SAFETY_REQUIRED=false)"
    try:
        with open(SAFETY_FILE) as f:
            data = json.load(f)
    except Exception:
        return False, "LiDAR safety file missing — motion blocked."
    age = time.time() - data.get("timestamp", 0)
    if age > SAFETY_MAX_AGE:
        return False, f"LiDAR data stale ({age:.1f}s) — motion blocked."
    safe = data.get("safe_to_move", {})
    dist = data.get("distances", {})
    checks = [
        (vx >  0.001, "forward",  "front"),
        (vx < -0.001, "backward", "back"),
        (vy >  0.001, "left",     "left"),
        (vy < -0.001, "right",    "right"),
    ]
    for cond, direction, sector in checks:
        if cond and not safe.get(direction, False):
            return False, f"Obstacle {direction}: {dist.get(sector, 0):.2f}m (min 0.35m)."
    return True, "clear"


MAPS_DIR = os.getenv("MAPS_DIR", "/home/jetson/clawbot/maps")


def _occupancy_grid_to_png_bytes(msg: OccupancyGrid) -> bytes:
    """Convert a ROS OccupancyGrid to a PNG image (bytes).

    Colour mapping:
      0   (free)     → white  (255,255,255)
      100 (occupied) → black  (  0,  0,  0)
      -1  (unknown)  → gray   (128,128,128)
    """
    w = msg.info.width
    h = msg.info.height
    data = np.array(msg.data, dtype=np.int8).reshape((h, w))
    img = np.full((h, w, 3), 128, dtype=np.uint8)      # default: unknown=gray
    img[data == 0]   = [255, 255, 255]                  # free = white
    img[data == 100] = [0,   0,   0]                    # occupied = black
    img = np.flipud(img)                                 # ROS origin is bottom-left
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


# ── Motion ────────────────────────────────────────────────────────────────────

class MotionRequest(BaseModel):
    linear_x:  float = Field(0.0, ge=-MAX_LINEAR_MS,  le=MAX_LINEAR_MS)
    linear_y:  float = Field(0.0, ge=-MAX_LINEAR_MS,  le=MAX_LINEAR_MS)
    angular_z: float = Field(0.0, ge=-MAX_ANGULAR_RS, le=MAX_ANGULAR_RS)


@app.post("/motion")
async def set_motion(req: MotionRequest) -> dict:
    """Set the robot's velocity after checking safety limits and obstacles.

    Args:
        req: MotionRequest containing linear and angular velocity.

    Returns:
        Status and applied velocities after clamping.
        
    Raises:
        HTTPException: 503 if ROS is not ready, 409 if obstructed.
    """
    global _last_motion_t
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    vx = _clamp(req.linear_x,  MAX_LINEAR_MS)
    vy = _clamp(req.linear_y,  MAX_LINEAR_MS)
    wz = _clamp(req.angular_z, MAX_ANGULAR_RS)
    if abs(vx) > 0.001 or abs(vy) > 0.001:
        ok, reason = _lidar_ok(vx, vy)
        if not ok:
            raise HTTPException(409, f"Obstacle — {reason}")
    msg = Twist()
    msg.linear.x = vx; msg.linear.y = vy; msg.angular.z = wz
    ros_node.cmd_vel_pub.publish(msg)
    _last_motion_t = time.time()
    return {"linear_x": vx, "linear_y": vy, "angular_z": wz,
            "watchdog_s": MOTION_WATCHDOG_S, "status": "ok"}


@app.post("/motion/stop")
async def stop_motion() -> dict:
    """Immediately publish zero velocity to stop the robot.

    Returns:
        A status confirmation.

    Raises:
        HTTPException: 503 if ROS is not ready.
    """
    global _last_motion_t
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    ros_node.cmd_vel_pub.publish(Twist())
    _last_motion_t = 0.0
    return {"status": "ok"}


# ── Servos ────────────────────────────────────────────────────────────────────

class ServoRequest(BaseModel):
    servo_id: int   = Field(..., ge=1, le=6)
    angle:    float = Field(..., ge=0, le=180)


@app.post("/servo")
async def control_servo(req: ServoRequest) -> dict:
    """Control a single servomotor by ID.

    Args:
        req: ServoRequest with servo ID and target angle (0-180).

    Returns:
        A status confirmation.
    """
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    msg = Int32MultiArray()
    msg.data = [req.servo_id, int(req.angle)]
    ros_node.servo_pub.publish(msg)
    ros_node.servo_angles[req.servo_id] = int(req.angle)
    return {"servo_id": req.servo_id, "angle": req.angle, "status": "ok"}


class ArmRequest(BaseModel):
    joints: list = Field(..., min_length=5, max_length=5)


@app.post("/arm")
async def control_arm(req: ArmRequest) -> dict:
    """Control the 5-DOF robotic arm.

    Args:
        req: ArmRequest containing exactly 5 joint angles (0-180).

    Returns:
        A status confirmation.
    """
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    for i, angle in enumerate(req.joints):
        msg = Int32MultiArray()
        clamped = int(max(0, min(180, angle)))
        msg.data = [i + 1, clamped]
        ros_node.servo_pub.publish(msg)
        ros_node.servo_angles[i + 1] = clamped
        await asyncio.sleep(0.06)
    return {"joints": req.joints, "status": "ok"}


class ClawRequest(BaseModel):
    state: str = Field(..., pattern="^(open|close)$")


@app.post("/claw")
async def control_claw(req: ClawRequest) -> dict:
    """Open or close the robotic claw.

    Args:
        req: ClawRequest containing the state ('open' or 'close').

    Returns:
        A status confirmation with the executed angle.
    """
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    angle = 0 if req.state == "open" else 180
    msg = Int32MultiArray()
    msg.data = [6, angle]
    ros_node.servo_pub.publish(msg)
    ros_node.servo_angles[6] = angle
    return {"state": req.state, "angle": angle, "status": "ok"}


ARM_POSES = {
    1: {"name": "Anti-collision", "angles": [90, 130, 10, 60, 90]},
    2: {"name": "Dance",          "angles": [90, 90,  90, 90, 90]},
    3: {"name": "Line-tracking",  "angles": [90, 160, 30, 90, 90]},
}


@app.post("/arm/pose/{pose_id}")
async def set_arm_pose(pose_id: int) -> dict:
    """Move the arm to a predefined pose.

    Args:
        pose_id: The ID of the pose (1, 2, or 3).

    Returns:
        The selected pose name and applied angles.

    Raises:
        HTTPException: 400 if the pose ID is unknown.
    """
    pose = ARM_POSES.get(pose_id)
    if not pose:
        raise HTTPException(400, f"Unknown pose {pose_id}. Use 1–3.")
    req = ArmRequest(joints=pose["angles"])
    await control_arm(req)
    return {"pose_id": pose_id, "pose_name": pose["name"],
            "angles": pose["angles"], "status": "ok"}


# ── Peripherals ───────────────────────────────────────────────────────────────

@app.post("/beep")
async def beep(delay_ms: int = Query(200, gt=0, le=5000)) -> dict:
    """Sound the buzzer for a specified duration.

    Args:
        delay_ms: Duration in milliseconds (default 200).

    Returns:
        A status confirmation.
    """
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    on = Bool(); on.data = True
    off = Bool(); off.data = False
    ros_node.buzzer_pub.publish(on)
    await asyncio.sleep(delay_ms / 1000.0)
    ros_node.buzzer_pub.publish(off)
    return {"status": "ok", "delay_ms": delay_ms}


class LampsRequest(BaseModel):
    r: int = Field(0, ge=0, le=255)
    g: int = Field(0, ge=0, le=255)
    b: int = Field(0, ge=0, le=255)


@app.post("/lamps")
async def set_lamps(req: LampsRequest) -> dict:
    """Set the color of the robot's RGB LED lamps.

    Args:
        req: LampsRequest containing R, G, B intensity values (0-255).

    Returns:
        A status confirmation.
    """
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    # Encode RGB as a single int: 0xRRGGBB
    val = (req.r << 16) | (req.g << 8) | req.b
    msg = Int32(); msg.data = val
    ros_node.rgb_pub.publish(msg)
    return {"r": req.r, "g": req.g, "b": req.b, "status": "ok"}


@app.get("/battery")
async def get_battery() -> dict:
    """Read the current battery voltage.

    Returns:
        Voltage reading and estimated percentage.
    """
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    v = ros_node.battery_volt
    pct = max(0, min(100, int((v - 9.6) / (12.6 - 9.6) * 100)))
    return {"voltage": round(v, 2), "unit": "V", "percentage": pct}


# ── Telemetry ────────────────────────────────────────────────────────────────

@app.get("/telemetry")
async def get_telemetry() -> dict:
    """Return live sensor telemetry from the robot.

    Aggregates all sensor data available without requiring direct serial access:
    - IMU accelerometer and gyroscope (from /imu/data_raw)
    - Measured wheel velocity (from /vel_raw)
    - Last commanded servo angles for arm joints 1-6
    - Battery voltage and percentage

    Returns:
        Dict containing imu, velocity, servos, and battery sub-dicts.
        Each field includes a 'stamp' (Unix timestamp) for staleness checks.
    """
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")

    v = ros_node.battery_volt
    pct = max(0, min(100, int((v - 9.6) / (12.6 - 9.6) * 100)))

    return {
        "imu": {
            "accel": ros_node.imu_accel,          # m/s²
            "gyro":  ros_node.imu_gyro,           # rad/s
            "stamp": ros_node.imu_stamp,
            "stale": (time.time() - ros_node.imu_stamp) > 1.0 if ros_node.imu_stamp else True,
        },
        "velocity": {
            "vx":      ros_node.vel_vx,           # m/s forward
            "vy":      ros_node.vel_vy,            # m/s lateral
            "angular": ros_node.vel_angular,       # rad/s
            "stamp":   ros_node.vel_stamp,
            "stale":   (time.time() - ros_node.vel_stamp) > 1.0 if ros_node.vel_stamp else True,
        },
        "servos": {
            # Last commanded angle per ID (1-6). -1 = not yet commanded this session.
            str(sid): angle
            for sid, angle in ros_node.servo_angles.items()
        },
        "battery": {
            "voltage":    round(v, 2),
            "percentage": pct,
        },
    }


# ── SLAM Map ─────────────────────────────────────────────────────────────────

@app.get("/map/live")
async def get_live_map() -> dict:
    """Return the current live SLAM map as a base64 PNG.

    Converts the last received /map OccupancyGrid to a PNG image.

    Returns:
        Dict with image_base64, dimensions, resolution and timestamp.

    Raises:
        HTTPException 404 if no map has been received yet.
    """
    if ros_node is None:
        raise HTTPException(503, "ROS 2 node not ready.")
    if ros_node.map_data is None:
        raise HTTPException(404, "No map received yet — is SLAM running?")
    try:
        png = _occupancy_grid_to_png_bytes(ros_node.map_data)
    except Exception as e:
        raise HTTPException(500, f"Map conversion error: {e}")
    b64 = base64.b64encode(png).decode()
    return {
        "image_base64": b64,
        "format":       "png",
        "width":        ros_node.map_data.info.width,
        "height":       ros_node.map_data.info.height,
        "resolution":   ros_node.map_data.info.resolution,
        "stamp":        ros_node.map_stamp,
    }


@app.get("/maps")
async def list_maps() -> dict:
    """List all saved maps in MAPS_DIR.

    Returns:
        Dict with a 'maps' list of {name, has_pgm, mtime}.
    """
    os.makedirs(MAPS_DIR, exist_ok=True)
    maps = []
    for f in sorted(os.listdir(MAPS_DIR)):
        if f.endswith(".yaml"):
            name      = f[:-5]
            pgm_path  = os.path.join(MAPS_DIR, name + ".pgm")
            yaml_path = os.path.join(MAPS_DIR, f)
            mtime     = os.path.getmtime(yaml_path) if os.path.exists(yaml_path) else 0
            maps.append({"name": name, "has_pgm": os.path.exists(pgm_path), "mtime": mtime})
    return {"maps": maps}


class SaveMapRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")


@app.post("/maps/save")
async def save_map(req: SaveMapRequest) -> dict:
    """Save the current SLAM map to disk using nav2 map_saver_cli.

    Args:
        req: SaveMapRequest with the map name (alphanumeric + _ -).

    Returns:
        Status and saved file path.

    Raises:
        HTTPException 500/504 if map_saver_cli fails or times out.
    """
    os.makedirs(MAPS_DIR, exist_ok=True)
    out_path = os.path.join(MAPS_DIR, req.name)
    cmd = [
        "bash", "-c",
        f"source /opt/ros/humble/setup.bash && "
        f"ROS_DOMAIN_ID={ROS_DOMAIN_ID} "
        f"ros2 run nav2_map_server map_saver_cli -f {out_path} "
        f"--ros-args -p map_subscribe_transient_local:=true"
    ]
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, lambda: subprocess.run(
            cmd, capture_output=True, text=True, timeout=15.0
        ))
        if result.returncode != 0:
            raise HTTPException(500, f"map_saver_cli failed: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "map_saver_cli timed out (15s)")
    return {"status": "ok", "name": req.name, "path": out_path}


@app.get("/maps/{name}/image")
async def get_map_image(name: str) -> dict:
    """Load a saved map PGM and return it as a base64 PNG.

    Args:
        name: Map name (without extension).

    Returns:
        Dict with image_base64, dimensions, resolution and name.

    Raises:
        HTTPException 404 if map not found.
    """
    pgm_path  = os.path.join(MAPS_DIR, name + ".pgm")
    yaml_path = os.path.join(MAPS_DIR, name + ".yaml")
    if not os.path.exists(pgm_path):
        raise HTTPException(404, f"Map not found: {name}")
    img = cv2.imread(pgm_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(500, "Failed to read PGM file.")
    rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    _, buf = cv2.imencode(".png", rgb)
    b64  = base64.b64encode(buf.tobytes()).decode()
    meta: dict = {}
    if os.path.exists(yaml_path):
        with open(yaml_path) as f:
            meta = _yaml.safe_load(f) or {}
    return {
        "image_base64": b64,
        "format":       "png",
        "width":        img.shape[1],
        "height":       img.shape[0],
        "resolution":   meta.get("resolution"),
        "name":         name,
    }


@app.delete("/maps/{name}")
async def delete_map(name: str) -> dict:
    """Delete a saved map (.pgm + .yaml files).

    Args:
        name: Map name (without extension).

    Returns:
        List of deleted files.

    Raises:
        HTTPException 404 if no files found.
    """
    deleted = []
    for ext in [".pgm", ".yaml"]:
        p = os.path.join(MAPS_DIR, name + ext)
        if os.path.exists(p):
            os.remove(p)
            deleted.append(p)
    if not deleted:
        raise HTTPException(404, f"Map not found: {name}")
    return {"status": "ok", "deleted": deleted}


# ── System Status ────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: float = 2.0) -> str:
    """Run a subprocess and return stdout, empty string on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


@app.get("/system/status")
async def system_status() -> dict:
    """Return full system status: services, ROS2 nodes/topics, LiDAR, battery.

    Returns:
        Aggregated status dict for the monitoring dashboard.
    """
    loop = asyncio.get_event_loop()

    # ── Systemd services ──────────────────────────────────────────────────────
    svc_names = ["ros2-hardware-service", "ros2-driver-node", "ros2-llm-bridge"]
    def _svc_status(name: str) -> str:
        return _run(["systemctl", "is-active", name]) or "unknown"

    # ── Docker containers ─────────────────────────────────────────────────────
    docker_containers = ["clawbot-llm_bridge-1", "clawbot-clawbot_monitoring-1"]
    def _docker_status(name: str) -> str:
        out = _run(["docker", "inspect", "--format", "{{.State.Status}}", name])
        return out or "unknown"

    # ── ROS2 nodes ────────────────────────────────────────────────────────────
    def _ros2_nodes() -> list[str]:
        out = _run([
            "bash", "-c",
            "source /opt/ros/humble/setup.bash && "
            f"ROS_DOMAIN_ID={ROS_DOMAIN_ID} ros2 node list 2>/dev/null"
        ], timeout=3.0)
        return [n for n in out.splitlines() if n.startswith("/")]

    # ── ROS2 topics ───────────────────────────────────────────────────────────
    def _ros2_topics() -> list[str]:
        out = _run([
            "bash", "-c",
            "source /opt/ros/humble/setup.bash && "
            f"ROS_DOMAIN_ID={ROS_DOMAIN_ID} ros2 topic list 2>/dev/null"
        ], timeout=3.0)
        return [t for t in out.splitlines() if t.startswith("/")]

    # ── Run all in thread pool to avoid blocking event loop ──────────────────
    services = {}
    for name in svc_names:
        services[name] = await loop.run_in_executor(None, _svc_status, name)
    for name in docker_containers:
        services[name] = await loop.run_in_executor(None, _docker_status, name)

    nodes  = await loop.run_in_executor(None, _ros2_nodes)
    topics = await loop.run_in_executor(None, _ros2_topics)

    # ── LiDAR ─────────────────────────────────────────────────────────────────
    lidar: dict = {"enabled": LIDAR_REQUIRED, "safe_to_move": None,
                   "distances": None, "age_s": None}
    try:
        with open(SAFETY_FILE) as f:
            data = json.load(f)
        age = round(time.time() - data.get("timestamp", 0), 1)
        lidar.update({
            "enabled":      LIDAR_REQUIRED,
            "safe_to_move": data.get("safe_to_move"),
            "distances":    data.get("distances"),
            "age_s":        age,
        })
    except Exception:
        pass

    # ── Battery ───────────────────────────────────────────────────────────────
    v = ros_node.battery_volt if ros_node else 0.0
    pct = max(0, min(100, int((v - 9.6) / (12.6 - 9.6) * 100)))

    return {
        "timestamp": time.time(),
        "services":  services,
        "ros2_nodes": nodes,
        "ros2_topics": topics,
        "lidar":     lidar,
        "battery":   {"voltage": round(v, 2), "percentage": pct},
    }


# ── Camera ────────────────────────────────────────────────────────────────────

def _capture(camera: str) -> bytes:
    idx = CAMERA_DEVICES.get(camera)
    if idx is None:
        raise ValueError(f"Unknown camera '{camera}'.")
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {camera} (index {idx})")
    for _ in range(3): cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError(f"Frame capture failed for '{camera}'")
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes()


@app.get("/capture")
async def capture_camera(
    camera: str = Query("front"),
    save:   bool = Query(True),
) -> dict:
    """Capture a raw frame from the specified camera.

    Args:
        camera: 'front' or 'claw' camera selection.
        save: Whether to save the image to disk.

    Returns:
        The image as a base64 encoded string and saved path.
    """
    try:
        jpeg = _capture(camera)
    except Exception as e:
        raise HTTPException(500, str(e))
    b64 = base64.b64encode(jpeg).decode()
    path = None
    if save:
        path = os.path.join(WORKSPACE, f"camera_{camera}.jpg")
        with open(path, "wb") as f:
            f.write(jpeg)
    return {"camera": camera, "image_base64": b64, "format": "jpeg", "saved_path": path}


# ── YOLO Detection Feed ───────────────────────────────────────────────────────

@app.get("/yolo/frame")
async def yolo_frame() -> dict:
    """Return the latest YOLO annotated frame as base64 JPEG.

    Returns 204 (no content) if no frame has been received yet (yolo-detector
    not running or not yet published).
    """
    if ros_node is None or ros_node.yolo_frame_bytes is None:
        raise HTTPException(204, "No YOLO frame available — is yolo-detector running?")
    b64 = base64.b64encode(ros_node.yolo_frame_bytes).decode()
    age = round(time.time() - ros_node.yolo_stamp, 2)
    return {
        "image_base64": b64,
        "format": "jpeg",
        "age_s": age,
        "detections": ros_node.yolo_detections,
    }


@app.get("/yolo/status")
async def yolo_status() -> dict:
    """Check YOLO node status: service state + last frame age + last detections."""
    loop = asyncio.get_event_loop()
    svc_state = await loop.run_in_executor(
        None, lambda: _run(["systemctl", "is-active", "yolo-detector"]) or "unknown"
    )
    active = svc_state in ("active", "running")
    frame_age = None
    if ros_node and ros_node.yolo_stamp > 0:
        frame_age = round(time.time() - ros_node.yolo_stamp, 2)
    return {
        "service": svc_state,
        "active": active,
        "frame_age_s": frame_age,
        "has_frame": ros_node is not None and ros_node.yolo_frame_bytes is not None,
        "detections": ros_node.yolo_detections if ros_node else [],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0",
                port=int(os.getenv("HARDWARE_SERVICE_PORT", "8001")),
                log_level="info")
