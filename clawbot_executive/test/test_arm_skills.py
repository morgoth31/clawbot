"""Skills du bras : liste blanche des poses, exécution, retour servo (P13).

Sans ROS : les skills reçoivent un contexte factice qui enregistre les trajectoires
demandées et rend les angles de servo simulés. Ce que ces tests prouvent :

  - la liste `config/arm_poses.yaml` ne contient que des poses validées, converties
    dans les limites de l'URDF ;
  - une pose inconnue ou non validée est refusée `INVALID_PARAMS` sans trajectoire ;
  - `arm_rest` commande la pose de repos puis vérifie la mesure avant de réussir ;
  - un retour servo invalide pendant plus de 0,5 s fait échouer le skill en cours
    `SERVO_NO_FEEDBACK` en moins d'une seconde.
"""

from __future__ import annotations

import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "clawbot_executive"))
# La conversion servo -> radians et les préconditions vivent hors de l'exécutif :
# les versions installées, plus anciennes, masqueraient le dépôt.
sys.path.insert(0, str(RACINE / "clawbot_arm_controller"))
sys.path.insert(0, str(RACINE / "clawbot_common"))

from clawbot_common.preconditions import charger as charger_preconditions  # noqa: E402
from clawbot_executive import bras  # noqa: E402
from clawbot_executive.etats import Etats  # noqa: E402
from clawbot_executive.registre import Definition  # noqa: E402
from clawbot_executive.skills import FAILED, REJECTED, SUCCEEDED, construire  # noqa: E402

POSES = RACINE / "config" / "arm_poses.yaml"
URDF = RACINE / "urdf" / "clawbot_x3plus.urdf"
PRECONDITIONS = RACINE / "config" / "preconditions.yaml"


# ── outillage ────────────────────────────────────────────────────────────────

class FauxExecuteur:
    """Enregistre les trajectoires ; rend l'issue et les angles qu'on lui donne."""

    def __init__(self, issue=None, angles=None, etats=None):
        self.trajectoires = []
        self.issue = issue
        self.angles = angles
        self.etats = etats

    def executer(self, groupe, positions, duree_s, timeout_s, surveillance=None):
        self.trajectoires.append((groupe, list(positions), duree_s))
        if surveillance is not None:
            # Le vrai exécuteur sonde toutes les 50 ms pendant la trajectoire ; le pilote,
            # lui, republie /arm/servo_angles à 10 Hz. On rejoue les deux : sans cela la
            # mesure serait périmée à la fin de la trajectoire simulée.
            for pas in range(40):
                if self.etats is not None and pas % 3 == 0:
                    self.etats.maj_servo_angles(self.etats.servo_angles)
                code = surveillance()
                if code:
                    return bras.Issue(False, code, "retour servo invalide simulé")
                time.sleep(0.02)
        if self.issue is not None:
            return self.issue
        return bras.Issue(True)


class FauxContexte:
    def __init__(self, params, poses=None, executeur=None, etats=None):
        self.params = params
        self.poses = poses or bras.charger(POSES)
        self.etats = etats or Etats()
        self.executeur = executeur or FauxExecuteur(etats=self.etats)
        if getattr(self.executeur, "etats", None) is None:
            self.executeur.etats = self.etats
        self.publies = []
        self.attentes = []

    # surface utilisée par les skills du bras
    def executer_bras(self, groupe, positions, duree_s, timeout_s, surveillance=None):
        return self.executeur.executer(groupe, positions, duree_s, timeout_s, surveillance)

    @property
    def servo_angles(self):
        return self.etats.servo_angles

    def age_servo(self):
        return self.etats.age_servo()

    def duree_invalide(self, maintenant=None):
        return self.etats.duree_invalide(maintenant)

    def maintenant(self):
        return time.monotonic()

    def attendre(self, duree):
        self.attentes.append(duree)
        time.sleep(min(float(duree), 0.05))

    def annule(self):
        return False

    def expire(self):
        return False

    def feedback(self, phase, progress):
        return None

    def publier(self, vx, vy, wz):
        self.publies.append((vx, vy, wz))


