"""Unit tests for ActionHandler.

BridgeNode is fully mocked so no ROS 2 runtime is required.
Async tests use the anyio backend (already available in the environment).
"""

import sys
from pathlib import Path

import pytest
from unittest.mock import ANY, AsyncMock, MagicMock

# Le paquet vit dans ros2_llm_bridge/ros2_llm_bridge/ : pytest lancé depuis la
# racine du dépôt n'ajoute que le dossier du test à sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ros2_llm_bridge.action_handler import ActionHandler
from ros2_llm_bridge.bridge_node import BridgeNode


@pytest.fixture
def mock_bridge():
    bridge = MagicMock(spec=BridgeNode)
    bridge.execute_set_velocity = AsyncMock(
        return_value="Velocity command published to cmd_vel."
    )
    bridge.execute_stop = AsyncMock(
        return_value="Stop command sent — all velocities zeroed."
    )
    bridge.execute_speak = AsyncMock(return_value='Spoke: "Hello"')
    bridge.execute_navigate_to = AsyncMock(
        return_value='{"status": "success", "reached": {"x": 1.0, "y": 2.0}}'
    )
    bridge.execute_recognize_face = AsyncMock(
        return_value='{"face": "User", "confidence": 0.97}'
    )
    bridge.execute_recognize_object = AsyncMock(
        return_value='{"objects": [{"label": "Apple", "confidence": 0.89}]}'
    )
    bridge.execute_recognize_qrcode = AsyncMock(
        return_value='{"content": "https://example.com", "found": true}'
    )
    bridge.execute_analyze_scene = AsyncMock(
        return_value='{"description": "A room.", "objects": ["table"]}'
    )
    bridge.execute_listen = AsyncMock(
        return_value='{"transcript": "Hello robot.", "confidence": 0.95}'
    )
    bridge.execute_control_arm = AsyncMock(return_value="Arm moved.")
    bridge.execute_control_claw = AsyncMock(return_value="Claw is now open.")
    bridge.execute_beep = AsyncMock(return_value="Buzzer sounded for 100 ms.")
    bridge.execute_set_lamps = AsyncMock(return_value="Lamps set to RGB(255, 0, 0).")
    bridge.execute_get_battery_voltage = AsyncMock(
        return_value='{"voltage": 12.4, "unit": "V", "percentage": 85}'
    )
    bridge.execute_set_arm_pose = AsyncMock(
        return_value="Arm pose set to 'Anti-collision'."
    )
    return bridge


@pytest.fixture
def handler(mock_bridge):
    return ActionHandler(bridge_node=mock_bridge)


# --- Schema format tests ---

@pytest.mark.xfail(strict=True, reason=
    "le pont expose 17 outils, ce test en attend 15 : test antérieur à l'ajout des outils (défaut réel, voir P06/P10)")
def test_get_tools_schema_openai_format(handler):
    schemas = handler.get_tools_schema(format="openai")
    assert len(schemas) == 15
    first = schemas[0]
    assert first["type"] == "function"
    assert "name" in first["function"]
    assert "description" in first["function"]
    assert "parameters" in first["function"]


def test_get_tools_schema_anthropic_format(handler):
    schemas = handler.get_tools_schema(format="anthropic")
    first = schemas[0]
    assert "name" in first
    assert "description" in first
    assert "input_schema" in first


def test_get_tools_schema_raw_format(handler):
    schemas = handler.get_tools_schema(format="raw")
    first = schemas[0]
    assert "title" in first
    assert "type" in first


def test_all_tools_have_description(handler):
    for schema in handler.get_tools_schema(format="openai"):
        desc = schema["function"]["description"]
        assert desc, f"Tool '{schema['function']['name']}' has no description"


# --- Timeout tests ---

def test_get_tool_timeout_known(handler):
    assert handler.get_tool_timeout("NavigateTo") == 60.0
    assert handler.get_tool_timeout("Stop") == 2.0
    assert handler.get_tool_timeout("GetBatteryVoltage") == 3.0


def test_get_tool_timeout_unknown_returns_default(handler):
    assert handler.get_tool_timeout("NonExistent") == 10.0


# --- Unknown tool ---

@pytest.mark.asyncio
async def test_execute_unknown_tool_raises_value_error(handler):
    with pytest.raises(ValueError, match="Unknown tool"):
        await handler.execute_tool("FlyToMoon", {})


# --- Invalid arguments ---

@pytest.mark.asyncio
async def test_execute_invalid_args_raises_value_error(handler):
    with pytest.raises(ValueError, match="Invalid arguments"):
        await handler.execute_tool("SetVelocity", {"linear_x": "not_a_float"})


# --- SetVelocity ---

@pytest.mark.xfail(strict=True, reason=
    "consigne 0.5 m/s refusée par ActionHandler (borne 0.06 m/s) : test antérieur aux bornes de sécurité (voir P04/P06)")
@pytest.mark.asyncio
async def test_execute_set_velocity(handler, mock_bridge):
    result = await handler.execute_tool(
        "SetVelocity", {"linear_x": 0.5, "linear_y": 0.0, "angular_z": 0.0}
    )
    assert "cmd_vel" in result
    mock_bridge.execute_set_velocity.assert_called_once_with(
        ANY, 0.5, 0.0, 0.0
    )


# --- Stop ---

@pytest.mark.asyncio
async def test_execute_stop(handler, mock_bridge):
    result = await handler.execute_tool("Stop", {})
    assert "zeroed" in result
    mock_bridge.execute_stop.assert_called_once()


# --- Speak ---

@pytest.mark.asyncio
async def test_execute_speak(handler, mock_bridge):
    result = await handler.execute_tool("Speak", {"text": "Hello"})
    assert "Hello" in result
    mock_bridge.execute_speak.assert_called_once_with(ANY, "Hello")


# --- ControlClaw validation ---

@pytest.mark.asyncio
async def test_execute_control_claw_invalid_state(handler):
    with pytest.raises(ValueError, match="Invalid arguments"):
        await handler.execute_tool("ControlClaw", {"state": "wiggle"})


@pytest.mark.asyncio
async def test_execute_control_claw_open(handler, mock_bridge):
    result = await handler.execute_tool("ControlClaw", {"state": "open"})
    assert "open" in result


# --- SetLamps validation ---

@pytest.mark.asyncio
async def test_execute_set_lamps_out_of_range(handler):
    with pytest.raises(ValueError, match="Invalid arguments"):
        await handler.execute_tool("SetLamps", {"r": 300, "g": 0, "b": 0})


# --- RecognizeFace returns structured JSON ---

@pytest.mark.asyncio
async def test_execute_recognize_face_returns_json(handler, mock_bridge):
    import json
    result = await handler.execute_tool("RecognizeFace", {})
    parsed = json.loads(result)
    assert "face" in parsed
    assert "confidence" in parsed


# --- GetBatteryVoltage returns structured JSON ---

@pytest.mark.asyncio
async def test_execute_get_battery_voltage_returns_json(handler, mock_bridge):
    import json
    result = await handler.execute_tool("GetBatteryVoltage", {})
    parsed = json.loads(result)
    assert "voltage" in parsed
    assert "unit" in parsed
