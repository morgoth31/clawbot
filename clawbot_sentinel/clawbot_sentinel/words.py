"""Mots d'arrêt locaux et oui/non conditionnel — logique pure, sans ROS.

« stop », « arrête-toi », « halte » coupent toujours, hors réseau et hors S2 (priorité 0,5).
« oui » et « non » ne sont rendus que si l'appelant est en WAITING_CONFIRMATION : hors de cet
état, la phrase appartient à S2 (« non, l'autre tasse » ne doit pas annuler la tâche).
"""

from __future__ import annotations

import re
import unicodedata

STOP = "STOP"
OUI = "OUI"
NON = "NON"

JETONS_ARRET = {"stop", "halte", "arret"}
EXPRESSIONS_ARRET = ("arrete toi",)
JETONS_OUI = {"oui", "ouais"}
JETONS_NON = {"non"}


def normaliser(texte: str | None) -> str:
    """Minuscules, sans accents ni ponctuation, apostrophes et tirets en espaces."""
    decompose = unicodedata.normalize("NFD", texte or "")
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    remplace = (sans_accents.lower()
                .replace("-", " ").replace("'", " ").replace("’", " "))
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", remplace).split())


def intention(texte: str | None) -> str | None:
    """STOP, OUI, NON, ou None. L'arrêt prime sur tout le reste de la phrase."""
    phrase = normaliser(texte)
    if not phrase:
        return None
    jetons = phrase.split()
    if any(jeton in JETONS_ARRET for jeton in jetons) \
            or any(expression in phrase for expression in EXPRESSIONS_ARRET):
        return STOP
    if jetons[0] in JETONS_OUI:
        return OUI
    if jetons[0] in JETONS_NON:
        return NON
    return None
