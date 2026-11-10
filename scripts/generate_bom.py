#!/usr/bin/env python3
"""Génère la nomenclature logicielle (BOM) du robot.

Sortie : `docs/knowledge-base/02_Software/bom_logiciel.md`.

Les versions sont lues sur le poste à l'exécution (métadonnées Python, dpkg, exécutables). Un
composant absent est écrit `absent` avec son incidence : la nomenclature sert aussi à savoir ce
qui manque, pas seulement ce qui est installé.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import time
from importlib import metadata
from pathlib import Path


def _iso8601(moment: time.struct_time | None = None) -> str:
    """ISO 8601 avec décalage horaire à deux points (+HH:MM), format exigé par le validateur OKF."""
    text = time.strftime("%Y-%m-%dT%H:%M:%S%z") if moment is None else time.strftime("%Y-%m-%dT%H:%M:%S%z", moment)
    return f"{text[:-2]}:{text[-2:]}" if len(text) >= 5 and text[-5] in "+-" else text
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "knowledge-base" / "02_Software" / "bom_logiciel.md"

#: (nom d'affichage, distribution, module, rôle, criticité)
PYTHON_PACKAGES: tuple[tuple[str, str, str, str, str], ...] = (
    ("mcp", "mcp", "mcp", "SDK Model Context Protocol : serveur et client du pont", "vital"),
    ("rclpy", "ros-humble-rclpy", "rclpy", "Client Python ROS 2 (fourni par apt, pas par pip)", "vital"),
    ("fastapi", "fastapi", "fastapi", "API HTTP du service matériel et de la chaîne YOLO", "vital"),
    ("uvicorn", "uvicorn", "uvicorn", "Serveur ASGI des mêmes API", "vital"),
    ("opencv-python", "opencv-python-headless", "cv2", "Traitement d'image, capture caméra", "vital"),
    ("numpy", "numpy", "numpy", "Calcul numérique, images et tenseurs", "vital"),
    ("torch", "torch", "torch", "Inférence YOLO sur GPU", "important"),
    ("ultralytics", "ultralytics", "ultralytics", "Chargeur de modèles YOLO", "important"),
    ("pyserial", "pyserial", "serial", "Liaison série vers la carte de commande", "vital"),
    ("PyYAML", "PyYAML", "yaml", "Configuration et frontmatter OKF", "important"),
    ("requests", "requests", "requests", "Appels HTTP sortants", "important"),
    ("httpx", "httpx", "httpx", "Client HTTP asynchrone des tests", "outillage"),
    ("pytest", "pytest", "pytest", "Exécution des suites de tests", "vital"),
    ("pytest-asyncio", "pytest-asyncio", "pytest_asyncio", "Tests asynchrones", "outillage"),
    ("pytest-timeout", "pytest-timeout", "pytest_timeout", "Bornage des tests", "outillage"),
    ("mkdocs-material", "mkdocs-material", "material", "Thème du site de documentation", "important"),
    ("pymdown-extensions", "pymdown-extensions", "pymdownx", "Extensions Markdown (mermaid, admonitions)", "important"),
)


def _package_version(distribution: str, module: str) -> str:
    """Version d'un composant Python : métadonnée pip, sinon paquet apt, sinon import."""
    for name in (distribution, distribution.replace("-", "_")):
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    if distribution.startswith("ros-"):
        count, version = _dpkg_version(distribution)
        if count:
            return f"{version} (apt)"
    try:
        __import__(module)
        return "installé (sans métadonnée)"
    except Exception:  # noqa: BLE001 - tout échec d'import vaut absence
        return "absent"


def _command_version(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        return "absent"
    try:
        output = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        text = (output.stdout or "") + (output.stderr or "")
        match = re.search(r"\d+(?:\.\d+)+", text)
        return match.group(0) if match else "installé"
    except (subprocess.TimeoutExpired, OSError):
        return "illisible"


def _dpkg_version(pattern: str) -> tuple[int, str]:
    """Retourne (nombre de paquets, version du paquet exact s'il existe)."""
    try:
        listing = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\n", pattern],
            capture_output=True, text=True, timeout=20, check=False,
        ).stdout
    except (subprocess.TimeoutExpired, OSError):
        return 0, "illisible"
    lines = [line for line in listing.splitlines() if line.strip()]
    return len(lines), (lines[0].split("\t")[1] if lines else "absent")


def _os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            key, _, value = line.partition("=")
            values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values


