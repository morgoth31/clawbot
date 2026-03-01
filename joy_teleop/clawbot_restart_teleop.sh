#!/bin/bash

# clawbot_restart_teleop.sh
# Script pour nettoyer et relancer proprement les nœuds de contrôle de la manette.

echo "========================================================"
echo "🧹 1. Nettoyage des processus fantômes..."
echo "========================================================"

# Tuer les processus launch
pkill -f "joy_teleop_launch.py"
# Tuer les nœuds Python et C++
pkill -f "clawbot_joy_teleop.py"
pkill -f "joy_node"

echo "Attente de l'arrêt des processus..."
sleep 2

echo ""
echo "========================================================"
echo "🤖 2. Redémarrage du service ROS2 Hardware (driver_node)"
echo "========================================================"
# Le README indique de lancer ros2-driver-node si le SLAM n'est pas actif.
# On le redémarre pour avoir une base saine.
sudo systemctl restart ros2-driver-node
echo "✅ ros2-driver-node redémarré (mot de passe sudo peut-être requis ci-dessus)."

echo ""
# Source des environnements ROS 2
source /opt/ros/humble/setup.bash
source /home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash

export ROS_DOMAIN_ID=28

echo ""
echo "========================================================"
echo "🎮 3. Vérification de la Manette"
echo "========================================================"

while [ ! -e /dev/input/js0 ]; do
    echo "❌ Manette introuvable sur /dev/input/js0 !"
    echo "   👉 Veuillez allumer votre manette (appuyez sur le bouton Home ou n'importe quel bouton)."
    echo "   👉 Assurez-vous que les voyants indiquent une connexion Bluetooth/USB."
    echo "   👉 Si elle n'est pas appairée, ouvrez un autre terminal et exécutez :"
    echo "      /home/jetson/clawbot/joy_teleop/pair_procontroller.sh"
    echo ""
    echo "Recherche en cours... (Ctrl+C pour annuler)"
    sleep 3
done

echo "✅ Manette détectée !"

echo ""
echo "========================================================"
echo "🚀 4. Lancement du Joy Teleop"
echo "========================================================"
echo "Lancement de joy_teleop_launch.py avec device_id:=0 (Boutons/Sticks)"
echo "⚠️  (Ne pas utiliser device_id:=1 car c'est le gyroscope IMU !)"
echo "Appuyez sur Ctrl+C pour quitter."
echo "--------------------------------------------------------"

# On force device_id:=0 car c'est le périphérique contenant les boutons et joysticks
ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py device_id:=0
