# P13 — Le bras comme capacité : propositions de poses nommées

**Date :** 2026-11-22 · **Branche :** `feat/REQ-ARM-001-bras` · **Statut :** en attente de
validation opérateur (aucune pose ajoutée à la liste blanche, rien de déployé).

Ce document accompagne la porte du prompt P13 §3 : la liste `named_poses` est proposée
ici, l'opérateur valide chaque pose sur le robot, une par une, avant qu'elle n'entre
dans `config/arm_poses.yaml`.

## 1. Comment ces valeurs sont construites

- **Unité :** degrés de servo, l'unité que l'opérateur lit sur `/arm/servo_angles` et que
  le pilote envoie à la carte. Ordre : `[arm_joint1, arm_joint2, arm_joint3,
  arm_joint4, arm_joint5, grip_joint]` = servos 1 à 6.
- **Source des configurations :** les `group_state` du SRDF
  `clawbot_moveit_config/config/clawbot_x3plus.srdf` (`home`, `ready`, `open`,
  `closed`), converties par la table du contrôleur
  (`servo = 90 + 57,2958 × q` pour les axes 1 à 5, `servo = 180 + 116,883 × q` pour la
  pince, pince fermée à q = 0).
- **Bornes :** servos 1 à 4 sur [0, 180]°, servo 5 sur [0, 270]°, servo 6 sur [0, 180]° ;
  limites URDF : ±1,5708 rad pour les axes 1 à 4, [−1,5708 ; 3,14159] pour l'axe 5,
  [−1,54 ; 0] pour la pince.
- **Ce que les valeurs ne disent pas :** le zéro mécanique de chaque servo n'est pas
  identifié (base OKF `bras_6dof.md`). Une pose calculée n'est donc pas une position
  connue : seule la validation à l'œil, robot sous tension, la rend sûre. C'est
  précisément l'objet de la porte.

## 2. Pose déjà validée (dans la liste blanche)

| Nom | Servo 1-6 (°) | Ce que c'est | Validée par |
|---|---|---|---|
| `repos` | `[90, 180, 0, 0, 90, 149]` | Bras debout compact au-dessus de la colonne, pince à demi fermée, caméra du poignet vers l'avant. Enveloppe C10 ±5°. | opérateur, 2026-11-11T19:20:40+01:00 |

## 3. Poses proposées (NON commandables tant qu'elles ne sont pas validées)

| Nom | Servo 1-6 (°) | Origine | Ce que l'opérateur doit voir |
|---|---|---|---|
| `home` | `[90, 90, 90, 90, 90, 180]` | SRDF `group_state home` (toutes articulations à 0 rad) | Bras tendu verticalement au-dessus de la colonne, pince fermée, aucun contact avec le châssis ni la caméra. Sert de référence de cinématique directe. |
| `ready` | `[90, 119, 119, 90, 90, 180]` | SRDF `group_state ready` (axes 2 et 3 à +0,5 rad = 28,65° → 118,65 arrondi à 119) | Pince déportée vers l'avant, à environ 15 cm devant la colonne, à mi-hauteur ; aucun contact, caméra du poignet toujours dégagée. |

Schéma de principe (vue de côté, `base_link` à l'origine, échelle approximative) :

```text
        home                          ready
         ()                            ()
         |                             /
         |                           /
         |                         [pince]
         |                           |
      [pince]                         |
         |                            |
      -- base --                   -- base --
   bras vertical,               axes 2 et 3 à +28,65°,
   pince au-dessus              pince vers l'avant (~15 cm)
```

Les photos ne sont pas jointes : elles seront prises par l'opérateur pendant l'essai
(une par pose, même cadrage que la photo de la pose de repos du 2026-11-11) et
consignées dans `docs/knowledge-base/03_Operations/`.

## 4. Ce qui est demandé à l'opérateur

1. Robot immobile, sur cales ou au sol, volume de travail dégagé, main sur l'arrêt.
2. Exécuter `tests/hardware/HW-ARM-001.md` §(c), pose par pose, avec retour à `arm_rest`
   entre deux.
3. Pour chaque pose acceptée : donner le nom et la date de validation. Ces deux champs
   sont obligatoires — le chargeur refuse toute pose qui ne les porte pas, elle reste
   donc hors de la liste blanche et hors de portée des skills.
4. Pour une pose refusée : elle reste dans la section `propositions`, sans effet.

## 5. Ce que le code garantit déjà (sans la validation)

- `arm_named_pose` refuse `INVALID_PARAMS` toute pose absente de `poses`, sans envoyer
  de trajectoire (`clawbot_executive/test/test_arm_skills.py`).
- Une entrée de `poses` sans `validated_by` ou `validated_at` fait refuser le fichier au
  démarrage du serveur de skills (`bras.PosesInvalides`).
- Les six valeurs de chaque pose validée sont vérifiées contre les bornes servo et les
  limites URDF (même fichier de test).
- Aucune pose n'est commandée par Hermes dans le domaine 28 : l'essai est opérateur.
