"""Démarrage unique, nettoyage du dépôt et API unique (P14).

Ces tests lisent le dépôt, jamais `/etc` : les unités de `/etc/systemd/system` sont des
liens vers `services/` ou `systemd/`. Ils figent la cible du prompt avant que le code
existe — c'est pourquoi ils échouent sur le dépôt actuel.
"""
from __future__ import annotations

import configparser
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
UNITES = [*sorted((REPO / "services").glob("*.service")),
          *sorted((REPO / "systemd").glob("*.service"))]
CIBLE = REPO / "services" / "clawbot.target"
BRINGUP = REPO / "clawbot_bringup" / "launch"

# Unités attendues dans la cible (inventaire §1) : capacités always_on + exécutif.
ATTENDUES = [
    "ros2-driver-node.service",
    "clawbot-lidar.service",
    "clawbot-description.service",
    "clawbot-ekf.service",
    "clawbot-safety-arbitrator.service",
    "clawbot-capability-manager.service",
    "clawbot-skill-server.service",
    "clawbot-mission-executive.service",
    "clawbot-director.service",
    "clawbot-sentinel.service",
    "clawbot-health-monitor.service",
    "clawbot-wrist-camera.service",
]

# Paquets déplacés sous attic/ (inventaire §3).
ATTIC = [
    "pkg_action", "pkg_helloworld_py", "pkg_interfaces", "pkg_metapackage", "pkg_param",
    "pkg_service", "pkg_tf", "pkg_topic",
    "yahboomcar_astra", "yahboomcar_base_node", "yahboomcar_bringup", "yahboomcar_ctrl",
    "yahboomcar_KCFTracker", "yahboomcar_laser", "yahboomcar_linefollow",
    "yahboomcar_mediapipe", "yahboomcar_multi", "yahboomcar_nav", "yahboomcar_point",
    "yahboomcar_rviz", "yahboomcar_slam", "yahboomcar_visual", "yahboomcar_voice_ctrl",
    "yahboomcar_msgs",
    "clawbot_hardware_interface", "laserscan_to_point_pulisher",
    "robot_pose_publisher_ros2", "yahboom_app_save_map", "yahboom_web_savmap_interfaces",
]

# Unités hors cible ROS, conservées : code hors dépôt ou oneshot non ROS (inventaire §1).
HORS_CIBLE = {"yahboom_oled.service", "clawbot-health.service", "clawbot-docs.service"}


