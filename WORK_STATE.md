# WORK_STATE.md — État d'avancement du projet Clawbot
<!-- Auto-maintenu par Clawbot. Ne pas éditer manuellement. -->

## Dernière mise à jour
2026-03-01

## Priorité des tâches (cf. todo.md)

### ✅ Terminé
- [x] ros2-llm-bridge → /home/jetson/clawbot/
- [x] ros2-hardware-service → clawbot/
- [x] ros2-driver-node service créé et actif
- [x] LIDAR_SAFETY_REQUIRED=false bypass
- [x] scan_safety.py créé
- [x] /system/status endpoint (hardware_service.py)
- [x] Monitoring UI — System Status card
- [x] services/ folder versioned (deploy_services.sh)

### 🔄 En cours
- [ ] **TÂCHE 2.1** — Calibration Mecanum (test sol + facteur glissement)
- [ ] **TÂCHE 2.2** — MoveIt2 arm configuration

### 📋 Terminé aujourd'hui
- [x] **TÂCHE 1.1** URDF validé ✅ — urdf/clawbot_X3.urdf + validate_urdf.py
  - 9 links, 8 joints, arbre continu base_footprint→camera_link
  - xacro upstream a bug `ns` → utiliser URDF statique
- [x] **TÂCHE 4.1** Foxglove WebSocket bridge ✅ — rosbridge port 9090 actif
  - service: services/rosbridge.service (auto-start)
  - Connexion Foxglove: ws://[IP_ROBOT]:9090
- [x] **TÂCHE 3.1** Orbbec Astra Pro ✅ — device trouvé (serial ACRMB43003E)
  - depth 640x480@30Hz, launch: astra_camera astra_pro.launch.xml
  - service: services/orbbec-camera.service (non auto-start, à lancer manuellement)
- [x] **TÂCHE 3.2** YOLO ROS2 node ✅ — yolo_node/yolo_detector.py
  - Topics: /detections (JSON), /camera/detection_image (CompressedImage)
  - Tests OK: import + caméra 640x480
  - service: services/yolo-detector.service (non auto-start)

### 📋 À faire (priorité décroissante)

#### Moyen (1-4h)
- [ ] **TÂCHE 2.1** Calibration Mecanum — test sol + facteur correction glissement
- [ ] **TÂCHE 4.2** Dashboard étendu — Foxglove layout (LaserScan, IMU, arm, YOLO feed)

#### Large (> 4h)
- [ ] **TÂCHE 2.2** MoveIt2 config bras 5-DOF (SRDF, kinematics.yaml, move_group)
- [ ] **TÂCHE 3.3** SLAM 3D avec Orbbec + RTAB-Map

## Notes techniques importantes
- URDF: urdf/clawbot_X3.urdf valide, xacro upstream bugué (arg ns)
- Orbbec: astra_camera pkg dans library_ws, device ACRMB43003E OK
- YOLO: yolov5_env (Python 3.10, torch 2.5, cv2 4.11)
- Foxglove: ws://[ROBOT_IP]:9090 — tous les topics ROS2 domain 28
- Mecanum latence API: ~32ms (watchdog 1.5s)
- ROS_DOMAIN_ID=28, /dev/myserial→ttyUSB0 (CH340)
- MoveIt2: servo IDs 1-6, ranges dans BODY.md

## Agents en cours
(aucun)
