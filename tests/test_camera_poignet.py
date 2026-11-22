"""Caméra du poignet : cohérence entre l'URDF, l'unité systemd et la calibration déclarée.

Ces tests ne lisent pas d'image : le flux réel se prouve par `scripts/sonde_flux_camera.py`. Ils
protègent ce qui casse en silence à la première modification d'un fichier — un cadre optique
absent de l'URDF alors que l'unité publie son nom, un topic qui ne correspond plus à ce que le
service YOLO écoute, un domaine ROS oublié (le nœud se crée alors en domaine 0 et ne voit rien,
sans message d'erreur).
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[1]
URDF = RACINE / "urdf" / "clawbot_x3plus.urdf"
UNIT_CAMERA = RACINE / "services" / "clawbot-wrist-camera.service"
UNIT_YOLO = RACINE / "services" / "clawbot-yolo.service"
CALIBRATION = RACINE / "config" / "wrist_camera_info.yaml"

CADRE = "wrist_camera_optical_frame"
TOPIC = "/wrist_camera/image_raw"


@pytest.fixture(scope="module")
def urdf():
    return ET.parse(URDF).getroot()


@pytest.fixture(scope="module")
def unite_camera():
    return UNIT_CAMERA.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def unite_yolo():
    return UNIT_YOLO.read_text(encoding="utf-8")


# ── URDF ──────────────────────────────────────────────────────────────────────
def test_le_cadre_optique_existe_et_pend_au_bras(urdf):
    liens = {lien.get("name") for lien in urdf.findall("link")}
    assert CADRE in liens

    joint = next((j for j in urdf.findall("joint")
                  if j.get("name") == "wrist_camera_optical_joint"), None)
    assert joint is not None, "joint optique absent"
    assert joint.get("type") == "fixed", "un cadre optique ne bouge pas par rapport à son support"
    assert joint.find("parent").get("link") == "mono_link"
    assert joint.find("child").get("link") == CADRE


def test_le_cadre_optique_regarde_l_horizon_a_la_pose_de_repos():
    """Régression du 2026-11-11 : le cadre était décrit 90° trop bas.

    À la pose de repos validée `[90, 180, 0, 0, 90]`, l'image du poignet montre l'horizon et la même
    scène que l'Astra. Un modèle qui annonce −90° (vers le sol) rend la caméra inutilisable pour
    l'asservissement visuel, et l'erreur ne se voit qu'en comparant le modèle à l'image.
    """
    sys.path.insert(0, str(RACINE / "scripts"))
    from cinematique_bras import Bras, _decrire, _servo_vers_rad

    bras = Bras(URDF)
    repos = _decrire(bras, _servo_vers_rad([90, 180, 0, 0, 90]))
    assert abs(repos["tangage_deg"]) <= 2.0, repos["tangage_deg"]
    # et la correction ne doit pas être un demi-tour : l'axe doit pointer vers l'avant
    assert repos["visee"][0] > 0.95, repos["visee"]

    # à servo 2 = 140 la caméra pique vers le sol, l'image montre le parquet vu de dessus
    bas = _decrire(bras, _servo_vers_rad([90, 140, 0, 0, 90]))
    assert -50.0 <= bas["tangage_deg"] <= -30.0, bas["tangage_deg"]


def test_le_cadre_optique_est_atteignable_depuis_la_base(urdf):
    """`mono_link` est monté sur `arm_link4` : la chaîne doit relier base_footprint au cadre."""
    parents = {}
    for joint in urdf.findall("joint"):
        parents[joint.find("child").get("link")] = joint.find("parent").get("link")
    chaine, courant = [], CADRE
    while courant in parents:
        courant = parents[courant]
        chaine.append(courant)
    assert "arm_link4" in chaine and chaine[-1] == "base_footprint", chaine


def test_l_urdf_reste_valide():
    resultat = subprocess.run([sys.executable, str(RACINE / "urdf" / "validate_urdf.py"),
                               str(URDF)], capture_output=True, text=True, timeout=60)
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    assert "URDF valid" in resultat.stdout


# ── unité systemd de la caméra ────────────────────────────────────────────────
def test_l_unite_publie_le_cadre_de_l_urdf(unite_camera, urdf):
    assert f"camera_frame_id:={CADRE}" in unite_camera
    assert CADRE in {lien.get("name") for lien in urdf.findall("link")}


def test_l_unite_utilise_le_chemin_by_id_et_pas_un_index(unite_camera):
    assert "/dev/v4l/by-id/" in unite_camera, \
        "un index /dev/videoN change au rebranchement ; le nom by-id non"
    assert "/dev/video0 " not in unite_camera and "video_device:=/dev/video0" not in unite_camera


def test_l_unite_declare_le_domaine_et_un_seul_proprietaire(unite_camera):
    assert "Environment=ROS_DOMAIN_ID=28" in unite_camera
    assert "User=jetson" in unite_camera
    assert "wrist_camera" in unite_camera and "Conflicts=" not in unite_camera, \
        "la caméra appartient à une seule unité : ce n'est pas un conflit, c'est une propriété"


def test_l_unite_ne_convertit_pas_l_image_dans_le_noeud(unite_camera):
    """La conversion par image coûtait 60 ms et divisait la cadence : elle est faite à la demande."""
    assert "output_encoding:=yuv422_yuy2" in unite_camera


# ── service YOLO : la caméra lui est donnée par le topic ──────────────────────
def test_le_service_yolo_lit_la_camera_par_le_topic(unite_yolo, unite_camera):
    # Depuis P12, l'unité lance le nœud yolo_node, qui s'abonne au topic (BEST_EFFORT,
    # profondeur 1) : elle n'ouvre aucun /dev/video* et ne porte donc plus d'index V4L.
    assert "yolo_node.noeud" in unite_yolo
    assert "CAMERA_CLAW_INDEX" not in unite_yolo and "CAMERA_FRONT_INDEX" not in unite_yolo
    assert "Environment=ROS_DOMAIN_ID=28" in unite_yolo, \
        "sans domaine, le nœud du service vit en domaine 0 : abonnement muet, sans erreur"
    # le topic écouté doit être celui que la caméra publie (même espace de noms)
    assert "__ns:=/wrist_camera" in unite_camera


def test_le_contrat_d_image_est_lisible_par_le_service():
    """Le décodeur de la source ROS doit gérer l'encodage que la caméra publie réellement."""
    source = (RACINE / "yolo_service.py").read_text(encoding="utf-8")
    assert "CAMERA_CLAW_SOURCE" in source and "_image_ros" in source
    assert "yuv422_yuy2" in source, "l'encodage natif de la caméra doit être décodé"


# ── calibration déclarée ──────────────────────────────────────────────────────
def test_la_calibration_est_presente_et_declaree_non_mesuree():
    contenu = CALIBRATION.read_text(encoding="utf-8")
    assert "NON CALIBRÉES" in contenu or "NON CALIBREES" in contenu, \
        "un fichier d'intrinsèques non mesurées doit le dire dans son en-tête"
    assert "mire" in contenu
    infos = yaml.safe_load(contenu)
    assert infos["image_width"] == 640 and infos["image_height"] == 480
    assert infos["camera_matrix"]["data"][0] > 0, "fx nulle : aucune projection possible"
    assert infos["distortion_model"] == "plumb_bob"
    assert all(v == 0.0 for v in infos["distortion_coefficients"]["data"])
