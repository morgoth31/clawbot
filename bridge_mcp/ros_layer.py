"""Couche ROS 2 du serveur MCP — mesures réelles, jamais de valeur inventée.

Les outils du pont déléguaient tous à `not_wired`. Ce module fournit la couche basse :
il interroge le graphe ROS 2 (CLI `ros2`, domaine du robot) et n'invente rien. Trois
exceptions typées en sortent, traduites en codes MCP par `tools.py` :

    RosUnavailable -> MCP-E-PREREQ   (ROS 2 absent, nœud inconnu, service muet)
    RosInvalid     -> MCP-E-ARG      (nom de topic/nœud/action mal formé)
    RosTimeout     -> MCP-E-TIMEOUT  (mesure non terminée dans le délai)

Sécurité : aucun argument n'est concaténé sans validation ; les noms doivent respecter
`NAME_RE` et les valeurs d'action sont bornées dans `limits.py` avant appel.
"""

from __future__ import annotations

import json
import os
import re
import selectors
import shlex
import subprocess
import time
from pathlib import Path

ROS_SETUP = "/opt/ros/humble/setup.bash"
REPO_ROOT = Path(__file__).resolve().parents[1]
DIRECTOR_SERVICE_TIMEOUT_S = 8.0
NAME_RE = re.compile(r"^/?[A-Za-z0-9_][A-Za-z0-9_./-]*$")

#: actions autorisées à recevoir un objectif, avec leur type et l'ordre des articulations
ACTION_SPECS = {
    "/arm_controller/follow_joint_trajectory": {
        "type": "control_msgs/action/FollowJointTrajectory",
        "joints": ["arm_joint1", "arm_joint2", "arm_joint3", "arm_joint4", "arm_joint5"],
        "bounds_rad": (-1.5708, 3.14159),
    },
    "/grip_controller/follow_joint_trajectory": {
        "type": "control_msgs/action/FollowJointTrajectory",
        "joints": ["grip_joint"],
        "bounds_rad": (-1.54, 0.0),
    },
}


class RosUnavailable(RuntimeError):
    """La couche ROS 2 ne répond pas ou l'objet visé est inconnu."""


class RosInvalid(ValueError):
    """Argument refusé avant tout appel au système."""


class RosTimeout(RuntimeError):
    """Mesure interrompue faute de réponse dans le délai imparti."""


