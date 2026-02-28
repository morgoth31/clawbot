import logging
import uuid
from typing import Any, Callable, Dict, List, Literal, NamedTuple, Type

from pydantic import BaseModel, ValidationError

from ros2_llm_bridge.bridge_node import BridgeNode
from ros2_llm_bridge.schemas import (
    AnalyzeScene,
    Beep,
    CaptureCamera,
    ControlArm,
    ControlClaw,
    ControlServo,
    GetBatteryVoltage,
    Listen,
    NavigateTo,
    RecognizeFace,
    RecognizeObject,
    RecognizeQRCode,
    SetArmPose,
    SetLamps,
    SetVelocity,
    Speak,
    Stop,
)

logger = logging.getLogger("ros2_llm_bridge.action_handler")

ToolFormat = Literal["openai", "anthropic", "raw"]


class _ToolEntry(NamedTuple):
    schema_cls: Type[BaseModel]
    handler: Callable
    timeout: float  # seconds


def _to_openai_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    raw = model.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": raw.get("title", model.__name__),
            "description": raw.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": raw.get("properties", {}),
                "required": raw.get("required", []),
            },
        },
    }


def _to_anthropic_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    raw = model.model_json_schema()
    return {
        "name": raw.get("title", model.__name__),
        "description": raw.get("description", ""),
        "input_schema": {
            "type": "object",
            "properties": raw.get("properties", {}),
            "required": raw.get("required", []),
        },
    }


def _to_raw_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    return model.model_json_schema()


_FORMATTERS: Dict[str, Callable[[Type[BaseModel]], Dict[str, Any]]] = {
    "openai": _to_openai_schema,
    "anthropic": _to_anthropic_schema,
    "raw": _to_raw_schema,
}


