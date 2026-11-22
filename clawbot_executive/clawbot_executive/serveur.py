"""Serveur d'action des skills (P08).

`/clawbot/execute_skill` exécute un skill à la fois. Un `stop` préempte : c'est le
seul moyen d'interrompre une tâche longue sans passer par l'e-stop.

Multi-thread assumé ici : l'exécution d'un goal boucle pendant des secondes et doit
rester capable de recevoir une annulation (mutuellement exclusif pour les
abonnements d'état, réentrant pour l'action).
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray, String

from clawbot_common import preconditions as regles_preconditions

from clawbot_interfaces.action import ExecuteSkill

from . import bras
from .etats import Etats
from .executeur_bras import ExecuteurActions
from .registre import Definition, charger, valider_parametres
from .skills import (CANCELED, FAILED, REJECTED, SUCCEEDED, Resultat, construire)

REGISTRE_PAR_DEFAUT = "/home/jetson/clawbot/install/clawbot_executive/share/clawbot_executive/config/skills.yaml"
SNAPSHOTS_PAR_DEFAUT = "/var/lib/clawbot/snapshots"
POSES_PAR_DEFAUT = "/home/jetson/clawbot/config/arm_poses.yaml"
PRECONDITIONS_PAR_DEFAUT = "/home/jetson/clawbot/config/preconditions.yaml"


def _liste_detections(message) -> list:
    """Detection2DArray → la forme des détections du registre."""
    return [
        {"class": (d.results[0].hypothesis.class_id if d.results else ""),
         "class_id": 0,
         "confidence": round(d.results[0].hypothesis.score, 3) if d.results else 0.0,
         # vision_msgs/Pose2D : `position` (Point2D) + `theta`, pas `x`/`y` directs
         "bbox": {"x1": int(d.bbox.center.position.x - d.bbox.size_x / 2),
                  "y1": int(d.bbox.center.position.y - d.bbox.size_y / 2),
                  "x2": int(d.bbox.center.position.x + d.bbox.size_x / 2),
                  "y2": int(d.bbox.center.position.y + d.bbox.size_y / 2)}}
        for d in message.detections]


class Contexte:
    """Ce qu'un skill peut faire : publier une consigne, lire l'état, attendre."""

    def __init__(self, serveur: "ServeurSkills", params: dict, goal_handle,
                 definition=None):
        self.serveur = serveur
        self.params = params
        self.goal_handle = goal_handle
        # délai effectif : celui du goal s'il est fourni, sinon celui du registre
        demande = float(getattr(goal_handle.request, "timeout_s", 0.0) or 0.0)
        self.timeout_s = demande or float(getattr(definition, "timeout_s", 30.0))
        self._echeance = None

    def prochaines_detections(self, attente_s: float):
        """Détections reçues après l'appel, ou None si rien en `attente_s` (REQ-PERC-010)."""
        debut = time.monotonic()
        seuil = self.serveur._detections_stamp          # noqa: SLF001 — état partagé du nœud
        while time.monotonic() - debut < attente_s:
            if self.serveur._detections_stamp > seuil:  # noqa: SLF001
                return list(self.serveur._detections)
            time.sleep(0.05)
        return None

    @property
    def etats(self) -> Etats:
        return self.serveur.etats

    # ── bras ─────────────────────────────────────────────────────────────────
    @property
    def poses(self):
        return self.serveur.poses

    @property
    def servo_angles(self):
        return self.serveur.etats.servo_angles

    def age_servo(self):
        return self.serveur.etats.age_servo()

    def duree_invalide(self, maintenant=None):
        return self.serveur.etats.duree_invalide(maintenant)

    def executer_bras(self, groupe, positions, duree_s, timeout_s, surveillance=None):
        return self.serveur.executeur_bras.executer(
            groupe, positions, duree_s, timeout_s, surveillance)

    @property
    def periode(self) -> float:
        return self.serveur.periode_s

    def publier(self, vx: float, vy: float, wz: float) -> None:
        self.serveur.publier(vx, vy, wz)

    def attendre(self, duree_s: float) -> None:
        self.serveur.attendre(duree_s)

    def annule(self) -> bool:
        return bool(self.goal_handle.is_cancel_requested) or self.serveur.preempte()

    def feedback(self, phase: str, progress: float) -> None:
        retour = ExecuteSkill.Feedback()
        retour.phase = phase
        retour.progress = float(max(0.0, min(1.0, progress)))
        retour.detail_json = json.dumps({"skill": self.serveur.skill_courant or ""})
        self.goal_handle.publish_feedback(retour)

    def maintenant(self) -> float:
        return time.monotonic()

    def echeance(self) -> float:
        if self._echeance is None:
            self._echeance = self.maintenant() + self.timeout_s
        return self._echeance

    def expire(self) -> bool:
        return self.maintenant() >= self.echeance()

    def prochaine_image(self, camera: str, timeout_s: float):
        topic = {"wrist": "/wrist_camera/image_raw",
                 "astra": "/camera/color/image_raw"}.get(camera)
        if topic is None:
            return None
        return self.serveur.derniere_image(topic, timeout_s)

    def ecrire_snapshot(self, image, camera: str) -> str:
        return self.serveur.ecrire_snapshot(image, camera)


