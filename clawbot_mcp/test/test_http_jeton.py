"""HTTP : interface explicite et jeton exigé (REQ-MCP-007)."""
from __future__ import annotations

import pytest

from clawbot_mcp.serveur import (JETON_VARIABLE, configurer_transport, jeton_attendu,
                                 verifier_jeton)

pytestmark = pytest.mark.req("REQ-MCP-007")


def test_sans_jeton_401():
    assert verifier_jeton({}, "secret") is False
    assert verifier_jeton({"Authorization": "Bearer "}, "secret") is False


def test_jeton_faux_401():
    assert verifier_jeton({"Authorization": "Bearer faux"}, "secret") is False
    assert verifier_jeton({"authorization": "Basic secret"}, "secret") is False


def test_jeton_valide_accepte():
    assert verifier_jeton({"Authorization": "Bearer secret"}, "secret") is True
    assert verifier_jeton({"authorization": "bearer secret"}, "secret") is True


def test_aucun_jeton_attendu_refuse_tout():
    assert verifier_jeton({"Authorization": "Bearer "}, None) is False


def test_hote_lu_du_parametre_et_pas_de_wildcard():
    assert configurer_transport("http", "192.168.1.47", 8765) == {
        "transport": "http", "host": "192.168.1.47", "port": 8765}
    with pytest.raises(ValueError):
        configurer_transport("http", "0.0.0.0", 8765)
    with pytest.raises(ValueError):
        configurer_transport("http", "", 8765)
    with pytest.raises(ValueError):
        configurer_transport("inconnu", "127.0.0.1", 1)


def test_jeton_lu_dans_l_environnement(monkeypatch):
    monkeypatch.delenv(JETON_VARIABLE, raising=False)
    assert jeton_attendu() is None
    monkeypatch.setenv(JETON_VARIABLE, "secret")
    assert jeton_attendu() == "secret"
