# HW-ARM-001 — Mise en service du bras comme capacité (P13)

**Exécutant :** l'opérateur, à côté du robot, main sur l'arrêt.
**Hermes n'envoie aucun goal de bras dans le domaine 28.** Toutes les commandes de ce
document sont lancées par l'opérateur, depuis un terminal du Jetson.

**État requis :** robot immobile, sur cales ou au sol, espace de débattement du bras
dégagé (le bras peut balayer ~0,44 m devant la colonne et descendre sous le niveau du
châssis), personne dans le volume de travail.

**Arrêt d'urgence :** bouton du tableau de bord, ou `stop_robot` depuis le profil MCP
pilote. Ne jamais couper l'alimentation des servos pendant un mouvement : le bras
retombe.

## 0. Préparation

```bash
# terminal opérateur, domaine 28
export ROS_DOMAIN_ID=28
source /opt/ros/humble/setup.bash
source /home/jetson/clawbot/install/setup.bash

# état de départ
systemctl is-active clawbot-arm-controller.service clawbot-move-group.service
ros2 topic info /joint_states            # attendu : 1 éditeur (joint_state_publisher)
ros2 topic hz /arm/servo_angles          # relecture entrelacée, ~10 Hz sur le topic
ros2 topic echo --once /arm/servo_angles # doit être proche de [90, 180, 0, 0, 90, 149]
```

Consigner les six angles lus : ______________________

## (a) Activation de la capacité, bras au repos

```bash
ros2 service call /clawbot/capabilities/set clawbot_interfaces/srv/SetCapability \
  "{name: arm, active: true, timeout_s: 60.0}"
```

- Attendu : `success: true`, `state: ACTIVE`. La capacité n'est déclarée active que si
  `/move_action`, `/arm_controller/follow_joint_trajectory`,
  `/grip_controller/follow_joint_trajectory` et `/arm/joint_states` répondent.
- Attendu : **aucun mouvement du bras.** Le contrôleur démarre, publie ses consignes
  initiales et n'exécute aucune trajectoire.
- Contrôles :

```bash
ros2 topic hz /arm/joint_states    # >= 8 Hz (mesure de référence : 20 Hz)
ros2 action list | grep -E "move_action|arm_controller|grip_controller"
# attendu : /move_action (MoveIt), /arm_controller/..., /grip_controller/...
```

Consigner : `state` = __________ · `/arm/joint_states` = __________ Hz · mouvement
observé : oui / non

## (b) `arm_rest` depuis le repos

```bash
ros2 action send_goal /clawbot/execute_skill clawbot_interfaces/action/ExecuteSkill \
  "{skill: arm_rest, params_json: '{}', timeout_s: 20.0}" --feedback
```

- Attendu : `outcome: 0` (SUCCEEDED), message « bras dans l'enveloppe ».
- Attendu : aucun mouvement, ou un mouvement inférieur à 5° par axe.
- Consigner les angles relus après l'exécution : ______________________
- Écart maximal observé : ______ °

## (c) Validation des poses nommées, une par une

Les propositions sont dans `config/arm_poses.yaml`, section `propositions`. Elles ne
sont **pas** commandables tant qu'elles n'ont pas été validées ici. Pour chacune,
dans cet ordre, avec retour à `arm_rest` entre deux poses :

| # | Pose (degrés servo, 6 valeurs) | Commande | Attendu | Validée ? |
|---|---|---|---|---|
| 1 | `home` — [90, 90, 90, 90, 90, 180] | voir ci-dessous | bras tendu verticalement, pince fermée, aucun contact | ☐ |
| 2 | `ready` — [90, 119, 119, 90, 90, 180] | voir ci-dessous | pince ~15 cm devant la colonne, aucun contact | ☐ |

Procédure par pose (exemple pour `home`, à répéter pour chaque ligne). C'est le seul
chemin hors liste : l'opérateur demande la pose directement à MoveIt, qui planifie et
exécute. Aucun skill ne l'accepte avant validation.

