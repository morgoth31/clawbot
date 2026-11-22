# ADR-001 — Profondeur Astra : conserver, durcir, piloter par capacité

**Date :** 2026-11-22 · **Statut :** accepté par mesure · **Prompt :** P11
**Décideur :** opérateur (décision prise sur les mesures du 2026-11-22)

## 1. Contexte

L'audit (S09, S12, R01, Q01) décrivait `astra_camera` comme publiant la couleur à 30 Hz et
**aucun message de profondeur**. Deux autres prémisses du prompt se sont révélées fausses à la
vérification, comme le demande le skill :

| Prémisse du prompt | Constat du 2026-11-22 |
|---|---|
| « L'Astra n'a pas d'unité dédiée : elle est lancée par `hardware_service` » (S02, P01-M12) | **Faux aujourd'hui** : `orbbec-camera.service` existe (lien vers `services/orbbec-camera.service`), active depuis le 2026-11-12. `hardware_service.py` ne contient plus aucun motif `astra_camera` |
| « aucun message de profondeur en 12 s » | **Faux aujourd'hui** : `/camera/depth/image_raw` publie **19,36 Hz** (60 s) ; `camera_info` 18,3 Hz |
| « La couleur Astra n'a aucun abonné » (S07) | **Faux aujourd'hui** : 2 abonnés sur la couleur, 3 sur la profondeur (dont `sentinel`) |

Autrement dit, Q01 est déjà tranchée par la mesure : **la profondeur fonctionne sur ce matériel**,
autour de 19 Hz, sans aucun réglage.

## 2. Mesures

| Mesure | Valeur | Commande |
|---|---|---|
| `/camera/color/image_raw` | 20,07 Hz | `ros2 topic hz` (60 s) |
| `/camera/depth/image_raw` | **19,36 Hz** | `ros2 topic hz` (60 s) |
| `/camera/depth/camera_info` | 18,34 Hz | `ros2 topic hz` (60 s) |
| `/camera/ir/image_raw` | 26,07 Hz | `ros2 topic hz` (60 s) |
| Profondeur sur 10 min | voir `deploy/journal/2026-11-22_p11_mesures.md` | `ros2 topic hz` (640 s) |
| CPU du nœud Astra | 68,5 % (instantané, `top`) | `top -b -n 2 -d 2 -p 3678` |
| Bus | USB 2.0 (480 M), deux hubs en cascade | `lsusb -t` |

Le mode demandé par le lancement est `640×480 @ 30 fps` pour la couleur, la profondeur et l'IR
(`astro_pro_plus.launch.xml`). Les cadences obtenues (20 / 19 / 26 Hz) sont cohérentes avec un bus
**USB 2.0 partagé** : le flux n'est pas bloqué, il est borné par la bande passante (P01-M06). Aucune
hypothèse de panne ne tient : ni QoS, ni paramètre désactivé, ni mode non supporté.

## 3. Hypothèses examinées

| # | Hypothèse | Verdict |
|---|---|---|
| H1 | Profondeur désactivée par un paramètre | **Écartée** : `enable_depth:=true` et 19 Hz mesurés |
| H2 | QoS incompatible | **Écartée** : le message arrive ; `camera_info` et `image_raw` se suivent |
| H3 | Bus USB 2 saturé | **Retenue comme explication des cadences** (19 Hz < 30 fps), pas comme panne |
| H4 | Mode vidéo de profondeur non supporté | **Écartée** : mode natif du Pro+ servi par le SDK |

Aucune fenêtre d'immobilisation de 30 min n'a donc été ouverte : le réglage actuel tient déjà
l'exigence, et changer de mode n'aurait fait que dégrader ou déplacer la limite.

## 4. Décision

**Conserver la profondeur**, et traiter les trois défauts réels :

1. **Pilotage** : `depth_vision` passe `managed: true`, `always_on: false` ; l'unité déclarée est
   `orbbec-camera.service` — pas de nouvelle unité `clawbot-astra.service` : elle existe déjà, la
   dupliquer créerait deux pilotes concurrents sur un périphérique exclusif (leçon P07/P08). Écart
   au §4.3 du prompt, assumé et consigné.
2. **Durcissement** : l'unité n'avait aucune protection (P02 ne l'avait pas traitée). Elle reçoit
   `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome=read-only`,
   `ProtectKernelTunables`, `ProtectControlGroups`, `ProtectKernelModules`, `RestrictSUIDSGID`,
   `RestrictRealtime`, `LockPersonality`, `StateDirectory=clawbot` et `ROS_LOG_DIR` dans l'état du
   service.

   **`DeviceAllow` essayée puis retirée** : déclarer une liste `DeviceAllow` fait de systemd un
   filtre exclusif, et l'ouverture usbfs de l'Astra échouait alors en `Could not open
   "2bc5/060f@1/13": Input/output error`, en boucle, sans aucune image. Le retrait a rétabli
   immédiatement 20 Hz. Constat daté du 2026-11-22, journal de déploiement.
   `RestrictRealtime=yes` laisse un avertissement bénin du SDK (« USB events thread - failed to set
   priority ») : les mesures après durcissement ne montrent aucune perte (trou max 0,112 s).
3. **Dépendance par caméra** : `capture_image {camera: astra}` exigeait `wrist_vision` et
   répondait donc `CAPABILITY_INACTIVE` alors que l'Astra publiait — c'est le `CAPABILITY_INACTIVE`
   vu à l'essai P10. Le registre porte maintenant `requires_by_param`.

## 5. Conséquences

- REQ-PERC-002 (retrait complet) **n'est pas applicable** et n'est pas créée.
- `sentinel` conserve son abonnement à `/camera/depth/image_raw` (il fonctionne : 3 abonnés mesurés).
- `expected_flows.yaml` déclarait déjà profondeur (10 Hz) et couleur (25 Hz) sous `depth_vision`.
  La couleur est mesurée à 20,1 Hz sur USB 2 : le seuil de 25 Hz n'est pas tenu physiquement. Il
  passe à **18,0 Hz** (−10 % de la mesure), sans changer le seuil de profondeur.
- Le gestionnaire doit pouvoir `systemctl start|stop orbbec-camera.service` : la règle sudoers est
  régénérée (18 règles nominatives) et **doit être réinstallée** avec `visudo -c` au déploiement.
- Gain CPU attendu quand la capacité est inactive : le nœud mesure 68,5 % de CPU ; la mesure du
  gain réel se fait par `HW-PERC-001` (opérateur).
