import math
from typing import List, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------


class SetVelocity(BaseModel):
    """
    Set the robot's velocity. Always call Stop() after a timed move.
    The X3 Plus uses Mecanum wheels — lateral (y) movement is fully supported.

    ⚠️ SAFETY LIMITS (hard-enforced by hardware service):
      - linear_x / linear_y : max ±0.06 m/s
      - angular_z            : max ±0.25 rad/s
    Never exceed these. The hardware service will clamp any higher value.
    If in doubt, use lower values and shorter durations.
    """

    linear_x: float = Field(
        ...,
        description="Forward/backward velocity in m/s. Positive = forward. HARD LIMIT: ±0.06 m/s.",
        ge=-0.06,
        le=0.06,
    )
    linear_y: float = Field(
        0.0,
        description="Lateral velocity in m/s. Positive = left (Mecanum). HARD LIMIT: ±0.06 m/s.",
        ge=-0.06,
        le=0.06,
    )
    angular_z: float = Field(
        ...,
        description="Rotational velocity in rad/s. Positive = counter-clockwise. HARD LIMIT: ±0.25 rad/s.",
        ge=-0.25,
        le=0.25,
    )


class Stop(BaseModel):
    """
    Stop the robot immediately by publishing zero velocity on /cmd_vel.
    Always call this after a timed movement to prevent the robot from
    continuing indefinitely.
    """

    pass


class Speak(BaseModel):
    """
    Command the robot to speak a sentence via its text-to-speech system.
    """

    text: str = Field(..., description="The sentence the robot should say aloud.")


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


class NavigateTo(BaseModel):
    """
    Autonomously navigate to a Cartesian coordinate using SLAM/Nav2.
    The robot plans a path and avoids obstacles. Blocks until the goal is
    reached or fails. Requires Nav2 and a map to be active.
    """

    target_x: float = Field(
        ..., description="Target X coordinate in the map frame (meters)."
    )
    target_y: float = Field(
        ..., description="Target Y coordinate in the map frame (meters)."
    )


# ---------------------------------------------------------------------------
# Vision  (all vision tools capture real camera frames via hardware service)
# ---------------------------------------------------------------------------


class CaptureCamera(BaseModel):
    """
    Capture a JPEG frame from one of the robot's cameras and save it to the
    workspace. Returns the saved file path and a base64-encoded image.
    Use the image tool on the returned saved_path to visually analyse the frame.

    Cameras:
      - 'front' → /dev/video0, mounted on the front of the chassis
      - 'claw'  → /dev/video2, mounted on the robotic arm near the claw
    """

    camera: Literal["front", "claw"] = Field(
        "front",
        description="Which camera to capture from: 'front' (chassis) or 'claw' (arm).",
    )


class RecognizeFace(BaseModel):
    """
    Capture the front camera frame and return it for face recognition.
    After calling this tool, use the image tool on the saved_path to identify
    any faces in the scene.
    """

    pass


class RecognizeObject(BaseModel):
    """
    Capture the front camera frame and return it for object detection.
    After calling this tool, use the image tool on the saved_path to detect
    and list all objects present in the scene.
    """

    pass


class RecognizeQRCode(BaseModel):
    """
    Capture the front camera frame and return it for QR code decoding.
    After calling this tool, use the image tool on the saved_path to decode
    any QR codes visible in the frame.
    """

    pass


class AnalyzeScene(BaseModel):
    """
    Capture the front camera and return the frame for full scene analysis.
    After calling this tool, use the image tool on the saved_path to describe
    the environment, objects, spatial layout, and anything noteworthy.
    """

    pass


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


class Listen(BaseModel):
    """
    Record audio from the microphone and return a speech-to-text transcript.
    (Not yet implemented — stub.)
    """

    pass


# ---------------------------------------------------------------------------
# Arm & Effector control
# ---------------------------------------------------------------------------


class ControlServo(BaseModel):
    """
    Directly set a single servo to a target angle.
    Use this for precise individual joint control.

    Servo map:
      1 → Base rotation       (0–180°, center = 90°)
      2 → Shoulder lift       (0–180°, up = low value)
      3 → Elbow reach         (0–180°)
      4 → Wrist tilt (pitch)  (0–180°)
      5 → Wrist rotate (roll) (0–180°)
      6 → Claw open/close     (0° = open, 180° = closed)
    """

    servo_id: int = Field(
        ...,
        description="Servo ID to control (1–6).",
        ge=1,
        le=6,
    )
    angle: float = Field(
        ...,
        description="Target angle in degrees (0–180).",
        ge=0,
        le=180,
    )


class ControlArm(BaseModel):
    """
    Send joint angles (degrees) to the 5-DOF robotic arm servos 1–5.
    Provide exactly 5 values ordered: [base, shoulder, elbow, wrist-tilt, wrist-rotate].
    Each value must be in the range 0–180°. Use ControlClaw separately for the claw.

    Example — arm extended forward at mid-height:
        joints_array = [90, 120, 60, 90, 90]
    """

    joints_array: List[float] = Field(
        ...,
        description=(
            "5 joint angles in degrees [base, shoulder, elbow, wrist-tilt, wrist-rotate]. "
            "Each value 0–180. Use ControlClaw for servo 6."
        ),
        min_length=5,
        max_length=5,
    )


class ControlClaw(BaseModel):
    """
    Open or close the robot's end-effector claw (servo 6).
      - 'open'  → 0°   (fully open)
      - 'close' → 180° (fully closed / gripping)
    """

    state: Literal["open", "close"] = Field(
        ..., description="Desired claw state: 'open' or 'close'."
    )


# ---------------------------------------------------------------------------
# Peripherals
# ---------------------------------------------------------------------------


class Beep(BaseModel):
    """
    Sound the robot's buzzer for a fixed duration.
    """

    delay_ms: int = Field(
        200,
        description="Duration in milliseconds to sound the buzzer.",
        gt=0,
        le=5000,
    )


class SetLamps(BaseModel):
    """
    Set the colour of the robot's RGB LED lamps (all lamps at once).
    """

    r: int = Field(0, description="Red channel intensity (0–255).", ge=0, le=255)
    g: int = Field(0, description="Green channel intensity (0–255).", ge=0, le=255)
    b: int = Field(0, description="Blue channel intensity (0–255).", ge=0, le=255)


class GetBatteryVoltage(BaseModel):
    """
    Read the current battery voltage. Returns voltage in volts and estimated
    charge percentage based on the 3S LiPo curve (9.6 V–12.6 V).
    """

    pass


class SetArmPose(BaseModel):
    """
    Move the robot arm to a named predefined pose by ID.
      1 → Anti-collision  (arm folded back, safe for navigation)
      2 → Dance           (arm extended level forward)
      3 → Line-tracking   (arm low, camera pointing forward/down)
    """

    pose_id: int = Field(
        ...,
        description="Pose ID: 1 (Anti-collision), 2 (Dance), 3 (Line-tracking).",
        ge=1,
        le=3,
    )
