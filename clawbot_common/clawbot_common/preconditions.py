"""Préconditions de mouvement : ce que S1 exige avant de déplacer la base.

La règle de la spec est courte — « préconditions vérifiées par S1, S2 n'est jamais cru » — et elle a
une conséquence concrète : avant un déplacement, le bras doit être replié. Nav2 ne voit le bras que
par un rayon d'encombrement de 0,16 m ; un bras en extension est donc invisible dans son costmap.

Deux principes, appris des autres garde-fous de ce robot :

  - **le silence n'est pas un feu vert** : des angles jamais reçus ou périmés valent refus ;
  - **le refus nomme le servo fautif** : « bras non replié » ne se corrige pas, « servo 2 à 120°
    hors bande [87, 107] » si.

L'enveloppe est en degrés de servo, telle que publiée par `/arm/servo_angles`, et vit dans
`config/preconditions.yaml` : la changer est un acte explicite, pas un réglage de confort.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CHEMIN_PAR_DEFAUT = Path("/home/jetson/clawbot/config/preconditions.yaml")
VARIABLE_ENV = "CLAWBOT_PRECONDITIONS"
CLEFS_RACINE = frozenset({"arm", "skills_exigeant_bras_replie"})
CLEFS_ARM = frozenset({"source", "max_age_s", "joints", "reference_deg", "tolerance_deg",
                       "mesure_le", "valide_par_operateur"})


class PreconditionsInvalides(ValueError):
    """Configuration de préconditions inutilisable : on refuse de démarrer plutôt que de deviner."""


@dataclass(frozen=True)
class EnveloppeBras:
    source: str
    max_age_s: float
    joints: tuple[int, ...]
    reference_deg: tuple[float, ...]
    tolerance_deg: tuple[float, ...]
    mesure_le: str = ""
    valide_par_operateur: bool = False

    def bornes(self, index: int) -> tuple[float, float]:
        """Bande admissible, en degrés de servo, pour le servo d'index donné (0-based)."""
        centre = self.reference_deg[index]
        marge = self.tolerance_deg[index]
        return centre - marge, centre + marge


@dataclass(frozen=True)
class Preconditions:
    arm: EnveloppeBras
    skills_exigeant_bras_replie: frozenset[str] = field(default_factory=frozenset)
    chemin: str = ""

    def exige_bras_replie(self, skill: str) -> bool:
        return skill in self.skills_exigeant_bras_replie


def _nombre(valeur, champ: str) -> float:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise PreconditionsInvalides(f"{champ} doit etre un nombre, recu {valeur!r}")
    resultat = float(valeur)
    if not math.isfinite(resultat):
        raise PreconditionsInvalides(f"{champ} doit etre fini, recu {valeur!r}")
    return resultat


_CACHE: dict[str, Preconditions] = {}


def chemin_par_defaut() -> Path:
    impose = os.environ.get(VARIABLE_ENV)
    if impose:
        return Path(impose).expanduser()
    if CHEMIN_PAR_DEFAUT.is_file():
        return CHEMIN_PAR_DEFAUT
    return Path(__file__).resolve().parents[2] / "config" / "preconditions.yaml"


