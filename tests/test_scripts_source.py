"""REQ-OPS-053 — un `source` sous `set -u` tue l'unite.

`/opt/ros/humble/setup.bash` lit `AMENT_TRACE_SETUP_FILES` sans valeur par defaut et sort
en erreur sous `set -u` : `clawbot-joy-teleop.service` est mort en status=1/FAILURE le
2026-11-23 a 00:31 et a boucle en redemarrage sans jamais publier /joy.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
SCRIPTS = sorted(
    [*RACINE.glob("joy_teleop/*.sh"), *RACINE.glob("scripts/*.sh")])
# Seul le mot `source` est reconnu : le point seul est ambigu en shell (« . » est aussi
# le chemin courant, cf. `grep -rnE … . 2>/dev/null` dans check.sh). Les scripts
# du depot emploient tous `source`.
SOURCE = re.compile(r"^\s*source\s+\S")


@pytest.mark.req("REQ-OPS-053")
@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_chaque_source_est_encadre_par_set_plus_u(script):
    if not SCRIPTS:
        pytest.skip("aucun script a verifier")
    lignes = script.read_text(encoding="utf-8").splitlines()
    strict = False
    fautes = []
    for numero, ligne in enumerate(lignes, 1):
        nu = ligne.strip()
        if nu == "set -u":
            strict = True
        elif nu == "set +u":
            strict = False
        elif SOURCE.match(ligne) and strict:
            fautes.append(numero)
    assert not fautes, (
        f"{script.name} : `source` sous `set -u` aux lignes {fautes} — encadrez par "
        "`set +u` / `set -u` (REQ-OPS-053)")


@pytest.mark.req("REQ-OPS-053")
def test_le_cas_negatif_est_detecte(tmp_path):
    """Sans ce cas, le marqueur serait de complaisance."""
    fautif = tmp_path / "fautif.sh"
    fautif.write_text("set -u\nsource /opt/ros/humble/setup.bash\n", encoding="utf-8")
    lignes = fautif.read_text(encoding="utf-8").splitlines()
    strict, fautes = False, []
    for numero, ligne in enumerate(lignes, 1):
        nu = ligne.strip()
        if nu == "set -u":
            strict = True
        elif nu == "set +u":
            strict = False
        elif SOURCE.match(ligne) and strict:
            fautes.append(numero)
    assert fautes == [2], f"le detecteur doit voir la ligne 2, il a vu {fautes}"
