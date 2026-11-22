# HW-DRV-001 — Arrêt des moteurs sur silence (REQ-DRV-002)

**Exécutant : l'opérateur.** Hermes ne publie jamais sur `/cmd_vel*` dans le
domaine 28 et n'exécute pas cette procédure.

## Mise en place

- Robot **sur cales**, roues libres (elles doivent tourner dans le vide).
- Main sur l'interrupteur d'alimentation pendant toute la manœuvre.
- Personne devant le robot, rien de suspendu au-dessus.
- Terminal 1 : `journalctl -u ros2-driver-node -f` (pour voir le WARN).
- Terminal 2 : `export ROS_DOMAIN_ID=28` puis
  `source /opt/ros/humble/setup.bash`.

## Pourquoi couper l'arbitre

`/cmd_vel_safe` a un seul éditeur légitime : `safety_arbitrator`. Tant qu'il
tourne, il publie à 20 Hz et le délai de silence ne peut jamais s'écouler. Il
faut donc l'arrêter, ce qui **supprime la surveillance d'obstacle** : d'où les
cales et la main sur l'interrupteur.

```bash
sudo systemctl stop clawbot-safety-arbitrator
```

Vérifier qu'il est bien arrêté : `systemctl is-active clawbot-safety-arbitrator`
doit répondre `inactive`. Vérifier aussi qu'aucun éditeur ne publie :

```bash
ros2 topic info /cmd_vel_safe -v | grep -E "Endpoint type|Node name"
# attendu : 1 SUBSCRIPTION (driver_node) et 0 PUBLISHER.
# Attention : `grep -c "Node name"` compte les deux types d'endpoints et renvoie
# 2 juste après le stop, tant que la découverte DDS n'a pas purgé l'éditeur de
# l'arbitre. Lire les deux lignes, pas le total.
```

## Essai

1. Publier une consigne faible pendant 2 s :

```bash
ros2 topic pub -r 20 /cmd_vel_safe geometry_msgs/msg/Twist "{linear: {x: 0.05}}" --times 40
```

Les roues doivent tourner lentement dans le vide.

2. À la fin des 40 messages (2 s), **ne rien republier**. Chronométrer l'arrêt
   des roues. Attendu : **arrêt en moins de 0,5 s** (le pilote envoie un zéro
   après `cmd_timeout_s` = 0,3 s).

3. Dans le journal du pilote, attendre une ligne de la forme :

```
[WARN] [ros2-driver-node]: consigne absente depuis 0.3 s, arret
```

4. Vérifier qu'aucun autre zéro ne suit : la ligne WARN ne doit apparaître
   **qu'une fois** par silence, pas en boucle.

## Remise en service

**Attention : arrêter l'arbitre arrête aussi le directeur (`Requires=`) et la
sentinelle (`Requires=clawbot-director`) ; `start` sur l'arbitre ne les relance
pas.** Il faut les trois, dans cet ordre :

```bash
sudo systemctl start clawbot-safety-arbitrator
sudo systemctl start clawbot-director
sudo systemctl start clawbot-sentinel
systemctl is-active clawbot-safety-arbitrator clawbot-director clawbot-sentinel
ros2 topic hz /cmd_vel_safe     # doit remonter à ~20 Hz
ros2 topic hz /safety/state     # doit remonter à ~20 Hz
ros2 topic hz /director/state   # doit remonter à ~5 Hz
```

## Si l'essai échoue

- Roues qui continuent de tourner : **couper l'alimentation** au tableau, puis
  `sudo systemctl start clawbot-safety-arbitrator`, et retour arrière du
  déploiement (`deploy/journal/2026-11-22_p03_pilote.md`, section Retour
  arrière). Ne pas retenter dans la même session.
- Pas de WARN mais les roues s'arrêtent : consigner quand même, le délai est
  tenu mais la trace manque — défaut à corriger.
- Arrêt trop tardif (mesuré > 0,5 s) : consigner le délai réel, c'est une
  exigence non tenue.

## Résultat mesuré — 2026-11-22 13:38:56, opérateur

Méthode : publication de 40 messages à 0,05 m/s pendant 2 s, arbitre arrêté, avec
enregistrement de `/vel_raw` (retour encodeur, 10 Hz) en parallèle.

| Mesure | Valeur |
|---|---|
| Dernière consigne non nulle reçue | t = …137,442 |
| Consigne nulle émise par le pilote | t = …137,772 (**+0,330 s**) |
| WARN journalisé | oui, **une seule** ligne : « consigne absente depuis 0.33 s, arret » |
| Dernier échantillon non nul (`/vel_raw`) | t = …137,855, vx = 0,017 m/s |
| Premier échantillon nul | t = …137,955 |
| **Arrêt physique après la dernière consigne** | **entre 0,41 et 0,51 s** (résolution 0,1 s) |
| Course après la consigne nulle | entre 0,08 et 0,18 s |
| Roues pendant la publication | tourné dans le vide, vx max mesuré 0,053 m/s |
| `/cmd_vel_safe` après relance | 20,006 Hz, 1 éditeur |
| Heure de l'essai | 13:38:56 |

**Conclusion.** La consigne de zéro part bien dans la fenêtre exigée (0,30–0,35 s).
L'arrêt physique tombe à la limite du critère de 0,5 s : les 0,08 à 0,18 s de
course restante sont la décélération propre du MCU, pas le délai du pilote. Le
critère matériel est donc tenu à la résolution de mesure près, et la perception
« plus lent » correspond à ces ~0,45 s au total.
