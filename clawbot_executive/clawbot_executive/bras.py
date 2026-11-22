"""Poses nommées du bras et surveillance du retour servo (P13, REQ-ARM-003/005/006).

Ce module ne dépend pas de ROS : la liste blanche des poses, la conversion
degrés de servo -> radians d'articulation et la détection d'un retour servo invalide
sont des fonctions pures, testables sans robot.

Unités. L'opérateur valide des angles de servo (ce qu'il lit sur
`/arm/servo_angles`) ; l'action `FollowJointTrajectory` attend des radians
d'articulation. La conversion est celle du contrôleur
(`clawbot_arm_controller.servo_mapping`), jamais une seconde formule recopiée : deux
conversions divergentes commanderaient deux positions différentes pour la même pose.

Liste blanche. Une pose n'est commandable que si elle porte `validated_by` et
`validated_at`. Les propositions vivent dans une section distincte, informative,
que ce module ne lit jamais.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from clawbot_arm_controller.servo_mapping import default_arm_specs, default_gripper_spec

CHEMIN_PAR_DEFAUT = Path("/home/jetson/clawbot/config/arm_poses.yaml")
VARIABLE_ENV = "CLAWBOT_ARM_POSES"
JOINTS = ("arm_joint1", "arm_joint2", "arm_joint3", "arm_joint4", "arm_joint5", "grip_joint")
SERVO_MAX = (180.0, 180.0, 180.0, 180.0, 270.0, 180.0)   # plage matérielle par servo
SEUIL_SERVO_INVALIDE_S = 0.5
AGE_MESURE_MAX_S = 1.0


class PosesInvalides(ValueError):
    """Liste de poses inutilisable : on refuse de démarrer plutôt que de deviner."""


@dataclass(frozen=True)
class Issue:
    """Résultat d'une trajectoire, indépendant des constantes de `skills`."""

    ok: bool
    error_code: str = ""
    message: str = ""


@dataclass(frozen=True)
class Pose:
    """Pose validée : six angles de servo, une tolérance par servo."""

    nom: str
    servo_deg: tuple[float, ...]
    tolerance_deg: tuple[float, ...]
    valide_par_operateur: bool = False
    valide_le: str = ""
    description: str = ""

    def positions_rad(self) -> list[float]:
        """Les six positions d'articulation, dans l'ordre des servos."""
        specs = default_arm_specs() + [default_gripper_spec()]
        return [spec.to_joint_rad(deg) for spec, deg in zip(specs, self.servo_deg)]

    def positions_arm_rad(self) -> list[float]:
        return self.positions_rad()[:5]

    def position_pince_rad(self) -> float:
        return self.positions_rad()[5]

    def mesure_conforme(self, angles, age_s=None, age_max_s: float = AGE_MESURE_MAX_S,
                        servos=None) -> tuple[bool, str]:
        """La mesure `/arm/servo_angles` est-elle cette pose, à la tolérance près ?

        `servos` restreint la vérification à certains servos (0-based) : la pince ne
        juge que le servo 6, les cinq axes du bras restant où ils sont.
        """
        if angles is None:
            return False, "bras inconnu : aucun message sur /arm/servo_angles"
        if age_s is not None and age_s > age_max_s:
            return False, (f"mesure de bras périmée : {age_s:.1f} s sans message "
                           f"(limite {age_max_s:g} s)")
        if len(angles) < len(self.servo_deg):
            return False, (f"angles incomplets : {len(angles)} valeurs pour "
                           f"{len(self.servo_deg)} servos")
        indices = range(len(self.servo_deg)) if servos is None else servos
        for index in indices:
            mesure, cible, tolerance = angles[index], self.servo_deg[index], \
                self.tolerance_deg[index]
            if abs(float(mesure) - cible) > tolerance:
                return False, (f"servo {index + 1} à {int(mesure)}°, attendu "
                               f"{cible:g}±{tolerance:g}°")
        return True, ""


@dataclass(frozen=True)
class Pince:
    """Butées de la pince, en degrés de servo (0 ouvert, 180 fermé)."""

    ouvert_deg: float
    ferme_deg: float

    def cible_rad(self, action: str) -> float:
        deg = {"open": self.ouvert_deg, "close": self.ferme_deg}.get(action)
        if deg is None:
            raise PosesInvalides(f"action de pince inconnue : {action!r}")
        return default_gripper_spec().to_joint_rad(deg)


@dataclass(frozen=True)
class Poses:
    joints: tuple[str, ...]
    poses: dict[str, Pose]
    propositions: dict[str, dict]
    pince: Pince
    chemin: str = ""
    _document: dict | None = None

    def source_brute(self) -> dict:
        """Document YAML d'origine (copie) : sert à vérifier qu'une pose non validée est refusée."""
        import copy

        return copy.deepcopy(self._document or {})


def chemin_par_defaut() -> Path:
    impose = os.environ.get(VARIABLE_ENV)
    if impose:
        return Path(impose).expanduser()
    if CHEMIN_PAR_DEFAUT.is_file():
        return CHEMIN_PAR_DEFAUT
    return Path(__file__).resolve().parents[2] / "config" / "arm_poses.yaml"


