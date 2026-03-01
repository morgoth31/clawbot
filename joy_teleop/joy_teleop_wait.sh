#!/bin/bash
# Attend que la manette soit disponible, puis lance le teleop
# Utilisé par le service systemd clawbot-joy-teleop.service

set -e

ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-28}
CONTROLLER_MAC="98:B6:1F:49:26:F3"
MAX_WAIT=120   # secondes max avant abandon
POLL_INTERVAL=3

echo "[joy-teleop] Démarrage — attente manette..."

# Attendre que /dev/input/js0 (ou js1, js2) apparaisse
waited=0
while true; do
    if ls /dev/input/js* 2>/dev/null | head -1 | grep -q "js"; then
        JSDEV=$(ls /dev/input/js* | head -1)
        echo "[joy-teleop] Manette détectée: $JSDEV"
        break
    fi
    
    # NE PAS essayer de connecter depuis le host — pour le Pro Controller BT,
    # c'est la MANETTE qui doit initier la connexion (appui sur un bouton).
    # Un connect() depuis le host échoue avec br-connection-create-socket.
    
    waited=$((waited + POLL_INTERVAL))
    if [ $waited -ge $MAX_WAIT ]; then
        echo "[joy-teleop] Timeout — pas de manette après ${MAX_WAIT}s"
        exit 1
    fi
    
    echo "[joy-teleop] Attente... ${waited}s/${MAX_WAIT}s"
    sleep $POLL_INTERVAL
done

# Extraire l'index du device (js0 → 0, js1 → 1)
DEVICE_ID=$(echo "$JSDEV" | grep -oP '\d+$')
echo "[joy-teleop] Lancement avec device_id=$DEVICE_ID (ROS_DOMAIN_ID=$ROS_DOMAIN_ID)"

# Source ROS2
source /opt/ros/humble/setup.bash
source /home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash
export ROS_DOMAIN_ID=$ROS_DOMAIN_ID

exec ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py \
    device_id:=$DEVICE_ID
