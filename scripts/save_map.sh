#!/bin/bash
# Sauvegarde la carte courante dans la documentation (image + yaml).
set -e
DEST="${1:-/home/jetson/clawbot/docs/assets/maps/carte_couloir}"
export ROS_DOMAIN_ID=28
source /opt/ros/humble/setup.bash
ros2 run nav2_map_server map_saver_cli -f "$DEST" \
  --ros-args -p save_map_timeout:=20.0 -p map_subscribe_transient_local:=true
python3 - "$DEST" <<'PY'
import sys
from PIL import Image
base = sys.argv[1]
Image.open(base + ".pgm").save(base + ".png")
print("carte :", base + ".png")
PY
