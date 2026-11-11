---
title: "Compte rendu — appairage Bluetooth A2DP de la SRS-XB100 (état, preuves, pistes)"
date: "2026-11-11T16:05:00+01:00"
author: "Hermes Agent"
tags: [bluetooth, a2dp, srs-xb100, rtl8822cu, noyau, handoff, jetson]
status: actif
---

# Compte rendu — appairage Bluetooth A2DP de la SRS-XB100

Document de reprise : il décrit l'objectif, la configuration mesurée, les modifications appliquées,
les preuves, les hypothèses éliminées et celles qui restent, avec les expériences exactes à refaire.
Il est écrit pour être remis tel quel à un autre intervenant.

## 1. Objectif

Connecter l'enceinte Bluetooth Sony **SRS-XB100** au Jetson du robot pour en faire la sortie audio
A2DP du Système 1 (conception, §9). L'appairage n'aboutit pas ; la sortie audio n'existe donc pas.

## 2. Configuration mesurée du poste (2026-11-11)

| Élément | Valeur | Commande |
|---|---|---|
| Carte | Jetson Orin NX, L4T R36.4.7 (`generic`, kernel `oot`) | `cat /etc/nv_tegra_release` |
| Noyau | `5.15.148-tegra` | `uname -r` |
| Adaptateur | USB `0bda:c822` Realtek RTL8822CU, `DC:4A:9E:DF:D6:E3`, HCI/LMP 5.1 | `lsusb -d 0bda:c822`, `hciconfig hci0 version` |
| Pilote | `btusb` + `btrtl` (module constructeur `rtk_btusb` chargé mais **inutilisé**) | `readlink -f /sys/class/bluetooth/hci0/device/driver` |
| Firmware BT | `rtl8822cu_fw.bin` (58 960 o, sha256 `f412693e6c39ba3f…`), version `0x19b76d7d` | `dmesg` |
| BlueZ | 5.64 | `bluetoothd -v` |
| PulseAudio | 15.99.1 | `pulseaudio --version` |
| Enceinte | Sony SRS-XB100, adresse réelle après reset `40:72:18:F0:2C:C9` (BT 5.3) | `bluetoothctl devices` |

Options de noyau pertinentes (`zcat /proc/config.gz`) :

```text
CONFIG_BT=y
CONFIG_BT_BREDR=y
CONFIG_BT_RFCOMM=y
CONFIG_BT_HIDP=m
CONFIG_BT_HCIBTUSB=m
CONFIG_BT_HCIBTUSB_RTL=y
# CONFIG_BT_HS is not set
# CONFIG_BT_LE is not set
# CONFIG_BT_DEBUGFS is not set
# CONFIG_DYNAMIC_DEBUG is not set
```

## 3. Modifications appliquées au poste

### 3.1 Profils audio rétablis (persistant)

NVIDIA installe un drop-in qui **désactive les profils audio** de `bluetoothd` :

```text
/lib/systemd/system/bluetooth.service.d/nv-bluetooth-service.conf
ExecStart=/usr/lib/bluetooth/bluetoothd -d --noplugin=audio,a2dp,avrcp
```

Drop-in ajouté, qui neutralise les deux `ExecStart` précédents :

```text
/etc/systemd/system/bluetooth.service.d/zz-audio.conf
[Service]
ExecStart=
ExecStart=/usr/lib/bluetooth/bluetoothd
```

Vérification après `systemctl daemon-reload && systemctl restart bluetooth` : les UUID
`Audio Sink (0000110b)`, `Audio Source (0000110a)`, AVRCP (`0000110c`, `0000110e`), HFP (`0000111f`)
apparaissent dans `bluetoothctl show`. **Acquis : sans ce drop-in, aucune enceinte ne peut sortir
de son, même appairée.**

### 3.2 PulseAudio

`pulseaudio-module-bluetooth` était absent ; installé (`1:15.99.1+dfsg1-1ubuntu2.2`). Modules
chargés et vérifiés : `module-bluetooth-policy`, `module-bluetooth-discover`, `module-bluez5-discover`.

### 3.3 Retour arrière

```bash
sudo rm /etc/systemd/system/bluetooth.service.d/zz-audio.conf
sudo systemctl daemon-reload && sudo systemctl restart bluetooth
# optionnel : sudo apt remove pulseaudio-module-bluetooth
```