def definition(nom, **bornes):
    return Definition(nom=nom, description="", params_schema={}, requires=["arm"],
                      timeout_s=20.0, bornes=bornes)


# ── liste des poses (REQ-ARM-003) ─────────────────────────────────────────────

@pytest.mark.req("REQ-ARM-003")
def test_liste_des_poses_respecte_les_limites_de_l_urdf():
    poses = bras.charger(POSES)
    limites = {}
    for joint in ET.parse(URDF).getroot().findall("joint"):
        limite = joint.find("limit")
        if limite is not None and limite.get("lower") is not None \
                and limite.get("upper") is not None:
            limites[joint.get("name")] = (float(limite.get("lower")), float(limite.get("upper")))

    assert poses.poses, "aucune pose validée : le bras ne peut rien exécuter"
    for nom, pose in poses.poses.items():
        radians = pose.positions_rad()
        assert len(radians) == 6, nom
        for articulation, valeur in zip(poses.joints, radians):
            bas, haut = limites[articulation]
            assert bas - 1e-3 <= valeur <= haut + 1e-3, (nom, articulation, valeur, bas, haut)


@pytest.mark.req("REQ-ARM-003")
def test_pose_de_repos_est_la_pose_validee_du_11_novembre():
    poses = bras.charger(POSES)
    assert set(poses.poses) == {"repos"}
    repos = poses.poses["repos"]
    assert list(repos.servo_deg) == [90, 180, 0, 0, 90, 149]
    assert repos.valide_par_operateur and repos.valide_le
    assert repos.valide_le.startswith("2026-11-11"), repos.valide_le


@pytest.mark.req("REQ-ARM-003")
def test_une_proposition_non_validee_n_est_pas_commandable():
    poses = bras.charger(POSES)
    assert "home" not in poses.poses and "ready" not in poses.poses
    assert {"home", "ready"} <= set(poses.propositions)
    # Une entrée sans validation est refusée, même si elle est écrite dans `poses`.
    contenu = poses.source_brute()
    contenu["poses"]["home"] = dict(contenu["propositions"]["home"], tolerance_deg=[5] * 6)
    with pytest.raises(bras.PosesInvalides):
        bras.depuis_document(contenu)


# ── pose inconnue (REQ-ARM-003) ──────────────────────────────────────────────

@pytest.mark.req("REQ-ARM-003")
def test_pose_hors_liste_rejetee_invalid_params():
    ctx = FauxContexte({"pose": "salut"})
    skill = construire(definition("arm_named_pose"))
    resultat = skill.execute(ctx)

    assert resultat.outcome == REJECTED
    assert resultat.error_code == "INVALID_PARAMS"
    assert ctx.executeur.trajectoires == [], "aucune trajectoire ne doit partir"
    assert ctx.publies == []


@pytest.mark.req("REQ-ARM-003")
def test_arm_named_pose_repos_envoie_les_cinq_axes_et_la_pince():
    ctx = FauxContexte({"pose": "repos"}, etats=Etats())
    ctx.etats.maj_servo_angles([90, 180, 0, 0, 90, 149])
    resultat = construire(definition("arm_named_pose")).execute(ctx)

    assert resultat.outcome == SUCCEEDED, resultat.message
    groupes = [groupe for groupe, _, _ in ctx.executeur.trajectoires]
    assert groupes == ["arm", "grip"]
    _, positions, _ = ctx.executeur.trajectoires[0]
    assert positions == pytest.approx([0.0, 1.5708, -1.5708, -1.5708, 0.0], abs=2e-3)
    _, pince, _ = ctx.executeur.trajectoires[1]
    assert pince == pytest.approx([(149 - 180) / 116.88311688], abs=2e-3)


