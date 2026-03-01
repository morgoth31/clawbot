# Clawbot Joy Teleop — Pro Controller / Manette Générique

## Appairage Bluetooth Pro Controller

```bash
bluetoothctl
  power on
  agent on
  scan on
  # Maintenir le bouton SYNC (petit bouton haut du controller)
  pair XX:XX:XX:XX:XX:XX
  connect XX:XX:XX:XX:XX:XX
  trust XX:XX:XX:XX:XX:XX
  quit

# Vérifier que le device est détecté
ls /dev/input/js*
jstest /dev/input/js0     # tester les axes/boutons
```

## Lancement Téléop

```bash
# Terminal 1 — déjà en cours si SLAM actif (driver_node + hardware_service)
# Si pas de SLAM: sudo systemctl start ros2-driver-node

# Terminal 2 — Joystick + Téléop
source /opt/ros/humble/setup.bash
source /home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash
export ROS_DOMAIN_ID=28
ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py

# Ou avec options:
ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py \
  arm_step:=5.0 deadman_button:=7 linear_scale:=0.05
```

## Mapping Contrôles

### Chassis Mécanum (tenir ZR)
| Contrôle        | Action                    |
|-----------------|---------------------------|
| ZR (hold)       | **Deadman** — activer mouvement |
| Stick G. Y      | Avant / Arrière           |
| Stick G. X      | Strafe Gauche / Droite    |
| Stick D. X      | Rotation G / D            |
| Plus (+)        | ⛔ Stop d'urgence          |

### Bras (5 DOF)
| Contrôle        | Servo | Action                |
|-----------------|-------|-----------------------|
| D-pad Y         | S1    | Base haut/bas         |
| D-pad X         | S2    | Épaule gauche/droite  |
| Stick D. Y      | S3    | Coude haut/bas        |
| L (shoulder)    | S4    | Poignet -             |
| R (shoulder)    | S4    | Poignet +             |
| ZL + D-pad X    | S5    | Rotation poignet      |

### Pince & Poses
| Bouton   | Action                    |
|----------|---------------------------|
| A        | Pince ouverte             |
| B        | Pince fermée              |
| Y        | Pose sécurisée (anti-collision) |
| X        | Pose neutre (90°)         |
| Minus (-)| Reset bras → 90° partout  |

## Identifier le Mapping de ta Manette

Si les contrôles ne correspondent pas, lance:
```bash
ROS_DOMAIN_ID=28 python3 /home/jetson/clawbot/joy_teleop/identify_mapping.py
```
Puis bouge les sticks et appuie sur les boutons pour voir les indices.
Ensuite ajuste les constantes en haut de `clawbot_joy_teleop.py`.

## Ajustements Vitesse Bras

Par défaut `arm_step=3°` par tick. Si le bras bouge trop vite ou trop lentement:
```bash
# Plus lent (précis)
ros2 launch ... arm_step:=1.5

# Plus rapide
ros2 launch ... arm_step:=5.0
```

## Sans Deadman (démo/test sur cales)

```bash
ros2 launch /home/jetson/clawbot/joy_teleop/joy_teleop_launch.py deadman_button:=-1
```
(deadman_button=-1 → bouton index -1 = toujours False → chaos garanti, utiliser sur cales uniquement!)

En pratique pour désactiver le deadman: modifier `deadman_held = True` dans le code.