class RosLayer:
    """Accès au graphe ROS 2 du robot, sans processus persistant."""

    def __init__(self, domain_id: str | None = None, timeout: float = 20.0):
        self.domain_id = str(domain_id or os.environ.get("ROS_DOMAIN_ID", "28"))
        self.timeout = timeout

    # ── exécution ─────────────────────────────────────────────────────────
    def _env(self):
        return dict(os.environ, ROS_DOMAIN_ID=self.domain_id)

    def _command(self, args):
        if not all(isinstance(item, str) and item for item in args):
            raise RosInvalid(f"arguments invalides : {args!r}")
        return f"source {ROS_SETUP} >/dev/null 2>&1 && " + " ".join(shlex.quote(a) for a in args)

    def _run(self, args, timeout=None):
        """Commande courte, sortie complète."""
        try:
            proc = subprocess.run(["bash", "-c", self._command(args)],
                                  capture_output=True, text=True, env=self._env(),
                                  timeout=timeout or self.timeout)
        except FileNotFoundError as exc:
            raise RosUnavailable(f"bash introuvable : {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RosTimeout(f"délai dépassé : {' '.join(args)}") from exc
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "").strip().splitlines()
            raise RosUnavailable(message[-1] if message else f"code {proc.returncode}")
        return proc.stdout

    def _run_for(self, args, seconds):
        """Commande continue (ex. `topic hz`) lue pendant N secondes puis interrompue."""
        try:
            proc = subprocess.Popen(["bash", "-c", self._command(args)],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, env=self._env())
        except FileNotFoundError as exc:
            raise RosUnavailable(f"bash introuvable : {exc}") from exc
        lines = []
        deadline = time.time() + seconds
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        try:
            while time.time() < deadline:
                events = selector.select(timeout=min(0.2, max(0.0, deadline - time.time())))
                if not events:
                    continue
                line = proc.stdout.readline()
                if not line:
                    break
                lines.append(line)
        finally:
            selector.close()
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        return "".join(lines)

    @staticmethod
    def _check_name(value: str, kind: str) -> str:
        if not value or not NAME_RE.match(value):
            raise RosInvalid(f"{kind} invalide : {value!r}")
        return value

    # ── lecture du graphe ─────────────────────────────────────────────────
    def graph_snapshot(self, include_qos: bool = True) -> dict:
        """Nœuds et topics du domaine, avec types (et compteurs si demandé)."""
        nodes = [line.strip() for line in self._run(["ros2", "node", "list"]).splitlines() if line.strip()]
        topics = []
        for line in self._run(["ros2", "topic", "list", "-t"]).splitlines():
            match = re.match(r"^(\S+)\s+\[(.+)\]$", line.strip())
            if match:
                topics.append({"name": match.group(1), "type": match.group(2)})
        if not nodes and not topics:
            raise RosUnavailable(
                f"graphe vide sur le domaine {self.domain_id} : ROS 2 est-il lancé, "
                "et le domaine est-il le bon ?")
        payload = {
            "domain_id": self.domain_id,
            "nodes": sorted(nodes),
            "node_count": len(nodes),
            "topics": topics,
            "topic_count": len(topics),
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        if include_qos:
            payload["qos_requested"] = True
            payload["qos_note"] = ("QoS détaillée non collectée ici : utiliser topic_stats "
                                   "ou `ros2 topic info -v` pour un topic précis")
        return payload

    def topic_stats(self, topic: str, window_s: int = 5) -> dict:
        """Éditeurs, abonnés et cadence mesurée d'un topic."""
        self._check_name(topic, "topic")
        info = self._run(["ros2", "topic", "info", topic])
        publishers = re.search(r"Publisher count:\s*(\d+)", info)
        subscribers = re.search(r"Subscription count:\s*(\d+)", info)
        window = max(2, min(int(window_s), 30))
        output = self._run_for(["ros2", "topic", "hz", topic, "--window", "20"], window)
        rate = re.search(r"average rate:\s*([0-9.]+)", output)
        messages = re.search(r"window:\s*(\d+)", output)
        return {
            "topic": topic,
            "publishers": int(publishers.group(1)) if publishers else None,
            "subscribers": int(subscribers.group(1)) if subscribers else None,
            "rate_hz": float(rate.group(1)) if rate else None,
            "messages_seen": int(messages.group(1)) if messages else 0,
            "window_s": window,
            "verdict": "ok" if rate else "aucun message pendant la fenêtre",
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

    def tf_snapshot(self, root: str = "base_link", depth: int = 3) -> dict:
        """Arêtes TF observées sur /tf_static et /tf."""
        self._check_name(root, "root")
        edges = set()
        for topic in ("/tf_static", "/tf"):
            text = self._run_for(["ros2", "topic", "echo", topic], 3.0)
            # `ros2 topic echo` sort les champs header.frame_id puis child_frame_id
            for match in re.finditer(
                    r"frame_id:\s*(\S+)[\s\S]{0,160}?child_frame_id:\s*(\S+)", text):
                parent, child = match.group(1), match.group(2)
                if parent.startswith("frame_id:"):
                    continue
                edges.add((parent, child))
        if not edges:
            raise RosUnavailable("aucune arête TF lue : robot_state_publisher est-il actif ?")
        frames = sorted({frame for pair in edges for frame in pair})
        return {
            "root_requested": root,
            "edges": [{"parent": a, "child": b} for a, b in sorted(edges)],
            "edge_count": len(edges),
            "frames": frames,
            "depth": int(depth),
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

    def param_get(self, node: str, name: str) -> dict:
        """Valeur d'un paramètre d'un nœud vivant."""
        self._check_name(node, "node")
        self._check_name(name, "paramètre")
        output = self._run(["ros2", "param", "get", node, name]).strip()
        match = re.search(r"value is:\s*(.+)$", output, re.M)
        if not match:
            raise RosUnavailable(f"réponse inattendue pour {node}.{name} : {output[:200]}")
        return {"node": node, "name": name, "value": match.group(1).strip(),
                "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    def param_list(self, node: str) -> dict:
        """Paramètres déclarés par un nœud vivant."""
        self._check_name(node, "node")
        names = [line.strip() for line in self._run(["ros2", "param", "list", node]).splitlines() if line.strip()]
        if not names:
            raise RosUnavailable(f"aucun paramètre lisible sur {node}")
        return {"node": node, "parameters": names, "count": len(names),
                "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    def goal_list(self) -> dict:
        """Actions disponibles sur le domaine."""
        output = self._run_for(["ros2", "action", "list", "-t"], 4.0)
        actions = []
        for line in output.splitlines():
            match = re.match(r"^(\S+)\s+\[(.+)\]$", line.strip())
            if match:
                actions.append({"action": match.group(1), "type": match.group(2)})
        if not actions:
            output = self._run_for(["ros2", "action", "list"], 4.0)
            actions = [{"action": line.strip(), "type": None} for line in output.splitlines() if line.strip()]
        return {"actions": actions, "count": len(actions),
                "note": "les objectifs en cours ne sont pas interrogeables sans introspection d'action",
                "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    # ── intervention ──────────────────────────────────────────────────────
    def director_command(self, request: dict, timeout: float | None = None) -> dict:
        """Une opération sur le directeur S1, via son service /director/command.

        Le pont n'embarque pas de contexte rclpy : il lance `bridge_mcp.director_client`
        (JSON sur stdin, JSON sur stdout). `ros2 service call` est écarté : le CLI réinterprète
        l'argument en YAML et mange les guillemets du JSON.
        """
        if not isinstance(request, dict) or not request.get("op"):
            raise RosInvalid("requete directeur : objet avec op attendu")
        delai = float(timeout or min(self.timeout, DIRECTOR_SERVICE_TIMEOUT_S))
        commande = (f"source {ROS_SETUP} >/dev/null 2>&1 && cd {shlex.quote(str(REPO_ROOT))} "
                    "&& source install/setup.bash && exec python3 -m bridge_mcp.director_client")
        env = dict(self._env(), DIRECTOR_CLIENT_TIMEOUT_S=f"{delai:g}")
        try:
            proc = subprocess.run(["bash", "-c", commande],
                                  input=json.dumps(request, ensure_ascii=False),
                                  capture_output=True, text=True, env=env, timeout=delai + 10.0)
        except FileNotFoundError as exc:
            raise RosUnavailable(f"bash introuvable : {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RosTimeout(f"directeur muet au-dela de {delai + 10.0:g} s") from exc

        try:
            reponse = json.loads(proc.stdout)
        except ValueError as exc:
            message = (proc.stderr or proc.stdout or "").strip().splitlines()
            raise RosUnavailable(
                message[-1] if message else f"reponse illisible (code {proc.returncode})") from exc
        if proc.returncode == 3:
            raise RosUnavailable(reponse.get("reason") or "service /director/command absent")
        if proc.returncode == 4:
            raise RosTimeout(reponse.get("reason") or "directeur muet")
        if proc.returncode != 0:
            raise RosUnavailable(reponse.get("reason") or f"code {proc.returncode}")
        if not isinstance(reponse, dict) or "status" not in reponse:
            raise RosUnavailable(f"reponse du directeur sans statut : {str(reponse)[:200]}")
        return reponse

    def safety_stop(self) -> dict:
        """Vitesse nulle publiée sur /cmd_vel ; l'arrêt physique reste requis pour le bras."""
        published = 0
        for _ in range(3):
            self._run(["ros2", "topic", "pub", "--once", "/cmd_vel",
                       "geometry_msgs/msg/Twist",
                       "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"])
            published += 1
        return {"cmd_vel_zero_published": published,
                "arm_note": "aucun arrêt matériel du bras : couper l'alimentation si nécessaire",
                "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    def goal_send(self, action: str, goal: dict, timeout_s: float | None = None) -> dict:
        """Envoie un objectif FollowJointTrajectory borné à un contrôleur du bras."""
        if action not in ACTION_SPECS:
            raise RosInvalid(f"action non prise en charge : {action}")
        spec = ACTION_SPECS[action]
        if not isinstance(goal, dict):
            raise RosInvalid("goal doit être un dictionnaire {joint: valeur_rad}")
        positions = goal.get("positions_rad") or goal
        if not isinstance(positions, dict) or set(positions) != set(spec["joints"]):
            raise RosInvalid(f"articulations attendues : {spec['joints']}")
        low, high = spec["bounds_rad"]
        for joint, value in positions.items():
            if not isinstance(value, (int, float)) or not low <= float(value) <= high:
                raise RosInvalid(f"{joint} hors bornes [{low}, {high}] rad : {value!r}")
        duration = float(goal.get("duration_s", 2.0))
        if not 0.5 <= duration <= 10.0:
            raise RosInvalid("duration_s doit être dans [0.5, 10]")
        joints = ", ".join(spec["joints"])
        values = ", ".join(f"{float(positions[j]):.6f}" for j in spec["joints"])
        traj = ("{trajectory: {joint_names: [%s], points: [{positions: [%s], "
                "time_from_start: {sec: %d, nanosec: %d}}]}}" % (joints, values, int(duration),
                                                                 int((duration % 1) * 1e9)))
        output = self._run(["ros2", "action", "send_goal", action, spec["type"], traj],
                           timeout=timeout_s or duration + 20.0)
        return {"action": action, "sent": traj, "result": output.strip()[-400:],
                "succeeded": "SUCCEEDED" in output,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