# ── pince (REQ-ARM-003) ──────────────────────────────────────────────────────

@pytest.mark.req("REQ-ARM-003")
def test_gripper_ouvert_et_ferme():
    for action, attendu_deg in (("open", 0), ("close", 180)):
        ctx = FauxContexte({"action": action})
        ctx.etats.maj_servo_angles([90, 180, 0, 0, 90, attendu_deg])
        resultat = construire(definition("gripper")).execute(ctx)
        assert resultat.outcome == SUCCEEDED, (action, resultat.message)
        assert [g for g, _, _ in ctx.executeur.trajectoires] == ["grip"]
        _, positions, _ = ctx.executeur.trajectoires[0]
        assert positions == pytest.approx([(attendu_deg - 180) / 116.88311688], abs=2e-3)


# ── arm_rest vérifié sur la mesure (REQ-ARM-006) ─────────────────────────────

@pytest.mark.req("REQ-ARM-006")
def test_arm_rest_reussit_quand_la_mesure_est_dans_l_enveloppe():
    ctx = FauxContexte({}, etats=Etats())
    ctx.etats.maj_servo_angles([90, 180, 0, 0, 90, 149])
    resultat = construire(definition("arm_rest")).execute(ctx)

    assert resultat.outcome == SUCCEEDED, resultat.message
    assert [g for g, _, _ in ctx.executeur.trajectoires] == ["arm", "grip"]
    assert "[90, 180, 0, 0, 90, 149]" in resultat.message


@pytest.mark.req("REQ-ARM-006")
def test_arm_rest_echoue_si_la_mesure_ne_suit_pas():
    ctx = FauxContexte({}, etats=Etats())
    ctx.etats.maj_servo_angles([90, 120, 0, 0, 90, 180])   # bras resté ailleurs
    resultat = construire(definition("arm_rest", verification_timeout_s=0.2)).execute(ctx)

    assert resultat.outcome == FAILED
    assert resultat.error_code == "ARM_NOT_AT_REST"
    assert "servo 2" in resultat.message


@pytest.mark.req("REQ-ARM-006")
def test_arm_rest_echoue_si_aucune_mesure():
    ctx = FauxContexte({}, etats=Etats())
    resultat = construire(definition("arm_rest", verification_timeout_s=0.2)).execute(ctx)

    assert resultat.outcome == FAILED
    assert resultat.error_code == "ARM_NOT_AT_REST"


# ── retour servo invalide (REQ-ARM-005) ──────────────────────────────────────

@pytest.mark.req("REQ-ARM-005")
def test_surveillance_servo_declenche_apres_0_5_s():
    etats = Etats()
    debut = 100.0
    etats.maj_servo_angles([-1, 90, 90, 90, 90, 180], maintenant=debut)
    assert bras.surveillance_servo(etats, debut + 0.4) is None
    assert bras.surveillance_servo(etats, debut + 0.51) == "SERVO_NO_FEEDBACK"

    etats.maj_servo_angles([90, 90, 90, 90, 90, 180], maintenant=debut + 0.6)
    assert bras.surveillance_servo(etats, debut + 2.0) is None


@pytest.mark.req("REQ-ARM-005")
def test_valeur_hors_bornes_compte_comme_retour_invalide():
    etats = Etats()
    etats.maj_servo_angles([90, 90, 300, 90, 90, 180], maintenant=10.0)
    assert bras.surveillance_servo(etats, 10.6) == "SERVO_NO_FEEDBACK"


@pytest.mark.req("REQ-ARM-005")
def test_skill_de_bras_echoue_servo_no_feedback_en_moins_d_une_seconde():
    etats = Etats()
    etats.maj_servo_angles([-1, -1, -1, -1, -1, -1])
    ctx = FauxContexte({"pose": "repos"}, etats=etats)

    debut = time.monotonic()
    resultat = construire(definition("arm_named_pose")).execute(ctx)
    ecoule = time.monotonic() - debut

    assert resultat.outcome == FAILED
    assert resultat.error_code == "SERVO_NO_FEEDBACK"
    # Le premier message invalide date d'avant l'appel : l'échec doit être immédiat.
    assert ecoule < 1.0, ecoule