Aucune modification de `/etc/bluetooth/main.conf`, du noyau, du firmware, ni de l'enceinte.

### 3.4 Effets de bord

- Chaque `restart bluetooth` déconnecte le clavier Bluetooth `10:12:57:63:00:01` ; il se reconnecte
  quand on le rallume.
- Réglages `btmgmt` manipulés pendant l'enquête (`ssp`, `sc`, `io-cap`) : **runtime seulement**,
  remis à `on`, perdus au redémarrage du service.
- Entrée BlueZ de l'enceinte supprimée (elle n'était pas appairée). L'entrée `FF:72:18:F0:2C:C9`
  visible dans `bluetoothctl devices` est un cache obsolète (adresse aléatoire).

## 4. État courant vérifié

```text
bluetooth.service : active
hci0              : Powered yes, Pairable yes, Discoverable no
enceinte          : Paired no, Connected no, Trusted yes
cartes PulseAudio : aucune carte bluez
```

## 5. Preuves

### 5.1 L'enceinte est joignable, l'inquiry ne la voit pas

Six scans (25 à 60 s) : `Acer-F098110B`, `LORDI-99AHSTMP0`, `BCSO2405230693`, `Charge 6`,
clavier — **jamais** la SRS-XB100 avant reset.

Après reset usine, elle apparaît sous `40:72:18:F0:2C:C9` ; la page directe aboutit :

```text
$ sudo hcitool cc FF:72:18:F0:2C:C9
Connections:
  < ACL FF:72:18:F0:2C:C9 handle 1 state 7 lm CENTRAL
```

SDP résolu (`Audio Sink`, `Handsfree`, AVRCP, UUID constructeur Sony) : l'enceinte répond
correctement à la découverte de services.

### 5.2 L'appairage bloque au niveau de l'hôte

Capture `btmon` (tentative `bluetoothctl pair`) :

```text
> HCI Event: Command Status  #10   Authentication Requested (0x01|0x0011) ncmd 2
> HCI Event: Link Key Request #12   40:72:18:F0:2C:C9
< HCI Command: Link Key Request Negative Reply  #14
> HCI Event: IO Capability Request #16
   ... aucune commande hôte ...
@ MGMT Command: Cancel Pair Device  (timeout 25 s)
        Status: Cancelled (0x10)
```

Ni `IO Capability Request Reply` **ni** réponse négative ne sont émises. `bluetoothctl info` reste
`Paired: no`.

### 5.3 Condition exacte du noyau (source 5.15, `net/bluetooth/hci_event.c`)

```c
static void hci_io_capa_request_evt(struct hci_dev *hdev, struct sk_buff *skb)
{
    conn = hci_conn_hash_lookup_ba(hdev, ACL_LINK, &ev->bdaddr);
    if (!conn)
        goto unlock;
    hci_conn_hold(conn);
    if (!hci_dev_test_flag(hdev, HCI_MGMT))
        goto unlock;
    /* Allow pairing if we're pairable, the initiators of the
     * pairing or if the remote is not requesting bonding. */
    if (hci_dev_test_flag(hdev, HCI_BONDABLE) ||
        test_bit(HCI_CONN_AUTH_INITIATOR, &conn->flags) ||
        (conn->remote_auth & ~0x01) == HCI_AT_NO_BONDING) {
        /* envoie IO_CAPABILITY_REPLY */
    } else {
        /* envoie IO_CAPABILITY_NEG_REPLY */
    }
}
```

Comme **aucune** des deux réponses n'est émise, le gestionnaire est sorti avant la branche :
soit `conn` introuvable dans la hash (adresse/type), soit `HCI_MGMT` faux. C'est le point exact à
instrumenter (voir §7, piste 1).

### 5.4 Le BLE est absent du noyau

```text
$ zcat /proc/config.gz | grep CONFIG_BT_LE
# CONFIG_BT_LE is not set
$ sudo hcitool lescan
Enable scan failed: Input/output error
```

### 5.5 Le pilote constructeur ne prend pas le contrôleur

```text
$ sudo systemctl stop bluetooth && sudo modprobe -r btusb && sudo modprobe rtk_btusb
rtk_btusb 73728 0
aucun adaptateur HCI      # retour à btusb : hci0 rétabli
```

### 5.6 Téléphone (Pixel 6a, `24:95:2F:B7:73:F1`)

