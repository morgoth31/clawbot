"""Catalogue de waypoints : la seule surface où un nom devient une pose.

Trois règles, et rien d'autre dans ce module :

  1. **Énumération fermée.** Un waypoint existe parce qu'il est écrit dans `config/waypoints.yaml`,
     pas parce que S2 l'a nommé. Toute autre chaîne est refusée avec la liste des noms praticables.
  2. **Aucune coordonnée libre.** `resoudre()` n'accepte qu'une chaîne figurant au catalogue ; un
     couple (x, y), une liste, un nombre ou une chaîne « 1.0,2.0 » sont refusés explicitement.
  3. **Un catalogue malformé échoue au chargement.** Doublon de nom, valeur non finie, clé
     inconnue, waypoint hors bornes : tout est refusé avant qu'une tâche puisse démarrer, parce
     qu'une faute de frappe dans un YAML ne doit pas devenir un déplacement.

La cohérence géométrique du catalogue avec la carte (cellule libre, dégagement, connexité) est
vérifiée par les tests, pas ici : ce module ne lit pas la carte, il ne fait que porter les noms.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

NOM_VALIDE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
CLEFS_WAYPOINT = frozenset({"x", "y", "yaw", "description"})
COORDONNEE_MAX_M = 100.0
CHEMIN_PAR_DEFAUT = Path("/home/jetson/clawbot/config/waypoints.yaml")
VARIABLE_ENV = "CLAWBOT_WAYPOINTS"


class CatalogueInvalide(ValueError):
    """Le catalogue ne peut pas être chargé : rien ne doit démarrer avec un catalogue douteux."""


class WaypointInconnu(ValueError):
    """Nom absent de l'énumération fermée."""


class WaypointInvalide(ValueError):
    """Ce n'est pas un nom de waypoint (coordonnées libres, type inattendu, chaîne vide)."""


@dataclass(frozen=True)
class Waypoint:
    nom: str
    x: float
    y: float
    yaw: float = 0.0


@dataclass(frozen=True)
class Catalogue:
    frame: str
    carte: str
    waypoints: dict[str, Waypoint] = field(default_factory=dict)
    chemin: str = ""

    def resoudre(self, nom: object) -> Waypoint:
        """Pose du waypoint nommé. Refuse tout ce qui n'est pas un nom du catalogue."""
        if not isinstance(nom, str):
            raise WaypointInvalide(
                f"nom de waypoint attendu (chaine), recu {type(nom).__name__} : "
                f"les coordonnees libres sont refusees, voir {self.liste()}")
        nettoye = nom.strip()
        if not nettoye:
            raise WaypointInvalide("nom de waypoint vide")
        if nettoye in self.waypoints:
            return self.waypoints[nettoye]
        if re.search(r"\d\s*[,;]\s*-?\d", nettoye):
            raise WaypointInvalide(
                f"{nettoye!r} ressemble a des coordonnees : S2 nomme un waypoint, "
                f"il ne fournit pas de pose. Connus : {self.liste()}")
        raise WaypointInconnu(f"waypoint inconnu : {nettoye!r}. Connus : {self.liste()}")

    def liste(self) -> str:
        return ", ".join(sorted(self.waypoints))


_CACHE: dict[str, Catalogue] = {}


def chemin_par_defaut() -> Path:
    """Ordre : variable d'environnement, puis le dépôt, puis le voisinage du paquet."""
    impose = os.environ.get(VARIABLE_ENV)
    if impose:
        return Path(impose).expanduser()
    if CHEMIN_PAR_DEFAUT.is_file():
        return CHEMIN_PAR_DEFAUT
    return Path(__file__).resolve().parents[2] / "config" / "waypoints.yaml"


class _ChargeurSansDoublons(yaml.SafeLoader):
    """PyYAML accepte silencieusement un doublon de clé : ici c'est une faute, pas un écrasement."""


