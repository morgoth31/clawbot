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
import logging
import os
import threading
import time

import cv2
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

# ROS 2
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Float32, Int32, Int32MultiArray

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [hardware_service] %(levelname)s %(message)s",
)
logger = logging.getLogger("hardware_service")

# ── Safety limits ───────────────────────────────────────────────────────────
MAX_LINEAR_MS  = float(os.getenv("MAX_LINEAR_MS",  "0.06"))
MAX_ANGULAR_RS = float(os.getenv("MAX_ANGULAR_RS", "0.25"))
MOTION_WATCHDOG_S = float(os.getenv("MOTION_WATCHDOG_S", "1.5"))

SAFETY_FILE    = "/tmp/lidar_safety.json"
SAFETY_MAX_AGE = 2.0

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
    def __init__(self):
        super().__init__("hardware_service_node")
        best_effort = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.cmd_vel_pub  = self.create_publisher(Twist,          "/cmd_vel",    10)
        self.servo_pub    = self.create_publisher(Int32MultiArray, "/servo_ctrl", 10)
        self.buzzer_pub   = self.create_publisher(Bool,            "/Buzzer",     10)
        self.rgb_pub      = self.create_publisher(Int32,           "/RGBLight",   10)
        self.battery_volt = 0.0
        self.create_subscription(Float32, "/voltage", self._bat_cb, best_effort)
        self.get_logger().info(f"HardwareNode ready on domain {ROS_DOMAIN_ID}")

    def _bat_cb(self, msg: Float32):
        self.battery_volt = msg.data


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
        msg.data = [i + 1, int(max(0, min(180, angle)))]
        ros_node.servo_pub.publish(msg)
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0",
                port=int(os.getenv("HARDWARE_SERVICE_PORT", "8001")),
                log_level="info")
