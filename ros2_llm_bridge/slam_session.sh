#!/usr/bin/env bash
# slam_session.sh — Start a cartographer SLAM mapping session
# Usage: ./slam_session.sh [start|save|stop]

set -e
WS1="/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash"
WS2="/home/jetson/yahboomcar_ros2_ws/software/library_ws/install/setup.bash"
MAP_DIR="/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/yahboomcar_nav/share/yahboomcar_nav/maps"
SESSION="slam_mapping"

export ROBOT_TYPE=x3
export RPLIDAR_TYPE=4ROS

case "${1:-start}" in
  start)
    echo "[slam] Stopping hardware service to free serial port..."
    sudo systemctl stop ros2-hardware-service

    echo "[slam] Restarting bridge container (picks up motion fallback)..."
    cd /home/jetson/ros2_llm_bridge && docker compose restart
    sleep 5

    echo "[slam] Starting cartographer SLAM in tmux session '$SESSION'..."
    tmux new-session -d -s "$SESSION" -x 220 -y 50

    tmux send-keys -t "$SESSION" \
      "export ROBOT_TYPE=x3 RPLIDAR_TYPE=4ROS && \
       source $WS1 && source $WS2 && \
       ros2 launch yahboomcar_nav map_cartographer_launch.py" Enter

    sleep 3
    echo ""
    echo "✅ SLAM started in tmux session '$SESSION'"
    echo "   Watch logs:  tmux attach -t $SESSION"
    echo "   Save map:    ./slam_session.sh save my_map"
    echo "   Stop:        ./slam_session.sh stop"
    ;;

  save)
    NAME="${2:-new_map_$(date +%Y%m%d_%H%M%S)}"
    SAVE_PATH="$MAP_DIR/$NAME"
    echo "[slam] Saving map as '$NAME'..."
    source "$WS1" && source "$WS2"
    ros2 run nav2_map_server map_saver_cli -f "$SAVE_PATH" --ros-args -p save_map_timeout:=5.0
    echo "✅ Map saved: $SAVE_PATH.pgm + $SAVE_PATH.yaml"
    ;;

  stop)
    echo "[slam] Killing SLAM session..."
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    echo "[slam] Restarting hardware service..."
    sudo systemctl start ros2-hardware-service
    sleep 3
    echo "✅ Back to normal — hardware service running:"
    curl -s http://localhost:8001/health
    ;;
esac