```bash
# 1. l'opérateur essaie la proposition, une seule fois, à vitesse réduite (50 %) :
ros2 action send_goal /move_action moveit_msgs/action/MoveGroup \
  "{request: {group_name: arm, num_planning_attempts: 3, allowed_planning_time: 5.0,
    max_velocity_scaling_factor: 0.5, max_acceleration_scaling_factor: 0.5,
    goal_constraints: [{joint_constraints: [
      {joint_name: arm_joint1, position: 0.0, tolerance_above: 0.087, tolerance_below: 0.087, weight: 1.0},
      {joint_name: arm_joint2, position: 0.0, tolerance_above: 0.087, tolerance_below: 0.087, weight: 1.0},
      {joint_name: arm_joint3, position: 0.0, tolerance_above: 0.087, tolerance_below: 0.087, weight: 1.0},
      {joint_name: arm_joint4, position: 0.0, tolerance_above: 0.087, tolerance_below: 0.087, weight: 1.0},
      {joint_name: arm_joint5, position: 0.0, tolerance_above: 0.087, tolerance_below: 0.087, weight: 1.0}]}]},
   planning_options: {plan_only: false, replan: false}}"
```

Les positions ci-dessus (`0.0` partout) sont la proposition `home` en radians ; pour
`ready`, mettre `0.5` sur `arm_joint2` et `arm_joint3`. Un `error_code.val` négatif
(`-1`, `PLANNING_FAILED`) signifie : pose en collision, hors limites ou non
atteignable — elle ne doit pas être validée.

```bash
# 2. retour au repos, vérifié
ros2 action send_goal /clawbot/execute_skill clawbot_interfaces/action/ExecuteSkill \
  "{skill: arm_rest, params_json: '{}', timeout_s: 20.0}"

# 3. angles relus
ros2 topic echo --once /arm/servo_angles
```

- Si la pose est acceptée : consigner ici `validée par: ____________  date: ____________`
  et Hermes l'inscrit dans `poses` avec ces deux champs.
- Si la pose est refusée (contact, trajectoire peu sûre, position inattendue) : elle
  reste dans `propositions` et n'est jamais commandable.

## (d) Pince

```bash
ros2 action send_goal /clawbot/execute_skill clawbot_interfaces/action/ExecuteSkill \
  "{skill: gripper, params_json: '{\"action\": \"open\"}', timeout_s: 10.0}"
ros2 action send_goal /clawbot/execute_skill clawbot_interfaces/action/ExecuteSkill \
  "{skill: gripper, params_json: '{\"action\": \"close\"}', timeout_s: 10.0}"
```

- Attendu : `outcome: 0` deux fois ; la pince s'ouvre puis se ferme complètement.
- Consigner `servo 6` après `open` : ______ ° · après `close` : ______ °

## (e) Servo muet — échec `SERVO_NO_FEEDBACK`

**Bras au repos, posé, immobile.** L'opérateur coupe l'alimentation des servos
(interrupteur prévu pour cela), puis lance :

```bash
ros2 action send_goal /clawbot/execute_skill clawbot_interfaces/action/ExecuteSkill \
  "{skill: arm_rest, params_json: '{}', timeout_s: 20.0}"
```

- Attendu : `outcome: 1` (FAILED), `error_code: SERVO_NO_FEEDBACK`, **aucun mouvement**
  (les servos sont hors tension, mais le contrôleur ne doit envoyer aucune trajectoire
  au-delà du premier demi-seconde).
- Mesurer le délai entre le lancement et le résultat : ______ s (attendu < 1 s).
- Remettre l'alimentation, relancer `arm_rest` une fois : attendu `outcome: 0`.

## Clôture

| Contrôle | Résultat | Heure |
|---|---|---|
| (a) `set arm true`, aucun mouvement | | |
| (b) `arm_rest` < 5° | | |
| (c) poses validées | | |
| (d) pince ouverte/fermée | | |
| (e) `SERVO_NO_FEEDBACK` < 1 s | | |

Poses validées à inscrire dans `config/arm_poses.yaml` :

- nom : ____________________ · `validated_by: "opérateur"` · `validated_at: "________"`
- nom : ____________________ · `validated_by: "opérateur"` · `validated_at: "________"`

Toute pose non consignée ici reste hors de la liste blanche.