def _lire(chemin: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.read_file(chemin.open(encoding="utf-8"))
    return cp


def _exec_start(chemin: Path) -> str:
    cp = _lire(chemin)
    return cp.get("Service", "ExecStart", fallback="") if cp.has_section("Service") else ""


# ── REQ-OPS-040 : une seule cible de démarrage ───────────────────────────────

@pytest.mark.req("REQ-OPS-040")
def test_la_cible_declare_les_unites_attendues():
    assert CIBLE.is_file(), "clawbot.target absent"
    cp = _lire(CIBLE)
    wants = set(cp.get("Unit", "Wants", fallback="").split())
    manquantes = [unite for unite in ATTENDUES if unite not in wants]
    assert not manquantes, f"absentes de Wants= : {manquantes}"


@pytest.mark.req("REQ-OPS-040")
def test_aucune_unite_du_robot_ne_s_accroche_au_boot():
    accrochees = []
    for chemin in UNITES:
        if chemin.name in HORS_CIBLE:
            continue
        cp = _lire(chemin)
        if not cp.has_section("Install"):
            continue
        wanted_by = cp.get("Install", "WantedBy", fallback="").split()
        if "clawbot.target" not in wanted_by:
            accrochees.append((chemin.name, wanted_by))
    assert not accrochees, f"unités hors cible : {accrochees}"


# ── REQ-OPS-041 : un fichier de lancement par unité ──────────────────────────

@pytest.mark.req("REQ-OPS-041")
def test_chaque_unite_lance_un_fichier_de_bringup():
    ecarts = []
    for chemin in UNITES:
        if chemin.name in HORS_CIBLE:
            continue
        commande = _exec_start(chemin)
        if "ros2 launch clawbot_bringup " not in commande:
            ecarts.append((chemin.name, commande[:80]))
            continue
        fichier = re.search(r"clawbot_bringup\s+(\S+\.launch\.py)", commande)
        if fichier is None or not (BRINGUP / fichier.group(1)).is_file():
            ecarts.append((chemin.name, f"lancement absent de {BRINGUP}"))
    assert not ecarts, ecarts


@pytest.mark.req("REQ-OPS-041")
def test_plus_de_ros2_run_ni_de_python3_c_dans_les_unites():
    fautives = []
    for chemin in UNITES:
        if chemin.name in HORS_CIBLE:
            continue
        commande = _exec_start(chemin)
        if "ros2 run " in commande or "python3 -c" in commande:
            fautives.append(chemin.name)
        if "/home/jetson/clawbot/launch/" in commande:
            fautives.append(f"{chemin.name} (launch hors paquet)")
    assert not fautives, fautives


# ── REQ-OPS-042 : attic/ et COLCON_IGNORE ────────────────────────────────────

@pytest.mark.req("REQ-OPS-042")
def test_les_paquets_non_deployes_sont_sous_attic():
    absents = [nom for nom in ATTIC
               if not (REPO / "attic" / nom / "COLCON_IGNORE").is_file()]
    assert not absents, f"sans COLCON_IGNORE sous attic/ : {absents}"


@pytest.mark.req("REQ-OPS-042")
def test_aucun_paquet_de_l_attic_ne_reste_a_la_racine():
    restants = [nom for nom in ATTIC if (REPO / nom).exists()]
    assert not restants, f"encore à la racine : {restants}"


@pytest.mark.req("REQ-OPS-042")
def test_un_seul_api_server_dans_le_depot():
    implementations = [chemin for chemin in REPO.rglob("api_server.*")
                       if chemin.suffix in (".py", ".cpp")
                       and not any(part in {"install", "build", "log", "attic", "__pycache__"}
                                   for part in chemin.parts)]
    assert len(implementations) == 1, [str(c.relative_to(REPO)) for c in implementations]


# ── REQ-OPS-043 : API unique branchée sur l'exécutif ─────────────────────────

@pytest.mark.req("REQ-OPS-043")
def test_l_api_ne_publie_plus_aucune_vitesse():
    sources = list((REPO / "ros2_llm_bridge_cpp" / "src").glob("*.cpp"))
    sources += list((REPO / "ros2_llm_bridge_cpp" / "include").rglob("*.hpp"))
    coupables = [str(chemin.relative_to(REPO)) for chemin in sources
                 if "create_publisher<geometry_msgs::msg::Twist>" in
                 chemin.read_text(encoding="utf-8")]
    assert not coupables, coupables


@pytest.mark.req("REQ-OPS-043")
def test_les_routes_de_mouvement_appellent_l_executif():
    source = (REPO / "ros2_llm_bridge_cpp" / "src" / "bridge_node.cpp").read_text(encoding="utf-8")
    assert "/clawbot/execute_skill" in source or "/clawbot/execute_mission" in source, \
        "aucun appel à l'exécutif dans le pont"
    assert "/motion" not in source, "l'API appelle encore le service matériel pour bouger"


# ── REQ-OPS-044 : plus d'entrée legacy dans l'arbitre ────────────────────────

@pytest.mark.req("REQ-OPS-044")
def test_l_arbitre_n_ecoute_plus_cmd_vel():
    source = (REPO / "clawbot_safety" / "clawbot_safety" / "arbitrator.py").read_text(
        encoding="utf-8")
    assert '"legacy"' not in source and "'legacy'" not in source, "entrée legacy encore présente"
    assert '"/cmd_vel"' not in source, "topic /cmd_vel encore écouté"


# ── REQ-NET-001 : rosbridge retiré ou local ─────────────────────────────────

@pytest.mark.req("REQ-NET-001")
def test_rosbridge_absent_ou_lie_a_la_boucle_locale():
    unites = list((REPO / "services").glob("*rosbridge*.service"))
    if not unites:
        references = [str(p.relative_to(REPO)) for p in
                      [*sorted((REPO / "services").glob("*.service")),
                       *sorted((REPO / "systemd").glob("*.service")), CIBLE]
                      if p.is_file() and "rosbridge" in p.read_text(encoding="utf-8")]
        assert not references, f"rosbridge retiré du dépôt mais encore cité : {references}"
        return
    commande = _exec_start(unites[0])
    assert "127.0.0.1" in commande, f"rosbridge écoute encore sur toutes les interfaces : {commande[:100]}"
