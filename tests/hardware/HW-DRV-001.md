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
doit répondre `inactive`. Vérifier aussi qu'aucun autre éditeur ne reste :

```bash
ros2 topic info /cmd_vel_safe -v | grep -c "Node name"
# attendu : 0 éditeur (seul l'abonnement du pilote subsiste)
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

```bash
sudo systemctl start clawbot-safety-arbitrator
ros2 topic hz /cmd_vel_safe     # doit remonter à ~20 Hz
ros2 topic hz /safety/state     # doit remonter à ~20 Hz
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

## Résultat à consigner

| Mesure | Valeur |
|---|---|
| Délai entre le dernier message publié et l'arrêt des roues | ______ s |
| Ligne WARN présente | oui / non |
| Nombre de WARN sur 10 s de silence | ______ |
| `/cmd_vel_safe` remonté à 20 Hz après relance | oui / non |
| Heure de l'essai | ______ |