def _mapping_sans_doublons(chargeur, noeud, deep=False):
    resultat = {}
    for cle_noeud, valeur_noeud in noeud.value:
        cle = chargeur.construct_object(cle_noeud, deep=deep)
        if cle in resultat:
            raise CatalogueInvalide(f"doublon de cle dans le catalogue : {cle!r}")
        resultat[cle] = chargeur.construct_object(valeur_noeud, deep=deep)
    return resultat


_ChargeurSansDoublons.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping_sans_doublons)


def _nombre(valeur, champ: str, nom: str) -> float:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise CatalogueInvalide(f"{nom}.{champ} doit etre un nombre, recu {valeur!r}")
    resultat = float(valeur)
    if not math.isfinite(resultat):
        raise CatalogueInvalide(f"{nom}.{champ} doit etre fini, recu {valeur!r}")
    if abs(resultat) > COORDONNEE_MAX_M:
        raise CatalogueInvalide(
            f"{nom}.{champ} hors bornes (|valeur| <= {COORDONNEE_MAX_M:g} m) : {resultat}")
    return resultat


def charger(chemin: str | Path | None = None) -> Catalogue:
    """Charge et valide le catalogue ; lève CatalogueInvalide si quoi que ce soit cloche."""
    fichier = Path(chemin).expanduser() if chemin is not None else chemin_par_defaut()
    cle_cache = str(fichier)
    if cle_cache in _CACHE:
        return _CACHE[cle_cache]

    if not fichier.is_file():
        raise CatalogueInvalide(f"catalogue de waypoints absent : {fichier}")
    try:
        contenu = yaml.load(fichier.read_text(encoding="utf-8"), Loader=_ChargeurSansDoublons)
    except CatalogueInvalide:
        raise
    except yaml.YAMLError as exc:
        raise CatalogueInvalide(f"YAML invalide dans {fichier} : {exc}") from exc

    if not isinstance(contenu, dict):
        raise CatalogueInvalide(f"objet YAML attendu a la racine de {fichier}")

    frame = contenu.get("frame")
    if not isinstance(frame, str) or not frame.strip() or any(c.isspace() for c in frame):
        raise CatalogueInvalide(f"frame attendu (chaine sans espace), recu {frame!r}")

    carte = contenu.get("carte") or "inconnue"
    if not isinstance(carte, str):
        raise CatalogueInvalide(f"carte doit etre une chaine, recu {carte!r}")

    brut = contenu.get("waypoints")
    if not isinstance(brut, dict) or not brut:
        raise CatalogueInvalide(
            f"waypoints doit etre un objet non vide dans {fichier} : sans waypoint, "
            "navigate_to n'a aucune cible")

    waypoints: dict[str, Waypoint] = {}
    for nom, definition in brut.items():
        if not isinstance(nom, str) or not NOM_VALIDE.match(nom):
            raise CatalogueInvalide(
                f"nom de waypoint invalide : {nom!r} (minuscules, chiffres, _ ; 32 caracteres max)")
        if not isinstance(definition, dict):
            raise CatalogueInvalide(f"{nom} doit etre un objet avec x et y")
        inconnues = set(definition) - CLEFS_WAYPOINT
        if inconnues:
            raise CatalogueInvalide(f"{nom} : cle inconnue {sorted(inconnues)} "
                                    f"(attendu : {sorted(CLEFS_WAYPOINT)})")
        if "x" not in definition or "y" not in definition:
            raise CatalogueInvalide(f"{nom} : x et y sont obligatoires")
        waypoints[nom] = Waypoint(
            nom=nom,
            x=_nombre(definition["x"], "x", nom),
            y=_nombre(definition["y"], "y", nom),
            yaw=_nombre(definition.get("yaw", 0.0), "yaw", nom),
        )

    catalogue = Catalogue(frame=frame, carte=carte, waypoints=waypoints,
                           chemin=str(fichier))
    _CACHE[cle_cache] = catalogue
    return catalogue
