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
  reference_deg: [76, 97, 90, 90, 90]
  tolerance_deg: [10, 10, 10, 10, 10]
  mesure_le: "2026-11-11T16:20:00+01:00"
  valide_par_operateur: false
skills_exigeant_bras_replie: [navigate_to, follow_human, search_object]
```

L'enveloppe est en **degrés de servo**, tels que publiés par `/arm/servo_angles`, et non en radians
articulaires : c'est la seule mesure disponible sans passer par `joint_states`, qui n'est qu'une
consigne. La pose de référence est celle mesurée sur le robot à l'arrêt :

```text
2026-11-11T16:20:00+01:00  /arm/servo_angles -> [76, 97, 90, 90, 90, 149]
```

**`valide_par_operateur: false` est une information, pas un oubli.** La pose de repos est une pose
*observée* ; l'encombrement du bras dans cette pose n'a pas été mesuré, et la seule géométrie connue
du bras est le seuil de collision du mât (servo 2 ≈ 114°). L'enveloppe doit être validée par
l'opérateur, bras libre, avant le premier essai physique de navigation.

## 4. Comportement en cas de doute

| Situation | Verdict | Message |
|---|---|---|
| angles jamais reçus | refus | « bras inconnu : aucun message recu sur /arm/servo_angles » |
| angles plus vieux que 1,0 s | refus | « angles de bras perimes : 1,4 s sans message » |
| moins de 5 valeurs | refus | « angles de bras incomplets : 2 valeurs » |
| un servo hors bande | refus | « bras non replie : servo 2 a 120 degres, hors de l'enveloppe [87, 107] » |
| tout est dans la bande | accepté | — |

Le refus nomme le servo et sa bande : « bras non replié » ne se corrige pas, « servo 2 à 120° hors
bande [87, 107] » si. Le silence vaut refus, comme pour `/safety/state` : un bras inconnu n'est pas
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

Sur le robot, domaine 28, au repos :

```text
$ python3 scripts/etat_directeur.py
state          = IDLE
safety         = OK
arm_angles     = [76, 97, 90, 90, 90, 149]
arm_age_s      = 0.063
arm_folded     = True
```

`/director/state` publie désormais `arm_angles`, `arm_age_s` et `arm_folded` : un relevé daté, pas
une conclusion — un consommateur peut juger de la fraîcheur sans faire confiance au booléen.

## 6. Limites connues

| Limite | Conséquence |
|---|---|
| enveloppe non validée par l'opérateur | elle interdit une pose *différente de la pose de repos*, pas une pose dangereuse en soi |
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
