---
title: "ERR-2026-11-10-002 — occupation critique de la partition racine"
date: "2026-11-10T06:14:09+08:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, stockage, nvme, journaux]
status: ouvert
---

# ERR-2026-11-10-002 — occupation critique de la partition racine

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-002` |
| Horodatage de détection | 2026-11-10T06:11:53+08:00 (CST) |
| Composant concerné | [[jetson_orin_nx]] §4 — stockage NVMe |
| Gravité d'exploitation | Blocage probable de l'écriture de journaux et de journaux ROS 2 (`rosbag`, traces) |
| Statut | ouvert |
| Mitigation appliquée | Aucune suppression, aucun archivage effectué |

## 1. Mesure

```
$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1  147G  136G  4.3G  97% /
```

| Grandeur | Valeur |
|---|---|
| Périphérique | `/dev/nvme0n1p1` |
| Capacité totale | 147 Go |
| Espace utilisé | 136 Go |
| Espace disponible | 4,3 Go |
| Taux d'occupation | 97 % |

## 2. Conséquences mesurables

| Conséquence | État |
|---|---|
| Marge de 4,3 Go pour les journaux ROS 2 et les captures | Insuffisante pour une session d'enregistrement longue — volume non quantifié |
| Écriture de ce document | Succès (fichiers créés sous `/Robot_Knowledge_Base`, hors partition distincte : même système de fichiers `/`) |
| `dmesg` / journaux système saturés | Donnée non disponible — `journalctl` non interrogé lors de la capture |

## 3. Actions de mitigation

| Horodatage | Action | Résultat |
|---|---|---|
| 2026-11-10T06:16:00+08:00 | Consignation de la mesure dans [[jetson_orin_nx]] §4 et dans l'[[index]] | Documenté, aucune suppression effectuée |

## 4. Conditions de clôture

La trace passe à `validé` lorsque `df -h /` retourne `Use%` ≤ 85 % et `Avail` ≥ 20 Go.

## 5. Voir aussi

- Plateforme et stockage : [[jetson_orin_nx]]
- Journal de la session : [[2026-11-10_bootstrap_knowledge_base]]
