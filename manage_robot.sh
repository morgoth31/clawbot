#!/bin/bash

# Robot management script using tmux
# Commands: start, stop, restart, attach

SESSION_NAME="robot_bringup"
ROS_DOMAIN_ID=28

function start_robot() {
    echo "Démarrage des nœuds du robot (robot_state_publisher, etc.)..."
    
    # Check if session already exists
    tmux has-session -t $SESSION_NAME 2>/dev/null
    if [ $? == 0 ]; then
        echo "La session '$SESSION_NAME' est déjà en cours d'exécution."
        echo "Utilisez './manage_robot.sh attach' pour voir les logs."
        return
    fi
    
    # Create a new detached session
    tmux new-session -d -s $SESSION_NAME -n "bringup"
    
    # Bringup Window
    tmux send-keys -t $SESSION_NAME:0 "source /opt/ros/humble/setup.bash" C-m
    tmux send-keys -t $SESSION_NAME:0 "source /home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash" C-m
    tmux send-keys -t $SESSION_NAME:0 "export ROS_DOMAIN_ID=$ROS_DOMAIN_ID" C-m
    tmux send-keys -t $SESSION_NAME:0 "export FASTRTPS_DEFAULT_PROFILES_FILE=/home/jetson/clawbot/fastdds_profile.xml" C-m
    tmux send-keys -t $SESSION_NAME:0 "ros2 launch yahboomcar_bringup yahboomcar_bringup_X3_launch.py" C-m
    
    # Camera Window
    tmux new-window -t $SESSION_NAME -n "camera"
    tmux send-keys -t $SESSION_NAME:1 "source /opt/ros/humble/setup.bash" C-m
    tmux send-keys -t $SESSION_NAME:1 "source /home/jetson/clawbot/install/setup.bash" C-m
    tmux send-keys -t $SESSION_NAME:1 "export ROS_DOMAIN_ID=$ROS_DOMAIN_ID" C-m
    tmux send-keys -t $SESSION_NAME:1 "export FASTRTPS_DEFAULT_PROFILES_FILE=/home/jetson/clawbot/fastdds_profile.xml" C-m
    tmux send-keys -t $SESSION_NAME:1 "ros2 launch astra_camera astro_pro_plus.launch.xml" C-m

    # SLAM Window
    tmux new-window -t $SESSION_NAME -n "slam"
    tmux send-keys -t $SESSION_NAME:2 "source /opt/ros/humble/setup.bash" C-m
    tmux send-keys -t $SESSION_NAME:2 "source /home/jetson/clawbot/install/setup.bash" C-m
    tmux send-keys -t $SESSION_NAME:2 "export ROS_DOMAIN_ID=$ROS_DOMAIN_ID" C-m
    tmux send-keys -t $SESSION_NAME:2 "export FASTRTPS_DEFAULT_PROFILES_FILE=/home/jetson/clawbot/fastdds_profile.xml" C-m
    tmux send-keys -t $SESSION_NAME:2 "sleep 5 && ros2 launch /home/jetson/clawbot/slam_launch.py" C-m
    
    echo "Le robot a démarré avec succès en arrière-plan !"
    echo "Utilisez './manage_robot.sh attach' pour voir les logs."
}

function stop_robot() {
    echo "Arrêt du robot..."
    
    # Check if session exists before stopping
    tmux has-session -t $SESSION_NAME 2>/dev/null
    if [ $? != 0 ]; then
        echo "Aucune session '$SESSION_NAME' trouvée."
        return
    fi
    
    # Send Ctrl+C to the running process to stop ROS nodes gracefully
    tmux send-keys -t $SESSION_NAME C-c
    
    # Wait a moment for nodes to shutdown
    sleep 3
    
    # Kill the session completely
    tmux kill-session -t $SESSION_NAME
    echo "Le robot a été arrêté."
}

function attach_robot() {
    tmux has-session -t $SESSION_NAME 2>/dev/null
    if [ $? != 0 ]; then
        echo "Aucune session '$SESSION_NAME' trouvée. Le robot n'est probablement pas démarré."
        return
    fi
    
    echo "Attachement à la session. Appuyez sur Ctrl+b puis d pour vous détacher sans arrêter le robot."
    sleep 2
    tmux attach-session -t $SESSION_NAME
}

case "$1" in
    start)
        start_robot
        ;;
    stop)
        stop_robot
        ;;
    restart)
        stop_robot
        sleep 2
        start_robot
        ;;
    attach)
        attach_robot
        ;;
    *)
        echo "Utilisation : $0 {start|stop|restart|attach}"
        exit 1
        ;;
esac

exit 0
