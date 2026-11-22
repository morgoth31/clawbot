#!/bin/bash
# clawbot_restart_teleop.sh
# Nettoie les processus de téléopération et relance proprement la chaîne manette.

set -u

ICI=$(cd "$(dirname "$0")" && pwd)

echo "========================================================"
echo "🧹 1. Nettoyage des processus de téléopération"
echo "========================================================"

# -x : nom exact, pour ne pas tuer le shell qui porte le motif dans sa ligne de
# commande (piège rencontré avec pkill -f sur des motifs courts).
pkill -x js_joy_source 2>/dev/null || true
pkill -x joy_node 2>/dev/null || true
pkill -f "clawbot_joy_teleop.py" 2>/dev/null || true
pkill -f "joy_teleop_launch.py" 2>/dev/null || true
sleep 2

echo ""
echo "========================================================"
echo "🤖 2. Redémarrage du service ROS 2 Hardware (driver_node)"
echo "========================================================"
sudo systemctl restart ros2-driver-node
echo "✅ ros2-driver-node redémarré"

echo ""
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
# shellcheck disable=SC1091
source /home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-28}

echo ""
echo "========================================================"
echo "🎮 3. Vérification de la manette"
echo "========================================================"

# Le pad est le nœud js dont le nom n'est pas un capteur inertiel : son IMU
# apparaît elle aussi comme une manette, avec exactement le même nom SDL.
trouver_js() {
    local nom="" ligne jeton
    while IFS= read -r ligne; do
        case "$ligne" in
            "N: Name="*) nom=${ligne#N: Name=}; nom=${nom%\"}; nom=${nom#\"} ;;
            "H: Handlers="*)
                for jeton in $ligne; do
                    case "$jeton" in
                        js[0-9]*)
                            if [ -n "$nom" ] && ! echo "$nom" | grep -qiE "IMU|Accel|Gyro|Magnet"; then
                                echo "/dev/input/$jeton"
                                return 0
                            fi ;;
                    esac
                done ;;
        esac
    done < /proc/bus/input/devices
    return 1
}

while ! JSDEV=$(trouver_js); do
    echo "❌ Aucun nœud /dev/input/js* de manette"
    echo "   👉 allumer la manette (appui sur un bouton)"
    echo "   👉 vérifier : bluetoothctl info 98:B6:E9:43:94:AA"
    echo "   👉 si elle n'est pas appairée : sudo bash $ICI/pair_procontroller.sh"
    echo ""
    echo "Recherche en cours... (Ctrl+C pour annuler)"
    sleep 3
done

echo "✅ Manette détectée sur $JSDEV"

echo ""
echo "========================================================"
echo "🚀 4. Lancement du Joy Teleop"
echo "========================================================"
echo "Chemin du périphérique transmis explicitement — aucun index SDL à deviner."
echo "Appuyez sur Ctrl+C pour quitter."
echo "--------------------------------------------------------"

ros2 launch "$ICI/joy_teleop_launch.py" device_path:="$JSDEV"
