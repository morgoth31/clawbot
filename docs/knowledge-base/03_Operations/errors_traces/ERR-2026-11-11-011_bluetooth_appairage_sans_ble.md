---
title: "ERR-011 — appairage Bluetooth impossible : noyau sans BLE et profils audio désactivés"
date: "2026-11-11T15:20:00+01:00"
author: "Hermes Agent"
tags: [erreur, bluetooth, audio, a2dp, noyau, rtl8822cu, jetson]
status: ouvert
---

# ERR-2026-11-11-011 — appairage Bluetooth de la SRS-XB100 impossible

| Champ | Valeur |
|---|---|
| Identifiant | ERR-2026-11-11-011 |
| Horodatage | 2026-11-11T14:30:00+01:00 (premier scan) → 15:20:00+01:00 (clôture de l'enquête) |
| Domaine ROS 2 | 28 (aucun topic ROS concerné) |
| Topics concernés | aucun ; chaîne audio PulseAudio / BlueZ |
| Composant | adaptateur Realtek `0bda:c822` (RTL8822CU), `btusb` + `btrtl`, noyau 5.15.148-tegra, BlueZ 5.64 |
| Gravité d'exploitation | moyenne — la sortie vocale A2DP du §9 de la conception est bloquée |
| Statut | **ouvert** — contournement non appliqué |

## 1. Nature de l'échec

L'enceinte Sony SRS-XB100 ne peut pas être appairée au robot. Trois défauts distincts ont été
trouvés, dont deux corrigés :

1. **Profils audio désactivés** par le noyau NVIDIA : `bluetoothd` lancé avec
   `--noplugin=audio,a2dp,avrcp`, donc aucun profil audio enregistré (4 UUID seulement).
2. **Aucun module Bluetooth dans PulseAudio** : `pulseaudio-module-bluetooth` absent.
3. **Noyau compilé sans BLE** (`# CONFIG_BT_LE is not set`) : le contrôleur ne peut pas scanner
   en Bluetooth Low Energy, et l'appairage SSP n'aboutit pas.

## 2. Preuves

### 2.1 Profils audio avant/après

```text
$ systemctl cat bluetooth | grep ExecStart
ExecStart=/usr/lib/bluetooth/bluetoothd -d --noplugin=audio,a2dp,avrcp
$ bluetoothctl show | grep UUID      # avant : 4 UUID (GAP, GATT, PnP, Device Info)

après pose de /etc/systemd/system/bluetooth.service.d/zz-audio.conf :
UUID: Audio Sink (0000110b) · Audio Source (0000110a) · AVRCP (0000110c, 0000110e) · HFP (0000111f)
```

### 2.2 Enceinte invisible à l'inquiry, joignable en page directe

```text
6 scans (25, 40, 60, 40, 50, 60 s) : Acer-F098110B, LORDI-99AHSTMP0, BCSO2405230693,
Charge 6, clavier — jamais SRS-XB100.
$ sudo hcitool cc FF:72:18:F0:2C:C9
Connections:
  < ACL FF:72:18:F0:2C:C9 handle 1 state 7 lm CENTRAL     # la page aboutit
```

Après reset usine, l'enceinte apparaît sous sa vraie adresse `40:72:18:F0:2C:C9` (l'ancienne
`FF:72:18:F0:2C:C9` était une adresse aléatoire en cache) et son SDP est résolu :
`Audio Sink`, `Handsfree`, AVRCP, UUID constructeur Sony.

### 2.3 Blocage SSP, capture HCI

```text
> HCI Event: Link Key Request                       # l'enceinte demande une clé
< HCI Command: Link Key Request Negative Reply      # aucune clé de notre côté
> HCI Event: IO Capability Request                  # SSP engagé
   ... aucune réponse hôte (aucun IO Capability Request Reply) ...
@ MGMT Command: Cancel Pair Device                  # timeout de 25 s
        Status: Cancelled (0x10)
```

`bluetoothctl info` reste à `Paired: no` ; la connexion ACL monte puis retombe.

### 2.4 Absence de BLE dans le noyau

```text
$ zcat /proc/config.gz | grep CONFIG_BT_LE
# CONFIG_BT_LE is not set
$ sudo hcitool lescan
Enable scan failed: Input/output error
```

Test croisé : robot en `Discoverable: yes`, classe `0x006c0000`, nom `yahboom` — un téléphone
Android ne le voit pas non plus. L'inquiry est dégradée dans les deux sens.

### 2.5 Pilote constructeur écarté

```text
$ sudo modprobe -r btusb && sudo modprobe rtk_btusb
rtk_btusb 73728 0            # chargé, aucun adaptateur HCI créé
aucun adaptateur HCI
# retour à btusb : hci0 DC:4A:9E:DF:D6:E3 rétabli, bluetooth actif
```

## 3. Mitigation appliquée

| Horodatage | Action | Résultat mesuré |
|---|---|---|
| 14:33 | `pulseaudio-module-bluetooth` installé (1:15.99.1+dfsg1-1ubuntu2.2) | modules `bluetooth-policy`, `bluetooth-discover`, `bluez5-discover` chargés |
| 14:34 | Drop-in `zz-audio.conf` rétablissant `ExecStart=/usr/lib/bluetooth/bluetoothd` | UUID audio présents après redémarrage |
| 14:44 | Reset usine de l'enceinte (opérateur) | adresse réelle `40:72:18:F0:2C:C9` découverte |
| 14:58 | `btmgmt ssp/sc on` rétablis, `Pairable: yes` | état contrôleur propre |
| 15:12 | Essai du pilote `rtk_btusb` | sans effet, retour à `btusb` |

La pile audio est prête : dès qu'un appairage aboutit, la carte `bluez_card.*` doit apparaître sans
autre changement.

## 4. Conditions de clôture vérifiables

```bash
bluetoothctl info 40:72:18:F0:2C:C9 | grep -q "Paired: yes"
pactl list cards short | grep -q bluez
pactl list sinks short | grep -q bluez
pactl set-default-sink bluez_sink.40_72_18_F0_2C_C9.a2dp_sink
paplay /usr/share/sounds/alsa/Front_Center.wav   # son audible sur l'enceinte
```

Deux voies pour y arriver, aucune essayée à ce jour :

- **dongle Bluetooth USB** (CSR8510/BCM20702) : contourne le noyau sans le modifier ;
- **recompilation du noyau L4T avec `CONFIG_BT_LE=y`** : lourde, risque de démarrage, à planifier
  avec l'opérateur et une sauvegarde de la partition.

## 5. Voir aussi

[[inventaire_materiel]] · [[jetson_orin_nx]] · [[systemd_robot_services]] · [[index]]
