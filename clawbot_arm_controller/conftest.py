"""Rend le paquet importable par pytest depuis la racine du paquet."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
