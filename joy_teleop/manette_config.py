"""Configuration de manette : chargement, validation, décodage d'axes.

Une erreur de configuration ne doit jamais produire un mapping silencieusement faux :
chaque refus nomme la clé fautive et le fichier concerné. Le fichier est produit par
`joy_teleop/calibration.py`, jamais écrit à la main.
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
        """Ramène une valeur brute dans [-1, 1], positif = droite ou haut.

        L'inversion vient de la mesure : sur ce pad, la source jsdev donne un axe Y
        négatif vers le haut. La configuration stocke le sens observé, pas une
        convention supposée.
        """
        if valeur_brute is None or (isinstance(valeur_brute, float) and math.isnan(valeur_brute)):
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
    """Accès sémantique à la configuration : `bouton("home")`, `valeur(axes, "…")`."""

    def __init__(self, donnees: dict, chemin: Path):
        self.donnees = donnees
        self.chemin = chemin
        self.appareil = donnees.get("appareil") or {}
        self.boutons = {str(k): int(v) for k, v in (donnees.get("boutons") or {}).items()}
        self.aliases = {str(k): str(v) for k, v in (donnees.get("aliases") or {}).items()}
        self.absents = [str(x) for x in (donnees.get("absents") or [])]
        self.axes = {str(nom): _lire_axe(str(nom), d) for nom, d in donnees["axes"].items()}
        self.imu = donnees.get("imu") or {}
        self.capacites = donnees.get("capacites") or {}

    def verifier_appareil(self, nb_axes: int, nb_boutons: int) -> None:
        """Refuse de piloter si le pad ne présente pas la même forme qu'à la calibration.

        Une manette à commutateur de mode change de descripteur HID : mêmes codes
        numériques, boutons différents. Sans ce contrôle, un changement de mode
        produit un pilotage faux sans le moindre message.
        """
        attendu_axes = self.appareil.get("nb_axes")
        attendu_boutons = self.appareil.get("nb_boutons")
        if attendu_axes and int(attendu_axes) != int(nb_axes):
            raise ConfigInvalide(
                f"{self.chemin} : le pad expose {nb_axes} axes, la calibration en "
                f"décrit {attendu_axes} — mode changé, recalibrer")
        if attendu_boutons and int(attendu_boutons) != int(nb_boutons):
            raise ConfigInvalide(
                f"{self.chemin} : le pad expose {nb_boutons} boutons, la calibration "
                f"en décrit {attendu_boutons} — mode changé, recalibrer")

    def bouton(self, nom: str) -> int:
        if nom in self.boutons:
            return self.boutons[nom]
        if nom in self.aliases:
            cible = self.aliases[nom]
            if cible in self.boutons:
                return self.boutons[cible]
            raise ConfigInvalide(
                f"{self.chemin} : alias {nom!r} → {cible!r}, mais {cible!r} n'est pas "
                f"dans « boutons »")
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
    if abs(float(d["max"]) - float(d["min"])) < 0.5:
        raise ConfigInvalide(
            f"axe {nom!r} : débattement {float(d['max']) - float(d['min']):.2f} "
            f"(min {d['min']}, max {d['max']}) — axe jamais balayé, refaire la calibration")
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
        raise ConfigInvalide(
            f"{chemin} absent : lancer joy_teleop/calibration.py pour le produire")
    try:
        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as err:
        raise ConfigInvalide(f"{chemin} illisible : {err}") from err
    if not isinstance(donnees, dict):
        raise ConfigInvalide(f"{chemin} : la racine doit être un mapping")
    # Le schéma est validé avant les clés : un format inconnu ne doit pas être
    # interprété avec les règles d'une autre version.
    version = donnees.get("schema")
    if version != SCHEMA_SUPPORTE:
        raise ConfigInvalide(
            f"{chemin} : schéma {version!r} non supporté (attendu {SCHEMA_SUPPORTE})")
    manquantes = [c for c in CLES_OBLIGATOIRES if c not in donnees]
    if manquantes:
        raise ConfigInvalide(f"{chemin} : clés obligatoires manquantes {manquantes}")
    return Manette(donnees, chemin)
