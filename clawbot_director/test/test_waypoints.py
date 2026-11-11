"""Catalogue de waypoints : énumération fermée, vérifiée contre la carte réelle.

Ce que ces tests protègent, dans l'ordre d'importance :

  1. **Aucune coordonnée libre n'entre par cette porte.** S2 nomme, S1 résout. Un appel qui
     transporte un couple (x, y) est refusé avant tout envoi, pas « normalisé ».
  2. **Le catalogue est cohérent avec la carte sur laquelle il prétend s'appliquer** : chaque
     waypoint tombe dans une cellule libre, assez loin des obstacles pour un châssis de 20 cm,
     et tous les waypoints sont dans la même composante connexe — sinon un nom valide
     désignerait une cible inatteignable, ce qui est pire qu'une erreur de frappe.
  3. **Un YAML malformé échoue au chargement**, jamais à l'exécution : doublon de nom, valeur non
     finie, clé inconnue, waypoint hors carte.
"""

from __future__ import annotations

import math
import sys
from collections import deque
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clawbot_director import waypoints  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]          # /home/jetson/clawbot
CARTE_PGM = RACINE / "maps" / "test_cartographie_apres_deplacement.pgm"
CARTE_YAML = RACINE / "maps" / "test_cartographie_apres_deplacement.yaml"


# ── outils de lecture de la carte, indépendants du module testé ─────────────
def _lire_pgm(chemin: Path):
    donnees = chemin.read_bytes()
    jetons, i = [], 0
    while len(jetons) < 4:
        while donnees[i:i + 1].isspace():
            i += 1
        if donnees[i:i + 1] == b"#":
            while donnees[i:i + 1] not in (b"\n", b""):
                i += 1
            continue
        j = i
        while not donnees[j:j + 1].isspace():
            j += 1
        jetons.append(donnees[i:j])
        i = j
    largeur, hauteur = int(jetons[1]), int(jetons[2])
    return largeur, hauteur, donnees[i + 1:i + 1 + largeur * hauteur]


def _lire_meta(chemin: Path):
    texte = chemin.read_text()
    resolution = float(texte.split("resolution:")[1].split()[0])
    origine = [float(v) for v in texte.split("origin:")[1].split("[")[1].split("]")[0].split(",")]
    return resolution, origine


def _carte():
    largeur, hauteur, pixels = _lire_pgm(CARTE_PGM)
    resolution, origine = _lire_meta(CARTE_YAML)
    libre = set()
    for ligne in range(hauteur):
        for colonne in range(largeur):
            occupation = (255 - pixels[ligne * largeur + colonne]) / 255.0
            if occupation <= 0.25:
                libre.add((colonne, ligne))
    return {"largeur": largeur, "hauteur": hauteur, "resolution": resolution,
            "origine": origine, "libre": libre}


def _cellule(carte, x, y):
    return (int(round((x - carte["origine"][0]) / carte["resolution"])),
            int(round(carte["hauteur"] - 1 - (y - carte["origine"][1]) / carte["resolution"])))


def _distance_obstacles(carte):
    """Distance (en cellules) à la première cellule non navigable, bord de carte compris."""
    largeur, hauteur = carte["largeur"], carte["hauteur"]
    infini = 10 ** 9
    distances = [[infini] * largeur for _ in range(hauteur)]
    file = deque()
    for ligne in range(hauteur):
        for colonne in range(largeur):
            if (colonne, ligne) not in carte["libre"] or colonne < 2 or ligne < 2 \
                    or colonne >= largeur - 2 or ligne >= hauteur - 2:
                distances[ligne][colonne] = 0
                file.append((colonne, ligne))
    while file:
        colonne, ligne = file.popleft()
        for dc, dl in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nc, nl = colonne + dc, ligne + dl
            if 0 <= nc < largeur and 0 <= nl < hauteur and distances[nl][nc] == infini:
                distances[nl][nc] = distances[ligne][colonne] + 1
                file.append((nc, nl))
    return distances


# ── 1. chargement et contrat de lecture ────────────────────────────────────
def test_le_catalogue_par_defaut_se_charge():
    catalogue = waypoints.charger()
    assert catalogue.frame == "map"
    assert catalogue.carte == "test_cartographie_apres_deplacement"
    assert len(catalogue.waypoints) >= 3
    assert all(-math.pi <= w.yaw <= math.pi for w in catalogue.waypoints.values())


def test_un_waypoint_connu_se_resout_en_pose():
    catalogue = waypoints.charger()
    pose = catalogue.resoudre("est")
    assert (pose.x, pose.y) == (5.30, 0.48)
    assert pose.yaw == pytest.approx(0.0)


