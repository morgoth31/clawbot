# ROS Environment Report

## Overview
Based on the system inspection, the primary ROS environment running on this Jetson machine is **ROS 2 Humble**.

### Environment Variables
- `ROS_DISTRO`: humble
- `ROS_LOCALHOST_ONLY`: 0
- Workspace paths indicate usage of `yahboomcar_ros2_ws` (which contains `yahboomcar_msgs`, navigation, and SLAM packages).

---

## 🐳 Docker Containers
There are currently two related Docker containers running on the system:
1. **`ros2_llm_bridge-llm_bridge-1`** (Image: `ros2_llm_bridge-llm_bridge`)
2. **`charles_robot_suite-charles-dashboard-1`** (Image: `yahboomtechnology/ros-foxy-orbslam2:1.0.0`) - *Note: This container appears to be running ROS 1/2 Foxy based on the image name.*

---

## 🤖 Active ROS 2 Nodes
The following ROS 2 nodes were detected as visible on the network:
- `/hardware_service_node`
*(Note: `/llm_bridge_node` also appears to have active services registered, even if not fully listed in `node list`.)*

---

## 📡 Active ROS 2 Topics
The system is currently publishing/subscribing to the following topics:
- `/Buzzer`
- `/RGBLight`
- `/cmd_vel`
- `/parameter_events`
- `/rosout`
- `/servo_ctrl`
- `/voltage`

---

## ⚙️ Active ROS 2 Services
The following services are currently running and available:

### Hardware Service Node Services
- `/hardware_service_node/describe_parameters`
- `/hardware_service_node/get_parameter_types`
- `/hardware_service_node/get_parameters`
- `/hardware_service_node/list_parameters`
- `/hardware_service_node/set_parameters`
- `/hardware_service_node/set_parameters_atomically`

### LLM Bridge Node Services
- `/llm_bridge_node/describe_parameters`
- `/llm_bridge_node/get_parameter_types`
- `/llm_bridge_node/get_parameters`
- `/llm_bridge_node/list_parameters`
- `/llm_bridge_node/set_parameters`
- `/llm_bridge_node/set_parameters_atomically`