def _nombre(valeur, champ: str) -> float:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise PosesInvalides(f"{champ} doit être un nombre, reçu {valeur!r}")
    resultat = float(valeur)
    if not math.isfinite(resultat):
        raise PosesInvalides(f"{champ} doit être fini, reçu {valeur!r}")
    return resultat


def depuis_document(document: dict, chemin: str = "") -> Poses:
    """Valide un document YAML de poses ; lève `PosesInvalides` au premier défaut."""
    if not isinstance(document, dict):
        raise PosesInvalides("objet YAML attendu à la racine")
    joints = document.get("joints")
    if list(joints or []) != list(JOINTS):
        raise PosesInvalides(f"joints attendus {list(JOINTS)}, reçu {joints!r}")

    brut = document.get("poses")
    if not isinstance(brut, dict) or not brut:
        raise PosesInvalides("section `poses` absente ou vide : aucune pose commandable")

    poses: dict[str, Pose] = {}
    for nom, entree in brut.items():
        if not isinstance(entree, dict):
            raise PosesInvalides(f"{nom} : entrée non conforme")
        deg = entree.get("servo_deg")
        if not isinstance(deg, list) or len(deg) != len(JOINTS):
            raise PosesInvalides(f"{nom} : servo_deg doit contenir {len(JOINTS)} valeurs")
        valeurs = tuple(_nombre(v, f"{nom}.servo_deg") for v in deg)
        for index, (valeur, plafond) in enumerate(zip(valeurs, SERVO_MAX)):
            if not 0.0 <= valeur <= plafond:
                raise PosesInvalides(
                    f"{nom} : servo {index + 1} à {valeur:g}°, hors de [0, {plafond:g}]")

        tolerance = entree.get("tolerance_deg")
        if not isinstance(tolerance, list) or len(tolerance) != len(JOINTS):
            raise PosesInvalides(f"{nom} : tolerance_deg doit contenir {len(JOINTS)} valeurs")
        marges = tuple(_nombre(v, f"{nom}.tolerance_deg") for v in tolerance)
        if any(marge <= 0 for marge in marges):
            raise PosesInvalides(f"{nom} : tolerance_deg doit être strictement positif")

        valide_par = entree.get("validated_by")
        valide_le = entree.get("validated_at")
        if not isinstance(valide_par, str) or not valide_par.strip():
            raise PosesInvalides(
                f"{nom} : pose sans `validated_by` — l'opérateur ne l'a pas validée sur le "
                "robot, elle n'est pas commandable (la mettre dans `propositions`)")
        if not isinstance(valide_le, str) or not valide_le.strip():
            raise PosesInvalides(f"{nom} : pose sans `validated_at`")

        poses[nom] = Pose(
            nom=nom, servo_deg=valeurs, tolerance_deg=marges,
            valide_par_operateur=True, valide_le=valide_le.strip(),
            description=str(entree.get("description") or "").strip(),
        )

    pince_brute = document.get("pince")
    if not isinstance(pince_brute, dict):
        raise PosesInvalides("section `pince` absente")
    ouvert = _nombre((pince_brute.get("ouvert") or {}).get("servo_deg"),
                     "pince.ouvert.servo_deg")
    ferme = _nombre((pince_brute.get("ferme") or {}).get("servo_deg"),
                    "pince.ferme.servo_deg")

    return Poses(
        joints=tuple(JOINTS), poses=poses,
        propositions=dict(document.get("propositions") or {}),
        pince=Pince(ouvert_deg=ouvert, ferme_deg=ferme),
        chemin=chemin,
        _document=document,
    )


def charger(chemin: str | Path | None = None) -> Poses:
    fichier = Path(chemin).expanduser() if chemin is not None else chemin_par_defaut()
    if not fichier.is_file():
        raise PosesInvalides(f"poses absentes : {fichier}")
    try:
        document = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PosesInvalides(f"YAML invalide dans {fichier} : {exc}") from exc
    return depuis_document(document, chemin=str(fichier))


# ── retour servo ─────────────────────────────────────────────────────────────

def retour_servo_invalide(angles) -> int | None:
    """Index du premier servo muet (`-1`) ou hors [0, 270], sinon None."""
    if angles is None:
        return None
    for index, valeur in enumerate(angles):
        try:
            entier = int(valeur)
        except (TypeError, ValueError):
            return index
        if entier < 0 or entier > 270:
            return index
    return None


def surveillance_servo(source, maintenant=None, seuil_s: float = SEUIL_SERVO_INVALIDE_S
                       ) -> str | None:
    """Code d'erreur si un servo ne répond plus depuis plus de `seuil_s`.

    `source` est un état exposant `duree_invalide(maintenant)` (voir `Etats`).
    """
    duree = source.duree_invalide(maintenant)
    if duree is not None and duree > seuil_s:
        return "SERVO_NO_FEEDBACK"
    return None


def contraintes_articulaires(pose: Pose) -> list[tuple[str, float, float]]:
    """Contraintes MoveIt d'une pose : (articulation, position rad, tolérance rad).

    MoveIt ne connaît pas les degrés de servo : la pose validée est convertie une
    seule fois, ici, par la table du contrôleur. La tolérance est celle que
    l'opérateur a validée, convertie de la même façon.
    """
    radians = pose.positions_arm_rad()
    tolerances = [math.radians(marge) for marge in pose.tolerance_deg[:5]]
    return list(zip(JOINTS[:5], radians, tolerances))