@pytest.mark.req("REQ-ARM-005")
def test_retour_servo_invalide_pendant_la_trajectoire_annule_le_skill():
    etats = Etats()
    etats.maj_servo_angles([90, 180, 0, 0, 90, 149])

    class PiloteQuiMeurt(FauxExecuteur):
        """Le servo 3 tombe à -1 après deux sondes."""

        def executer(self, groupe, positions, duree_s, timeout_s, surveillance=None):
            self.trajectoires.append((groupe, list(positions), duree_s))
            etats.maj_servo_angles([90, 180, -1, 0, 90, 149])
            debut = time.monotonic()
            while time.monotonic() - debut < 2.0:
                code = surveillance()
                if code:
                    return bras.Issue(False, code, "servo 3 muet")
                time.sleep(0.02)
            return bras.Issue(True)

    ctx = FauxContexte({"pose": "repos"}, etats=etats, executeur=PiloteQuiMeurt())
    debut = time.monotonic()
    resultat = construire(definition("arm_named_pose")).execute(ctx)

    assert resultat.outcome == FAILED
    assert resultat.error_code == "SERVO_NO_FEEDBACK"
    assert time.monotonic() - debut < 1.5


# ── préconditions de base (REQ-ARM-004) ──────────────────────────────────────

def _etats_bras(angles, age_s=0.0):
    etats = Etats()
    etats.maj_servo_angles(angles, maintenant=time.monotonic() - age_s)
    return etats


@pytest.mark.req("REQ-ARM-004")
@pytest.mark.parametrize("nom", ["move_relative", "rotate", "navigate_to"])
def test_bras_hors_enveloppe_refuse_les_skills_de_base(nom):
    regles = charger_preconditions(PRECONDITIONS)
    skill = construire(Definition(nom=nom, params_schema={}), regles=regles)
    etats = _etats_bras([90, 120, 0, 0, 90, 149])          # servo 2 hors bande

    assert skill.check_preconditions(etats) == "ARM_NOT_AT_REST"
    assert "servo 2" in skill.detail_precondition(etats)


@pytest.mark.req("REQ-ARM-004")
@pytest.mark.parametrize("nom", ["move_relative", "rotate", "navigate_to"])
def test_bras_dans_l_enveloppe_laisse_passer_les_skills_de_base(nom):
    regles = charger_preconditions(PRECONDITIONS)
    skill = construire(Definition(nom=nom, params_schema={}), regles=regles)
    assert skill.check_preconditions(_etats_bras([90, 180, 0, 0, 90, 149])) is None


@pytest.mark.req("REQ-ARM-004")
def test_angles_perimes_ou_absents_refusent_le_deplacement():
    regles = charger_preconditions(PRECONDITIONS)
    skill = construire(Definition(nom="move_relative", params_schema={}), regles=regles)
    assert skill.check_preconditions(_etats_bras([90, 180, 0, 0, 90, 149], age_s=5.0)) \
        == "ARM_NOT_AT_REST"
    assert skill.check_preconditions(Etats()) == "ARM_NOT_AT_REST"


@pytest.mark.req("REQ-ARM-004")
def test_les_skills_du_bras_ne_sont_pas_geles_par_la_precondition():
    regles = charger_preconditions(PRECONDITIONS)
    etats = _etats_bras([90, 120, 0, 0, 90, 149])
    for nom, params in (("arm_rest", {}), ("arm_named_pose", {"pose": "repos"}),
                        ("gripper", {"action": "close"})):
        skill = construire(Definition(nom=nom, params_schema={}, requires=["arm"]), regles=regles)
        assert skill.check_preconditions(etats) != "ARM_NOT_AT_REST", nom
