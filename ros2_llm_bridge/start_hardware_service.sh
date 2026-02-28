#!/usr/bin/env bash
# Start the hardware service directly on the host (without systemd).
# Use this for development/testing; use systemd for production.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Install Python deps if needed
pip3 install --quiet fastapi uvicorn httpx opencv-python-headless 2>/dev/null || true

export ROSMASTER_PORT="${ROSMASTER_PORT:-/dev/myserial}"
export WORKSPACE_PATH="${WORKSPACE_PATH:-/home/jetson/.openclaw/workspace}"
export CAMERA_FRONT_INDEX="${CAMERA_FRONT_INDEX:-0}"
export CAMERA_CLAW_INDEX="${CAMERA_CLAW_INDEX:-2}"
export HARDWARE_SERVICE_PORT="${HARDWARE_SERVICE_PORT:-8001}"

echo "[hardware_service] Starting on port $HARDWARE_SERVICE_PORT ..."
exec python3 hardware_service.py
