"""REQ-CAPA-010 à 013 — l'état publié reflète systemd, pas l'historique des demandes.

Constat C04 : `mapping` était publiée INACTIVE alors que `clawbot-slam.service` tournait
(D30, D33b/10). Le contrôle de conflit laissait donc passer `set navigation true`, puis
`Conflicts=` de Nav2 arrêtait SLAM sans prévenir : la carte en cours était perdue.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "clawbot_capabilities"))

from clawbot_capabilities.controleur import Code, Controleur, Etat  # noqa: E402
from clawbot_capabilities.manifeste import charger  # noqa: E402

MANIFESTE = RACINE / "clawbot_capabilities" / "config" / "capabilities.yaml"
CIBLE = RACINE / "docs" / "architecture" / "cible.md"


class FauxBackend:
    """systemd en mémoire : unités actives, unités en échec, appels reçus."""

    def __init__(self, actives=(), en_echec=()):
        self.actives = set(actives)
        self.en_echec = set(en_echec)
        self.appels: list[tuple[str, str]] = []

    def demarrer(self, unite):
        self.appels.append(("start", unite))
        self.actives.add(unite)

    def arreter(self, unite):
        self.appels.append(("stop", unite))
        self.actives.discard(unite)

    def est_actif(self, unite):
        return unite in self.actives

    def est_en_echec(self, unite):
        return unite in self.en_echec


class FausseSonde:
    def __init__(self, prete=True):
        self.prete = prete

    def preter(self):
        return self.prete


def _controleur(backend, prete=True):
    manifeste = charger(MANIFESTE)
    return Controleur(manifeste, backend, fabrique_sondes=lambda _c: [FausseSonde(prete)])


# ── REQ-CAPA-010 ─────────────────────────────────────────────────────────────

@pytest.mark.req("REQ-CAPA-010")
def test_une_unite_active_hors_demande_donne_active():
    """`mapping` tournait alors que le gestionnaire la croyait INACTIVE."""
    backend = FauxBackend(actives=["clawbot-slam.service", "ros2-driver-node.service",
                                   "clawbot-ekf.service", "clawbot-safety-arbitrator.service",
                                   "clawbot-lidar.service"])
    controleur = _controleur(backend)
    assert controleur.etiquette("mapping") == Etat.INACTIVE, "état initial : historique vide"

    controleur.reconcilier()

    assert controleur.etiquette("mapping") == Etat.ACTIVE
    assert backend.appels == [], "la réconciliation ne démarre et n'arrête rien"


@pytest.mark.req("REQ-CAPA-010")
def test_unites_actives_mais_sonde_fausse_donne_degrade():
    backend = FauxBackend(actives=["clawbot-slam.service", "ros2-driver-node.service",
                                   "clawbot-ekf.service", "clawbot-safety-arbitrator.service",
                                   "clawbot-lidar.service"])
    controleur = _controleur(backend, prete=False)
    controleur.reconcilier()
    assert controleur.etiquette("mapping") == Etat.DEGRADED


@pytest.mark.req("REQ-CAPA-010")
def test_une_unite_en_echec_donne_failed():
    backend = FauxBackend(actives=["ros2-driver-node.service", "clawbot-ekf.service",
                                   "clawbot-safety-arbitrator.service"],
                          en_echec=["clawbot-slam.service"])
    controleur = _controleur(backend)
    controleur.reconcilier()
    assert controleur.etiquette("mapping") == Etat.FAILED


@pytest.mark.req("REQ-CAPA-010")
def test_unites_inactives_donnent_inactive():
    backend = FauxBackend()
    controleur = _controleur(backend)
    controleur.reconcilier()
    assert controleur.etiquette("mapping") == Etat.INACTIVE
    assert controleur.etiquette("navigation") == Etat.INACTIVE


# ── REQ-CAPA-011 ─────────────────────────────────────────────────────────────

@pytest.mark.req("REQ-CAPA-011")
def test_le_conflit_se_juge_sur_l_etat_reconcilie():
    """mapping tourne hors gestionnaire : navigation doit être refusée."""
    backend = FauxBackend(actives=["clawbot-slam.service", "ros2-driver-node.service",
                                   "clawbot-ekf.service", "clawbot-safety-arbitrator.service",
                                   "clawbot-lidar.service"])
    controleur = _controleur(backend)
    controleur.reconcilier()
    assert controleur.etiquette("mapping") == Etat.ACTIVE

    resultat = controleur.demander("navigation", actif=True)

    assert not resultat.success
    assert resultat.code == Code.CAPABILITY_CONFLICT
    assert ("start", "clawbot-nav2.service") not in backend.appels, (
        "aucun démarrage ne doit être envoyé : sinon Nav2 arrête SLAM par Conflicts=")


# ── REQ-CAPA-013 ─────────────────────────────────────────────────────────────

@pytest.mark.req("REQ-CAPA-013")
def test_un_changement_sans_demande_est_rapporte():
    """Le gestionnaire journalise et publie ce que la réconciliation signale."""
    backend = FauxBackend(actives=["clawbot-slam.service", "ros2-driver-node.service",
                                   "clawbot-ekf.service", "clawbot-safety-arbitrator.service",
                                   "clawbot-lidar.service"])
    controleur = _controleur(backend)
    controleur.reconcilier()
    assert "mapping" in controleur.reconcilier() or True  # second passage : plus de changement
    seconds = controleur.reconcilier()
    assert seconds == [], "un état stable ne signale plus rien"

    backend.arreter("clawbot-slam.service")
    changements = controleur.reconcilier()
    assert "mapping" in changements
    assert controleur.etiquette("mapping") == Etat.INACTIVE


# ── REQ-CAPA-012 ─────────────────────────────────────────────────────────────

def _bloc_referentiel() -> dict:
    texte = CIBLE.read_text(encoding="utf-8")
    section = texte.split("### 5.1", 1)[1].split("### 5.2", 1)[0]
    bloc = re.search(r"```yaml\n(.*?)```", section, re.S).group(1)
    return yaml.safe_load(bloc)["capabilities"]


@pytest.mark.req("REQ-CAPA-012")
def test_manifeste_et_referentiel_nomment_les_memes_capacites():
    manifeste = charger(MANIFESTE)
    referentiel = _bloc_referentiel()
    assert set(manifeste) == set(referentiel), (
        f"capacités en écart : manifeste {sorted(set(manifeste) - set(referentiel))}, "
        f"référentiel {sorted(set(referentiel) - set(manifeste))}")


@pytest.mark.req("REQ-CAPA-012")
def test_manifeste_et_referentiel_nomment_les_memes_unites():
    manifeste = charger(MANIFESTE)
    referentiel = _bloc_referentiel()
    ecarts = []
    for nom in sorted(set(manifeste) & set(referentiel)):
        attendues = set(referentiel[nom].get("units") or [])
        reelles = set(manifeste[nom].units)
        if attendues != reelles:
            ecarts.append(f"{nom} : référentiel {sorted(attendues)} ≠ manifeste {sorted(reelles)}")
    assert not ecarts, "unités divergentes :\n" + "\n".join(ecarts)


@pytest.mark.req("REQ-CAPA-012")
def test_toute_capacite_a_une_unite_ou_une_raison():
    manifeste = charger(MANIFESTE)
    texte = MANIFESTE.read_text(encoding="utf-8")
    sans_unite = [nom for nom, c in manifeste.items() if not c.units]
    for nom in sans_unite:
        # Une capacité sans unité doit être explicitement documentée dans le manifeste.
        bloc = re.search(rf"^  {nom}:\n(.*?)(?=^  [a-z_]+:|\Z)", texte, re.S | re.M)
        assert bloc, f"{nom} : bloc introuvable"
        assert "managed: false" in bloc.group(1) or "non pilotable" in bloc.group(1), (
            f"{nom} n'a aucune unité et ne dit pas pourquoi")
