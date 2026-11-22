# HW-SAF-001 — Multiplexeur, arrêt d'urgence et réarmement (P04)

**Exécutant : l'opérateur.** Hermes ne publie jamais sur `/cmd_vel*` dans le
domaine 28 et n'exécute pas cette procédure.

Robot **sur cales**, roues libres, main sur l'interrupteur. Rien devant le robot.

## Mise en place

```bash
# terminal 1 — état de sécurité en continu
watch -n 0.2 'ROS_DOMAIN_ID=28 ros2 topic echo /safety/state --once'
```

Le champ `state` doit valoir `OK`, `estop_latched` valoir `false`, et `source`
indiquer l'entrée retenue (`teleop`, `nav`, `skill`, `legacy`, ou `null`).

## (a) La téléopération bat le skill

```bash
# terminal 2 — tableau de bord 8001 : 0,05 m/s
curl -s -X POST http://localhost:8001/motion \
     -H 'Content-Type: application/json' \
     -d '{"linear_x": 0.05, "linear_y": 0, "angular_z": 0}'

# terminal 3 — consigne concurrente, plus rapide, sur l'entrée skill
ros2 topic pub -r 10 /cmd_vel/skill geometry_msgs/msg/Twist "{linear: {x: 0.20}}"
```

Attendu : les roues tournent **lentement** (0,05 m/s), pas à 0,20 ; `source`
reste `teleop`. Arrêter la publication concurrente (Ctrl+C) et renouveler le
`curl /motion` toutes les 0,3 s pour garder la téléopération fraîche (son entrée
expire à 0,5 s).

## (b) Mot d'arrêt : e-stop immédiat et verrou

```bash
# arrêter toute publication de vitesse, puis dire « arrête » près du micro
```

Attendu en moins d'une seconde : roues immobiles, `state` = `ESTOP_LATCHED`,
`estop_latched` = `true`. Le journal de la sentinelle montre `ARRET_LOCAL`.

## (c) Téléopération refusée tant que le verrou est actif

```bash
curl -s -X POST http://localhost:8001/motion \
     -H 'Content-Type: application/json' -d '{"linear_x": 0.05}'
```

Attendu : réponse HTTP 200 de la route (`/motion` publie sur l'entrée teleop),
**mais aucune roue ne tourne** : l'arbitre sort un zéro tant que le verrou tient.

## (d) Réarmement par le tableau de bord

```bash
curl -s -X POST http://localhost:8001/estop/reset
```

Attendu : `{"status":"ok","message":"verrou leve"}` ; `estop_latched` passe à
`false`. Si le signal d'e-stop est encore `true`, la réponse est
`{"status":"refuse", ...}` — c'est voulu : relâcher d'abord.

Puis refaire (a) : les roues doivent repartir.

## (e) Durée des callbacks

```bash
watch -n 0.5 'ros2 topic echo /safety/state --once | grep max_callback_ms'
```

Laisser tourner **10 minutes**. Attendu : `max_callback_ms` < 20 en permanence.
Consigner le maximum observé.

## Remise en service / sortie d'essai

Aucune unité n'est arrêtée par cette procédure. Vérifier seulement :

```bash
systemctl is-active clawbot-safety-arbitrator ros2-hardware-service clawbot-sentinel \
                       clawbot-director clawbot-ekf clawbot-slam
ros2 topic hz /cmd_vel_safe     # ~20 Hz
```

## Si l'essai échoue

- Roues qui tournent alors que le verrou est actif : **couper l'alimentation**,
  puis retour arrière du déploiement (`deploy/journal/…`, section Retour
  arrière). Ne pas retenter dans la même session.
- `source` jamais renseigné : le multiplexeur ne reçoit rien — vérifier les
  abonnements (`ros2 topic info /cmd_vel/teleop -v`).
- Réarmement accepté alors que le signal est encore `true` : défaut de sûreté,
  arrêter et revenir en arrière.

## Résultat à consigner

| Point | Mesure |
|---|---|
| (a) téléopération l'emporte | oui / non — `source` observé : ______ |
| (b) délai d'arrêt après le mot | ______ s ; `state` : ______ |
| (c) téléopération refusée sous verrou | oui / non |
| (d) réarmement accepté / refusé à bon escient | ______ |
| (e) `max_callback_ms` max sur 10 min | ______ ms |
| Heure de l'essai | ______ |
