"""Contrôle du contrat `DirectorCommand` à la frontière du directeur (REQ-ARCH-014).

Fonction pure, sans ROS : le nœud l'appelle depuis `commande()`, les tests
l'exercent seule. En mode `warn`, la requête suit son cours et l'écart part au
journal ; en mode `enforce`, elle est refusée avant tout traitement.
"""
from __future__ import annotations

import json

from clawbot_common.validation import validate

MODE_WARN = "warn"
MODE_ENFORCE = "enforce"
MODES = (MODE_WARN, MODE_ENFORCE)
TRONCATURE_JOURNAL = 500


def controler(demande, mode: str = MODE_WARN) -> tuple[list[str], dict | None]:
    """(erreurs de contrat, réponse de refus).

    Le refus n'est produit qu'en `enforce` : c'est la seule différence de
    comportement autorisée par le prompt.
    """
    if mode not in MODES:
        raise ValueError(f"mode de validation inconnu : {mode!r} (attendu {MODES})")

    erreurs = validate(demande, "director_command")
    if not erreurs:
        return [], None
    if mode == MODE_ENFORCE:
        return erreurs, {"ok": False, "error_code": "INVALID_PARAMS",
                         "message": " ; ".join(erreurs)}
    return erreurs, None


def extrait_pour_journal(texte: str) -> str:
    """Le JSON reçu, tronqué : un journal ne doit pas avaler un mégaoctet."""
    return texte[:TRONCATURE_JOURNAL]


def resume_journal(demande, erreurs: list[str]) -> str:
    try:
        texte = json.dumps(demande, ensure_ascii=False)
    except (TypeError, ValueError):
        texte = repr(demande)
    return (f"contrat DirectorCommand : {' ; '.join(erreurs)}"
            f" — reçu {extrait_pour_journal(texte)}")
