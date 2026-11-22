# Calibration de la manette — plan d'implémentation

Date : 2026-11-15 14:48 CET
Dépôt : `/home/jetson/clawbot`
Auteur du plan : Hermes Agent

---

## Objectif

Remplacer une collection de mesures manuelles par **une procédure guidée unique**
(`joy_teleop/calibration.py`) qui identifie toutes les entrées du pad, mesure les
calibrations analogiques (sticks, IMU), teste les actionneurs (vibration, lumière),
écrit un fichier `config/manette.yaml`, et fait consommer ce fichier par le nœud de
téléopération — de sorte qu'aucune constante de mapping ne soit plus codée en dur.

---

## Pourquoi une seule mesure ne suffit pas — et pourquoi ça change

La question est légitime, la réponse est mesurée : **le numéro d'un bouton dépend de
la couche qui le lit**.

| Chemin de lecture | ZR | L | Home |
|---|---|---|---|
| paquet `joy` (SDL) | 6 | 7 | 11 |
| `jsdev` (`/dev/input/jsN`, notre source) | 8 (numérotation noyau) | 5 | 11 |

Le noyau numérote les boutons dans l'ordre des codes `BTN_*` du périphérique ; SDL
réordonne selon sa propre table. Une table relevée à travers SDL est donc fausse dès
qu'on lit `jsdev` — c'est exactement le bug qui a coûté trois tours de manipulation
aujourd'hui sur les axes (`X` positif à droite sur `jsdev`, inversé via SDL).

Il faut donc **un appui par entrée, sur le chemin définitif**. Ce que la procédure
apporte n'est pas « moins de mesures » mais : mesures automatisées, horodatées,
rejouables, écrites dans un fichier, et vérifiées par un test avant d'être utilisées.
Un pad remplacé ou une mise à jour du noyau se re-calibrent en une commande.

---

## Contexte actuel / hypothèses

Fichiers existants concernés :

- `joy_teleop/js_joy_source.py` — publie `sensor_msgs/Joy` depuis `/dev/input/jsN`
  (sans SDL). Choisit le nœud dont le nom n'est pas un capteur inertiel.
- `joy_teleop/clawbot_joy_teleop.py` — `/joy` → `/cmd_vel` + `/servo_ctrl`.
  **Contient encore des tables constantes** (`AX_*`, `BTN_*`) relevées à travers SDL,
  donc fausses sur au moins trois entrées.
- `joy_teleop/joy_teleop_launch.py` — lance la source et le teleop, transmet
  `device_path`, `rate`, `deadzone`, `linear_scale`, `angular_scale`, `arm_step`,
  `deadman_button`, `deadband`.
- `services/clawbot-joy-teleop.service` — lance `joy_teleop/joy_teleop_wait.sh`.
- `tests/test_joy_teleop_mapping.py` — 11 tests, domaine ROS 98.
- `config/` — configuration versionnée du robot (`preconditions.yaml`, `nav2_clawbot.yaml`…).

Faits mesurés le 2026-11-15 (à conserver tels quels, ils fondent les tests) :

- Pad Bluetooth `98:B6:E9:43:94:AA`, VID:PID `057e:2009`, nom BlueZ « Pro Controller ».
- Deux nœuds d'entrée : `js0` = pad (6 axes, 14 boutons), `js1` = IMU (6 axes, 0 bouton).
- Axes `jsdev` : `0` stick gauche X, `1` stick gauche Y, `2` stick droit X,
  `3` stick droit Y, `4` croix X, `5` croix Y.
- Signes `jsdev` mesurés : X positif vers la droite, Y négatif vers le haut.
- `EV_FF` présent sur le nœud du pad (`FF_RUMBLE`, `FF_GAIN`, `FF_PERIODIC`).
  `fftest` est installé sur le poste.
- Aucune LED de pad n'a été observée exposée à ce jour — à re-mesurer pad allumé.
- `M1` et `M2` ont produit les mêmes codes que `A` et `B` sur le chemin SDL : ce sont
  des doublons, pas des entrées distinctes. À re-vérifier sur `jsdev`, sans présumer.
- Le pad se met en veille ; la reconnexion ne peut pas être initiée par l'hôte
  (`br-connection-create-socket`). La calibration devra le dire si le pad disparaît.

Hypothèses de travail :

- Les gâchettes `ZL`/`ZR` sont **binaires** sur ce pad (aucun axe de gâchette dans les
  six axes). La procédure doit le **vérifier**, pas le supposer.
- `T`, `rond`, et `light` peuvent être soit de vrais boutons, soit des doublons,
  soit absents du rapport HID. La procédure enregistre lequel des trois.
- Le pad applique déjà sa calibration usine dans `hid-nintendo` (journal noyau :
  « using user cal for left stick ») : on mesure malgré tout centre, débattement et
  zone morte, car un clone peut dériver.

---

## Architecture

Trois modules, un contrat de données, zéro constante de mapping dans le code :

```
/proc/bus/input/devices ─┐
/sys/class/input/jsN/…   ├─→ joy_teleop/js_lecteur.py    (protocole jsdev, une fois)
/sys/class/input/eventN  │        ↑            ↑
/sys/class/leds          │        │            │
                         │  js_joy_source.py   calibration.py ──→ config/manette.yaml
                         │        │                                     │
                         └────────┴──────────→ /joy                     │
                                                    │                   │
                                    clawbot_joy_teleop.py ←─ manette_config.py
                                                    │
                                        /cmd_vel   /servo_ctrl
```

- `js_lecteur.py` — **seule** implémentation du format binaire `struct js_event`,
  partagée par la source temps réel et par la calibration (DRY).
- `manette_config.py` — charge, valide et expose le YAML : `bouton("home")`,
  `valeur(axes, "stick_gauche_x")`. Toute erreur nomme la clé fautive.
- `calibration.py` — procédure guidée, écriture atomique, refus d'écrire un YAML
  incomplet.

### Schéma du YAML (v1)

