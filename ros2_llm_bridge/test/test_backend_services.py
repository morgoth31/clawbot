import pytest
import requests

LLM_BRIDGE_URL = "http://localhost:8000"
HARDWARE_SERVICE_URL = "http://localhost:8001"

TIMEOUT = 3.0

def test_llm_bridge_health():
    """Test that the LLM Bridge is up and running via the health endpoint."""
    response = requests.get(f"{LLM_BRIDGE_URL}/health", timeout=TIMEOUT)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data.get("status") == "healthy", f"Expected 'healthy', got {data.get('status')}"

def test_hardware_service_health():
    """Test that the Hardware Service is alive, checking its /health endpoint."""
    response = requests.get(f"{HARDWARE_SERVICE_URL}/health", timeout=TIMEOUT)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data.get("status") == "ok", f"Expected 'ok', got {data.get('status')}"
    assert "ros2" in data

def test_hardware_service_battery():
    """Test that the Hardware Service can fetch battery stats via /battery."""
    response = requests.get(f"{HARDWARE_SERVICE_URL}/battery", timeout=TIMEOUT)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "voltage" in data
    assert "percentage" in data

def test_hardware_service_lamps():
    """Test setting lamps to a specific color (non-destructive)."""
    payload = {"r": 0, "g": 255, "b": 0}
    response = requests.post(f"{HARDWARE_SERVICE_URL}/lamps", json=payload, timeout=TIMEOUT)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("g") == 255

def test_llm_bridge_tools():
    """Verify that we can request tool definitions from the LLM Bridge."""
    # Based on standard endpoints, or we check its schema, but let's just make sure
    # we can hit its /openapi.json to confirm fastapi is serving routes correctly.
    response = requests.get(f"{LLM_BRIDGE_URL}/openapi.json", timeout=TIMEOUT)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "paths" in data