Voit « yahboom » en mode découvrable, mais l'association échoue aussi. **La tentative n'a laissé
aucune trace HCI** dans `btmon` — soit elle est restée côté téléphone, soit elle est passée en BLE.
Expérience à refaire proprement (§7, piste 2), c'est le discriminant hôte/enceinte.

## 6. Hypothèses éliminées

| Hypothèse | Test | Résultat |
|---|---|---|
| Incompatibilité de version | HCI 5.1 vs BT 5.3 | rétrocompatible, écarté |
| Enceinte hors mode appairage | reset usine, voyant rapide confirmé | elle répond en ACL et SDP, écarté comme cause unique |
| Clé obsolète côté enceinte | reset usine, adresse redevenue `40:72:…` | `Link Key Request Negative Reply` est la séquence normale, écarté |
| Profils audio absents | drop-in + paquet PulseAudio | corrigé, mais l'échec est en amont (appairage) |
| Pilote constructeur Realtek | `modprobe rtk_btusb` | aucun adaptateur HCI, écarté |
| Manque de place / service en root | — | sans rapport ici |

## 7. Pistes restantes, par ordre de coût

1. **Instrumenter `hci_io_capa_request_evt`** (le plus informatif). Le poste n'a ni `bpftrace` ni
   `trace-cmd`, et `CONFIG_KPROBE_EVENTS`/`CONFIG_DYNAMIC_DEBUG` sont absents : il faut soit
   installer `bpftrace` (`apt install bpftrace`), soit recompiler avec les options. But : savoir si
   `conn == NULL` ou `HCI_MGMT` faux. Si `conn == NULL`, le problème est l'appariement
   adresse/type de connexion côté noyau ; si `HCI_MGMT` est faux, bluetoothd n'a pas pris la main
   sur le contrôleur via mgmt.
2. **Téléphone avec capture active**, `Pairable: yes` vérifié au moment de la tentative, agent
   d'appairage enregistré (`bluetoothctl` → `agent NoInputNoOutput` + `default-agent`, session
   maintenue ouverte). Si l'association échoue encore sans aucune trame HCI, le téléphone tente un
   appairage BLE : ce serait cohérent avec `CONFIG_BT_LE` absent.
3. **Activer `HCI_BONDABLE` au moment du `pair`** : `Pairable` revient à `no` à chaque
   redémarrage de `bluetoothd`. Vérifier `bluetoothctl show | grep Pairable` **juste avant** le
   `pair`, puis capturer. C'est la variable la moins contrôlée des tentatives déjà faites.
4. **Dongle Bluetooth USB** (CSR8510, BCM20702) : contourne le noyau sans le modifier, apporte
   BR/EDR + BLE. C'est la voie la plus courte vers un son audible.
5. **Recompiler le noyau L4T** avec `CONFIG_BT_LE=y`, `CONFIG_BT_HS=y`, `CONFIG_BT_DEBUGFS=y`
   (et éventuellement `CONFIG_KPROBE_EVENTS`) : lourd, risque de démarrage, à faire avec sauvegarde
   de la partition et accès physique.
6. **Coexistence Wi-Fi 2,4 GHz** : non testée volontairement, la session SSH passe par
   `wlP1p1s0` (192.168.1.47). À tester seulement si l'accès passe en Ethernet.

## 8. Commandes de diagnostic à réutiliser

```bash
export ROS_DOMAIN_ID=28; source /opt/ros/humble/setup.bash   # inutile pour BT, mais réflexe du poste

sudo btmon -w /tmp/bt.snoop            # capture HCI (laisser tourner pendant l'essai)
sudo btmon -r /tmp/bt.snoop | less     # relecture

bluetoothctl show                       # Powered / Pairable / Discoverable / UUID
bluetoothctl info 40:72:18:F0:2C:C9      # Paired / Connected / UUID
sudo hcitool con                        # ACL établies
sudo hcitool lescan                     # échoue : BLE absent du noyau (EIO)
pactl list cards short | grep -i bluez  # carte audio attendue après appairage
pactl set-default-sink bluez_sink.40_72_18_F0_2C_C9.a2dp_sink
```

Séquence d'appairage utilisée (agent maintenu dans la même session, sinon la demande du pair est
rejetée) :

```bash
{ echo "agent on"; sleep 1; echo "default-agent"; sleep 1;
  echo "pair 40:72:18:F0:2C:C9"; sleep 12; echo quit; } | bluetoothctl
```