```yaml
schema: 1
genere_le: "2026-11-15T15:30:00+01:00"
outil: "joy_teleop/calibration.py"
poste: "yahboom"
appareil:
  nom: "Nintendo Switch Pro Controller"
  vid: "057e"
  pid: "2009"
  adresse: "98:B6:E9:43:94:AA"
  js_pad: "/dev/input/js0"
  js_imu: "/dev/input/js1"
  nb_axes: 6
  nb_boutons: 14
boutons:                     # nom logique → index jsdev MESURÉ
  A: 1
  B: 0
  X: 2
  Y: 3
  plus: 10
  moins: 9
  home: 11
  ZL: 7
  ZR: 8
  L: 5
  R: 6
  appui_stick_gauche: 12
  appui_stick_droit: 13
aliases:                     # entrée déclarée qui renvoie le code d'une autre
  M1: A
  M2: B
absents:                     # déclarée par l'opérateur, jamais observée
  - T
  - rond
  - light
axes:
  stick_gauche_x: {index: 0, centre: 0.003, min: -0.996, max: 1.0, zone_morte: 0.09, inverser: false}
  stick_gauche_y: {index: 1, centre: 0.002, min: -0.990, max: 0.990, zone_morte: 0.09, inverser: true}
  stick_droit_x:  {index: 2, centre: 0.001, min: -1.0, max: 1.0, zone_morte: 0.09, inverser: false}
  stick_droit_y:  {index: 3, centre: 0.004, min: -1.0, max: 1.0, zone_morte: 0.09, inverser: true}
  croix_x:        {index: 4, centre: 0.0, min: -1.0, max: 1.0, zone_morte: 0.5, inverser: false}
  croix_y:        {index: 5, centre: 0.0, min: -1.0, max: 1.0, zone_morte: 0.5, inverser: true}
imu:
  chemin: "/dev/input/js1"
  biais: [0.010, -0.021, 0.978, 0.001, -0.002, 0.000]   # 3 accéléromètre, 3 gyroscope
  gravite: 0.985
  bruit: [0.004, 0.004, 0.005, 0.002, 0.002, 0.002]
capacites:
  vibration: {disponible: true, methode: "evdev EV_FF", verifie: true}
  lumieres:  {disponible: false, raison: "aucune entrée /sys/class/leds rattachée au pad"}
  imu:       {disponible: true}
protocole:
  duree_s: 214
  etapes: 27
```

Règle non négociable : une entrée non observée est écrite dans `absents` **avec sa
raison**, jamais inventée ni silencieusement omise (règle 3 de la base OKF).

### Flux de données

1. `calibration.py` ouvre `js0` via `js_lecteur`, pose une question par entrée,
   capture la transition, écrit le YAML de façon atomique.
2. `js_joy_source.py` continue de publier `/joy` **brut** (index noyau) : c'est un
   miroir fidèle, pas une couche de traduction.
3. `clawbot_joy_teleop.py` charge le YAML et traduit les noms logiques en index.
   Changer de pad = re-calibrer, pas re-coder.

---

## Tâches

### T0 — Hygiène d'exécution des tests (2 min)

Le poste a trois pièges qui font échouer pytest pour de mauvaises raisons. Toute
commande de test de ce plan utilise ce préambule :

```bash
cd /home/jetson/clawbot
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1     # les plugins launch_testing de Humble cassent pytest
rm -rf joy_teleop/__pycache__                # un .pyc périmé rejoue le code d'hier
```

Vérification :

```bash
python3 -m pytest tests/test_joy_teleop_mapping.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : `11 passed` puis `EXIT=0`.

Créer `tests/conftest.py` pour que ce préambule soit inutile côté code :

```python
"""Neutralise les plugins pytest de ROS, incompatibles avec pytest 9 sur ce poste."""
import os

os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
```

Attendu après ajout : `python3 -m pytest tests/ -q` fonctionne sans la variable.

Commit : `test: neutralise les plugins pytest de ROS (launch_testing casse la collecte)`

---

### T1 — `js_lecteur.py` : le protocole jsdev, une seule fois (10 min)

**Test d'abord** — créer `tests/test_js_lecteur.py` :

```python
"""Décodage du format binaire js_event, sans périphérique réel."""
import struct

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "joy_teleop"))

from js_lecteur import LecteurJs, decodifier


def evenement(valeur, etype, numero, init=False):
    t = etype | (0x80 if init else 0)
    return struct.pack("<IhBB", 0, valeur, t, numero)


def test_axe_normalise():
    l = LecteurJs()
    l.ingerer(evenement(32767, 2, 1))
    assert l.etat().axes[1] == pytest.approx(1.0)


def test_bouton_appuye():
    l = LecteurJs()
    l.ingerer(evenement(1, 1, 6))
    assert l.etat().boutons[6] == 1


def test_evenement_init_ignore_mais_compte():
    """JS_EVENT_INIT annonce les capacités : il ne doit pas produire de transition."""
    l = LecteurJs()
    l.ingerer(evenement(0, 2, 0, init=True))
    assert l.etat().axes[0] == 0.0
    assert l.etat().nb_boutons_connus == 0


def test_plusieurs_evenements_dans_un_tampon():
    tampon = evenement(1000, 2, 0) + evenement(1, 1, 3)
    l = LecteurJs()
    l.ingerer(tampon)
    assert l.etat().axes[0] == pytest.approx(1000 / 32767)
    assert l.etat().boutons[3] == 1
```

```bash
python3 -m pytest tests/test_js_lecteur.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : `ModuleNotFoundError: No module named 'js_lecteur'` → échec attendu (RED).

**Implémenter** `joy_teleop/js_lecteur.py` :

