---
title: "Étalonnage du bras — zéros servo, modèle et collisions avec le mât"
date: "2026-11-10T23:20:00+01:00"
author: "Hermes Agent"
tags: [software, bras, etalonnage, moveit2, collision, urdf, servo]
status: actif
---

# Étalonnage du bras — zéros servo, modèle et collisions avec le mât

Question posée : peut-on valider ou calibrer le bras pour que MoveIt évite les collisions avec le
mât qui porte la caméra Orbbec ?

Réponse retenue le 2026-11-10 : **la conversion servo → articulation était bonne, c'est le volume du
mât qui manquait au modèle de collision.** La position publiée a été validée à l'œil dans RViz par
l'opérateur (modèle et robot superposés, pose zéro comme pose courante), puis le support a été
ajouté comme objet de collision avec une marge de 2 cm. Les quatre critères de recette sont
satisfaits (§5). La procédure d'étalonnage des zéros (§3) reste en réserve : elle redeviendra
nécessaire après un remplacement de servo ou si le modèle cesse de coller à la réalité.

Retour à l'[[index]] ; chaîne concernée : [[manipulation_moveit]].

## 1. Ce que la mesure disait du modèle (constat du 2026-11-10 23:15, avant correction)

Configuration qui a physiquement bloqué le bras le 2026-11-10 à 22:43 (servos `76, 156, 54, …`) :

| Vérification | Résultat | Commande |
|---|---|---|
| Validité au sens de MoveIt | **valide** — aucune collision détectée | `tools/check_state.py --servos 76 156 54 0 90` |
| Position du bout de chaîne dans le modèle | `arm_link5` en `x = +0,130, y = +0,008, z = +0,337` | `/compute_fk`, repère `base_link` |
| Position du support heurté | caméra Astra en `x = −0,0436, z = +0,4196` | `astra_joint` de l'URDF |
| Contenu réel du maillage `base_link` au-dessus de `z = 0,15` | **18 points, tous à `z = 0,382`** : la seule plaque haute, aucune structure verticale | lecture binaire du STL de collision |

Conclusion corrigée : le maillage ne contient que la plaque supérieure du support. La structure
verticale entre le châssis et la plaque est absente, donc le planificateur ignorait le mât. La
conversion servo → articulation, elle, s'est révélée juste dès la comparaison dans RViz.

## 2. Ce dont on a besoin

| Grandeur | État | Source |
|---|---|---|
| Longueurs de segments, axes de rotation, géométrie du châssis | connues et fixes | `urdf/clawbot_x3plus.urdf` |
| Position du mât et de la caméra | connue : `astra_joint` à `(−0,0436 ; 0 ; 0,4196)` | URDF, maillage `base_link` jusqu'à `z = 0,382` |
| Zéro mécanique de chaque servo | convention `90°` **validée à l'œil dans RViz** le 2026-11-10 | `arm_zero_deg` de `config/arm_controller.yaml` |
| Signe de chaque axe | convention `+` **validée à l'œil dans RViz** le 2026-11-10 | `arm_scale_deg_per_rad` |

Seules les deux dernières lignes étaient à déterminer ; l'opérateur les a validées visuellement (modèle superposé au robot dans RViz, aux poses zéro et courante). La procédure ci-dessous reste la méthode à suivre si un doute réapparaît.

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

## 5. Le mât : ce qui est fait

Le support est publié comme objet de collision `camera_support`, rattaché à `base_link`, à chaque
démarrage de `clawbot-move-group.service` (nœud `apply_mast`, installé avec le paquet).

| Paramètre | Valeur | Source |
|---|---|---|
| Empreinte reprise du maillage | `x ∈ [−0,057 ; −0,037]`, `y ∈ [−0,083 ; +0,083]` | plaque `base_link` à `z = 0,382` |
| Hauteur couverte | `z` de 0,100 à 0,382 | haut du châssis jusqu'à la plaque |
| Volume déclaré | boîte 0,060 × 0,206 × 0,322 m en `x = −0,047`, `y = 0` | 0,020 × 0,166 d'empreinte + marge |
| Marge de sécurité | 0,020 m sur toutes les faces | `config/mast.yaml` |

Vérifications mesurées le 2026-11-10 à 23:32, `move_group` actif, objet confirmé dans la scène par
`/get_planning_scene` (`camera_support`, dimensions `[0,060 ; 0,206 ; 0,322]`) :

| Test | Résultat |
|---|---|
| `check_state.py --servos 90 90 90 90 90` (pose zéro) | **valide** |
| `check_state.py --servos 76 156 54 0 90` (pose qui avait bloqué) | **EN COLLISION**, contact `camera_support` ↔ `mono_link` |
| Planification vers cette même pose, tolérance 0,005 rad | **refusée** (`error_code 99999`) |
| Planification vers la pose zéro, tolérance 0,005 rad (témoin) | **acceptée** (`error_code 1`) |

