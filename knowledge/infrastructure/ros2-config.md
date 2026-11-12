---
type: Infrastructure
title: "ROS2 Configuration -- Domain 28, FastDDS, Topics"
description: Configuration ROS2 Humble du Clawbot: domaine, profil DDS, topics cles.
status: stable
tags: [ros2, dds, configuration]
generated:
  by: hermes-agent/glm-5.2
  at: 2026-08-10T23:30:00Z
sources:
  - id: fastdds-profile
    resource: file:///home/jetson/clawbot/fastdds_profile.xml
    title: fastdds_profile.xml
    author: human:jetson
    last_modified: 2026-03-02
  - id: codebase-map
    resource: file:///home/jetson/clawbot/CODEBASE_MAP.md
    title: CODEBASE_MAP.md
    author: human:jetson
    last_modified: 2026-03-06
---

# ROS2 Configuration

## Domaine
- **ROS_DOMAIN_ID**: 28 (tous les nodes doivent matcher)
- **Distribution**: ROS2 Humble
- **DDS**: FastDDS (eProsima)

## FastDDS Profile
- **Fichier**: `/home/jetson/clawbot/fastdds_profile.xml`
- **UDP buffers**: 4MB
- **Transport**: UDP (pas de shared memory pour compat Docker)

## Sources ROS2
```bash
source /opt/ros/humble/setup.bash
source /home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash
```

## Topics Cles (~50 total)

### Controle
| Topic | Type | Publisher | Subscriber(s) |
|-------|------|-----------|---------------|
| /cmd_vel | geometry_msgs/Twist | hardware_service | driver_node |
| /servo_ctrl | std_msgs/Int32MultiArray | hardware_service | driver_node |
| /Buzzer | std_msgs/Bool | hardware_service | driver_node |
| /RGBLight | std_msgs/Int32 | hardware_service | driver_node |

### Capteurs
| Topic | Type | Publisher | Subscriber(s) |
|-------|------|-----------|---------------|
| /scan | sensor_msgs/LaserScan | ydlidar_ros2_driver | SLAM, avoidance |
| /voltage | std_msgs/Float32 | driver_node | hardware_service |
| /imu/data_raw | sensor_msgs/Imu | driver_node | hardware_service |
| /vel_raw | geometry_msgs/Twist | driver_node | hardware_service |
| /odom | nav_msgs/Odometry | driver_node | (bug: toujours 0) |

### SLAM/Nav
| Topic | Type | Publisher | Subscriber(s) |
|-------|------|-----------|---------------|
| /map | nav_msgs/OccupancyGrid | cartographer | hardware_service |
| /tf | tf2_msgs/TFMessage | robot_state_publisher | all |

### Vision
| Topic | Type | Publisher | Subscriber(s) |
|-------|------|-----------|---------------|
| /detections | std_msgs/String | yolo_detector | hardware_service |
| /camera/detection_image | sensor_msgs/CompressedImage | yolo_detector | hardware_service |

## Verification
```bash
ROS_DOMAIN_ID=28 ros2 node list
ROS_DOMAIN_ID=28 ros2 topic list
ROS_DOMAIN_ID=28 ros2 topic echo /cmd_vel
```