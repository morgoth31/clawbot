# Dossier de déploiement — P11, Astra pilotée et durcie

**Date :** 2026-11-22 · **Branche :** `fix/REQ-PERC-001-astra` · **Commit :** voir fin de dossier
**Robot requis :** sur cales, immobile, aucune mission en cours · **Indisponibilité :** ≈ 2 min
(redémarrages d'unités, la caméra est exclusive : elle est arrêtée puis relancée)

## 1. Ce qui change

| Élément | Avant | Après |
|---|---|---|
| `services/orbbec-camera.service` | aucune protection systemd | durcie (P02) : `NoNewPrivileges`, `ProtectSystem=full`, `ProtectHome=read-only`, `PrivateTmp`, `ProtectKernel*`, `RestrictSUIDSGID`, `RestrictRealtime`, `LockPersonality`, `StateDirectory=clawbot`, `ROS_LOG_DIR`, `DeviceAllow` ciblée |
| `capabilities.yaml` → `depth_vision` | `managed: false` | `managed: true`, `always_on: false` |
| `deploy/sudoers/clawbot-capabilities` | 16 règles (8 unités) | **18 règles (9 unités)** : + `start|stop orbbec-camera.service` |
| `expected_flows.yaml` → couleur Astra | `min_hz: 25.0` (jamais tenu : 20,1 Hz mesurés) | `min_hz: 18.0` (mesure − 10 %, C12) |
| `skills.yaml` → `capture_image` | `requires: [wrist_vision]` (refusait l'Astra quand le poignet était en panne) | `requires_by_param` : `wrist → wrist_vision`, `astra → depth_vision` |
| `clawbot_executive` | — | `requires_by_param` dans le registre et les préconditions |

## 2. Unités touchées (une à la fois, dans cet ordre)

1. `orbbec-camera` — `daemon-reload` puis `restart` (durcissement).
2. `clawbot-capability-manager` — relit `capabilities.yaml` (`depth_vision` pilotable).
3. `clawbot-skill-server` — code `clawbot_executive` reconstruit.
4. `clawbot-health-monitor` — relit `expected_flows.yaml`.
5. `clawbot-sentinel` — inchangé, mais redémarré en dernier pour repartir sur les nouveaux flux.

## 3. Fichiers hors dépôt touchés

- `/etc/sudoers.d/clawbot-capabilities` : **remplacé** (18 règles nominales) après `visudo -c` et
  sauvegarde dans `~/clawbot_backups/<TS>/`. C'est une écriture dans `/etc` : incluse dans l'accord.
- `/etc/systemd/system/orbbec-camera.service` est un **lien** vers le dépôt : le durcissement passe
  par `daemon-reload`, aucun fichier de `/etc` n'est réécrit.

## 4. Décision jointe : `disable` de l'unité

Aujourd'hui `orbbec-camera.service` est `enabled` : elle démarre au boot, en permanence, même si
personne ne consomme la profondeur (68,5 % de CPU). Le prompt demande « qu'elle ne tourne plus en
permanence si personne ne la consomme ». Je propose donc `systemctl disable orbbec-camera.service`
(le gestionnaire la démarre à la demande via `set depth_vision true`).

**Conséquence à accepter** : au boot, la profondeur n'est **pas** disponible tant que la capacité
n'est pas activée ; `sentinel` ne reçoit plus d'images de profondeur au démarrage (sa règle de
distance reste inerte et doit être documentée comme telle), et `capture_image {camera: astra}`
répond `CAPABILITY_INACTIVE` jusqu'à l'activation. Si vous préférez garder la caméra active au boot,
dites-le : je laisse `enabled` et la capacité démarre ACTIVE.

## 5. Contrôles après bascule

```bash
systemctl is-active orbbec-camera clawbot-capability-manager clawbot-skill-server clawbot-health-monitor
ros2 topic hz /camera/depth/image_raw        # ≈ 19 Hz, capacité active
ros2 topic hz /camera/color/image_raw        # ≈ 20 Hz
ros2 service call /clawbot/capabilities/list  # depth_vision ACTIVE
bash ~/.hermes/skills/clawbot/clawbot-deploy/scripts/smoke_check.sh
```

Puis `HW-PERC-001` (opérateur) : `set depth_vision false` → `pgrep astra_camera_node` = 0, plus
aucun message couleur/profondeur, CPU relevé ; `set depth_vision true` → retour à ≈ 19 Hz.

## 6. Retour arrière

```bash
cd /home/jetson/clawbot
git checkout $(cat ~/clawbot_backups/<TS>/commit_precedent.txt)
rm -rf install && tar -C /home/jetson/clawbot -xzf ~/clawbot_backups/<TS>/install.tgz
sudo install -m 0440 ~/clawbot_backups/<TS>/clawbot-capabilities /etc/sudoers.d/clawbot-capabilities
sudo systemctl daemon-reload
sudo systemctl start orbbec-camera clawbot-capability-manager clawbot-skill-server clawbot-health-monitor
bash ~/.hermes/skills/clawbot/clawbot-deploy/scripts/smoke_check.sh
```

## 7. Résultat

*(à remplir après la bascule)*
