---
title: "Procédure — mise à jour du firmware de la carte Rosmaster"
date: "2026-11-10T11:30:00+01:00"
author: "Hermes Agent"
tags: [operations, firmware, mcu, rosmaster, stm32, procedure, flashage]
status: actif
---

# Procédure — mise à jour du firmware de la carte Rosmaster

Procédure constructeur pour reprogrammer le microcontrôleur de la carte d'extension (STM32) qui pilote moteurs, encodeurs, centrale inertielle, servos, ruban RGB et buzzer. Composant concerné : [[rosmaster_x3_mcu]] ; source : dépôt `YahboomTechnology/ROSMASTERX3-PLUS`, chapitre `05.Basic course/1. Update the firmware/1. Update the firmware.pdf`.

**Cette procédure n'a pas été exécutée sur ce robot.** Aucune version de firmware MCU n'a été relevée à ce jour (voir [[rosmaster_x3_mcu]] §7) : il n'existe donc ni version de départ ni version cible validées ici.

## 1. Quand l'appliquer

Le constructeur écrit que le microcontrôleur est programmé en usine et demande de **ne pas mettre à jour le firmware sans nécessité**. Cette page existe pour rendre l'opération reproductible si un défaut matériel documenté l'exige (perte du lien série, comportement moteur incohérent après vérification du câblage, régression connue du firmware), pas comme opération de maintenance courante.

## 2. Prérequis

| Prérequis | Détail | Vérification |
|---|---|---|
| Fichier firmware | `Rosmaster_XXX.hex` fourni avec les cours du dépôt constructeur | empreinte du fichier notée avant flashage |
| Outil de flashage | `mcuisp` (ou `flymcu`), outil **Windows** portable ; aucune voie Linux documentée par le constructeur | exécutable présent sur le poste de flashage |
| Pilote CH340 | `CH341SER.EXE` si le poste ne connaît pas déjà le pont `1a86:7523` | port COM visible dans l'outil |
| Câble | micro-USB **de données** (pas un câble de charge seule) | — |
| Alimentation | carte alimentée en DC 12 V par la batterie ; jamais par l'USB 5 V pour un essai moteur | `1.About expansion boardV3.0.pdf` §12.5 du cours moteur |

Avant de brancher la carte sur le poste de flashage, débrancher le câble micro-USB **et** l'alimentation qui relient la carte au Jetson, conformément à la procédure constructeur.

## 3. Séquence

1. Ouvrir `mcuisp`, sélectionner le port série correspondant à la carte. En cas de doute entre plusieurs ports : débrancher le câble de la carte, lancer une recherche, noter les ports, rebrancher, relancer la recherche — le port apparu est celui de la carte.
2. Sélectionner le fichier `Rosmaster_XXX.hex` (chemin sans caractère chinois ni symbole).
3. Régler les options de téléchargement sur **« DTR low-level reset, RTS high-level into BootLoader »**. Sans cette option, le constructeur signale un échec de téléchargement.
4. Mettre le microcontrôleur en mode programmation : **maintenir BOOT0, appuyer sur RESET, relâcher BOOT0**.
5. Lancer la programmation. Succès = message `successfully run www.mcuisp.com ...`.
6. Débrancher le câble de données, remettre la carte sous alimentation 12 V, rebrancher le lien vers le Jetson, puis redémarrer le service du nœud de conduite.

## 4. Vérification après flashage

Aucune de ces commandes n'a encore été exécutée après un flashage : elles constituent les critères de clôture à satisfaire.

```bash
sudo systemctl restart ros2-driver-node.service
systemctl is-active ros2-driver-node.service
export ROS_DOMAIN_ID=28 && source /opt/ros/humble/setup.bash
ros2 topic hz /voltage          # ~10 Hz
ros2 topic hz /imu/data_raw     # ~10 Hz
ros2 topic echo --once --field name /joint_states
```

Lecture de la version MCU, qui exige l'arrêt du nœud de conduite (le port `/dev/ttyUSB1` ne peut pas être partagé) :

```bash
sudo systemctl stop ros2-driver-node.service
python3 -c "from Rosmaster_Lib import Rosmaster; r=Rosmaster(); print(r.get_version())"
sudo systemctl start ros2-driver-node.service
```

Essai moteur roues levées : `/cmd_vel` non nul doit faire tourner les quatre roues dans le sens attendu, et `/vel_raw` doit renvoyer une vitesse non nulle.

## 5. Risques et retour arrière

| Risque | Effet | Parade |
|---|---|---|
| Flashage interrompu (câble, alimentation) | microcontrôleur en mode BootLoader, carte muette | relancer la séquence §3 ; la reprise par BOOT0+RESET reste possible tant que la carte s'alimente |
| Firmware d'une autre variante de châssis | moteurs inversés, encodeurs incohérents | conserver l'empreinte de l'ancien `.hex` et le reflasher |
| Flashage pendant que le Jetson tient le port | échec de téléchargement | débrancher le lien Jetson avant (§2) |
| Perte de la configuration Flash (type de châssis, PID) | comportement par défaut | `set_car_type(1)` et `set_pid_param(...)` à recharger, ou `reset_flash_value()` pour un retour usine explicite |

Retour arrière : reflasher le fichier `.hex` précédent avec la même séquence ; aucune sauvegarde automatique n'existe sur la carte.

## 6. Voir aussi

- Carte de commande et protocole série : [[rosmaster_x3_mcu]]
- Nœud consommateur : [[yahboomcar_bringup_driver_node]]
- Unités systemd à redémarrer : [[systemd_robot_services]]
- Dépôt constructeur et cours d'origine : [[documentation_constructeur_yahboom]]
