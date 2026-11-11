---
title: "Enceinte Bluetooth Sony SRS-XB100 — appairage et sortie A2DP"
date: "2026-11-11T16:45:00+01:00"
author: "Hermes Agent"
tags: [hardware, audio, bluetooth, a2dp, srs-xb100, pulseaudio]
status: validé
---

# Enceinte Bluetooth Sony SRS-XB100 — appairage et sortie A2DP

Retour à l'[[index]] ; anomalie d'appairage et cause racine : [[ERR-2026-11-11-011_bluetooth_appairage_sans_ble]].

## 1. Identification mesurée (2026-11-11 16:40)

| Élément | Valeur | Commande |
|---|---|---|
| Modèle | Sony SRS-XB100, Bluetooth 5.3, hors V4L (audio seul) | `bluetoothctl info` |
| Adresse | `40:72:18:F0:2C:C9` (publique) | `bluetoothctl devices` |
| Classe | `0x00240414` (audio) | `bluetoothctl info` |
| Adaptateur hôte | Realtek `0bda:c822`, `DC:4A:9E:DF:D6:E3`, HCI 5.1 | `lsusb -d 0bda:c822` |
| État | `Paired: yes`, `Trusted: yes`, `Connected: yes` | `bluetoothctl info 40:72:18:F0:2C:C9` |
| Clé de liaison | stockée dans `/var/lib/bluetooth/DC:4A:9E:DF:D6:E3/40:72:18:F0:2C:C9/info` (`LinkKey`, `store_hint 1`) | `sudo grep -c LinkKey …/info` |
| Profils résolus | A2DP Source/Sink (`110a`/`110b`), AVRCP (`110c`/`110e`), HFP (`111e`), UUID constructeur Sony | `bluetoothctl info` |

## 2. Sortie audio

| Élément | Valeur |
|---|---|
| Carte PulseAudio | `bluez_card.40_72_18_F0_2C_C9` (`module-bluez5-device.c`) |
| Profil actif | `a2dp_sink` |
| Sink | `bluez_sink.40_72_18_F0_2C_C9.a2dp_sink`, s16le 2 canaux 44,1 kHz |
| Test | `paplay /usr/share/sounds/alsa/Front_Center.wav` → sink de `SUSPENDED` à `IDLE`, son entendu |

Routage par défaut, non persistant après redémarrage de PulseAudio :

```bash
./scripts/audio_enceinte_defaut.sh   # idempotent, sans effet si l'enceinte est absente
```

## 3. Procédure d'appairage (contournement documenté)

Le noyau ne répond pas à `IO_Capability_Request` (voir ERR-011) ; l'appairage n'aboutit qu'en
injectant la réponse manquante au niveau HCI :

```bash
# enceinte en mode appairage : voyant bleu clignotant vite + annonce « Bluetooth pairing »
sudo ./scripts/appairer_enceinte_bluetooth.sh 40:72:18:F0:2C:C9
```

Le script envoie, en boucle courte pendant le `btmgmt pair` :

```text
IO_Capability_Request_Reply      OGF 0x01 OCF 0x002b : IO cap 0x03 (NoInputNoOutput), OOB 0x00, AuthReq 0x04
User_Confirmation_Request_Reply  OGF 0x01 OCF 0x002c : valide le « Just Works »
```

Puis `trust` et `connect`, et affiche `Paired/Connected`. Séquence validée manuellement le
2026-11-11 : premier essai `status 0x0a (Busy)`, second essai `new_link_key … store_hint 1`,
`Paired: yes`, `Connection successful`.

## 4. Reconnexion après redémarrage

Mesuré le 2026-11-11 après `systemctl restart bluetooth` : `Paired: yes` et `Trusted: yes`
**conservés** (clé sur disque), `Connected: no` — la reconnexion n'est pas automatique. De plus
PulseAudio perd la carte `bluez` quand `bluetoothd` redémarre. Le script suivant enchaîne les trois
étapes (connexion, rechargement des modules PulseAudio, profile + sink par défaut) :

```bash
./scripts/audio_enceinte_defaut.sh 40:72:18:F0:2C:C9   # MAC optionnelle, celle-ci par défaut
# sink par défaut : bluez_sink.40_72_18_F0_2C_C9.a2dp_sink
```

Vérifié après redémarrage : carte recréée, `Default Sink` sur l'enceinte, `paplay` fait passer le
sink de `SUSPENDED` à `IDLE`.

## 5. Pièges

- **La réponse IO Capability vient de l'hôte, pas de l'enceinte.** Sans elle, la capture `btmon`
  montre `IO_Capability_Request` puis un silence jusqu'au timeout — d'où le contournement.
- **La commande de désactivation de Secure Connections** (`hcitool -i hci0 cmd 0x03 0x007a 0x00`)
  renvoie `status 0x0c` (refusée) sur ce firmware ; elle est sans effet sur le résultat. Elle est
  conservée dans le script parce qu'elle ne casse rien, pas parce qu'elle aide.
- **`btmgmt pair` en `Busy`** si une tentative précédente n'est pas soldée : `btmgmt cancelpair`
  puis `bluetoothctl disconnect` avant de relancer.
- **`btmgmt find` est rejeté** (`0x0b Rejected`) quand `bluetoothd` tourne ; utiliser
  `bluetoothctl scan on`, même pile MGMT.
- **Clé persistante** : l'appairage survit au redémarrage du poste. Ne relancer le script qu'après
  un désappairage ou un reset de l'enceinte.
- **Sortie seule** : l'A2DP est unidirectionnel ; le micro de l'enceinte n'est pas utilisé, le STT
  reste sur les micros existants (conception, §9).

## 6. Voir aussi

[[ERR-2026-11-11-011_bluetooth_appairage_sans_ble]] · [[inventaire_materiel]] ·
[[jetson_orin_nx]] · [[2026-11-11_compte_rendu_bluetooth_srs_xb100]] · [[index]]
