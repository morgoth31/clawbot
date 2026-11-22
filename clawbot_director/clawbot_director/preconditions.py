"""Préconditions de mouvement — façade de compatibilité (P13).

La logique vit désormais dans `clawbot_common.preconditions` : l'exécutif (S2/P13) doit
vérifier la même enveloppe que le directeur (S1) avant un skill qui déplace la base, et
le skill `clawbot-dev-cycle` interdit de recopier un module d'un paquet à l'autre.

Ce module ne garde que les noms : `from clawbot_director import preconditions` continue
de fonctionner, y compris pour les tests et le nœud du directeur.
"""

from clawbot_common.preconditions import (  # noqa: F401
    CHEMIN_PAR_DEFAUT,
    CLEFS_ARM,
    CLEFS_RACINE,
    VARIABLE_ENV,
    EnveloppeBras,
    Preconditions,
    PreconditionsInvalides,
    charger,
    chemin_par_defaut,
    verifier,
    verifier_bras,
)

__all__ = [
    "CHEMIN_PAR_DEFAUT",
    "CLEFS_ARM",
    "CLEFS_RACINE",
    "VARIABLE_ENV",
    "EnveloppeBras",
    "Preconditions",
    "PreconditionsInvalides",
    "charger",
    "chemin_par_defaut",
    "verifier",
    "verifier_bras",
]
