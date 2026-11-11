---
title: "Préconditions de mouvement — bras replié avant tout skill qui déplace la base"
date: "2026-11-11T16:41:06+01:00"
author: "Hermes Agent"
tags: [software, ros2, directeur, préconditions, sécurité, bras, nav2]
status: validé
---

# Préconditions de mouvement

Application de la règle §6.3 de la conception — « préconditions vérifiées par S1, S2 n'est jamais
cru ». Jusqu'au 2026-11-11, la logique du directeur acceptait un *callable* de précondition…
initialisé à « toujours vrai » : `navigate_to` démarrait donc bras en extension, alors que Nav2 ne
connaît le bras que par un rayon d'encombrement de 0,16 m. Retour à l'[[index]] ; mécanisme général :
[[directeur_s1]] ; navigation : [[navigation_nav2_waypoints]].

## 1. Ce qui est vérifié, et par quoi

| Skill | Précondition | Source de la mesure |
|---|---|---|
| `navigate_to`, `follow_human`, `search_object` | bras dans son enveloppe de repos, mesure fraîche | `/arm/servo_angles` (10 Hz) |
| `arm_move`, `grip_set` | aucune | — (sinon le bras ne pourrait plus être replié) |
| tous | `/safety/state` = `OK` frais | arbitre 20 Hz |

## 2. Fichiers

| Élément | Chemin |
|---|---|
| Enveloppe et liste des skills concernés | `config/preconditions.yaml` |
| Lecture et vérification | `clawbot_director/clawbot_director/preconditions.py` |
| Branchement | `clawbot_director/clawbot_director/director_node.py` |
| Tests | `clawbot_director/test/test_preconditions.py` (21 tests) |

## 3. Enveloppe en service

```yaml
arm:
  source: /arm/servo_angles
  max_age_s: 1.0
  joints: [1, 2, 3, 4, 5]
  reference_deg: [90, 180, 0, 0, 90]
  tolerance_deg: [5, 5, 5, 5, 5]
  mesure_le: "2026-11-11T19:20:40+01:00"
  valide_par_operateur: true
skills_exigeant_bras_replie: [navigate_to, follow_human, search_object]
```

L'enveloppe est en **degrés de servo**, tels que publiés par `/arm/servo_angles`, et non en radians
articulaires. La pose de référence est celle lue sur le robot à l'arrêt :

```text
2026-11-11T19:20:40+01:00  /arm/servo_angles -> [90, 180, 0, 0, 90, 149]
```

**Cette pose est celle validée par l'opérateur le 2026-11-11 à 19:20 comme position de repos et de
déplacement.** Le bras est debout au-dessus de la colonne — `arm_link3` et `arm_link4` à x ≈ 0,015 m,
pince à x = 0,190 m / z = 0,304 m, calculés par `scripts/cinematique_bras.py` — et la caméra du
poignet regarde vers l'avant, dans le même sens que l'Astra : vérifié à 19:19 en comparant les deux
images, qui montrent la même scène (interrupteur du mur gauche, couloir au centre, portes sombres à
droite). C'est la seule pose connue où le bras est à la fois compact et utile à la perception pendant
un déplacement.

La pose précédente — `[76, 97, 90, 90, 90]`, mesurée à 16:20 — avait un bras vertical haut et la
caméra du poignet tournée vers le plafond : elle ne servait à rien en déplacement et n'a jamais été
validée. Elle est remplacée, pas complétée.

**La lecture redevient une mesure depuis le 2026-11-11 19:12.** Le 17:35, `/arm/servo_angles`
renvoyait exactement les consignes envoyées, bras immobile : c'était le registre du MCU. Depuis, une
relecture échantillonnée pendant un pas montre des valeurs **jamais commandées** et intermédiaires —
35° puis 39° pour une consigne 20° → 40°, et 115°, 135°, 179° au cours de la montée du servo 2. La
valeur retarde sur la consigne, donc elle mesure un déplacement. La précondition vérifie une
position, pas une valeur déclarée ; la réserve inverse (un servo non alimenté) reste possible.

**`valide_par_operateur: true` porte la parole de l'opérateur, rien de plus.** L'encombrement du bras
dans cette pose n'a pas été mesuré au mètre ; c'est le seuil de collision du mât (servo 2 ≈ 114°,
constaté dans une autre configuration) qui reste la seule géométrie de référence. La validation
autorise le premier essai physique de navigation ; elle ne remplace pas la mesure.

## 4. Comportement en cas de doute

| Situation | Verdict | Message |
|---|---|---|
| angles jamais reçus | refus | « bras inconnu : aucun message recu sur /arm/servo_angles » |
| angles plus vieux que 1,0 s | refus | « angles de bras perimes : 1,4 s sans message » |
| moins de 5 valeurs | refus | « angles de bras incomplets : 2 valeurs » |
| un servo hors bande | refus | « bras non replie : servo 2 a 120 degres, hors de l'enveloppe [175, 185] » |
| tout est dans la bande | accepté | — |

Le refus nomme le servo et sa bande : « bras non replié » ne se corrige pas, « servo 2 à 120° hors
bande [175, 185] » si. Le silence vaut refus, comme pour `/safety/state` : un bras inconnu n'est pas
un bras replié.

## 5. Mesures

Domaine 99, faux serveur `NavigateToPose` et faux contrôleur de bras :

| Test | Résultat |
|---|---|
| bras en extension (servo 2 = 120°) | `PRECONDITION_FAILED`, 0 goal envoyé à Nav2 |
| bras dans l'enveloppe | `ACCEPTED`, goal reçu par Nav2 |
| angles périmés (flux arrêté) | `PRECONDITION_FAILED`, motif « perimes » |
| `arm_move` bras hors enveloppe | `ACCEPTED` — le bras reste commandable |
| configuration malformée (8 cas) | `PreconditionsInvalides` au chargement |

Sur le robot, domaine 28, au repos dans la pose validée :

```text
$ python3 scripts/etat_directeur.py
state          = IDLE
safety         = OK
arm_angles     = [90, 180, 0, 0, 90, 149]
arm_age_s      = 0.036
arm_folded     = True
```

Relevé à 19:24, après redémarrage de `clawbot-director` pour recharger la nouvelle enveloppe : la
pose que l'opérateur vient de valider est acceptée par la précondition, sans quoi elle n'aurait
servi à rien — c'est le sens de ce test.

`/director/state` publie désormais `arm_angles`, `arm_age_s` et `arm_folded` : un relevé daté, pas
une conclusion — un consommateur peut juger de la fraîcheur sans faire confiance au booléen.

## 6. Limites connues

| Limite | Conséquence |
|---|---|
| l'encombrement de la pose validée n'est pas mesuré | la validation autorise l'essai, elle ne remplace pas la mesure du volume balayé ni des dégagements |
| bande de ±5° | un bras qui dérive de plus de 5° sur un axe est refusé : c'est voulu, mais cela se produira en usage réel et le message doit rester lisible |
| pas de mesure de l'occupation de la pince | « pince vide » reste non vérifiable : aucun capteur |
| vérification à l'entrée et entre deux étapes | un bras déplacé **pendant** une navigation n'est pas détecté ; cela relèverait de l'arbitre, pas du directeur |
| enveloppe globale, pas par trajectoire | un waypoint passant près du mât ne réduit pas la bande admissible |

## 7. Voir aussi

- [[index]]
- [[directeur_s1]]
- [[navigation_nav2_waypoints]]
- [[systeme1_arbitre]]
- [[etalonnage_bras]]
- [[inventaire_materiel]]