```python
"""Lecture d'un périphérique /dev/input/jsN : décodage de struct js_event.

Unique implémentation du protocole dans le dépôt : `js_joy_source.py` l'utilise en
temps réel, `calibration.py` l'utilise en mode guidé. Le format est décrit dans
linux/input.h (struct js_event : __u32 time, __s16 value, __u8 type, __u8 number).
"""
from __future__ import annotations

import os
import select
import struct
from dataclasses import dataclass, field

EVENT_FMT = "<IhBB"
EVENT_TAILLE = struct.calcsize(EVENT_FMT)   # 8
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80


def decodifier(tampon: bytes):
    """Rend [(type, numero, valeur)] pour un tampon d'octets complet."""
    evenements = []
    for offset in range(0, len(tampon) - EVENT_TAILLE + 1, EVENT_TAILLE):
        _, valeur, etype, numero = struct.unpack_from(EVENT_FMT, tampon, offset)
        evenements.append((etype, numero, valeur))
    return evenements


@dataclass
class Etat:
    axes: dict[int, float] = field(default_factory=dict)
    boutons: dict[int, int] = field(default_factory=dict)
    nb_axes_connus: int = 0
    nb_boutons_connus: int = 0


class LecteurJs:
    """État courant d'un jsdev. `etat()` est toujours complet (trous à zéro)."""

    def __init__(self, chemin: str | None = None):
        self.chemin = chemin
        self._etat = Etat()
        self.fd = None
        if chemin:
            self.fd = os.open(chemin, os.O_RDONLY | os.O_NONBLOCK)

    def inerer(self, tampon: bytes) -> None:
        self.ingerer(tampon)

    def ingerer(self, tampon: bytes) -> None:
        for etype, numero, valeur in decodifier(tampon):
            init = bool(etype & JS_EVENT_INIT)
            etype &= ~JS_EVENT_INIT
            if etype == JS_EVENT_AXIS:
                self._etat.axes[numero] = valeur / 32767.0
                self._etat.nb_axes_connus = max(self._etat.nb_axes_connus, numero + 1)
            elif etype == JS_EVENT_BUTTON:
                self._etat.boutons[numero] = int(valeur)
                self._etat.nb_boutons_connus = max(self._etat.nb_boutons_connus, numero + 1)
            elif init:
                pass   # capacité annoncée, aucune transition d'état

    def lire(self, attente_s: float = 0.02) -> bool:
        """Lit ce qui est disponible. False si le périphérique a disparu."""
        if self.fd is None:
            return False
        lus, _, _ = select.select([self.fd], [], [], attente_s)
        if not lus:
            return True
        donnees = os.read(self.fd, EVENT_TAILLE * 64)
        if not donnees:
            return False
        self.ingerer(donnees)
        return True

    def etat(self) -> Etat:
        axe_max = max(self._etat.axes, default=-1) + 1
        btn_max = max(self._etat.boutons, default=-1) + 1
        return Etat(
            axes=[self._etat.axes.get(i, 0.0) for i in range(axe_max)],
            boutons=[self._etat.boutons.get(i, 0) for i in range(btn_max)],
            nb_axes_connus=self._etat.nb_axes_connus,
            nb_boutons_connus=self._etat.nb_boutons_connus,
        )

    def fermer(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
```

⚠️ `Etat.axes` et `Etat.boutons` sont typés `dict` dans la dataclass mais rendus en
**listes** par `etat()` — corriger la dataclass en `list[float]` / `list[int]` et le
stockage interne en dicts nommés `_axes` / `_boutons`. Le test `test_axe_normalise`
doit indexer une liste (`l.etat().axes[1]`), ce qui impose cette correction.

```bash
python3 -m pytest tests/test_js_lecteur.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : `4 passed` puis `EXIT=0`.

Commit : `feat(joy): extrait le protocole jsdev dans js_lecteur.py`

---

### T2 — `js_joy_source.py` utilise `js_lecteur` (5 min)

Remplacer dans `joy_teleop/js_joy_source.py` les fonctions `_lire()` et les champs
`self.axes` / `self.boutons` par une instance de `LecteurJs`. La sélection du
périphérique (`lister_manettes`) ne change pas.

Ajouter au fichier de test existant `tests/test_joy_teleop_mapping.py` :

```python
def test_source_reutilise_le_lecteur():
    source = (RACINE / "joy_teleop" / "js_joy_source.py").read_text()
    assert "from js_lecteur import LecteurJs" in source
    assert "struct.unpack" not in source      # plus de décodage en double
