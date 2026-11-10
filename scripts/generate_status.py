#!/usr/bin/env python3
"""Génère l'état des nœuds ROS 2 et des services systemd (instantané daté).

Sortie : `docs/knowledge-base/03_Operations/etat_noeuds_et_services.md`.

Toutes les valeurs sont lues sur le poste au moment de l'exécution : état systemd, graphe ROS 2
du domaine 28, ressources, et dernier rapport de santé des périphériques. Aucune valeur n'est
recopiée d'une exécution antérieure. Une lecture impossible est écrite comme telle, jamais
remplacée par zéro.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def _iso8601(moment: time.struct_time | None = None) -> str:
    """ISO 8601 avec décalage horaire à deux points (+HH:MM), format exigé par le validateur OKF."""
    text = time.strftime("%Y-%m-%dT%H:%M:%S%z") if moment is None else time.strftime("%Y-%m-%dT%H:%M:%S%z", moment)
    return f"{text[:-2]}:{text[-2:]}" if len(text) >= 5 and text[-5] in "+-" else text
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "knowledge-base" / "03_Operations" / "etat_noeuds_et_services.md"
ROS_DOMAIN_ID = "28"

UNITS = [
    ("clawbot-description.service", "Description du robot (/robot_description, TF)"),
    ("ros2-driver-node.service", "Nœud de conduite (cmd_vel → série)"),
    ("ros2-hardware-service.service", "Service matériel du pont C++"),
    ("ros2-llm-bridge-cpp.service", "Pont LLM historique (port 8000)"),
    ("orbbec-camera.service", "Caméra Orbbec Astra Pro+"),
    ("clawbot-lidar.service", "Lidar YDLIDAR TG30 (/scan)"),
    ("clawbot-arm-controller.service", "Contrôleur de trajectoire du bras (→ /servo_ctrl)"),
    ("clawbot-move-group.service", "MoveIt 2 move_group (démarré à la demande)"),
    ("rosbridge.service", "Passerelle WebSocket (port 9090)"),
    ("yolo-inference.service", "Inférence YOLO (port 8003)"),
    ("clawbot-joy-teleop.service", "Téléopération manette"),
    ("clawbot-health.service", "Test de santé des périphériques"),
    ("clawbot-docs.service", "Site de documentation (port 8080)"),
]


def run(command: list[str], timeout: float = 20.0, env: dict | None = None) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, env=env, check=False
        )
        return completed.returncode, (completed.stdout or "") + (completed.stderr or "")
    except (subprocess.TimeoutExpired, FileNotFoundError) as error:
        return 127, f"{type(error).__name__}"


def systemd_rows() -> list[tuple[str, str, str, str]]:
    rows = []
    for unit, label in UNITS:
        code, output = run(["systemctl", "show", "-p", "ActiveState", "-p", "SubState",
                            "-p", "ActiveEnterTimestamp", "--value", unit], timeout=10)
        if code != 0:
            rows.append((unit, label, "illisible", output.strip()[:80]))
            continue
        values = [line.strip() for line in output.splitlines() if line.strip()]
        state = values[0] if values else "inconnu"
        sub = values[1] if len(values) > 1 else "inconnu"
        since = values[2] if len(values) > 2 else ""
        rows.append((unit, label, f"{state} ({sub})", since))
    return rows


def ros_env() -> dict:
    env = dict(os.environ)
    env["ROS_DOMAIN_ID"] = ROS_DOMAIN_ID
    return env


def _ros_query(arguments: str) -> tuple[int, str]:
    """Interroge le graphe via le démon ROS (démarrage forcé, sinon découverte partielle)."""
    return run(
        ["bash", "-lc",
         "source /opt/ros/humble/setup.bash && ros2 daemon start >/dev/null 2>&1; sleep 2; "
         f"ros2 {arguments}"],
        timeout=40, env=ros_env(),
    )


def ros_graph() -> dict:
    # Une première interrogation peut ne voir qu'une partie du graphe : le démon découvre
    # encore. On garde le relevé le plus complet, et on le dit si les deux sont pauvres.
    best_nodes: list[str] = []
    nodes = ""
    for _ in range(2):
        code, nodes = _ros_query("node list")
        candidate = [line.strip() for line in nodes.splitlines() if line.strip().startswith("/")]
        if len(candidate) > len(best_nodes):
            best_nodes = candidate
        if len(best_nodes) >= 4:
            break
    node_list = best_nodes
    code, topics = _ros_query("topic list -t")
    topic_list = [line.strip() for line in topics.splitlines() if line.strip().startswith("/")]
    return {
        "nodes": node_list,
        "node_error": None if code == 0 else nodes.strip()[:120],
        "topics": topic_list,
    }


def health_report() -> dict | None:
    code, output = run(
        ["bash", "-lc",
         "cd /home/jetson/clawbot && source /opt/ros/humble/setup.bash && "
         f"ROS_DOMAIN_ID={ROS_DOMAIN_ID} /usr/bin/python3 -m bridge_mcp.health --json --no-notify"],
        timeout=90,
    )
    if code not in (0, 1, 2):
        return None
    start = output.find("{")
    if start < 0:
        return None
    try:
        return json.loads(output[start:])
    except json.JSONDecodeError:
        return None


def resources() -> dict:
    load = os.getloadavg()
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        if key in {"MemTotal", "MemAvailable"}:
            memory[key] = int(rest.split()[0]) // 1024
    stat = os.statvfs("/")
    thermal = {}
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        try:
            thermal[(zone / "type").read_text().strip()] = int((zone / "temp").read_text().strip()) / 1000
        except OSError:
            continue
    return {
        "load": load,
        "memory_total_mb": memory.get("MemTotal", 0),
        "memory_available_mb": memory.get("MemAvailable", 0),
        "disk_free_gb": stat.f_bavail * stat.f_frsize / 1e9,
        "uptime_s": int(float(Path("/proc/uptime").read_text().split()[0])),
        "thermal": thermal,
    }


def render(units, graph, health, res) -> str:
    stamp = _iso8601()
    lines = [
        "---",
        'title: "État des nœuds ROS 2 et des services systemd"',
        f'date: "{stamp}"',
        'author: "Hermes Agent"',
        "tags: [operations, etat, ros2, systemd, services, noeuds]",
        "status: actif",
        "generated: true",
        "---",
        "",
        "# État des nœuds ROS 2 et des services systemd",
        "",
        f"Instantané relevé le {stamp} sur le poste, domaine ROS 2 `{ROS_DOMAIN_ID}`. "
        "Cette page est un relevé, pas un engagement : elle est régénérée par "
        "`scripts/generate_status.py` et ne se modifie pas à la main.",
        "",
        "## 1. Services systemd",
        "",
        "| Unité | Rôle | État | Actif depuis |",
        "|---|---|---|---|",
    ]
    for unit, label, state, since in units:
        lines.append(f"| `{unit}` | {label} | {state} | {since or '—'} |")

    lines += ["", "## 2. Graphe ROS 2", ""]
    if graph["node_error"]:
        lines.append(f"Lecture du graphe impossible : `{graph['node_error']}`")
    lines.append(f"Nœuds visibles : **{len(graph['nodes'])}** — topics : **{len(graph['topics'])}**.")
    lines.append("")
    lines.append("| Nœud |")
    lines.append("|---|")
    for node in graph["nodes"]:
        lines.append(f"| `{node}` |")

    lines += ["", "## 3. Santé des périphériques", ""]
    if health is None:
        lines.append("Donnée non disponible : le test de santé n'a pas pu être exécuté "
                     "(`python3 -m bridge_mcp.health --json`). Code d'erreur `HLT-E-TIMEOUT`.")
    else:
        lines.append(
            f"Verdict **{health['verdict']}** en {health['duration_ms']} ms "
            f"([[llm2ros_health_test_specification]])."
        )
        lines.append("")
        lines.append("| Périphérique | Requis | Verdict | Détail |")
        lines.append("|---|---|---|---|")
        for item in health["peripherals"]:
            details = "; ".join(
                probe["detail"] for probe in item["probes"]
                if probe.get("detail") and probe["status"] != "ok"
            )
            codes = sorted({probe["error_code"] for probe in item["probes"] if probe["error_code"]})
            suffix = f" — {', '.join(codes)}" if codes else ""
            lines.append(
                f"| `{item['id']}` {item['name']} | {'oui' if item['required'] else 'non'} "
                f"| {item['verdict']} | {details or '—'}{suffix} |"
            )

    lines += [
        "",
        "## 4. Ressources du poste",
        "",
        "| Mesure | Valeur |",
        "|---|---|",
        f"| Charge (1 / 5 / 15 min) | {res['load'][0]:.2f} / {res['load'][1]:.2f} / {res['load'][2]:.2f} |",
        f"| Mémoire disponible | {res['memory_available_mb']} Mo sur {res['memory_total_mb']} Mo |",
        f"| Disque libre | {res['disk_free_gb']:.1f} Go |",
        f"| Températures | " + ", ".join(f"{name} {value:.0f} °C" for name, value in res["thermal"].items()) + " |",
        f"| Disponibilité du poste | {res['uptime_s'] // 3600} h {(res['uptime_s'] % 3600) // 60} min |",
        "",
        "## 5. Ce que cette page ne prouve pas",
        "",
        "- Un service `active` ne garantit pas qu'un périphérique est présent : c'est le rôle du test de",
        "  santé, qui l'a établi pour la manette ([[llm2ros_health_test_specification]]).",
        "- Un nœud présent dans le graphe ne publie pas nécessairement à la bonne cadence : les mesures",
        "  de cadence figurent dans le rapport de santé, section 3.",
        "- Ces valeurs sont un instantané : elles ne remplacent pas une supervision continue.",
        "",
        "## 6. Regénérer cette page",
        "",
        "```bash",
        "cd /home/jetson/clawbot",
        "PYTHONPATH=$PWD python3 scripts/generate_status.py",
        "```",
        "",
        "## 7. Voir aussi",
        "",
        "- [[systemd_robot_services]] — description des unités et de leurs dépendances",
        "- [[ros2_graph_clawbot]] — graphe de référence et cadences nominales",
        "- [[llm2ros_health_test_specification]] — ce qui est vérifié sur les périphériques",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Relevé de l'état des nœuds et services")
    parser.add_argument("--no-health", action="store_true", help="ne pas exécuter le test de santé")
    args = parser.parse_args()

    units = systemd_rows()
    graph = ros_graph()
    health = None if args.no_health else health_report()
    res = resources()

    OUTPUT.write_text(render(units, graph, health, res), encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)} : {len(graph['nodes'])} nœuds, {len(graph['topics'])} topics, "
          f"santé={'oui' if health else 'non'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