class ActionHandler:
    """Maps HTTP tool-call requests to BridgeNode execution methods."""

    def __init__(self, bridge_node: BridgeNode):
        self.bridge_node = bridge_node

        self._registry: Dict[str, _ToolEntry] = {
            # Motion
            "SetVelocity":        _ToolEntry(SetVelocity,        self._exec_set_velocity,        5.0),
            "Stop":               _ToolEntry(Stop,               self._exec_stop,                2.0),
            "Speak":              _ToolEntry(Speak,              self._exec_speak,               15.0),
            "NavigateTo":         _ToolEntry(NavigateTo,         self._exec_navigate_to,         60.0),
            # Vision
            "CaptureCamera":      _ToolEntry(CaptureCamera,      self._exec_capture_camera,      10.0),
            "AnalyzeScene":       _ToolEntry(AnalyzeScene,       self._exec_analyze_scene,       15.0),
            "RecognizeFace":      _ToolEntry(RecognizeFace,      self._exec_recognize_face,      10.0),
            "RecognizeObject":    _ToolEntry(RecognizeObject,    self._exec_recognize_object,    10.0),
            "RecognizeQRCode":    _ToolEntry(RecognizeQRCode,    self._exec_recognize_qrcode,    10.0),
            # Audio
            "Listen":             _ToolEntry(Listen,             self._exec_listen,              30.0),
            # Arm & claw
            "ControlServo":       _ToolEntry(ControlServo,       self._exec_control_servo,        5.0),
            "ControlArm":         _ToolEntry(ControlArm,         self._exec_control_arm,         10.0),
            "ControlClaw":        _ToolEntry(ControlClaw,        self._exec_control_claw,         5.0),
            "SetArmPose":         _ToolEntry(SetArmPose,         self._exec_set_arm_pose,        10.0),
            # Peripherals
            "Beep":               _ToolEntry(Beep,               self._exec_beep,                 5.0),
            "SetLamps":           _ToolEntry(SetLamps,           self._exec_set_lamps,            2.0),
            "GetBatteryVoltage":  _ToolEntry(GetBatteryVoltage,  self._exec_get_battery_voltage,  3.0),
        }
        logger.info(
            "ActionHandler initialised with %d tools: %s",
            len(self._registry),
            list(self._registry),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tools_schema(self, format: ToolFormat = "openai") -> List[Dict[str, Any]]:
        formatter = _FORMATTERS.get(format, _to_openai_schema)
        return [formatter(entry.schema_cls) for entry in self._registry.values()]

    def get_tool_timeout(self, func_name: str, default: float = 10.0) -> float:
        entry = self._registry.get(func_name)
        return entry.timeout if entry else default

    async def execute_tool(self, func_name: str, args: Dict[str, Any]) -> str:
        if func_name not in self._registry:
            available = ", ".join(self._registry)
            raise ValueError(
                f"Unknown tool '{func_name}'. Available tools: {available}"
            )
        entry = self._registry[func_name]
        cid = str(uuid.uuid4())
        logger.info("[CID: %s] Executing '%s' with args: %s", cid, func_name, args)
        try:
            validated = entry.schema_cls(**args)
        except ValidationError as exc:
            raise ValueError(f"Invalid arguments for '{func_name}': {exc}") from exc
        result = await entry.handler(cid, validated)
        logger.info("[CID: %s] Result: %s", cid, result[:200] if len(str(result)) > 200 else result)
        return result

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    async def _exec_set_velocity(self, cid: str, cmd: SetVelocity) -> str:
        return await self.bridge_node.execute_set_velocity(
            cid, cmd.linear_x, cmd.linear_y, cmd.angular_z
        )

    async def _exec_stop(self, cid: str, cmd: Stop) -> str:
        return await self.bridge_node.execute_stop(cid)

    async def _exec_speak(self, cid: str, cmd: Speak) -> str:
        return await self.bridge_node.execute_speak(cid, cmd.text)

    async def _exec_navigate_to(self, cid: str, cmd: NavigateTo) -> str:
        return await self.bridge_node.execute_navigate_to(cid, cmd.target_x, cmd.target_y)

    async def _exec_capture_camera(self, cid: str, cmd: CaptureCamera) -> str:
        return await self.bridge_node.execute_capture_camera(cid, cmd.camera)

    async def _exec_analyze_scene(self, cid: str, cmd: AnalyzeScene) -> str:
        return await self.bridge_node.execute_analyze_scene(cid)

    async def _exec_recognize_face(self, cid: str, cmd: RecognizeFace) -> str:
        return await self.bridge_node.execute_recognize_face(cid)

    async def _exec_recognize_object(self, cid: str, cmd: RecognizeObject) -> str:
        return await self.bridge_node.execute_recognize_object(cid)

    async def _exec_recognize_qrcode(self, cid: str, cmd: RecognizeQRCode) -> str:
        return await self.bridge_node.execute_recognize_qrcode(cid)

    async def _exec_listen(self, cid: str, cmd: Listen) -> str:
        return await self.bridge_node.execute_listen(cid)

    async def _exec_control_servo(self, cid: str, cmd: ControlServo) -> str:
        return await self.bridge_node.execute_control_servo(cid, cmd.servo_id, cmd.angle)

    async def _exec_control_arm(self, cid: str, cmd: ControlArm) -> str:
        return await self.bridge_node.execute_control_arm(cid, cmd.joints_array)

    async def _exec_control_claw(self, cid: str, cmd: ControlClaw) -> str:
        return await self.bridge_node.execute_control_claw(cid, cmd.state)

    async def _exec_set_arm_pose(self, cid: str, cmd: SetArmPose) -> str:
        return await self.bridge_node.execute_set_arm_pose(cid, cmd.pose_id)

    async def _exec_beep(self, cid: str, cmd: Beep) -> str:
        return await self.bridge_node.execute_beep(cid, cmd.delay_ms)

    async def _exec_set_lamps(self, cid: str, cmd: SetLamps) -> str:
        return await self.bridge_node.execute_set_lamps(cid, cmd.r, cmd.g, cmd.b)

    async def _exec_get_battery_voltage(self, cid: str, cmd: GetBatteryVoltage) -> str:
        return await self.bridge_node.execute_get_battery_voltage(cid)
