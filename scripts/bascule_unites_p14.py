#!/usr/bin/python3
"""Reecrit les unites du robot vers `ros2 launch clawbot_bringup` (P14).

Chaque unite garde son durcissement et ses dependances : seule la ligne `ExecStart`
change (et l'accrochage, qui passe a `clawbot.target`). Les valeurs de politique de
redemarrage de REQ-OPS-010 sont ajoutees si elles manquent, jamais modifiees.

    /usr/bin/python3 scripts/bascule_unites_p14.py --verifier
    /usr/bin/python3 scripts/bascule_unites_p14.py
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SERVICES = RACINE / "services"
SYSTEMD = RACINE / "systemd"
ENV_FILE = "/home/jetson/clawbot/deploy/env/clawbot.env"

# unite -> fichier de lancement (None = hors cible ROS, laissee intacte)
BASCULE = {
    "ros2-driver-node.service": "base.launch.py",
    "clawbot-lidar.service": "lidar.launch.py",
    "ros2-hardware-service.service": "hardware.launch.py",
    "clawbot-ekf.service": "localization.launch.py",
    "clawbot-slam.service": "mapping.launch.py",
    "clawbot-description.service": "description.launch.py",
    "clawbot-safety-arbitrator.service": "safety.launch.py",
    "clawbot-capability-manager.service": "capabilities.launch.py",
    "clawbot-skill-server.service": "executive.launch.py",
    "clawbot-mission-executive.service": "mission.launch.py",
    "clawbot-director.service": "director.launch.py",
    "clawbot-sentinel.service": "sentinel.launch.py",
    "clawbot-health-monitor.service": "health.launch.py",
    "clawbot-wrist-camera.service": "wrist_camera.launch.py",
    "orbbec-camera.service": "depth_camera.launch.py",
    "clawbot-yolo.service": "detection.launch.py",
    "ros2-llm-bridge-cpp.service": "api.launch.py",
    "clawbot-arm-controller.service": "arm_controller.launch.py",
    "clawbot-move-group.service": "move_group.launch.py",
    "clawbot-nav2.service": "navigation.launch.py",
    "clawbot-joy-teleop.service": "teleop.launch.py",
}

# Unites qui sourcent un overlay vendor en plus de ROS : le fichier de lancement ne peut
# pas le faire, l'unite garde donc sa ligne `source` supplementaire.
OVERLAYS = {
    "ros2-hardware-service.service": "/home/jetson/yahboomcar_ros2_ws/yahboomcar_ws/install/setup.bash",
    "orbbec-camera.service": "/home/jetson/yahboomcar_ros2_ws/software/library_ws/install/setup.bash",
    "clawbot-lidar.service": None,
}

EXEC = ('ExecStart=/bin/bash -c "set +u; source /opt/ros/humble/setup.bash; '
        '{overlay}source /home/jetson/clawbot/install/setup.bash; set -u; '
        'exec ros2 launch clawbot_bringup {launch}"')


def chemin(unite: str) -> Path | None:
    for dossier in (SERVICES, SYSTEMD):
        candidat = dossier / unite
        if candidat.is_file():
            return candidat
    return None


def reecrire(texte: str, unite: str, launch: str) -> str:
    overlay = OVERLAYS.get(unite)
    ligne = EXEC.format(overlay=f"source {overlay}; " if overlay else "", launch=launch)

    # Remplace le bloc ExecStart (avec ses continuations) par une ligne unique.
    lignes = texte.splitlines()
    sortie, saute = [], False
    for ligne_courante in lignes:
        if ligne_courante.startswith("ExecStart="):
            saute = ligne_courante.rstrip().endswith("\\")
            sortie.append(ligne)
            continue
        if saute:
            saute = ligne_courante.rstrip().endswith("\\")
            continue
        sortie.append(ligne_courante)
    texte = "\n".join(sortie) + "\n"

    # Environnement : un seul fichier partage.
    if "EnvironmentFile=" not in texte:
        texte = re.sub(r"(?m)^\[Service\]\n", f"[Service]\nEnvironmentFile={ENV_FILE}\n", texte)
    # Politique de redemarrage (REQ-OPS-010), ajoutee si absente.
    for cle, valeur in (("StartLimitIntervalSec", "60"), ("StartLimitBurst", "5")):
        if not re.search(rf"(?m)^{cle}=", texte):
            texte = texte.replace("[Unit]\n", f"[Unit]\n{cle}={valeur}\n", 1)
    for cle, valeur in (("Restart", "on-failure"), ("RestartSec", "2"),
                        ("TimeoutStopSec", "10")):
        if not re.search(rf"(?m)^{cle}=", texte):
            texte = texte.replace("[Service]\n", f"[Service]\n{cle}={valeur}\n", 1)
    # Accrochage unique : la cible.
    texte = re.sub(r"(?m)^WantedBy=.*$", "WantedBy=clawbot.target", texte)
    return texte


def main(argv=None):
    import sys

    verifier = "--verifier" in (argv if argv is not None else sys.argv[1:])
    ecarts = []
    for unite, launch in sorted(BASCULE.items()):
        fichier = chemin(unite)
        if fichier is None:
            ecarts.append(f"{unite} : introuvable")
            continue
        nouveau = reecrire(fichier.read_text(encoding="utf-8"), unite, launch)
        if verifier:
            if fichier.read_text(encoding="utf-8") != nouveau:
                ecarts.append(f"{unite} : non bascule")
            continue
        fichier.write_text(nouveau, encoding="utf-8")
    if verifier:
        print("a jour" if not ecarts else "\n".join(ecarts))
        return 0 if not ecarts else 1
    print(f"{len(BASCULE)} unites reecrites vers ros2 launch clawbot_bringup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
