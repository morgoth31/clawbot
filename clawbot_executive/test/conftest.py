"""Rend le paquet importable depuis le dépôt (même pitfall qu'en P07)."""
import sys
from pathlib import Path

PARENT = Path(__file__).resolve().parent.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))
