"""Contrôleur des capacités : liste blanche, conflits, dépendances, états (REQ-CAPA-001 à 005)."""
from __future__ import annotations

import pytest

from clawbot_capabilities.controleur import Code, Controleur, Etat
from clawbot_capabilities.manifeste import Capacite, Manifeste


class FauxBackend:
    """systemd en mémoire : retient les unités actives et l'ordre des appels."""

    def __init__(self, en_echec=()):
        self.actives: set[str] = set()
        self.appels: list[tuple[str, str]] = []
        self.en_echec = set(en_echec)

    def demarrer(self, unite: str) -> None:
        self.appels.append(("start", unite))
        if unite in self.en_echec:
            raise RuntimeError(f"systemctl start {unite} : code 1")
        self.actives.add(unite)

    def arreter(self, unite: str) -> None:
        self.appels.append(("stop", unite))
        if unite in self.en_echec:
            raise RuntimeError(f"systemctl stop {unite} : code 1")
        self.actives.discard(unite)

    def est_actif(self, unite: str) -> bool:
        return unite in self.actives


class FausseSonde:
    def __init__(self, prete: bool = True):
        self.prete = prete

    def preter(self) -> bool:
        return self.prete


def manifeste_minimal() -> Manifeste:
    """Trois capacités : base (always_on), navigation (requires base), mapping (conflit nav)."""
    return Manifeste({
        "base": Capacite(nom="base", units=["base.service"], always_on=True, managed=True,
                         ready_when=[{"topic": "/odom", "min_hz": 8.0}], timeout_s=30.0),
        "mapping": Capacite(nom="mapping", units=["clawbot-slam.service"], requires=["base"],
                            conflicts=["navigation"], managed=True,
                            ready_when=[{"topic": "/map", "max_age_s": 30.0}], timeout_s=30.0),
        "navigation": Capacite(nom="navigation", units=["clawbot-nav2.service"], requires=["base"],
                               conflicts=["mapping"], managed=True,
                               ready_when=[{"action": "/navigate_to_pose"}], timeout_s=0.5),
        "depth_vision": Capacite(nom="depth_vision", units=[], managed=False,
                                 ready_when=[{"topic": "/camera/depth/image_raw", "min_hz": 10.0}]),
    })


def controleur(sondes_prete=True, **kw) -> tuple[Controleur, FauxBackend]:
    backend = FauxBackend(**kw)
    controleur = Controleur(manifeste_minimal(), backend=backend,
                            fabrique_sondes=lambda c: [FausseSonde(sondes_prete)],
                            horloge=lambda: controleur_maintenant[0])
    return controleur, backend


controleur_maintenant = [0.0]


@pytest.fixture(autouse=True)
def _horloge():
    controleur_maintenant[0] = 0.0


@pytest.mark.req("REQ-CAPA-001")
def test_liste_blanche_refuse_un_nom_inconnu():
    ctl, backend = controleur()
    resultat = ctl.demander("hyperdrive", actif=True)
    assert (resultat.success, resultat.code) == (False, Code.UNKNOWN_CAPABILITY)
    assert backend.appels == []


@pytest.mark.req("REQ-CAPA-001")
def test_aucun_shell(monkeypatch):
    """SystemdBackend n'appelle jamais un shell : subprocess en liste d'arguments."""
    from clawbot_capabilities import backend as module

    appels = []

    def faux_run(argv, **kw):
        appels.append((argv, kw))

        class R:
            returncode = 0
            stdout = b""
            stderr = b""
        return R()

    monkeypatch.setattr(module.subprocess, "run", faux_run)
    module.SystemdBackend().demarrer("clawbot-slam.service")
    (argv, kw), = appels
    assert isinstance(argv, list)
    assert "start" in argv and argv[-1] == "clawbot-slam.service"
    assert not kw.get("shell", False)


@pytest.mark.req("REQ-CAPA-002")
def test_active_quand_les_sondes_repondent():
    ctl, _ = controleur()
    ctl.demander("base", actif=True)
    assert ctl.etiquette("base") == Etat.STARTING
    ctl.rafraichir()
    assert ctl.etiquette("base") == Etat.ACTIVE
    assert ctl.changements == 2          # STARTING puis ACTIVE publiés


@pytest.mark.req("REQ-CAPA-002")
def test_failed_apres_timeout():
    ctl, backend = controleur(sondes_prete=False)
    ctl.demander("navigation", actif=True)          # timeout_s = 0.5
    ctl.rafraichir()
    assert ctl.etiquette("navigation") == Etat.STARTING
    controleur_maintenant[0] = 0.6
    ctl.rafraichir()
    assert ctl.etiquette("navigation") == Etat.FAILED
    assert backend.actives == {"base.service", "clawbot-nav2.service"}


@pytest.mark.req("REQ-CAPA-003")
def test_conflit_refuse():
    ctl, _ = controleur()
    ctl.demander("mapping", actif=True)
    ctl.rafraichir()
    assert ctl.etiquette("mapping") == Etat.ACTIVE
    resultat = ctl.demander("navigation", actif=True)
    assert (resultat.success, resultat.code) == (False, Code.CAPABILITY_CONFLICT)
    assert "mapping" in resultat.message


@pytest.mark.req("REQ-CAPA-004")
def test_dependances_activees_dans_l_ordre():
    ctl, backend = controleur()
    resultat = ctl.demander("navigation", actif=True)
    assert resultat.success
    assert backend.appels == [("start", "base.service"), ("start", "clawbot-nav2.service")]
    assert ctl.etiquette("base") == Etat.STARTING


@pytest.mark.req("REQ-CAPA-005")
def test_always_on_refuse_l_arret():
    ctl, backend = controleur()
    ctl.demander("base", actif=True)
    ctl.rafraichir()
    resultat = ctl.demander("base", actif=False)
    assert (resultat.success, resultat.code) == (False, Code.ALWAYS_ON)
    assert ctl.etiquette("base") == Etat.ACTIVE
    assert ("stop", "base.service") not in backend.appels


@pytest.mark.req("REQ-CAPA-005")
def test_arret_refuse_si_une_capacite_active_en_depend():
    ctl, backend = controleur()
    ctl.demander("base", actif=True)
    ctl.rafraichir()
    resultat = ctl.demander("base", actif=False)
    assert resultat.code in (Code.ALWAYS_ON, Code.DEPENDENCY_ACTIVE)


@pytest.mark.req("REQ-CAPA-001")
def test_capacite_non_geree_refusee():
    ctl, _ = controleur()
    resultat = ctl.demander("depth_vision", actif=True)
    assert (resultat.success, resultat.code) == (False, Code.CAPABILITY_NOT_MANAGED)


@pytest.mark.req("REQ-CAPA-002")
def test_unite_en_echec_donne_failed():
    ctl, _ = controleur(en_echec=["clawbot-nav2.service"])
    resultat = ctl.demander("navigation", actif=True)
    assert (resultat.success, resultat.code) == (False, Code.UNIT_FAILED)
    assert ctl.etiquette("navigation") == Etat.FAILED
    assert ctl.etiquette("base") == Etat.STARTING    # la dépendance reste lancée