def main() -> int:
    stamp = _iso8601()
    os_release = _os_release()
    l4t = "Donnée non disponible"
    l4t_path = Path("/etc/nv_tegra_release")
    if l4t_path.exists():
        l4t = l4t_path.read_text().strip().splitlines()[0].replace("# ", "")
    ros_packages, ros_version = _dpkg_version("ros-humble-*")
    kernel = Path("/proc/sys/kernel/osrelease").read_text().strip()

    lines = [
        "---",
        'title: "Nomenclature logicielle (BOM) du robot"',
        f'date: "{stamp}"',
        'author: "Hermes Agent"',
        "tags: [software, bom, inventaire, dependances, versions]",
        "status: actif",
        "generated: true",
        "---",
        "",
        "# Nomenclature logicielle (BOM)",
        "",
        f"Relevé le {stamp} par `scripts/generate_bom.py`. Toute ligne absente du poste est écrite "
        "`absent` : une nomenclature qui ne liste que l'installé ne dit pas ce qui manque.",
        "",
        "## 1. Socle système",
        "",
        "| Composant | Version | Source |",
        "|---|---|---|",
        f"| Système d'exploitation | {os_release.get('PRETTY_NAME', 'Donnée non disponible')} | `/etc/os-release` |",
        f"| Noyau | {kernel} | `uname -r` |",
        f"| Paquet NVIDIA L4T | {l4t} | `/etc/nv_tegra_release` |",
        f"| Python | {platform.python_version()} | exécutable `/usr/bin/python3` |",
        f"| Node.js | {_command_version(['node', '--version'])} | paquet système |",
        f"| ROS 2 | Humble ({ros_packages} paquets `ros-humble-*`) | apt, `/opt/ros/humble` |",
        "",
        "## 2. Bibliothèques Python",
        "",
        "| Composant | Paquet | Version | Rôle | Criticité |",
        "|---|---|---|---|---|",
    ]
    for display, distribution, module, role, criticality in PYTHON_PACKAGES:
        version = _package_version(distribution, module)
        lines.append(f"| {display} | `{distribution}` | {version} | {role} | {criticality} |")

    lines += [
        "",
        "## 3. Paquets ROS 2 utilisés par le robot",
        "",
        "| Paquet | Version | Rôle |",
        "|---|---|---|",
    ]
    for package, role in (
        ("ros-humble-desktop", "Métapaquet de la distribution"),
        ("ros-humble-rosbridge-suite", "Passerelle WebSocket `/rosbridge_websocket`"),
        ("ros-humble-image-transport", "Transport des images caméra"),
        ("ros-humble-cv-bridge", "Conversion images ↔ OpenCV"),
        ("ros-humble-tf2-ros", "Transformations entre cadres"),
        ("ros-humble-rosbag2", "Enregistrement et relecture de topics"),
        ("ros-humble-nav2-bringup", "Pile de navigation (installée, non déployée)"),
        ("ros-humble-diagnostic-aggregator", "Agrégation de diagnostics"),
    ):
        count, version = _dpkg_version(package)
        lines.append(f"| `{package}` | {version if count else 'absent'} | {role} |")

    lines += [
        "",
        "## 4. Outils en ligne de commande",
        "",
        "| Outil | Version | Usage |",
        "|---|---|---|",
        f"| `git` | {_command_version(['git', '--version'])} | Versionnement des sources et de la documentation |",
        f"| `colcon` | {_command_version(['colcon', 'version'])} | Construction des espaces de travail ROS 2 |",
        f"| `ros2` | {_command_version(['ros2', '--version'])} | Inspection du graphe et exécution des nœuds |",
        f"| `jq` | {_command_version(['jq', '--version'])} | Lecture JSON dans les scripts d'exploitation |",
        f"| `dot` (graphviz) | {_command_version(['dot', '-V'])} | Rendu de graphes hors Mermaid |",
        f"| `v4l2-ctl` | {_command_version(['v4l2-ctl', '--version'])} | Contrôle des périphériques vidéo |",
        f"| `mkdocs` | {_command_version(['mkdocs', '--version'])} | Construction du site de documentation |",
        f"| `gh` | {_command_version(['gh', '--version'])} | Gestion des tickets et PR GitHub |",
        f"| `frama-c` | {_command_version(['frama-c', '-version'])} | Preuve formelle C (skills ACSL installés, non exécutables) |",
        "",
        "## 5. Incidences des absences",
        "",
        "| Absence | Incidence | Contournement en place |",
        "|---|---|---|",
        "| `gh` | pas de gestion de tickets GitHub en ligne de commande | suivi local dans `.scratch/<fonctionnalite>/issues/` |",
        "| `frama-c`, `why3`, `z3`, `coqc` | les skills de méthodes formelles sont installés mais ne peuvent pas prouver | analyse manuelle ; installation d'opam à prévoir |",
        "| `ros-humble-nav2-bringup` si absent | aucune navigation autonome possible | trajectoires directes par le nœud de conduite |",
        "",
        "## 6. Regénérer cette page",
        "",
        "```bash",
        "cd /home/jetson/clawbot",
        "PYTHONPATH=$PWD python3 scripts/generate_bom.py",
        "```",
        "",
        "## 7. Voir aussi",
        "",
        "- [[jetson_orin_nx]] — plateforme matérielle et système",
        "- [[systemd_robot_services]] — unités qui exécutent ces composants",
        "- [[ros2_graph_clawbot]] — nœuds et topics produits",
        "- [[etat_noeuds_et_services]] — état d'exécution au dernier relevé",
        "",
    ]

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)} : {len(PYTHON_PACKAGES)} bibliothèques Python, "
          f"{ros_packages} paquets ROS 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
