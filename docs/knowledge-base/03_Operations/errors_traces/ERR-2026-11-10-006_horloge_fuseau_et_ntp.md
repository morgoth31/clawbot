---
title: "ERR-2026-11-10-006 — horloge locale au fuseau chinois, RTC à l'époque Unix"
date: "2026-11-10T06:55:00+01:00"
author: "Hermes Agent"
tags: [operations, erreur, trace, horloge, ntp, timezone, systemd]
status: validé
---

# ERR-2026-11-10-006 — horloge locale au fuseau chinois, RTC à l'époque Unix

| Champ | Valeur |
|---|---|
| Identifiant | `ERR-2026-11-10-006` |
| Horodatage de détection | 2026-11-10T13:49:37+08:00 (heure locale d'alors) |
| Composant | horloge système, fuseau, RTC et `systemd-timesyncd` |
| Gravité d'exploitation | moyenne — horodatage faux de 7 h dans les documents et journaux |
| Statut | clos le 2026-11-10 |
| Mitigation appliquée | fuseau `Europe/Paris`, RTC en UTC, serveurs NTP français |

## 1. Symptôme

Toutes les dates affichées étaient en `CST +0800` alors que le robot est en France :

```
$ date -Iseconds
2026-11-10T13:49:37+08:00

$ timedatectl
               Local time: Tue 2026-11-10 13:49:37 CST
           Universal time: Tue 2026-11-10 05:49:37 UTC
                 RTC time: Thu 1970-01-01 08:55:57
                Time zone: Asia/Shanghai (CST, +0800)
System clock synchronized: yes
              NTP service: active
              RTC in local TZ: yes
```

## 2. Diagnostic — l'heure absolue était bonne, le fuseau non

| Vérification | Résultat |
|---|---|
| Heure UTC du système | `2026-11-10T05:49:44+00:00` |
| Heure annoncée par un serveur externe | `Tue, 10 Nov 2026 05:49:44 GMT` |
| Écart | **0 s** |
| Fuseau configuré | `Asia/Shanghai` (`/etc/timezone`, `/etc/localtime`) |
| Synchronisation NTP | active et synchronisée (`systemd-timesyncd`) |
| RTC matériel | `1970-01-01 08:55:57`, soit l'époque Unix |

L'horloge était donc **exacte en UTC** : seule la conversion locale était fausse, avec 7 heures
d'avance sur l'heure française. Deux défauts secondaires ont été relevés :

1. `RTC in local TZ: yes` — la RTC était censée stocker l'heure locale, mode que systemd déconseille
   explicitement (il casse au changement d'heure).
2. La RTC elle-même valait 1970 : elle n'a pas été mise à l'heure, ou n'est pas alimentée hors tension.

## 3. Correction appliquée

| Action | Commande | Effet constaté |
|---|---|---|
| Fuseau français | `timedatectl set-timezone Europe/Paris` | `Time zone: Europe/Paris (CET, +0100)` |
| RTC en UTC | `timedatectl set-local-rtc 0` | `RTC in local TZ: no` |
| Serveurs NTP français | `/etc/systemd/timesyncd.conf` | `NTP=0.fr.pool.ntp.org 1.fr.pool.ntp.org 2.fr.pool.ntp.org 3.fr.pool.ntp.org`, secours `ntp.ubuntu.com` |
| Redémarrage du service | `systemctl restart systemd-timesyncd` | `ServerName=0.fr.pool.ntp.org`, stratum 3, délai 7 ms |
| RTC mise à l'heure | `hwclock --systohc` | `RTC time: 2026-11-10 05:49:58` (UTC) |

Résultat :

```
$ date -Iseconds
2026-11-10T06:49:58+01:00

$ timedatectl
               Local time: Tue 2026-11-10 06:49:58 CET
           Universal time: Tue 2026-11-10 05:49:58 UTC
                 RTC time: Tue 2026-11-10 05:49:58
                Time zone: Europe/Paris (CET, +0100)
System clock synchronized: yes
              NTP service: active
              RTC in local TZ: no

écart avec l'heure d'un serveur externe : 0 s (résolution de l'en-tête HTTP : 1 s)
```

## 4. Conséquences sur les documents déjà produits

Les documents antérieurs portent des horodatages en `+08:00`. Ils restent **exacts** : un horodatage
ISO 8601 avec décalage désigne un instant absolu, pas une heure locale. Aucune réécriture n'est donc
nécessaire ; les documents produits à partir de maintenant portent `+01:00` (CET) ou `+02:00` (CEST en
été, géré par la base de fuseaux).

Les commits Git antérieurs sont dans le même cas : décalage `+0800`, instant correct.

## 5. Risque résiduel

| Risque | Constat | Parade |
|---|---|---|
| RTC non alimentée hors tension | la RTC valait 1970 alors que l'UTC était juste | au démarrage, l'heure est fausse jusqu'à la synchronisation NTP (quelques secondes après le réseau) |
| Démarrage sans réseau | pas de NTP, pas de RTC valide → heure à l'époque Unix | les services qui dépendent de TLS peuvent échouer ; `After=network-online.target` sur les unités concernées |
| Changement d'heure | géré par `Europe/Paris` | plus de mode « RTC en heure locale », donc plus de dérive au changement |

La présence d'une pile de sauvegarde sur la carte (RTC du module Jetson) n'a pas été vérifiée
physiquement : c'est une **hypothèse non confirmée**, à contrôler lors d'une coupure d'alimentation
planifiée.

## 6. Voir aussi

- [[etat_noeuds_et_services]] — relevé horodaté, régénéré après correction
- [[jetson_orin_nx]] — plateforme et périphériques
- [[systemd_robot_services]] — unités et dépendances
