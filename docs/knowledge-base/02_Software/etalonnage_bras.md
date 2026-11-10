---
title: "Étalonnage du bras — zéros servo, modèle et collisions avec le mât"
date: "2026-11-10T23:20:00+01:00"
author: "Hermes Agent"
tags: [software, bras, etalonnage, moveit2, collision, urdf, servo]
status: actif
---

# Étalonnage du bras — zéros servo, modèle et collisions avec le mât

Question posée : peut-on valider ou calibrer le bras pour que MoveIt évite les collisions avec le
mât qui porte la caméra Orbbec ? Réponse mesurée : **oui, mais pas dans cet ordre**. Tant que la
conversion servo → articulation n'est pas calée sur la mécanique, un objet de collision
supplémentaire rendrait le planificateur faux dans les deux sens.

Retour à l'[[index]] ; chaîne concernée : [[manipulation_moveit]].

## 1. Ce que la mesure dit du modèle actuel

Configuration qui a physiquement bloqué le bras le 2026-11-10 à 22:43 (servos `76, 156, 54, …`) :

| Vérification | Résultat | Commande |
|---|---|---|
| Validité au sens de MoveIt | **valide** — aucune collision détectée | `tools/check_state.py --servos 76 156 54 0 90` |
| Position du bout de chaîne dans le modèle | `arm_link5` en `x = +0,130, y = +0,008, z = +0,337` | `/compute_fk`, repère `base_link` |
| Position réelle du support heurté | caméra Astra en `x = −0,0436, z = +0,4196` ([[orbbec_astra_pro_plus]]) | `astra_joint` de l'URDF |
| Interprétation | le modèle place le bras **devant**, la réalité l'a posé **derrière**, contre le mât | — |

Autrement dit : à cette configuration, le modèle croit le bras à 13 cm devant la base, alors que le
bras réel était en appui sur un support situé 4 cm derrière l'axe. La cause n'est pas le maillage —
le mât est bien dans le modèle : le maillage de collision de `base_link` monte jusqu'à `z = 0,382`
(`x ∈ [−0,155 ; +0,145]`, `y ∈ [−0,120 ; +0,120]`). La cause est la **correspondance servo →
articulation** : elle applique la convention `q = (angle_servo − 90) / 57,2958` sans preuve
mécanique. Un décalage de zéro ou un signe inversé sur un seul axe suffit à poser le modèle du
mauvais côté.

Conséquence pratique : MoveIt accepte aujourd'hui des trajectoires qui touchent le mât, et refuse
peut-être des poses sûres. Le planificateur n'est donc pas utilisable comme garde-fou tant que
l'étalonnage n'est pas fait.

## 2. Ce dont on a besoin

| Grandeur | État | Source |
|---|---|---|
| Longueurs de segments, axes de rotation, géométrie du châssis | connues et fixes | `urdf/clawbot_x3plus.urdf` |
| Position du mât et de la caméra | connue : `astra_joint` à `(−0,0436 ; 0 ; 0,4196)` | URDF, maillage `base_link` jusqu'à `z = 0,382` |
| Zéro mécanique de chaque servo | **convention, non mesuré** | `arm_zero_deg` de `config/arm_controller.yaml` |
| Signe de chaque axe | **convention, non mesuré** | `arm_scale_deg_per_rad` |

Seules les deux dernières lignes sont à déterminer.

## 3. Pose de référence : le bras droit debout

Dans l'URDF, les axes `arm_joint1` à `arm_joint4` sont colinéaires (`axis = 0 0 −1`) et
`arm_joint5` aussi (`0 0 1`), avec des origines empilées en `z`. Donc **à `q = 0` sur les cinq axes,
le bras est une colonne verticale** : c'est la seule pose où l'erreur de zéro se voit à l'œil sans
instrument, et elle ne demande aucune mesure de distance.

Procédure, opérateur présent, 40 cm dégagés, interrupteur batterie à portée :