## 9. Ce qu'un intervenant suivant doit savoir

- `Pairable` (mgmt `bondable`) n'est **pas** persistant : il est remis à `no` au redémarrage de
  `bluetoothd`. Toute tentative d'appairage doit le vérifier à l'instant T.
- `ros2 service call` n'a rien à voir ici, mais le même piège de couche existe : ne jamais
  réinterpréter un protocole binaire/JSON par un CLI qui le re-formate.
- La pile audio est prête ; le jour où l'appairage aboutit, la carte `bluez_card.*` apparaît sans
  autre changement. Toute la difficulté est en amont, dans l'appairage HCI.
- Les traces et ce compte rendu sont versionnés : `docs/knowledge-base/03_Operations/`.


## 10. Directives appliquées le 2026-11-11 16:20 — résultat

Quatre règles ont été appliquées strictement, sans `hcitool` ni `hciconfig` :

1. **BR/EDR forcé** — `/etc/bluetooth/main.conf` (sauvegarde `main.conf.bak-20261111`) :

   ```ini
   PairableTimeout = 0
   ControllerMode = bredr
   JustWorksRepairing = always
   ```

   Vérifié ensuite par `btmgmt info` : `current settings: powered bondable ssp br/edr secure-conn`
   — `le` **absent** de la liste, donc BLE bien désactivé.
2. **Cache purgé** : `FF:72:18:F0:2C:C9` et `40:72:18:F0:2C:C9` supprimés de
   `/var/lib/bluetooth/DC:4A:9E:DF:D6:E3/cache/`.
3. **Réglages MGMT** : `ssp on`, `bondable on`, `pairable on`, `le off` acceptés.
   `sc off` **refusé** : `Set Secure Connections for hci0 failed with status 0x0c (Not Supported)`,
   y compris contrôleur éteint (`power off` → `sc off` → `power on`). `secure-conn` reste donc actif ;
   à noter que l'enceinte n'annonce pas SC (ses extended features ne portent que
   `Secure Simple Pairing (Host Support)`), donc l'hypothèse SC n'est pas testable par ce levier.
4. **Scan MGMT** : `btmgmt find` est **rejeté** quand `bluetoothd` tourne
   (`Unable to start discovery. status 0x0b (Rejected)`) ; le scan a été fait par
   `bluetoothctl scan on`, même pile MGMT. L'enceinte est bien vue :
   `NEW Device 40:72:18:F0:2C:C9 SRS-XB100`.

Appairage demandé :

```bash
sudo btmgmt cancelpair 40:72:18:F0:2C:C9      # état propre après un premier essai « Busy »
sudo btmgmt pair -c 3 -t 0 40:72:18:F0:2C:C9  # -c 3 = NoInputNoOutput, -t 0 = BR/EDR
```

Trace HCI obtenue (capture `btmon`, 30 s) :

```text
< HCI Command: Authentication Requested
> HCI Event: Link Key Request            40:72:18:F0:2C:C9
< HCI Command: Link Key Request Negative Reply
> HCI Event: IO Capability Request
> HCI Event: Read Remote Supported Features   (l'enceinte répond)
> HCI Event: Read Remote Extended Features
   ... aucune IO Capability Request Reply, ni négative ...
@ MGMT Close: btmgmt                      après 30 s
```

État final : `Paired: no`, `Connected: yes` (ACL nue), aucune carte `bluez` dans PulseAudio.

**Conclusion de cette passe** : ni le mode BR/EDR forcé, ni la purge du cache, ni `JustWorksRepairing`,
ni l'appairage MGMT en `NoInputNoOutput` ne changent le symptôme. Le gestionnaire noyau
`hci_io_capa_request_evt` reste muet alors que `bondable` est actif et `HCI_MGMT` nécessairement
établi (les commandes mgmt fonctionnent). Deux explications restent : `hci_conn_hash_lookup_ba`
échoue pour cette connexion, ou le noyau L4T embarque une variante de ce gestionnaire. Les deux se
tranchent par instrumentation (`bpftrace` sur `hci_io_capa_request_evt`), pas par configuration.

## Voir aussi

[[ERR-2026-11-11-011_bluetooth_appairage_sans_ble]] · [[inventaire_materiel]] ·
[[jetson_orin_nx]] · [[systemd_robot_services]] · [[index]]
