"""Rend le paquet importable depuis le dépôt (pitfall « paquet régulier vs namespace »).

`<dépôt>` est sur `sys.path` (rootdir pytest) et `<dépôt>/clawbot_capabilities` n'a pas
d'`__init__.py` : c'est un paquet-espace de noms, si bien que `clawbot_capabilities.controleur`
ne résout pas. On insère le **parent du paquet**, qui contient le vrai paquet régulier.
"""
import sys
from pathlib import Path

PARENT = Path(__file__).resolve().parent.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))