1. Lire la pose : `scripts/read_arm_angles.py` (pilote arrêté, 3 appels).
2. Pour chaque axe, du plus distal au plus proximal (5, 4, 3, 2, puis 1) :
   a. commander des pas de 5° sur `/servo_ctrl` et relire après chaque pas ;
   b. quand l'opérateur confirme que le segment est **aligné verticalement**, noter l'angle servo :
      c'est `zero_deg` de cet axe ;
   c. commander +5° puis −5° et observer le modèle dans RViz : si le segment part du côté opposé,
      l'axe est de signe **négatif**.
3. Pour `arm_joint1`, la verticalité ne renseigne rien : la référence est l'azimut du plan du bras.
   Aligner à vue le plan du bras sur l'axe `x` du châssis et noter l'angle.
4. Écrire les valeurs :

```bash
python3 scripts/set_arm_zeros.py --zeros "90,95,90,90,90" --signs "+, -, +, +, +"
sudo systemctl stop ros2-driver-node
python3 scripts/sync_arm_pose.py          # la pose change de sens avec les nouveaux zéros
sudo systemctl start ros2-driver-node
sudo systemctl restart clawbot-arm-controller
```

5. Vérifier la cohérence du modèle, sans mouvement :

```bash
# la pose qui bloquait doit maintenant être refusée
python3 clawbot_moveit_config/tools/check_state.py --servos 76 156 54 0 90   # attendu : EN COLLISION
# la pose courante doit rester valide
python3 clawbot_moveit_config/tools/check_state.py --servos <angles lus>      # attendu : valide
```

## 4. Critères d'acceptation

| Critère | Mesure |
|---|---|
| Le modèle refuse la configuration qui a bloqué le bras | `check_state.py` renvoie `EN COLLISION` avec un contact `base_link` ↔ `arm_link*` |
| Le modèle accepte la pose réelle courante | `check_state.py` renvoie `valide` |
| Un objectif atteignant le mât est refusé | `move_joint_step.py --plan-only` renvoie un `error_code` différent de 1 |
| Le bras commandé par MoveIt ne touche plus le mât | essai physique à 5°, opérateur présent |

Tant que ces quatre lignes ne sont pas satisfaites, la prudence reste celle des essais du
2026-11-10 : petits pas, opérateur présent, relecture des angles après chaque mouvement.

## 5. Le mât : quand faudra-t-il l'ajouter explicitement ?

Le mât est déjà présent via le maillage de collision de `base_link`. Deux cas justifieraient un
objet de collision dédié (boîte ou cylindre publié dans la scène de planification) :

- le maillage s'avère trop grossier après étalonnage (le planificateur laisse passer le bras à
  travers le support alors que la pose est correcte) ;
- le support est démonté ou déplacé : le maillage du châssis ne suivrait pas.

Dans ces cas seulement, publier le support comme `CollisionObject` rattaché à `base_link` avec des
dimensions mesurées au réglet — jamais avec des dimensions estimées à vue.

## 6. Limites

- L'étalonnage se fait **à l'œil** : la précision attendue est de quelques degrés par axe, pas mieux.
  Pour une précision millimétrique, il faudrait une mire et la calibration main-caméra, hors de
  portée aujourd'hui (aucune caméra étalonnée ne voit le bras).
- Aucune rétroaction : après un remplacement de servo, l'étalonnage est à refaire.
- Le sens et le zéro sont indépendants : un axe peut avoir le bon zéro et le mauvais signe.
- Les zéros écrits valent pour la mécanique actuelle, à la date de la mesure.

## 7. Voir aussi

- Chaîne de manipulation : [[manipulation_moveit]]
- Bras et servos : [[bras_6dof]]
- Modèle géométrique : [[modele_urdf_clawbot]]
- Caméra qui porte le mât : [[orbbec_astra_pro_plus]]
- Journal des essais : [[2026-11-10_mise_en_service_manipulation]]
