#!/bin/bash
set -e

# Setup ROS 2 environment
source /opt/ros/humble/setup.bash
if [ -f /app/install/setup.bash ]; then
    source /app/install/setup.bash
fi

# Start the FastAPI server
exec uvicorn ros2_llm_bridge.api_server:app --host 0.0.0.0 --port 8000