Le contact est détecté avec `mono_link`, un petit lien fixe porté par `arm_link4` : c'est donc cette
pièce qui touchait le support, ce qui explique qu'aucun maillage de collision n'ait été signalé au
départ.

### 5.1 Objection examinée : le servo 4 était en défaut, donc son q4 était inconnu

Objection légitime : la pose de référence 76/156/54/0/90 a été testée avec un `q4` arbitraire
(servo 4 = 0°), alors que le servo 4 renvoyait justement une valeur invalide. Le verdict « valide »
du 23:15 ne prouvait donc rien à lui seul.

Expérience refaite le 2026-11-10 à 23:38, en balayant `q4` de 0 à 180° par pas de 15° avec les
autres axes figés à 76/156/54/90, objet retiré puis remis :

| Scène | Valeurs de `q4` en collision |
|---|---|
| objet `camera_support` **retiré** | **aucune** (13 valeurs testées, toutes valides) |
| objet `camera_support` **présent** | **les 13** (contact `camera_support` ↔ `mono_link`) |

Conclusion : quel que soit `q4`, le modèle ne disposait d'aucune géométrie pour arrêter le bras
contre le support. Le défaut du servo 4 n'explique donc pas le silence du planificateur ; l'absence
du volume vertical du mât, oui. Le défaut du servo, lui, expliquait l'impossibilité de *savoir* où
était l'axe 4 — deux problèmes distincts, tous deux corrigés (rebranchement du servo, objet de
collision).

Recette finale après remise de l'objet : pose zéro **valide**, pose 76/156/54/90/90 **EN
COLLISION**.

Deux points de méthode :

1. **La tolérance d'objectif compte.** Avec ±0,05 rad, la planification vers la pose qui touche
   réussit : MoveIt trouve un état valide dans la marge de tolérance. Un test de garde-fou se fait
   donc à 0,005 rad, sinon il ne prouve rien.
2. **La marge se règle dans `config/mast.yaml`** puis `sudo systemctl restart clawbot-move-group`.
   L'enveloppe actuelle reprend l'empreinte de la plaque élargie de 2 cm ; resserrer la boîte
   demanderait de mesurer la section réelle du support, ce qui n'a pas été fait.

### 5.2 Reproduction physique du contact et seuil du modèle (23:45-23:55)

But : savoir ce qui se passe réellement quand on s'approche du mât, et à quelle distance le modèle
intervient.

Approche depuis la pose zéro, par paliers de 5° (axe 1) puis 10° (axe 2), opérateur présent :

| Étape | Consigne | Angle relu | Observation |
|---|---|---|---|
| axe 1 | 90 → 76° | 77° | rien |
| axe 2 | 90 → 100 → 110 → 120° | **114°** (6° sous la consigne) | **contact** au niveau de la caméra USB (`mono_link`) — le servo est en butée |
| relâchement | 120 → 110 → 104 → 100 → 96° | 97° | libre |

Seuil du modèle sur la même famille de poses (balayage de `q2`, autres axes figés) :

| Configuration testée | Premier refus du modèle | Contact physique |
|---|---|---|
| servo 1/3/4/5 = 77/89/89/90 | `servo2 = 106°` (valide à 104°) | ~114° |
| servo 1/3/4/5 = 76/90/90/90 | `servo2 = 105°` (valide à 96°) | ~114° |

Conséquences mesurées :

- Le modèle refuse **8 à 9° avant** le contact réel : c'est l'effet de la marge de 2 cm. Une
  trajectoire planifiée par MoveIt s'arrête donc avant que la caméra USB ne touche le support.
- La paire en collision annoncée par MoveIt (`camera_support` ↔ `mono_link`) correspond exactement
  à ce que l'opérateur voit : le contact se fait par la caméra USB montée sur `arm_link4`.
- Planification vers `servo2 = 120°` (la pose qui a touché), tolérance 0,005 rad : **refusée**
  (`error_code 99999`). Vers `servo2 = 95°`, zone libre : **acceptée** (`error_code 1`).
- La pose `76/156/54` enregistrée le 2026-11-10 n'était pas le premier contact mais l'**état final
  après poussée** du servo dans le support : le premier contact se produit vers 114°. C'est le seuil,
  pas cette pose, qui sert de référence.

État laissé : servos `[76, 97, 90, 90, 90, 149]`, déclaré **valide** par le modèle, pose
resynchronisée dans la configuration du contrôleur.

Cas où un objet dédié resterait nécessaire même après étalonnage : support démonté ou déplacé (le
maillage du châssis ne suivrait pas).

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
