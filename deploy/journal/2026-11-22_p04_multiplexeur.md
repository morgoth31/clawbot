# Déploiement P04 — arbitre multiplexé et arrêt d'urgence verrouillé

**Date :** 2026-11-22 · **Branche :** `feat/REQ-SAFETY-010-multiplexeur` · **Commit :** `1409f83`
**État du robot requis :** sur cales, roues libres, personne devant le robot, opérateur présent
pour HW-SAF-001. Indisponibilité estimée : 2 min (une construction + quatre redémarrages).

## Ce qui change sur le robot

| Unité | Redémarrage | Effet visible |
|---|---|---|
| `clawbot-director` | oui | lit `/safety/state` en JSON **ou** en chaîne nue |
| `clawbot-safety-arbitrator` | oui | multiplexeur 4 entrées, e-stop verrouillé, `/safety/state` en JSON, `Nice=-10`, cœur 4, YAML chargé |
| `ros2-hardware-service` | oui | publie la téléopération sur `/cmd_vel/teleop`, nouvelle route `POST /estop/reset` |
| `clawbot-sentinel` | oui | ne publie plus de vitesse ; ses mots d'arrêt posent `/safety/estop` |

**Ordre imposé :** directeur **d'abord**, puis arbitre. Un directeur non redémarré lit le JSON
de l'arbitre comme un état inconnu, refuse les tâches et annule celle en cours ; le nouveau
directeur accepte les deux formes, donc il peut être redémarré avant sans conséquence.

Aucun fichier hors du dépôt n'est modifié : `/etc/systemd/system/clawbot-*.service` sont des
liens vers le dépôt. Aucune écriture dans `/etc`.

## Construction

L'installation en service est une **copie** (aucun lien symbolique sous `install/`) : la
modification du dépôt n'a aucun effet tant que `colcon build` n'a pas réécrit `install/`.

```bash
cd /home/jetson/clawbot
source /opt/ros/humble/setup.bash
colcon build --packages-select clawbot_safety clawbot_sim clawbot_sentinel clawbot_director \
             ros2_llm_bridge
```

Contrôle après construction : `install/clawbot_safety/share/clawbot_safety/config/arbitrator.yaml`
existe, et `ros2 pkg executables clawbot_sim` liste `fake_inputs`.

## Contrôles attendus

```bash
ros2 topic hz /cmd_vel_safe                       # 20 Hz ± 10 % (18–22)
ros2 topic info /cmd_vel_safe -v | grep -c "Node name"   # 1 éditeur (safety_arbitrator)
ros2 topic info /cmd_vel -v | grep "Node name"    # llm_bridge_node seul (legacy, priorité 10)
ros2 topic echo /safety/state --once              # JSON : state, source, estop_latched=false, max_callback_ms
ros2 param get /safety_arbitrator inputs.teleop.priority   # 100
ros2 param set /safety_arbitrator publish_rate_hz 10.0     # refusé : read-only
systemctl show clawbot-safety-arbitrator -p Nice -p CPUAffinity   # -10 / 4
bash ~/.hermes/skills/clawbot/clawbot-deploy/scripts/smoke_check.sh
```

Puis **HW-SAF-001** (`tests/hardware/HW-SAF-001.md`), exécuté par l'opérateur : téléopération
0,05 m/s, concurrence sur `/cmd_vel/skill`, mot d'arrêt, refus sous verrou, réarmement par
`POST /estop/reset`, relevé de `max_callback_ms` sur 10 min.

## Risques connus

- **Réarmement.** Après un mot d'arrêt, seul `POST http://localhost:8001/estop/reset` lève le
  verrou, et seulement si `/safety/estop` est retombé à `false`. L'outil MCP `stop_robot` ne
  passe pas encore par `/safety/estop` (prévu P10/P14) : il publie encore sur `/cmd_vel`.
- **QoS.** Tout éditeur de `/safety/estop` non `TRANSIENT_LOCAL` est ignoré par l'arbitre ;
  l'abonné est `RELIABLE` + `TRANSIENT_LOCAL`. Constaté et corrigé pendant les tests.
- **`/safety/state` en JSON.** Tout consommateur qui compare la chaîne brute à `"OK"` cesse de
  fonctionner. Le directeur est adapté ; les scripts `scripts/test_safety_hold.py` et
  `clawbot_arm_controller` lisent `/safety/hold` (Bool), inchangé.
- Le verrou survit à l'arrêt du nœud ? Non : il vit en mémoire. Un redémarrage de l'arbitre
  relâche le verrou — c'est un geste d'exploitation, pas un geste de sûreté.

## Retour arrière

```bash
TS=<horodatage de la sauvegarde>
cd /home/jetson/clawbot
git checkout afa59a0        # dernier commit avant le code P04 (exigences + tests seulement)
rm -rf install && tar -C /home/jetson/clawbot -xzf ~/clawbot_backups/$TS/install.tgz
sudo systemctl daemon-reload
sudo systemctl restart clawbot-sentinel ros2-hardware-service clawbot-safety-arbitrator clawbot-director
bash ~/.hermes/skills/clawbot/clawbot-deploy/scripts/smoke_check.sh
```

Le retour arrière est sûr dans les deux sens : l'ancien arbitre publie `/safety/state` en chaîne
nue, que le nouveau directeur accepte.

## Journal

| Heure | Étape | Résultat |
|---|---|---|
| | accord opérateur | |
| | sauvegarde | |
| | construction | |
| | redémarrages | |
| | contrôles | |
| | HW-SAF-001 | |