def charger(chemin: str | Path | None = None) -> Preconditions:
    fichier = Path(chemin).expanduser() if chemin is not None else chemin_par_defaut()
    cle = str(fichier)
    if cle in _CACHE:
        return _CACHE[cle]

    if not fichier.is_file():
        raise PreconditionsInvalides(f"preconditions absentes : {fichier}")
    try:
        contenu = yaml.safe_load(fichier.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PreconditionsInvalides(f"YAML invalide dans {fichier} : {exc}") from exc
    if not isinstance(contenu, dict):
        raise PreconditionsInvalides(f"objet YAML attendu a la racine de {fichier}")
    inconnues = set(contenu) - CLEFS_RACINE
    if inconnues:
        raise PreconditionsInvalides(f"cle inconnue a la racine : {sorted(inconnues)}")

    arm_brut = contenu.get("arm")
    if not isinstance(arm_brut, dict):
        raise PreconditionsInvalides("bloc `arm` attendu")
    inconnues = set(arm_brut) - CLEFS_ARM
    if inconnues:
        raise PreconditionsInvalides(f"arm : cle inconnue {sorted(inconnues)}")

    joints = arm_brut.get("joints")
    reference = arm_brut.get("reference_deg")
    tolerance = arm_brut.get("tolerance_deg")
    for nom, valeur in (("joints", joints), ("reference_deg", reference),
                        ("tolerance_deg", tolerance)):
        if not isinstance(valeur, list) or not valeur:
            raise PreconditionsInvalides(f"arm.{nom} doit etre une liste non vide")
        if len(valeur) != len(joints):
            raise PreconditionsInvalides(
                f"arm.{nom} doit contenir {len(joints)} valeurs, comme arm.joints")
    for joint in joints:
        if not isinstance(joint, int) or not 1 <= joint <= 6:
            raise PreconditionsInvalides(f"arm.joints : numero de servo invalide {joint!r}")

    marges = tuple(_nombre(v, "arm.tolerance_deg") for v in tolerance)
    if any(marge <= 0 for marge in marges):
        raise PreconditionsInvalides("arm.tolerance_deg doit etre strictement positif")

    source = arm_brut.get("source") or "/arm/servo_angles"
    if not isinstance(source, str) or not source.startswith("/"):
        raise PreconditionsInvalides(f"arm.source doit etre un topic absolu, recu {source!r}")

    age = _nombre(arm_brut.get("max_age_s", 1.0), "arm.max_age_s")
    if not 0.1 <= age <= 10.0:
        raise PreconditionsInvalides(f"arm.max_age_s hors bornes [0.1, 10] : {age}")

    skills = contenu.get("skills_exigeant_bras_replie")
    if not isinstance(skills, list) or not skills:
        raise PreconditionsInvalides("skills_exigeant_bras_replie doit etre une liste non vide")
    for skill in skills:
        if not isinstance(skill, str) or not skill.strip():
            raise PreconditionsInvalides(f"nom de skill invalide : {skill!r}")

    resultat = Preconditions(
        arm=EnveloppeBras(
            source=source,
            max_age_s=age,
            joints=tuple(int(j) for j in joints),
            reference_deg=tuple(_nombre(v, "arm.reference_deg") for v in reference),
            tolerance_deg=marges,
            mesure_le=str(arm_brut.get("mesure_le") or ""),
            valide_par_operateur=bool(arm_brut.get("valide_par_operateur", False)),
        ),
        skills_exigeant_bras_replie=frozenset(skill.strip() for skill in skills),
        chemin=str(fichier),
    )
    _CACHE[cle] = resultat
    return resultat


def verifier_bras(angles, age_s, preconditions: Preconditions) -> tuple[bool, str]:
    """Le bras est-il dans l'enveloppe de repos, et cette mesure est-elle fraîche ?

    Args:
        angles: six valeurs de servo (`/arm/servo_angles`), ou None si rien n'a été reçu.
        age_s: âge de la mesure en secondes, ou None.
        preconditions: enveloppe chargée.

    Returns:
        (ok, raison) — `raison` est vide quand tout va bien.
    """
    enveloppe = preconditions.arm
    if angles is None or age_s is None:
        return False, (f"bras inconnu : aucun message recu sur {enveloppe.source} "
                       "(un bras inconnu n'est pas un bras replie)")
    if age_s > enveloppe.max_age_s:
        return False, (f"angles de bras perimes : {age_s:.1f} s sans message sur "
                       f"{enveloppe.source} (limite {enveloppe.max_age_s:g} s)")
    try:
        valeurs = [int(v) for v in angles]
    except (TypeError, ValueError):
        return False, f"angles de bras illisibles : {angles!r}"
    if len(valeurs) < max(enveloppe.joints):
        return False, (f"angles de bras incomplets : {len(valeurs)} valeurs pour "
                       f"les servos {list(enveloppe.joints)}")

    for index, numero in enumerate(enveloppe.joints):
        bas, haut = enveloppe.bornes(index)
        mesure = valeurs[numero - 1]
        if not bas <= mesure <= haut:
            return False, (f"bras non replie : servo {numero} a {mesure} degres, hors de "
                           f"l'enveloppe [{bas:g}, {haut:g}] (repli attendu puis nouvel essai)")
    return True, ""


def verifier(skill: str, angles, age_s, preconditions: Preconditions) -> tuple[bool, str]:
    """Précondition applicable au skill demandé ; les skills non concernés passent."""
    if not preconditions.exige_bras_replie(skill):
        return True, ""
    return verifier_bras(angles, age_s, preconditions)