class ServeurSkills(Node):
    def __init__(self, registre: str | Path | None = None, etats: Etats | None = None,
                 editeur=None, demarrer: bool = False, nom: str = "skill_server",
                 poses: str | Path | None = None, preconditions: str | Path | None = None,
                 executeur_bras=None):
        super().__init__(nom)
        self.declare_parameter("registre", REGISTRE_PAR_DEFAUT)
        self.declare_parameter("snapshots_dir", SNAPSHOTS_PAR_DEFAUT)
        self.declare_parameter("periode_s", 0.05)
        self.declare_parameter("arm_poses", POSES_PAR_DEFAUT)
        self.declare_parameter("preconditions", PRECONDITIONS_PAR_DEFAUT)

        chemin = str(registre or self.get_parameter("registre").value)
        self.definitions: dict[str, Definition] = charger(chemin)
        self.periode_s = float(self.get_parameter("periode_s").value)
        self.snapshots_dir = Path(str(self.get_parameter("snapshots_dir").value))

        # Liste blanche des poses et enveloppe de repos : chargées au démarrage, pas au
        # premier goal. Un fichier inutilisable doit empêcher le service de démarrer,
        # pas produire un refus incompréhensible au moment du mouvement (P13).
        chemin_poses = str(poses or self.get_parameter("arm_poses").value)
        chemin_preconditions = str(preconditions or self.get_parameter("preconditions").value)
        self.poses = bras.charger(chemin_poses)
        self.regles = regles_preconditions.charger(chemin_preconditions)

        self.etats = etats if etats is not None else Etats()
        self._detections: list = []
        self._detections_stamp = 0.0
        self._en_cours = None                 # goal_handle du skill en exécution
        self.skill_courant: str | None = None
        self._preemption = threading.Event()  # stop demandé pendant une exécution
        self._verrou = threading.Lock()

        from geometry_msgs.msg import Twist

        self.cmd_pub = editeur if editeur is not None else self.create_publisher(
            Twist, "/cmd_vel/skill", 10)

        groupe_etats = MutuallyExclusiveCallbackGroup()
        self.create_subscription(String, "/safety/state",
                                 lambda m: self.etats.maj_safety(m.data), 10,
                                 callback_group=groupe_etats)
        self.create_subscription(String, "/clawbot/capabilities/state",
                                 lambda m: self.etats.maj_capacites(m.data), 10,
                                 callback_group=groupe_etats)
        try:
            from vision_msgs.msg import Detection2DArray

            def _recevoir(message) -> None:
                self._detections = _liste_detections(message)
                self._detections_stamp = time.monotonic()

            self.create_subscription(Detection2DArray, "/perception/detections",
                                     _recevoir, 10, callback_group=groupe_etats)
        except ImportError:                                  # pragma: no cover
            self.get_logger().warn("vision_msgs absent : detect_objects indisponible")
        try:
            from nav_msgs.msg import Odometry

            self.create_subscription(Odometry, "/odom", self._sur_odom, 10,
                                     callback_group=groupe_etats)
        except ImportError:                        # pragma: no cover
            self.get_logger().warn("nav_msgs absent : odométrie indisponible")

        # Angles de servo relus par le pilote : seule mesure du bras (REQ-ARM-005/006).
        # Abonnement typé conservé par le nœud ; la sonde de capacité s'abonne de son
        # côté, sur la même durée de vie courte.
        self.create_subscription(Int32MultiArray, "/arm/servo_angles",
                                 self._sur_servo_angles, 10,
                                 callback_group=groupe_etats)

        self.executeur_bras = executeur_bras or ExecuteurActions(self, self.etats)

        self._images: dict[str, object] = {}
        self._images_lock = threading.Lock()
        try:
            from rclpy.qos import qos_profile_sensor_data
            from sensor_msgs.msg import Image

            # QoS capteur (best effort) : une caméra publie en best effort, un abonné
            # reliable ne reçoit rien (leçon P05 sur les flux image).
            for topic in ("/wrist_camera/image_raw", "/camera/color/image_raw"):
                self.create_subscription(
                    Image, topic,
                    lambda m, t=topic: self._sur_image(t, m),
                    qos_profile_sensor_data,
                    callback_group=groupe_etats)
        except ImportError:                        # pragma: no cover
            pass

        self._action = ActionServer(
            self, ExecuteSkill, "/clawbot/execute_skill",
            execute_callback=self.executer_goal,
            goal_callback=lambda _g: GoalResponse.ACCEPT,
            cancel_callback=lambda _g: CancelResponse.ACCEPT,
            callback_group=ReentrantCallbackGroup())

        self.get_logger().info(
            f"skill_server pret : {len(self.definitions)} skills ({', '.join(self.definitions)})")

        self._executeur = None
        self._fil = None
        if demarrer:
            self._executeur = MultiThreadedExecutor(num_threads=3)
            self._executeur.add_node(self)
            self._fil = threading.Thread(target=self._executeur.spin, daemon=True)
            self._fil.start()

    def preempte(self) -> bool:
        """Vrai quand un `stop` a demandé la préemption du skill en cours."""
        return self._preemption.is_set()

    # ── abonnements d'état ───────────────────────────────────────────────────
    def _sur_odom(self, msg) -> None:
        position = msg.pose.pose.position
        self.etats.maj_odom(position.x, position.y, Etats.lacet(msg.pose.pose.orientation))

    def _sur_servo_angles(self, msg) -> None:
        self.etats.maj_servo_angles(list(msg.data))

    def _sur_image(self, topic: str, msg) -> None:
        with self._images_lock:
            self._images[topic] = msg

    # ── sortie de vitesse ────────────────────────────────────────────────────
    def publier(self, vx: float, vy: float, wz: float) -> None:
        from geometry_msgs.msg import Twist

        commande = Twist()
        commande.linear.x = float(vx)
        commande.linear.y = float(vy)
        commande.angular.z = float(wz)
        self.cmd_pub.publish(commande)

    def attendre(self, duree_s: float) -> None:
        if duree_s > 0:
            time.sleep(min(duree_s, 1.0))

    # ── images ───────────────────────────────────────────────────────────────
    def derniere_image(self, topic: str, timeout_s: float):
        fin = time.monotonic() + max(0.1, timeout_s)
        while time.monotonic() < fin:
            with self._images_lock:
                if topic in self._images:
                    return self._images[topic]
            time.sleep(0.05)
        return None

    def ecrire_snapshot(self, image, camera: str) -> str:
        import cv2                    # noqa: PLC0415 - dépendance lourde, import tardif
        import numpy as np

        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        mission = (self.skill_courant or "skill")
        horodatage = time.strftime("%Y%m%d-%H%M%S")
        chemin = self.snapshots_dir / f"{mission}_{camera}_{horodatage}.jpg"
        hauteur, largeur = image.height, image.width
        donnees = np.frombuffer(bytes(image.data), dtype=np.uint8)
        try:
            frame = donnees.reshape((hauteur, largeur, -1))[:, :, :3]
            if frame.shape[2] == 3:                   # bgr8 ou rgb8
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except ValueError:
            frame = cv2.imdecode(donnees, cv2.IMREAD_COLOR)
        cv2.imwrite(str(chemin), frame)
        return str(chemin)

    # ── exécution d'un goal ──────────────────────────────────────────────────
    def executer_goal(self, goal_handle):
        demandee = goal_handle.request.skill
        resultat = ExecuteSkill.Result()

        if demandee not in self.definitions:
            return self._terminer(goal_handle, resultat, Resultat(
                REJECTED, "UNKNOWN_SKILL", f"skill inconnu : {demandee!r}"),
                skill=demandee)

        try:
            params = json.loads(goal_handle.request.params_json or "{}")
        except ValueError as exc:
            return self._terminer(goal_handle, resultat, Resultat(
                REJECTED, "INVALID_PARAMS", f"params_json illisible : {exc}"),
                skill=demandee)
        if not isinstance(params, dict):
            return self._terminer(goal_handle, resultat, Resultat(
                REJECTED, "INVALID_PARAMS", "params_json doit être un objet"),
                skill=demandee)

        definition = self.definitions[demandee]
        erreurs = valider_parametres(definition, params)
        if erreurs:
            return self._terminer(goal_handle, resultat, Resultat(
                REJECTED, "INVALID_PARAMS", "; ".join(erreurs)[:300]),
                skill=demandee, params=params)

        with self._verrou:
            occupe = self._en_cours is not None
            if occupe and demandee != "stop":
                return self._terminer(goal_handle, resultat, Resultat(
                    REJECTED, "CAPABILITY_CONFLICT",
                    f"un skill s'exécute déjà ({self.skill_courant}) : un seul à la fois"),
                    skill=demandee, params=params)
            if occupe:
                # stop préempte : la boucle en cours voit le drapeau au tick suivant
                self._preemption.set()
            self._en_cours = goal_handle
            self.skill_courant = demandee

        try:
            skill = construire(definition, self.regles)
            code = skill.check_preconditions(self.etats, params)
            if code:
                return self._terminer(goal_handle, resultat, Resultat(
                    FAILED, code, skill.detail_precondition(self.etats, params)),
                    skill=demandee, params=params)
            ctx = Contexte(self, params, goal_handle, definition=definition)
            resultat_skill = skill.execute(ctx)
        except Exception as exc:                        # noqa: BLE001
            self.get_logger().error(f"{demandee} : exception {exc}")
            resultat_skill = Resultat(FAILED, "UNHANDLED_EXCEPTION", str(exc)[:200])
        finally:
            self.publier(0.0, 0.0, 0.0)
            with self._verrou:
                if self._en_cours is goal_handle:
                    self._en_cours = None
                    self.skill_courant = None
                    self._preemption.clear()

        if resultat_skill.outcome == CANCELED or goal_handle.is_cancel_requested:
            try:
                goal_handle.canceled()
            except Exception:                         # noqa: BLE001
                # Préemption par `stop` : rcl_action refuse la transition EXECUTING →
                # CANCELED sans demande d'annulation du client. L'état DDS est donc
                # ABORTED, mais le résultat porte bien l'issue CANCELED.
                goal_handle.abort()
            resultat.outcome = CANCELED
            resultat.error_code = ""
            resultat.message = resultat_skill.message or "annulé"
            return resultat
        return self._terminer(goal_handle, resultat, resultat_skill,
                              mission_id=goal_handle.request.mission_id, params=params,
                              skill=demandee)

    def _terminer(self, goal_handle, resultat, issue: Resultat, mission_id: str = "",
                  params: dict | None = None, skill: str = ""):
        resultat.outcome = issue.outcome
        resultat.error_code = issue.error_code
        resultat.error_category = ""
        resultat.message = issue.message
        resultat.result_json = issue.result_json or "{}"
        if issue.outcome == SUCCEEDED:
            goal_handle.succeed()
        elif issue.outcome == REJECTED:
            goal_handle.abort()
        else:
            goal_handle.abort()
        if issue.error_code:
            try:
                resultat.failure_report_json = self.rapport_echec(
                    mission_id or "sans-mission", issue, params or {},
                    skill=skill or self.skill_courant or "")
            except Exception as exc:                 # noqa: BLE001 - ne jamais perdre le résultat
                self.get_logger().error(f"rapport d'échec indisponible : {exc}")
                resultat.failure_report_json = ""
            try:
                from clawbot_common.errors import category

                resultat.error_category = category(issue.error_code)
            except Exception:                            # pragma: no cover
                resultat.error_category = ""
        else:
            resultat.failure_report_json = ""
        return resultat

    def rapport_echec(self, mission_id: str, issue: Resultat, params: dict,
                      skill: str = "") -> str:
        from clawbot_common.errors import rapport_echec

        sante = {
            "level": "OK" if self.etats.safety_state in ("OK", "UNKNOWN") else "ERROR",
            "active_capabilities": sorted(n for n in self.etats.capacites
                                          if self.etats.capacite_active(n)),
            "stale_flows": [],
            "safety_state": self.etats.safety_state,
            "estop_latched": bool(self.etats.estop_latched),
            "voltage": 0.0,
        }
        try:
            rapport = rapport_echec(
                mission_id=mission_id, objective="", step_index=0,
                skill=skill or self.skill_courant or "inconnu", params=params,
                error_code=issue.error_code, message=issue.message, health=sante,
                budget={"escalations_left": 2, "same_step_attempts_left": 1,
                        "time_left_s": 120.0})
        except KeyError:                                 # code hors table
            return ""
        return json.dumps(rapport, ensure_ascii=False)

    # ── arrêt propre ─────────────────────────────────────────────────────────
    def destroy_node(self):
        if self._executeur is not None:
            self._executeur.shutdown(timeout_sec=2.0)
            self._executeur = None
        super().destroy_node()


def main(argv=None) -> int:
    from rclpy.executors import ExternalShutdownException

    rclpy.init(args=argv)
    serveur = None
    try:
        serveur = ServeurSkills()
        executeur = MultiThreadedExecutor(num_threads=3)
        executeur.add_node(serveur)
        executeur.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if serveur is not None:
            serveur.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
