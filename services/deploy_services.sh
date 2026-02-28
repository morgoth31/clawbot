#!/bin/bash
# deploy_services.sh — Symlink all clawbot systemd services from this repo
# Usage: sudo bash services/deploy_services.sh

set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

for svc in "$REPO_DIR"/*.service; do
    name=$(basename "$svc")
    echo "→ Linking $name"
    sudo ln -sf "$svc" "/etc/systemd/system/$name"
done

sudo systemctl daemon-reload
echo "✅ All services deployed and daemon reloaded."
echo "   Run: sudo systemctl enable ros2-hardware-service ros2-driver-node ros2-llm-bridge"
