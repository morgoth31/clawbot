#!/bin/bash
# Attend que la manette soit disponible, puis lance le teleop.
# Utilisé par le service systemd clawbot-joy-teleop.service.
#
# Ce script ne devine plus d'index : il transmet le CHEMIN du nœud d'entrée du
# pad (celui dont le nom n'est pas un capteur inertiel) à js_joy_source. La
# traduction « jsN → device_id := N » de la version précédente était fausse :
# `device_id` est un index SDL, dont l'ordre a permuté après une reconnexion
# Bluetooth (mesuré le 2026-11-15 : l'IMU est passé en index 0).

set -u

ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-28}
MANETTE_CONFIG=${MANETTE_CONFIG:-/home/jetson/clawbot/config/manette.yaml}
CONTROLLER_MAC=${CONTROLLER_MAC:-98:B6:E9:43:94:AA}   # adresse publique mesurée le 2026-11-15
MAX_WAIT=${MAX_WAIT:-120}
POLL_INTERVAL=3

echo "[joy-teleop] Démarrage — attente manette..."

# Trouve le nœud js dont le nom n'est pas un capteur inertiel.
trouver_js() {
    local nom=""
    local ligne
    while IFS= read -r ligne; do
        case "$ligne" in
            "N: Name="*)
                nom=${ligne#N: Name=}
                nom=${nom%\"}
                nom=${nom#\"}
                ;;
            "H: Handlers="*)
                local jeton
                for jeton in $ligne; do
                    case "$jeton" in
                        js[0-9]*)
                            if [ -n "$nom" ] && ! echo "$nom" | grep -qiE "IMU|Accel|Gyro|Magnet"; then
                                echo "/dev/input/$jeton"
                                return 0
                            fi
                            ;;
                    esac
                done
                ;;
        esac
    done < /proc/bus/input/devices
    return 1
}

# La reconnexion n'est PAS automatique et ne peut pas être initiée par l'hôte :
# mesuré le 2026-11-15, `bluetoothctl connect` échoue avec
# « br-connection-create-socket ». C'est la manette qui doit reprendre la main,
# par un appui sur n'importe quel bouton — d'où l'attente, sans tentative inutile.
if ! bluetoothctl info "$CONTROLLER_MAC" 2>/dev/null | grep -q "Connected: yes"; then
    echo "[joy-teleop] Manette appairée mais déconnectée."
    echo "[joy-teleop] Appuyer sur un bouton du pad pour qu'elle reprenne la liaison."
fi

waited=0
JSDEV=""
while true; do
    JSDEV=$(trouver_js) && break
    waited=$((waited + POLL_INTERVAL))
    if [ "$waited" -ge "$MAX_WAIT" ]; then
        echo "[joy-teleop] Timeout — aucun nœud js de manette après ${MAX_WAIT}s"
        echo "[joy-teleop] Vérifier : bluetoothctl info $CONTROLLER_MAC ; appuyer sur un bouton du pad"
        exit 1
    fi
    echo "[joy-teleop] Attente... ${waited}s/${MAX_WAIT}s"
    sleep $POLL_INTERVAL
done

echo "[joy-teleop] Manette trouvée sur $JSDEV (ROS_DOMAIN_ID=$ROS_DOMAIN_ID)"

# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
# shellcheck disable=SC1091
source /home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash
export ROS_DOMAIN_ID=$ROS_DOMAIN_ID

exec ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py \
    device_path:="$JSDEV" manette_config:="$MANETTE_CONFIG"
