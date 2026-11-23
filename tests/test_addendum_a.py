"""REQ-ARCH-020 — le referentiel integre l'addendum A (F00)."""
from __future__ import annotations

from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
CIBLE = RACINE / "docs" / "architecture" / "cible.md"
ADDENDUM = RACINE / "docs" / "architecture" / "addendum_A_fonctions.md"


@pytest.mark.req("REQ-ARCH-020")
def test_l_addendum_est_dans_le_referentiel():
    assert ADDENDUM.is_file(), "docs/architecture/addendum_A_fonctions.md absent"
    assert "INV-11" in ADDENDUM.read_text(encoding="utf-8")


@pytest.mark.req("REQ-ARCH-020")
def test_cible_nomme_les_cinq_invariants_et_renvoie_a_l_addendum():
    texte = CIBLE.read_text(encoding="utf-8")
    manquants = [inv for inv in ("INV-11", "INV-12", "INV-13", "INV-14", "INV-15")
                 if inv not in texte]
    assert not manquants, f"invariants absents de cible.md : {manquants}"
    assert "addendum_A_fonctions.md" in texte, "cible.md doit renvoyer vers l'addendum"