```

```bash
python3 -m pytest tests/test_joy_teleop_mapping.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : `12 passed`, `EXIT=0` (le test ci-dessus échoue avant l'implémentation).

Vérification réelle (pad allumé, téléop arrêté) :

```bash
python3 joy_teleop/js_joy_source.py --ros-args -p device_path:=auto -p rate:=20.0
```

Attendu, une ligne :
`source /joy sur /dev/input/js0 (Nintendo Switch Pro Controller) — 6 axes, 14 boutons, 20 Hz, deadzone 0.05`

Commit : `refactor(joy): js_joy_source s'appuie sur js_lecteur`

---

### T3 — `manette_config.py` : chargeur et validation (15 min)

**Test d'abord** — `tests/test_manette_config.py` :

```python
"""Chargement du YAML de manette : validation, alias, décodage d'axe."""
import math
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

from manette_config import Axe, ConfigInvalide, charger

FIXTURE = RACINE / "tests" / "fixtures" / "manette_test.yaml"


def test_charge_un_yaml_valide():
    m = charger(FIXTURE)
    assert m.bouton("home") == 11
    assert m.axe("stick_gauche_x").index == 0


def test_alias_resolu():
    m = charger(FIXTURE)
    assert m.bouton("M1") == m.bouton("A")


def test_cle_manquante_nomme_la_cle(tmp_path):
    chemin = tmp_path / "invalide.yaml"
    chemin.write_text("schema: 1\nappareil: {nom: x}\nboutons: {A: 1}\n")
    with pytest.raises(ConfigInvalide) as err:
        charger(chemin)
    assert "axes" in str(err.value)


def test_schema_inconnu_refuse(tmp_path):
    chemin = tmp_path / "futur.yaml"
    chemin.write_text("schema: 99\n")
    with pytest.raises(ConfigInvalide) as err:
        charger(chemin)
    assert "99" in str(err.value)


def test_decode_axe_centre_et_zone_morte():
    a = Axe("x", 0, centre=0.02, minimum=-1.0, maximum=1.0, zone_morte=0.1, inverser=False)
    assert a.decoder(0.02) == 0.0          # au centre
    assert a.decoder(0.08) == 0.0          # dans la zone morte
    assert a.decoder(1.0) == pytest.approx(1.0)
    assert a.decoder(-1.0) == pytest.approx(-1.0)


def test_decode_axe_inverse():
    a = Axe("y", 1, centre=0.0, minimum=-1.0, maximum=1.0, zone_morte=0.1, inverser=True)
    assert a.decoder(1.0) == pytest.approx(-1.0)


def test_nan_vaut_zero():
    a = Axe("x", 0, centre=0.0, minimum=-1.0, maximum=1.0, zone_morte=0.1, inverser=False)
    assert a.decoder(math.nan) == 0.0


def test_valeur_hors_tableau_vaut_zero():
    m = charger(FIXTURE)
    assert m.valeur([], "stick_gauche_x") == 0.0
```

Créer `tests/fixtures/manette_test.yaml` :

```yaml
schema: 1
genere_le: "2026-11-15T00:00:00+01:00"
outil: "tests"
appareil: {nom: "Fixture", vid: "057e", pid: "2009"}
boutons: {A: 1, B: 0, X: 2, Y: 3, home: 11, ZL: 7, ZR: 8, L: 5, R: 6, plus: 10, moins: 9}
aliases: {M1: A}
absents: [T, rond, light]
axes:
  stick_gauche_x: {index: 0, centre: 0.0, min: -1.0, max: 1.0, zone_morte: 0.08, inverser: false}
  stick_gauche_y: {index: 1, centre: 0.0, min: -1.0, max: 1.0, zone_morte: 0.08, inverser: true}
  stick_droit_x:  {index: 2, centre: 0.0, min: -1.0, max: 1.0, zone_morte: 0.08, inverser: false}
  stick_droit_y:  {index: 3, centre: 0.0, min: -1.0, max: 1.0, zone_morte: 0.08, inverser: true}
  croix_x:        {index: 4, centre: 0.0, min: -1.0, max: 1.0, zone_morte: 0.5, inverser: false}
  croix_y:        {index: 5, centre: 0.0, min: -1.0, max: 1.0, zone_morte: 0.5, inverser: true}
imu: {chemin: "/dev/input/js1", biais: [0, 0, 0, 0, 0, 0], gravite: 1.0, bruit: [0, 0, 0, 0, 0, 0]}
capacites:
  vibration: {disponible: true, methode: "evdev EV_FF", verifie: false}
  lumieres: {disponible: false, raison: "fixture"}
```

```bash
python3 -m pytest tests/test_manette_config.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu RED : `ModuleNotFoundError: No module named 'manette_config'`.

**Implémenter** `joy_teleop/manette_config.py` :

```python
"""Configuration de manette : chargement, validation, décodage d'axes.

Une erreur de configuration ne doit jamais produire un mapping silencieusement faux :
chaque refus nomme la clé fautive et le fichier concerné.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA_SUPPORTE = 1
CLES_OBLIGATOIRES = ("schema", "appareil", "boutons", "axes")


class ConfigInvalide(Exception):
    """Configuration absente, illisible, incomplète ou incohérente."""


@dataclass(frozen=True)
class Axe:
    nom: str
    index: int
    centre: float
    minimum: float
    maximum: float
    zone_morte: float
    inverser: bool

    def decoder(self, valeur_brute: float) -> float:
        """Ramène une valeur brute dans [-1, 1], positif = droite ou haut."""
        if valeur_brute is None or valeur_brute != valeur_brute:   # NaN
            return 0.0
        ecart = valeur_brute - self.centre
        if abs(ecart) <= self.zone_morte:
            return 0.0
        reference = (self.maximum - self.centre) if ecart > 0 else (self.centre - self.minimum)
        if reference <= 1e-6:
            return 0.0
        valeur = max(-1.0, min(1.0, ecart / reference))
        return -valeur if self.inverser else valeur


class Manette:
    def __init__(self, donnees: dict, chemin: Path):
        self.donnees = donnees
        self.chemin = chemin
        self.appareil = donnees.get("appareil") or {}
        self.boutons = {str(k): int(v) for k, v in (donnees.get("boutons") or {}).items()}
        self.aliases = {str(k): str(v) for k, v in (donnees.get("aliases") or {}).items()}
        self.absents = [str(x) for x in (donnees.get("absents") or [])]
        self.axes = {str(nom): _lire_axe(nom, d) for nom, d in donnees["axes"].items()}
        self.imu = donnees.get("imu") or {}
        self.capacites = donnees.get("capacites") or {}

    def bouton(self, nom: str) -> int:
        if nom in self.boutons:
            return self.boutons[nom]
        if nom in self.aliases:
            cible = self.aliases[nom]
            if cible in self.boutons:
                return self.boutons[cible]
            raise ConfigInvalide(
                f"{self.chemin} : alias {nom!r} → {cible!r}, mais {cible!r} n'est pas dans « boutons »")
        if nom in self.absents:
            raise ConfigInvalide(
                f"{self.chemin} : {nom!r} déclaré absent à la calibration, aucun code à lire")
        raise ConfigInvalide(f"{self.chemin} : bouton {nom!r} inconnu")

    def bouton_ou_none(self, nom: str) -> int | None:
        try:
            return self.bouton(nom)
        except ConfigInvalide:
            return None

    def axe(self, nom: str) -> Axe:
        if nom not in self.axes:
            raise ConfigInvalide(f"{self.chemin} : axe {nom!r} inconnu")
        return self.axes[nom]

    def valeur(self, axes: list[float], nom: str) -> float:
        a = self.axe(nom)
        if a.index >= len(axes):
            return 0.0
        return a.decoder(axes[a.index])


def _lire_axe(nom: str, d: dict) -> Axe:
    obligatoires = ("index", "centre", "min", "max", "zone_morte")
    manquantes = [c for c in obligatoires if c not in d]
    if manquantes:
        raise ConfigInvalide(f"axe {nom!r} : clés manquantes {manquantes}")
    return Axe(
        nom=nom,
        index=int(d["index"]),
        centre=float(d["centre"]),
        minimum=float(d["min"]),
        maximum=float(d["max"]),
        zone_morte=float(d["zone_morte"]),
        inverser=bool(d.get("inverser", False)),
    )


def charger(chemin: str | Path) -> Manette:
    chemin = Path(chemin)
    if not chemin.exists():
        raise ConfigInvalide(f"{chemin} absent : lancer joy_teleop/calibration.py")
    try:
        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as err:
        raise ConfigInvalide(f"{chemin} illisible : {err}") from err
    if not isinstance(donnees, dict):
        raise ConfigInvalide(f"{chemin} : la racine doit être un mapping")
    manquantes = [c for c in CLES_OBLIGATOIRES if c not in donnees]
    if manquantes:
        raise ConfigInvalide(f"{chemin} : clés obligatoires manquantes {manquantes}")
    version = donnees.get("schema")
    if version != SCHEMA_SUPPORTE:
        raise ConfigInvalide(
            f"{chemin} : schéma {version!r} non supporté (attendu {SCHEMA_SUPPORTE})")
    return Manette(donnees, chemin)
```

```bash
python3 -m pytest tests/test_manette_config.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : `8 passed`, `EXIT=0`.

Commit : `feat(joy): chargeur YAML de manette avec validation nommée`

---

### T4 — Découverte matérielle : capacités, LEDs, vibration (10 min)

**Test d'abord** — `tests/test_manette_materiel.py`, avec une arborescence sysfs
synthétique dans `tmp_path` (aucun matériel requis) :

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "joy_teleop"))

from manette_materiel import decoder_bitmap, leds_du_pad, vibration_supportee


def test_decoder_bitmap_trouve_les_codes():
    # 7ffb000000000000 sur le mot 5 = bits 304,305,307..319 (BTN_SOUTH..BTN_THUMBR)
    codes = decoder_bitmap("7ffb000000000000 0 0 0 0")
    assert 304 in codes and 305 in codes and 306 not in codes
    assert 316 in codes            # BTN_MODE = Home


def test_vibration_detectee(tmp_path):
    sysfs = tmp_path / "ff"
    sysfs.write_text("107030000 0")
    assert vibration_supportee(sysfs) is True


def test_vibration_absente(tmp_path):
    sysfs = tmp_path / "ff"
    sysfs.write_text("0")
    assert vibration_supportee(sysfs) is False


def test_leds_du_pad(tmp_path):
    base = tmp_path / "hid"
    (base / "leds" / "nintendo_player1").mkdir(parents=True)
    assert leds_du_pad(base) == [base / "leds" / "nintendo_player1"]
```

```bash
python3 -m pytest tests/test_manette_materiel.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu RED : module absent.

**Implémenter** `joy_teleop/manette_materiel.py` :

```python
"""Ce que le matériel expose réellement : capacités d'entrée, LEDs, vibration.

Aucune de ces fonctions ne suppose une capacité : elles lisent sysfs et rendent un
verdict, y compris « non disponible » avec la source consultée.
"""
from __future__ import annotations

from pathlib import Path

CHEMIN_JEUX = Path("/proc/bus/input/devices")
CHEMIN_INPUT = Path("/sys/class/input")


def decoder_bitmap(texte: str) -> list[int]:
    """Codes EV_* positionnés, à partir du format sysfs « mots 64 bits, MSB d'abord »."""
    mots = texte.split()
    codes: list[int] = []
    for rang, mot in enumerate(reversed(mots)):
        valeur = int(mot, 16)
        for bit in range(64):
            if valeur >> bit & 1:
                codes.append(rang * 64 + bit)
    return sorted(codes)


def chemin_sysfs(noeud: str, capacite: str) -> Path:
    return CHEMIN_INPUT / noeud / "device" / "capabilities" / capacite


def vibration_supportee(chemin_ff: Path) -> bool:
    """FF_RUMBLE = bit 0x50 (80). Présent = le noyau sait jouer un effet de vibration."""
    try:
        codes = decoder_bitmap(chemin_ff.read_text(encoding="utf-8"))
    except OSError:
        return False
    return 80 in codes


def leds_du_pad(base_hid: Path) -> list[Path]:
    """Entrées LED rattachées au périphérique HID donné (vide si le pilote n'en expose pas)."""
    dossier = base_hid / "leds"
    if not dossier.is_dir():
        return []
    return sorted(p for p in dossier.iterdir() if p.is_dir())


def nom_du_noeud(noeud: str) -> str:
    return (CHEMIN_INPUT / noeud / "device" / "name").read_text(encoding="utf-8").strip()
```

```bash
python3 -m pytest tests/test_manette_materiel.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : `4 passed`, `EXIT=0`.

Vérification réelle, **pad allumé et appairé** :

```bash
ls /sys/class/input/js*
cat /sys/class/input/js0/device/capabilities/key
cat /sys/class/input/js0/device/capabilities/ff
ls /sys/bus/hid/devices/*/leds 2>&1
```

Attendu : un couple `js0`/`js1`, un bitmap `key` non vide, un bitmap `ff` non vide
(le pad expose `FF_RUMBLE`). Pour `leds`, noter la sortie réelle : `No such file or
directory` **est un résultat** et deviendra `capacites.lumieres.disponible: false`
avec cette raison exacte.

Commit : `feat(joy): découverte des capacités matérielles du pad`

---

### T5 — Squelette de la calibration + écriture atomique (15 min)

**Test d'abord** — `tests/test_calibration.py` :

```python
import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "joy_teleop"))

from calibration import Calibration, EtatCapture


def test_refuse_ecriture_si_entree_declaree_non_traitee(tmp_path):
    cal = Calibration(sortie=tmp_path / "manette.yaml")
    cal.declarer_entree("A")
    cal.declarer_entree("home")
    cal.enregistrer_bouton("A", 1)          # home reste non traité
    with pytest.raises(RuntimeError) as err:
        cal.ecrire()
    assert "home" in str(err.value)


def test_ecriture_atomique(tmp_path):
    cal = Calibration(sortie=tmp_path / "manette.yaml")
    cal.declarer_entree("A")
    cal.enregistrer_bouton("A", 1)
    cal.ecrire()
    contenu = yaml.safe_load((tmp_path / "manette.yaml").read_text())
    assert contenu["boutons"]["A"] == 1
    assert contenu["schema"] == 1
    assert not (tmp_path / "manette.yaml.tmp").exists()


def test_alias_detecte():
    cal = Calibration(sortie=Path("/dev/null"))
    cal.declarer_entree("A")
    cal.declarer_entree("M1")
    cal.enregistrer_bouton("A", 1)
    cal.enregistrer_bouton("M1", 1)          # même code → alias, pas un doublon
    assert cal.donnees["aliases"]["M1"] == "A"
    assert "M1" not in cal.donnees["boutons"]
```

```bash
python3 -m pytest tests/test_calibration.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu RED : module absent.

**Implémenter** le squelette dans `joy_teleop/calibration.py` : dataclasses `EtatCapture`,
classe `Calibration` avec `declarer_entree`, `enregistrer_bouton`, `enregistrer_alias`,
`marquer_absent`, `enregistrer_axe`, `ecrire()` (tmp + `os.replace`), et un
`main()` qui n'implémente encore aucune phase (il affiche `procédure non encore
implémentée` et sort en code 2).

Règles portées par cette classe :

1. `ecrire()` refuse tant qu'une entrée déclarée n'est ni mesurée, ni aliasée, ni absente.
2. Un index déjà attribué à une autre entrée devient un alias — jamais un second bouton.
3. `genere_le`, `poste`, `outil`, `appareil` sont remplis par la classe, pas par l'appelant.
4. Aucune clé inventée : ce qui n'est pas mesuré n'existe pas dans le fichier.

```bash
python3 -m pytest tests/test_calibration.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : `3 passed`, `EXIT=0`.

Commit : `feat(joy): squelette de calibration avec écriture atomique`

---

### T6 — Phase « boutons » (20 min)

Ajouter à `joy_teleop/calibration.py` :

```python
ENTREES_DECLAREES = [
    ("A",  "le bouton A (à droite)"),
    ("B",  "le bouton B (en bas)"),
    ("X",  "le bouton X (en haut)"),
    ("Y",  "le bouton Y (à gauche)"),
    ("plus",  "le bouton +"),
    ("moins", "le bouton −"),
    ("home",  "le bouton Home (maison)"),
    ("T",  "le bouton T s'il existe, sinon appuyer sur A"),
    ("rond", "le bouton rond s'il existe"),
    ("light", "le bouton lumière s'il existe"),
    ("ZL", "la gâchette haute gauche (ZL)"),
    ("ZR", "la gâchette haute droite (ZR)"),
    ("L",  "la gâchette basse gauche (L)"),
    ("R",  "la gâchette basse droite (R)"),
    ("M1", "le bouton M1 (palette)"),
    ("M2", "le bouton M2 (palette)"),
    ("appui_stick_gauche", "un appui vertical sur le stick gauche"),
    ("appui_stick_droit",  "un appui vertical sur le stick droit"),
]


def capturer_appui(lecteur, delai_s: float = 25.0) -> int | None:
    """Attend une transition 0→1 et rend l'index. None si délai dépassé."""
    depart = time.monotonic()
    avant = list(lecteur.etat().boutons)
    while time.monotonic() - depart < delai_s:
        if not lecteur.lire(0.02):
            raise RuntimeError("manette déconnectée pendant la capture")
        apres = list(lecteur.etat().boutons)
        nouveaux = [i for i, v in enumerate(apres) if v and (i >= len(avant) or not avant[i])]
        if nouveaux:
            return nouveaux[0]
        avant = apres
    return None
```

Texte affiché pour chaque entrée, mot pour mot :

```
[12/18] Appuie sur : la gâchette haute droite (ZR)
        (25 s max, puis l'entrée sera notée « absente »)
```

Si l'index capturé est déjà connu : afficher `↳ même code que A (index 1) : enregistré
comme alias`, sans demander confirmation. Si l'entrée dépasse le délai : marquer
`absents` avec la raison `délai de 25 s dépassé sans événement`.

**Test** — ajouter à `tests/test_calibration.py` un faux lecteur :

```python
class FauxLecteur:
    def __init__(self, scenarios):
        self.scenarios = list(scenarios)
        self.index = 0

    def lire(self, attente=0.02):
        return True

    def etat(self):
        from js_lecteur import Etat
        if self.index < len(self.scenarios):
            appuis = self.scenarios[self.index]
        else:
            appuis = []
        self.index += 1
        boutons = [0] * 14
        for i in appuis:
            boutons[i] = 1
        return Etat(axes=[0.0] * 6, boutons=boutons, nb_axes_connus=6, nb_boutons_connus=14)


def test_phase_boutons_alias_et_absent(tmp_path):
    cal = Calibration(sortie=tmp_path / "m.yaml")
    lecteur = FauxLecteur([[1], [1], [11], [], [], [], []])
    cal.phase_boutons(lecteur, entrees_decrites=["A", "M1", "home"])
    assert cal.donnees["boutons"]["A"] == 1
    assert cal.donnees["aliases"]["M1"] == "A"
    assert cal.donnees["boutons"]["home"] == 11
```

```bash
python3 -m pytest tests/test_calibration.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : tous verts, dont le nouveau test.

Vérification réelle (pad allumé, ~3 min de manipulations) :

```bash
sudo systemctl stop clawbot-joy-teleop 2>/dev/null
python3 joy_teleop/calibration.py --seulement boutons --sortie /tmp/manette_boutons.yaml
cat /tmp/manette_boutons.yaml
```

Attendu : un `boutons:` avec 13 à 16 entrées, un `aliases:` non vide (M1/M2 très
probablement), un `absents:` qui liste au moins une des entrées `T`, `rond`, `light`.

Commit : `feat(joy): phase boutons de la calibration (alias et absents compris)`

---

### T7 — Phase « axes » : centre, débattement, zone morte, sens (20 min)

Deux sous-étapes par axe, chacune avec sa consigne exacte :

```
[axe stick gauche]
  1) Ne touche à rien pendant 2 s (mesure du repos et du bruit).
  2) Fais tourner le stick gauche d'un cercle complet, doucement, 5 s.
  3) Pousse le stick gauche à FOND À DROITE et maintiens 1 s.
  4) Pousse le stick gauche à FOND EN HAUT et maintiens 1 s.
```

Calculs, à écrire tels quels :

- `centre = moyenne(repos)`
- `bruit = écart_type(repos)`
- `zone_morte = max(0.08, 4 * bruit)` — plancher 0.08 comme la source actuelle
- `min`/`max` = extrêmes observés pendant le cercle
- `inverser` : pour un axe X, `True` si la valeur pendant « à droite » est
  **inférieure** au centre ; pour un axe Y, `True` si la valeur pendant « en haut »
  est **supérieure** au centre. C'est la seule façon d'obtenir un repère unique
  « positif = droite / haut » sans dépendre d'une convention de couche.

Test : même `FauxLecteur`, en simulant un repos à 0.02 et un débattement `[-0.99, 1.0]`.

```bash
python3 -m pytest tests/test_calibration.py -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : verts.

Vérification réelle :

```bash
python3 joy_teleop/calibration.py --seulement axes --sortie /tmp/manette_axes.yaml
cat /tmp/manette_axes.yaml
```

Attendu : six axes, `zone_morte` entre 0.08 et 0.2, `inverser: true` sur les trois
axes Y (`stick_gauche_y`, `stick_droit_y`, `croix_y`) **si et seulement si** les
signes mesurés aujourd'hui se confirment.

Commit : `feat(joy): phase axes avec centre, débattement et sens mesurés`

---

### T8 — Phase « gâchettes » : binaire ou analogique (10 min)

Consigne unique par gâchette :

```
Appuie PROGRESSIVEMENT à fond sur la gâchette L, puis relâche.
```

Mesure : si un axe bouge de plus de 0.2 pendant l'appui, la gâchette est
**analogique** → enregistrer un axe `gachette_l` avec min/max ; sinon elle est
**binaire** → enregistrer `type: binaire` dans une section `entrees_analogiques_absentes`.

Résultat attendu sur ce pad (à confirmer, pas à supposer) : aucune gâchette
analogique, donc YAML sans axe de gâchette et une ligne explicite dans `capacites`
(`gachettes_analogiques: false, raison: "aucun axe ne bouge pendant l'appui"`).

Test : `FauxLecteur` avec un axe qui bouge → `gachette_l` apparaît ; sans mouvement →
`capacites.gachettes_analogiques is False` + raison.

Commit : `feat(joy): typage binaire/analogique des gâchettes`

---

### T9 — Phase « IMU » (15 min)

Lecture de `js1` (déjà écarté par `lister_manettes`, donc jamais confondu avec le pad).

```
  1) Pose la manette à plat, immobile, 3 s (biais accéléromètre et gyroscope).
  2) Retourne la manette, écran vers le bas, immobile, 3 s (contrôle de l'échelle).
```

Calculs : `biais` = moyenne des 6 axes au repos ; `bruit` = écart-type ;
`gravite` = norme moyenne du vecteur accéléromètre ; contrôle : la composante
verticale doit changer de signe entre les deux poses, sinon écrire
`capacites.imu.verifie: false` avec la raison (pas d'invention).

Commit : `feat(joy): phase IMU (biais, bruit, contrôle de gravité)`

---

### T10 — Phase « actionneurs » : vibration et lumière (15 min)

- **Vibration** : `vibration_supportee()` sur `capabilities/ff`. Si vrai, lancer
  `fftest /dev/input/eventN` en sous-processus, faire jouer un effet rumble, puis
  demander : `As-tu senti la vibration ? [o/n]`. Enregistrer
  `capacites.vibration = {disponible: true, verifie: true|false, methode: "evdev EV_FF"}`.
  Si l'opérateur répond non, `verifie: false` et la raison — le bit noyau ne prouve
  pas que le moteur tourne.
- **Lumière** : `leds_du_pad(base_hid)`. Si vide →
  `capacites.lumieres = {disponible: false, raison: "aucune entrée /sys/class/leds rattachée au pad"}`.
  Si non vide → écrire `255` dans `brightness`, demander confirmation, restaurer `0`.
  Ne **jamais** écrire de rapport HID brut sur `hidraw0` : le pilote `hid-nintendo`
  possède le périphérique et un accès concurrent produit des erreurs silencieuses.

Commit : `feat(joy): phase actionneurs (vibration, LEDs) avec confirmation opérateur`

---

### T11 — CLI et garde-fous (10 min)

`joy_teleop/calibration.py`, arguments : `--sortie` (défaut
`/home/jetson/clawbot/config/manette.yaml`), `--seulement boutons,axes,imu,actionneurs`
(défaut : tout), `--duree-appui 25`, `--forcer`.

Garde-fous, dans cet ordre, avant toute ouverture de périphérique :

1. `systemctl is-active --quiet clawbot-joy-teleop` → refuser :
   `la téléopération tourne : elle commande les servos à chaque appui. sudo systemctl stop clawbot-joy-teleop, ou --forcer.`
   (Même discipline que `scripts/read_arm_angles.py` face au pilote.)
2. Aucun nœud `js` non inertiel → refuser en nommant la commande d'appairage.
3. Sortie existante → sauvegarde `manette.yaml.bak-<horodatage>` avant remplacement.

Test :

```bash
python3 joy_teleop/calibration.py --seulement axes --sortie /tmp/x.yaml ; echo "EXIT=$?"
```

Attendu si la téléop tourne : message ci-dessus, `EXIT=3`, aucun fichier créé.

Commit : `feat(joy): CLI de calibration et garde-fous de sûreté`

---

### T12 — Le teleop consomme le YAML (20 min)

Dans `joy_teleop/clawbot_joy_teleop.py` :

- supprimer les constantes `AX_*` et `BTN_*` (elles deviennent des noms logiques) ;
- ajouter le paramètre `manette_config` (défaut
  `/home/jetson/clawbot/config/manette.yaml`) ;
- instancier `self.manette = charger(config)` ; si `ConfigInvalide` → journaliser
  l'erreur et **quitter en code 1** (aucun mapping par défaut : un pad mal mappé vaut
  moins qu'un pad absent) ;
- remplacer les lectures : `self.manette.bouton("home")`, `self.manette.valeur(axes, "stick_gauche_y")`.

Les noms d'axes utilisés par le teleop : `stick_gauche_x`, `stick_gauche_y`,
`stick_droit_x`, `stick_droit_y`, `croix_x`, `croix_y`.
Les noms de boutons : `A`, `B`, `X`, `Y`, `plus`, `moins`, `home`, `ZL`, `ZR`, `L`, `R`.

Mettre à jour `tests/test_joy_teleop_mapping.py` : la fixture `Banc` instancie le nœud
avec `manette_config=str(FIXTURE)` ; les tests existants deviennent des tests de
traduction (mêmes attentes : stick droit en haut → `linear.x > 0`, etc.).

```bash
python3 -m pytest tests/ -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : `19 passed` environ, `EXIT=0`.

Vérification réelle :

```bash
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME; export PATH=/usr/bin:/bin:/usr/sbin:/sbin
export ROS_DOMAIN_ID=98; source /opt/ros/humble/setup.bash
ros2 launch joy_teleop/joy_teleop_launch.py manette_config:=config/manette.yaml
```

Attendu au journal :
`✅ ClawbotJoyTeleop ready — manette config/manette.yaml (057e:2009), 13 boutons, 6 axes`

Commit : `refactor(joy): le teleop lit config/manette.yaml, plus aucune constante`

---

### T13 — Lancement et unité systemd (10 min)

- `joy_teleop/joy_teleop_launch.py` : ajouter
  `DeclareLaunchArgument("manette_config", default_value="/home/jetson/clawbot/config/manette.yaml")`
  et le transmettre au teleop.
- `joy_teleop/joy_teleop_wait.sh` : transmettre aussi `manette_config:="$MANETTE_CONFIG"`.
- `services/clawbot-joy-teleop.service` : ajouter
  `Environment=MANETTE_CONFIG=/home/jetson/clawbot/config/manette.yaml`.

Vérification :

```bash
systemctl show clawbot-joy-teleop.service -p FragmentPath -p LoadState
```

Attendu : `LoadState=loaded` (le fichier étant lié par symlink, `FragmentPath` pointe
`/etc/systemd/system/clawbot-joy-teleop.service`).

Commit : `chore(joy): chemin du YAML transmis par le lancement et l'unité`

---

### T14 — Documentation OKF (20 min)

Selon la procédure de la skill `robot-knowledge-base` :

1. `01_Hardware/manette_pro_controller_bt.md` — identité mesurée (`057e:2009`, adresse,
   hidraw, deux nœuds d'entrée), tableau des entrées réellement observées, entrées
   absentes avec la commande qui l'établit, capacités (vibration, LEDs), pièges
   payés : `joycond` qui grabbe `event6`, `ATTRS{idVendor}` inopérant en Bluetooth,
   index SDL instable, SDL qui inverse les axes.
2. `02_Software/joy_teleop.md` — les quatre fichiers, le schéma du YAML, la commande de
   calibration, la commande de lancement, ce que le nœud publie.
3. Corriger sur place les trois pages qui déclarent `clawbot-joy-teleop.service`
   `active (running)` alors qu'elle n'était pas installée
   (`02_Software/systemd_robot_services.md`, `03_Operations/etat_noeuds_et_services.md`,
   `01_Hardware/inventaire_materiel.md`).

```bash
python3 /home/jetson/.hermes/skills/robotics/robot-knowledge-base/scripts/validate_okf.py
```

Attendu : `aucune erreur` et code de sortie 0.

Commit : `docs(okf): manette Bluetooth et joy_teleop, constats périmés corrigés`

---

## Validation globale

```bash
cd /home/jetson/clawbot
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME; export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
rm -rf joy_teleop/__pycache__
python3 -m pytest tests/ -q 2>/dev/null; echo "EXIT=$?"
```

Attendu : tous verts, `EXIT=0`.

Puis, **robot dégagé, opérateur présent**, la seule preuve qui compte :

```bash
python3 joy_teleop/calibration.py                  # une passe complète, ~4 min
export ROS_DOMAIN_ID=98
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
source /opt/ros/humble/setup.bash
ros2 launch joy_teleop/joy_teleop_launch.py
# Home, puis stick droit en haut / à droite / stick gauche à droite
ros2 topic echo /cmd_vel
```

Attendu : `linear.x > 0`, `linear.y < 0`, `angular.z < 0` sur les trois gestes.
Ensuite seulement, en domaine 28, avec le robot sur cales ou dégagé.

---

## Risques, compromis, questions ouvertes

1. **`T`, `rond`, `light` peuvent ne pas exister côté HID.** La procédure les
   enregistre comme absents avec la raison exacte. Ne pas les inventer pour « faire
   complet » : un bouton fantôme dans le YAML produit un mapping mort.
2. **M1/M2.** Mesuré aujourd'hui : mêmes codes que `A`/`B` sur le chemin SDL. Si
   `jsdev` les distingue, ils deviennent de vrais boutons ; sinon ils restent des
   alias. Leur programmation en macro se fait dans le firmware du pad (outil
   constructeur, souvent Windows/Android) — **pas** depuis Linux, sauf si le pad
   expose une interface de configuration, ce que rien n'indique.
3. **LEDs.** Aucune entrée `/sys/class/leds` observée. Écrire un rapport HID brut sur
   `hidraw0` est exclu (conflit avec `hid-nintendo`). La capacité sera
   `disponible: false` avec la source consultée — c'est un résultat, pas un échec.
4. **Vibration.** Le bit `FF_RUMBLE` est présent ; la confirmation auditive/tactile
   reste humaine. `verifie: false` est une valeur légitime.
5. **IMU.** `jsdev` normalise les valeurs : ce ne sont pas des m/s². Le YAML stocke
   biais, bruit et norme de gravité dans cette unité, et le dit.
6. **Le pad se met en veille** (constaté trois fois aujourd'hui). La calibration doit
   abandonner proprement sans écrire de fichier partiel, et le message doit rappeler
   qu'un appui sur le pad suffit à le réveiller.
7. **Décision à confirmer** : le YAML généré est-il versionné dans
   `config/manette.yaml` (recommandé : une calibration par robot, tracée en Git) ou
   laissé hors dépôt dans `~/.config/clawbot/` ?
8. **Décision à confirmer** : faut-il garder un `config/manette.yaml.example` dans le
   dépôt pour que les tests d'intégration tournent sur une machine sans pad (recommandé :
   oui, c'est ce que fait `tests/fixtures/manette_test.yaml`) ?
