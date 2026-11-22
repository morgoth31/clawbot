"""C02 — la vérification doit construire, linter et contrôler ses cliquets.

Quatre propriétés, une par exigence :

1. `--self-test` annonce les étapes, `build` comprise quand `--build` est passé
   (REQ-TEST-010) ;
2. la construction propre ne dépend ni de `$AMENT_PREFIX_PATH` ni d'un
   `install/setup.bash` : elle tourne sous `env -i` (REQ-TEST-010) ;
3. une dépendance non déclarée fait échouer `--build` (REQ-TEST-010) ;
4. l'absence d'outil de lint fait échouer l'étape au lieu d'avertir (REQ-TEST-011),
   et un cliquet qui monte par rapport à `main` fait échouer l'étape `cliquets`
   (REQ-TEST-013).
"""

import os
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
CHECK = RACINE / "scripts" / "check.sh"


def _check(script, args, env=None, cwd=None, timeout=900):
    """Lance check.sh avec un environnement minimal et rend le résultat complet."""
    base = {
        "HOME": os.environ.get("HOME", "/home/jetson"),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C.UTF-8",
        "ROS_DOMAIN_ID": "98",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    if env:
        base.update(env)
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True, text=True, timeout=timeout,
        env=base, cwd=str(cwd or script.parent.parent),
    )


@pytest.mark.req("REQ-TEST-010")
def test_self_test_annonce_les_etapes_et_build():
    resultat = _check(CHECK, ["--self-test"])
    assert resultat.returncode == 0, resultat.stderr
    for etape in ("lint", "unit", "trace", "doublons", "interdits", "cliquets"):
        assert etape in resultat.stdout, f"étape {etape} non annoncée :\n{resultat.stdout}"

    avec_build = _check(CHECK, ["--self-test", "--build"])
    assert avec_build.returncode == 0, avec_build.stderr
    assert "build" in avec_build.stdout, (
        f"--build doit ajouter l'étape build :\n{avec_build.stdout}")


@pytest.mark.req("REQ-TEST-010")
def test_la_construction_propre_ne_depend_pas_de_l_environnement_courant():
    source = CHECK.read_text(encoding="utf-8")
    lignes = source.splitlines()
    index = next((i for i, l in enumerate(lignes)
                  if "colcon build" in l and "source /opt/ros/humble" in l), None)
    assert index is not None, "aucune commande colcon build dans check.sh"
    # La commande est répartie sur plusieurs lignes (continuations) : on lit le bloc.
    ligne = " ".join(lignes[index:index + 6])
    assert "env -i" in source, "la construction doit tourner sous `env -i`"
    assert "install/setup.bash" not in ligne, (
        "la construction ne doit pas sourcer install/setup.bash (elle masque les "
        f"dépendances manquantes) : {ligne.strip()}")
    assert "/opt/ros/humble/setup.bash" in ligne, (
        f"la construction doit se limiter à l'underlay ROS : {ligne.strip()}")


@pytest.mark.integration
@pytest.mark.req("REQ-TEST-010")
def test_build_echoue_sur_une_dependance_non_declaree(tmp_path):
    """Deux paquets ament_cmake : `aapp` appelle find_package(zbib) sans le déclarer."""
    (tmp_path / "requirements").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "aapp").mkdir()
    (tmp_path / "zbib").mkdir()
    (tmp_path / "scripts" / "check.sh").write_text(
        CHECK.read_text(encoding="utf-8"), encoding="utf-8")
    _ = (tmp_path / "requirements" / ".untraced_baseline").write_text("0\n")

    gabarit = """<?xml version="1.0"?>
<package format="3">
  <name>{nom}</name>
  <version>0.0.1</version>
  <description>paquet de test</description>
  <maintainer email="t@example.com">t</maintainer>
  <license>Apache-2.0</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <export><build_type>ament_cmake</build_type></export>
</package>
"""
    (tmp_path / "zbib" / "package.xml").write_text(gabarit.format(nom="zbib"))
    (tmp_path / "zbib" / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.8)\n"
        "project(zbib)\n"
        "find_package(ament_cmake REQUIRED)\n"
        "install(FILES ${CMAKE_CURRENT_SOURCE_DIR}/zbibConfig.cmake\n"
        "        DESTINATION share/zbib/cmake)\n"
        "ament_package()\n")
    (tmp_path / "zbib" / "zbibConfig.cmake").write_text(
        "# marqueur de configuration de zbib\n")

    # `aapp` trie avant `zbib` : colcon le configure le premier et échoue.
    (tmp_path / "aapp" / "package.xml").write_text(gabarit.format(nom="aapp"))
    (tmp_path / "aapp" / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.8)\n"
        "project(aapp)\n"
        "find_package(ament_cmake REQUIRED)\n"
        "find_package(zbib REQUIRED)\n"
        "ament_package()\n")

    resultat = _check(tmp_path / "scripts" / "check.sh", ["--build", "--etape", "build"],
                      cwd=tmp_path)
    assert resultat.returncode != 0, (
        "check.sh --build a réussi alors que aapp trouve zbib sans le déclarer :\n"
        + resultat.stdout + resultat.stderr)
    assert "zbib" in (resultat.stdout + resultat.stderr), (
        "l'échec doit nommer le paquet manquant :\n" + resultat.stdout + resultat.stderr)


@pytest.mark.req("REQ-TEST-011")
def test_lint_echoue_si_l_outil_manque(tmp_path):
    # flake8 est fourni par le paquet système python3-flake8 : il reste importable même
    # avec un PATH nu. Le seul environnement sans outil est un python qui n'a ni
    # dist-packages ni site-packages — un venv vide fait cela, sans installer quoi que ce soit.
    resultat = _check(CHECK, ["--etape", "lint"],
                      env={"PATH": "/usr/bin:/bin", "CLAWBOT_LINT_SANS_OUTIL": "1"})
    assert resultat.returncode != 0, (
        "l'étape lint doit échouer quand aucun outil n'est disponible, pas avertir :\n"
        + resultat.stdout + resultat.stderr)
    sortie = resultat.stdout + resultat.stderr
    assert "aucun outil de lint" in sortie or "flake8" in sortie, (
        "le message doit nommer l'outil manquant :\n" + sortie)


@pytest.mark.req("REQ-TEST-013")
def test_cliquets_refusent_une_hausse_par_rapport_a_main(tmp_path):
    """Un cliquet plus haut que sur `main` doit faire échouer l'étape."""
    (tmp_path / "requirements").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check.sh").write_text(
        CHECK.read_text(encoding="utf-8"), encoding="utf-8")
    cliquet = tmp_path / "requirements" / ".untraced_baseline"

    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True,
                              text=True, check=True)

    cliquet.write_text("352\n")
    git("init", "-q", "-b", "main")
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "add", "-A")
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "base")
    git("switch", "-q", "-c", "branche")
    cliquet.write_text("400\n")

    resultat = _check(tmp_path / "scripts" / "check.sh", ["--etape", "cliquets"], cwd=tmp_path)
    assert resultat.returncode != 0, (
        "un cliquet passé de 352 (main) à 400 doit être refusé :\n"
        + resultat.stdout + resultat.stderr)
    assert ".untraced_baseline" in (resultat.stdout + resultat.stderr)

    # Et la valeur égale ou inférieure reste acceptée.
    cliquet.write_text("352\n")
    resultat = _check(tmp_path / "scripts" / "check.sh", ["--etape", "cliquets"], cwd=tmp_path)
    assert resultat.returncode == 0, (
        "un cliquet inchangé doit passer :\n" + resultat.stdout + resultat.stderr)