def test_un_waypoint_inconnu_est_refuse_avec_la_liste():
    catalogue = waypoints.charger()
    with pytest.raises(waypoints.WaypointInconnu) as erreur:
        catalogue.resoudre("cuisine")
    message = str(erreur.value)
    assert "cuisine" in message
    for nom in catalogue.waypoints:
        assert nom in message, "le refus doit rappeler l'énumération praticable"


def test_les_coordonnees_libres_sont_refusees():
    catalogue = waypoints.charger()
    for interdit in ({"x": 1.0, "y": 2.0}, [1.0, 2.0], 42, None, "", "1.0,2.0", "est; 1 2"):
        with pytest.raises(ValueError):
            catalogue.resoudre(interdit)


# ── 2. cohérence avec la carte ──────────────────────────────────────────────
def test_chaque_waypoint_est_dans_une_cellule_libre_et_degagee():
    catalogue = waypoints.charger()
    carte = _carte()
    distances = _distance_obstacles(carte)
    for nom, waypoint in catalogue.waypoints.items():
        colonne, ligne = _cellule(carte, waypoint.x, waypoint.y)
        assert (colonne, ligne) in carte["libre"], f"{nom} hors de l'espace libre de la carte"
        degagement = distances[ligne][colonne] * carte["resolution"]
        assert degagement >= 0.40, f"{nom} trop pres d'un obstacle : {degagement:.2f} m"


def test_tous_les_waypoints_sont_dans_la_meme_composante_connexe():
    catalogue = waypoints.charger()
    carte = _carte()
    distances = _distance_obstacles(carte)
    largeur, hauteur = carte["largeur"], carte["hauteur"]
    # région praticable : au moins 0,30 m de dégagement, ce qui laisse passer un châssis de 20 cm
    praticable = {(c, l) for l in range(hauteur) for c in range(largeur)
                  if distances[l][c] * carte["resolution"] >= 0.30}
    premier = next(iter(catalogue.waypoints.values()))
    depart = _cellule(carte, premier.x, premier.y)
    assert depart in praticable, "le premier waypoint doit etre praticable"
    vus, file = {depart}, deque([depart])
    while file:
        colonne, ligne = file.popleft()
        for dc, dl in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            voisin = (colonne + dc, ligne + dl)
            if voisin in praticable and voisin not in vus:
                vus.add(voisin)
                file.append(voisin)
    for nom, waypoint in catalogue.waypoints.items():
        assert _cellule(carte, waypoint.x, waypoint.y) in vus, \
            f"{nom} est dans une zone non connexe : aucun chemin depuis {premier.nom}"


# ── 3. un catalogue malformé échoue au chargement ──────────────────────────
def _ecrire(tmp_path: Path, contenu: str) -> Path:
    chemin = tmp_path / "waypoints.yaml"
    chemin.write_text(contenu)
    return chemin


def _yaml_valide(x: str = "1.0", y: str = "2.0", yaw: str = "0.0",
                 extra: str = "") -> str:
    return (f"frame: map\ncarte: test\nwaypoints:\n"
            f"  a:\n    x: {x}\n    y: {y}\n    yaw: {yaw}\n{extra}")


@pytest.mark.parametrize("contenu, motif", [
    ("waypoints:\n  a: {x: 1.0, y: 2.0}\n", "frame"),
    ("frame: map\nwaypoints: {}\n", "waypoints"),
    ("frame: map\nwaypoints:\n  a: {x: 1.0}\n", "y"),
    (_yaml_valide(x=".nan"), "fini"),
    (_yaml_valide(y="250.0"), "borne"),
    # PyYAML lit `1e9` comme une chaîne (YAML 1.1 exige un point) : c'est refusé, mais pour le
    # bon motif — un type inattendu, pas une borne.
    (_yaml_valide(y="1e9"), "nombre"),
    (_yaml_valide(extra="  a: {x: 0.0, y: 0.0}\n"), "doublon"),
    (_yaml_valide(extra="  B: {x: 0.0, y: 0.0}\n"), "nom"),
    (_yaml_valide(extra="  b: {x: 0.0, y: 0.0, couleur: rouge}\n"), "inconnue"),
])
def test_un_catalogue_malforme_est_refuse_au_chargement(tmp_path, contenu, motif):
    chemin = _ecrire(tmp_path, contenu)
    with pytest.raises(waypoints.CatalogueInvalide) as erreur:
        waypoints.charger(chemin)
    assert motif in str(erreur.value).lower(), str(erreur.value)


def test_un_catalogue_absent_est_refuse(tmp_path):
    with pytest.raises(waypoints.CatalogueInvalide):
        waypoints.charger(tmp_path / "inexistant.yaml")
