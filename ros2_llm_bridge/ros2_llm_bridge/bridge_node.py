import json
import logging
import os
from typing import List

import httpx
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

logger = logging.getLogger("ros2_llm_bridge.node")

# Hardware service base URL (host-side, reachable via host networking)
HARDWARE_URL = os.getenv("HARDWARE_SERVICE_URL", "http://localhost:8001")
HW_TIMEOUT = float(os.getenv("HARDWARE_SERVICE_TIMEOUT", "10.0"))


class BridgeNode(Node):
    """ROS 2 Node that bridges LLM tool calls to ROS 2 topics/services and
    the host hardware service (Rosmaster_Lib + OpenCV cameras).

    Attributes:
        cmd_vel_pub: Publisher for geometry_msgs/msg/Twist velocity commands.
    """

    def __init__(self):
        super().__init__("llm_bridge_node")
        self.cmd_vel_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self._hw = httpx.AsyncClient(base_url=HARDWARE_URL, timeout=HW_TIMEOUT)
        self.get_logger().info(
            f"BridgeNode initialised. Hardware service: {HARDWARE_URL}"
        )

    def log_with_correlation(
        self, correlation_id: str, message: str, level: int = logging.INFO
    ):
        log_msg = f"[CID: {correlation_id}] {message}"
        logger.log(level, log_msg)
        if level >= logging.WARNING:
            self.get_logger().warn(log_msg)
        else:
            self.get_logger().info(log_msg)

    # ------------------------------------------------------------------ #
    # Internal helper                                                      #
    # ------------------------------------------------------------------ #

    async def _hw_get(self, path: str, **params) -> dict:
        resp = await self._hw.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def _hw_post(self, path: str, json_body: dict = None, **params) -> dict:
        resp = await self._hw.post(path, json=json_body, params=params)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ #
    # Motion — ROS 2 /cmd_vel (no hardware service needed)                #
    # ------------------------------------------------------------------ #

    async def execute_set_velocity(
        self,
        correlation_id: str,
        linear_x: float,
        linear_y: float,
        angular_z: float,
    ) -> str:
        """Send velocity commands to the hardware service.

        The hardware service enforces safety limits and checks ultrasonic sensors
        for obstacles before moving. If blocked, the robot will not move.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            linear_x: Forward/backward speed in meters per second.
            linear_y: Left/right sliding speed in meters per second (mecanum wheels).
            angular_z: Rotational speed in radians per second.

        Returns:
            A string indicating whether the command succeeded, was clamped, or was blocked.
        """
        self.log_with_correlation(
            correlation_id,
            f"SetVelocity: linear_x={linear_x}, linear_y={linear_y}, angular_z={angular_z}",
        )
        # Hardware service is the only motion path — it does safety + speed clamping.
        # Do NOT fall back to /cmd_vel: that would bypass obstacle detection.
        try:
            data = await self._hw_post(
                "/motion",
                json_body={"linear_x": linear_x, "linear_y": linear_y, "angular_z": angular_z},
            )
            clamped = data.get("clamped", False)
            note = " [speed was clamped to safe limit]" if clamped else ""
            return f"Velocity set: vx={data['linear_x']}, vy={data['linear_y']}, wz={data['angular_z']}.{note}"
        except httpx.HTTPStatusError as exc:
            # 409 = obstacle detected — surface the reason clearly
            detail = exc.response.json().get("detail", str(exc))
            return f"BLOCKED: {detail}"
        except Exception as exc:
            return f"ERROR: hardware service unreachable — {exc}. Robot not moved."

    async def execute_stop(self, correlation_id: str) -> str:
        """Immediately stop the robot.

        Attempts to stop the robot via the hardware service. If the hardware service
        is unreachable, it falls back to publishing an empty Twist message to `/cmd_vel`.

        Args:
            correlation_id: A unique ID for tracking this specific request.

        Returns:
            A string confirming the stop command was processed.
        """
        self.log_with_correlation(correlation_id, "Stop: zeroing all velocities")
        try:
            data = await self._hw_post("/motion/stop")
            return f"Stop command sent. status={data.get('status')}"
        except Exception:
            # Stop must always work — fall back to /cmd_vel as last resort
            self.cmd_vel_pub.publish(Twist())
            return "Stop sent to /cmd_vel (hardware service unreachable)."

    async def execute_speak(self, correlation_id: str, text: str) -> str:
        """Perform text-to-speech.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            text: The sentence or phrase for the robot to speak.

        Returns:
            A string acknowledging the command.
        """
        self.log_with_correlation(correlation_id, f"Speak: '{text}'")
        # TODO: wire to TTS ROS 2 service when available
        return f'Speak acknowledged: "{text}"'

    # ------------------------------------------------------------------ #
    # Navigation — stub (wire Nav2 action client here when needed)         #
    # ------------------------------------------------------------------ #

    async def execute_navigate_to(
        self, correlation_id: str, target_x: float, target_y: float
    ) -> str:
        """Navigate autonomously to a target coordinate.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            target_x: The X coordinate in the map frame.
            target_y: The Y coordinate in the map frame.

        Returns:
            A JSON string containing the status.
        """
        self.log_with_correlation(
            correlation_id, f"NavigateTo: ({target_x}, {target_y})"
        )
        # TODO: send Nav2 NavigateToPose goal and await result
        return json.dumps(
            {"status": "stub", "message": "Nav2 not wired yet — implement NavigateToPose action client."}
        )

    # ------------------------------------------------------------------ #
    # Vision — captures real frames via hardware service                   #
    # ------------------------------------------------------------------ #

    async def execute_capture_camera(
        self, correlation_id: str, camera: str
    ) -> str:
        """Capture a frame from the specified camera and save it to the workspace.

        Returns a JSON object with the saved file path and base64 image data so
        the caller can either display the file or analyse the base64 blob.
        """
        self.log_with_correlation(correlation_id, f"CaptureCamera: {camera}")
        data = await self._hw_get("/capture", camera=camera, save=True)
        # Strip the potentially large base64 blob from the log
        self.log_with_correlation(
            correlation_id,
            f"CaptureCamera done: saved_path={data.get('saved_path')}",
        )
        return json.dumps({
            "camera": data["camera"],
            "saved_path": data.get("saved_path"),
            "image_base64": data["image_base64"],
            "format": "jpeg",
        })

    async def execute_analyze_scene(self, correlation_id: str) -> str:
        """Capture the front camera and prompt the LLM to analyze the scene.

        Args:
            correlation_id: A unique ID for tracking this specific request.

        Returns:
            A JSON string with the image path and base64 data.
        """
        """Capture the front camera and return the image for LLM analysis."""
        self.log_with_correlation(correlation_id, "AnalyzeScene → CaptureCamera(front)")
        data = await self._hw_get("/capture", camera="front", save=True)
        return json.dumps({
            "instruction": (
                "Scene captured. Use the image tool with the saved_path to analyse "
                "what is in the scene and describe the environment."
            ),
            "saved_path": data.get("saved_path"),
            "image_base64": data["image_base64"],
            "format": "jpeg",
        })

    async def execute_recognize_face(self, correlation_id: str) -> str:
        """Capture the front camera and prompt the LLM to recognize faces.

        Args:
            correlation_id: A unique ID for tracking this specific request.

        Returns:
            A JSON string with the image path and base64 data.
        """
        self.log_with_correlation(correlation_id, "RecognizeFace → CaptureCamera(front)")
        data = await self._hw_get("/capture", camera="front", save=True)
        return json.dumps({
            "instruction": "Use the image tool on saved_path to identify any faces.",
            "saved_path": data.get("saved_path"),
            "image_base64": data["image_base64"],
        })

    async def execute_recognize_object(self, correlation_id: str) -> str:
        """Capture the front camera and prompt the LLM to recognize objects.

        Args:
            correlation_id: A unique ID for tracking this specific request.

        Returns:
            A JSON string with the image path and base64 data.
        """
        self.log_with_correlation(correlation_id, "RecognizeObject → CaptureCamera(front)")
        data = await self._hw_get("/capture", camera="front", save=True)
        return json.dumps({
            "instruction": "Use the image tool on saved_path to detect and list all objects.",
            "saved_path": data.get("saved_path"),
            "image_base64": data["image_base64"],
        })

    async def execute_recognize_qrcode(self, correlation_id: str) -> str:
        """Capture the front camera and prompt the LLM to decode QR codes.

        Args:
            correlation_id: A unique ID for tracking this specific request.

        Returns:
            A JSON string with the image path and base64 data.
        """
        self.log_with_correlation(correlation_id, "RecognizeQRCode → CaptureCamera(front)")
        data = await self._hw_get("/capture", camera="front", save=True)
        return json.dumps({
            "instruction": "Use the image tool on saved_path to decode any QR codes.",
            "saved_path": data.get("saved_path"),
            "image_base64": data["image_base64"],
        })

    async def execute_listen(self, correlation_id: str) -> str:
        """Listen to ambient audio and perform speech-to-text.

        Args:
            correlation_id: A unique ID for tracking this specific request.

        Returns:
            A JSON string containing the transcribed text.
        """
        self.log_with_correlation(correlation_id, "Listen")
        # TODO: call speech-to-text service
        return json.dumps({"status": "stub", "message": "STT not wired yet."})

    # ------------------------------------------------------------------ #
    # Arm & Claw — real hardware via hardware service                      #
    # ------------------------------------------------------------------ #

    async def execute_control_servo(
        self, correlation_id: str, servo_id: int, angle: float
    ) -> str:
        """Move a specific servomotor to an absolute angle.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            servo_id: The ID of the servomotor (e.g., 1 for camera pan).
            angle: The target angle in degrees (0 to 180).

        Returns:
            A string indicating success or failure.
        """
        self.log_with_correlation(
            correlation_id, f"ControlServo: id={servo_id}, angle={angle}°"
        )
        data = await self._hw_post(
            "/servo", json_body={"servo_id": servo_id, "angle": angle}
        )
        return f"Servo {servo_id} → {angle}°. status={data.get('status')}"

    async def execute_control_arm(
        self, correlation_id: str, joints_array: List[float]
    ) -> str:
        """Control the robotic arm by specifying joint angles.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            joints_array: A list of target angles (in degrees) for the arm joints.

        Returns:
            A string indicating success or failure.
        """
        self.log_with_correlation(
            correlation_id, f"ControlArm: joints={joints_array}"
        )
        data = await self._hw_post("/arm", json_body={"joints": joints_array})
        return f"Arm moved to joints (deg): {joints_array}. status={data.get('status')}"

    async def execute_control_claw(self, correlation_id: str, state: str) -> str:
        """Open or close the robotic claw.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            state: Either 'open' or 'close'.

        Returns:
            A string indicating the new claw state.
        """
        self.log_with_correlation(correlation_id, f"ControlClaw: {state}")
        data = await self._hw_post("/claw", json_body={"state": state})
        return f"Claw is now {state} (angle={data.get('angle')}°)."

    async def execute_set_arm_pose(self, correlation_id: str, pose_id: int) -> str:
        """Set the robotic arm to a predefined pose.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            pose_id: An ID corresponding to a known pose (e.g., 1 for driving position).

        Returns:
            A string detailing the selected pose name and angles.
        """
        self.log_with_correlation(correlation_id, f"SetArmPose: pose_id={pose_id}")
        data = await self._hw_post(f"/arm/pose/{pose_id}")
        return (
            f"Arm pose set to '{data.get('pose_name')}' "
            f"(angles: {data.get('angles')}). status={data.get('status')}"
        )

    # ------------------------------------------------------------------ #
    # Peripherals — real hardware via hardware service                     #
    # ------------------------------------------------------------------ #

    async def execute_beep(self, correlation_id: str, delay_ms: int) -> str:
        """Sound the robot's buzzer.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            delay_ms: Duration of the beep in milliseconds.

        Returns:
            A string acknowledging the buzzer was activated.
        """
        self.log_with_correlation(correlation_id, f"Beep: {delay_ms} ms")
        data = await self._hw_post("/beep", params={"delay_ms": delay_ms})
        return f"Buzzer sounded for {delay_ms} ms. status={data.get('status')}"

    async def execute_set_lamps(
        self, correlation_id: str, r: int, g: int, b: int
    ) -> str:
        """Change the color of the robot's LED lamps.

        Args:
            correlation_id: A unique ID for tracking this specific request.
            r: Red intensity (0-255).
            g: Green intensity (0-255).
            b: Blue intensity (0-255).

        Returns:
            A string acknowledging the new LED colors.
        """
        self.log_with_correlation(
            correlation_id, f"SetLamps: r={r}, g={g}, b={b}"
        )
        data = await self._hw_post("/lamps", json_body={"r": r, "g": g, "b": b})
        return f"LEDs set to RGB({r}, {g}, {b}). status={data.get('status')}"

    async def execute_get_battery_voltage(self, correlation_id: str) -> str:
        """Check the current battery voltage of the robot.

        Args:
            correlation_id: A unique ID for tracking this specific request.

        Returns:
            A JSON string containing the battery voltage.
        """
        self.log_with_correlation(correlation_id, "GetBatteryVoltage")
        data = await self._hw_get("/battery")
        return json.dumps(data)
