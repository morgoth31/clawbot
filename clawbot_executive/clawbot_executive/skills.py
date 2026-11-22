"""Skills du registre (REQ-EXEC-001 à 007).

Un skill reçoit ses états par le contexte du serveur : il ne crée aucun abonnement
et ne publie que sur `/cmd_vel/skill`, par l'intermédiaire de l'éditeur fourni.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field

from .deplacement import Deplacement, code_safety
from .registre import Definition

SUCCEEDED = 0
FAILED = 1
CANCELED = 2
REJECTED = 3


@dataclass
class Resultat:
    outcome: int
    error_code: str = ""
    message: str = ""
    result_json: str = ""
    detail: dict = field(default_factory=dict)


class Skill:
    """Base commune : préconditions puis exécution."""

    def __init__(self, definition: Definition):
        self.definition = definition
        self.nom = definition.nom

    # ── préconditions ────────────────────────────────────────────────────────
    def capacites_requises(self, params=None) -> list[str]:
        """Capacités exigées, éventuellement dépendantes d'un paramètre.

        `requires_by_param: {camera: {wrist: [...], astra: [...]}}` : la valeur du
        paramètre choisit la liste (REQ-PERC-005). Sans paramètre, on retombe sur
        `requires`, ce qui garde le comportement d'avant P11.
        """
        par_param = getattr(self.definition, "requires_by_param", None) or {}
        for nom, valeurs in par_param.items():
            if params is not None and nom in params and params[nom] in valeurs:
                return list(valeurs[params[nom]])
        return list(self.definition.requires)

    def capacite_manquante(self, etats, params=None) -> str | None:
        for capacite in self.capacites_requises(params):
            if not etats.capacite_active(capacite):
                return capacite
        return None

    def detail_precondition(self, etats, params=None) -> str:
        manquante = self.capacite_manquante(etats, params)
        return f"capacité {manquante} inactive" if manquante else ""

    def check_preconditions(self, etats, params=None) -> str | None:
        """Code d'erreur si le skill ne peut pas démarrer, sinon None."""
        if self.capacite_manquante(etats, params):
            return "CAPABILITY_INACTIVE"
        return None

    # ── exécution ────────────────────────────────────────────────────────────
    def execute(self, ctx) -> Resultat:            # pragma: no cover - interface
        raise NotImplementedError


class Stop(Skill):
    """Consigne nulle immédiate, puis succès."""

    def execute(self, ctx) -> Resultat:
        ctx.publier(0.0, 0.0, 0.0)
        ctx.attendre(0.05)
        return Resultat(SUCCEEDED, message="consigne nulle publiée")


class Wait(Skill):
    """Attente bornée, annulable."""

    def execute(self, ctx) -> Resultat:
        secondes = float(ctx.params["seconds"])
        fin = ctx.maintenant() + secondes
        while ctx.maintenant() < fin:
            if ctx.annule():
                ctx.publier(0.0, 0.0, 0.0)
                return Resultat(CANCELED, message="attente annulée")
            ctx.feedback("waiting", (secondes - (fin - ctx.maintenant())) / secondes
                         if secondes else 1.0)
            ctx.attendre(min(ctx.periode, max(0.0, fin - ctx.maintenant())))
        return Resultat(SUCCEEDED, message=f"{secondes:.1f} s écoulées")


class MoveRelative(Skill):
    """Translation relative en ligne droite, boucle à 20 Hz sur /odom."""

    def execute(self, ctx) -> Resultat:
        dx = float(ctx.params.get("dx_m", 0.0))
        dy = float(ctx.params.get("dy_m", 0.0))
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            ctx.publier(0.0, 0.0, 0.0)
            return Resultat(SUCCEEDED, message="déplacement nul")
        max_speed = float(ctx.params.get("max_speed_mps")
                          or self.definition.bornes.get("max_speed_mps", 0.2))
        max_speed = min(max_speed, self.definition.bornes.get("max_speed_mps", 0.2))
        depart = (ctx.etats.x, ctx.etats.y)
        boucle = Deplacement(cible_m=math.hypot(dx, dy), max_speed=max_speed)
        # cap : on avance dans la direction demandée, sans réorientation
        cap = math.atan2(dy, dx) if (dx or dy) else 0.0
        while True:
            if ctx.annule():
                ctx.publier(0.0, 0.0, 0.0)
                return Resultat(CANCELED, message="déplacement annulé")
            if ctx.expire():
                ctx.publier(0.0, 0.0, 0.0)
                return Resultat(FAILED, "TIMEOUT",
                                f"cible non atteinte en {ctx.timeout_s:.1f} s",
                                detail={"avance_m": avance})
            code = code_safety(ctx.etats.safety_state, ctx.etats.estop_latched)
            avance = math.hypot(ctx.etats.x - depart[0], ctx.etats.y - depart[1])
            pas = boucle.pas(avance, code)
            if pas.termine:
                ctx.publier(0.0, 0.0, 0.0)
                if pas.code:
                    return Resultat(FAILED, pas.code, f"arrêt de sûreté : {pas.code}",
                                    detail={"avance_m": avance})
                return Resultat(SUCCEEDED, message=f"arrivé à {avance:.3f} m",
                                result_json=json.dumps({"avance_m": round(avance, 3)}))
            ctx.feedback("moving", pas.progress)
            ctx.publier(pas.vitesse_mps * math.cos(cap), pas.vitesse_mps * math.sin(cap), 0.0)
            ctx.attendre(boucle.periode_s)


class Rotate(Skill):
    """Rotation relative, boucle à 20 Hz sur le lacet de /odom."""

    def execute(self, ctx) -> Resultat:
        angle = float(ctx.params.get("angle_rad", 0.0))
        if abs(angle) < 1e-6:
            ctx.publier(0.0, 0.0, 0.0)
            return Resultat(SUCCEEDED, message="rotation nulle")
        max_speed = float(ctx.params.get("max_speed_rps")
                          or self.definition.bornes.get("max_speed_rps", 0.8))
        max_speed = min(max_speed, self.definition.bornes.get("max_speed_rps", 0.8))
        depart = ctx.etats.yaw
        boucle = Deplacement(cible_m=angle, max_speed=max_speed)
        while True:
            if ctx.annule():
                ctx.publier(0.0, 0.0, 0.0)
                return Resultat(CANCELED, message="rotation annulée")
            if ctx.expire():
                ctx.publier(0.0, 0.0, 0.0)
                return Resultat(FAILED, "TIMEOUT",
                                f"angle non atteint en {ctx.timeout_s:.1f} s")
            code = code_safety(ctx.etats.safety_state, ctx.etats.estop_latched)
            parcouru = _ecart_angle(ctx.etats.yaw - depart)
            pas = boucle.pas(parcouru, code)
            if pas.termine:
                ctx.publier(0.0, 0.0, 0.0)
                if pas.code:
                    return Resultat(FAILED, pas.code, f"arrêt de sûreté : {pas.code}",
                                    detail={"angle_rad": parcouru})
                return Resultat(SUCCEEDED, message=f"rotation de {parcouru:.3f} rad",
                                result_json=json.dumps({"angle_rad": round(parcouru, 3)}))
            ctx.feedback("rotating", pas.progress)
            ctx.publier(0.0, 0.0, pas.vitesse_mps)
            ctx.attendre(boucle.periode_s)


class CaptureImage(Skill):
    """Prend la prochaine image de la caméra demandée et l'écrit en JPEG.

    La capacité exigée dépend de la caméra (`requires_by_param`), pour que l'Astra
    ne soit jamais refusée parce que la caméra du poignet est indisponible.
    """
    """Prend la prochaine image de la caméra demandée et l'écrit en JPEG."""

    def execute(self, ctx) -> Resultat:
        camera = ctx.params["camera"]
        image = ctx.prochaine_image(camera, timeout_s=self.definition.timeout_s)
        if image is None:
            return Resultat(FAILED, "TIMEOUT", f"aucune image sur la caméra {camera}")
        chemin = ctx.ecrire_snapshot(image, camera)
        return Resultat(SUCCEEDED, message=f"image écrite : {chemin}",
                        result_json=json.dumps({"path": chemin, "camera": camera}))


class NavigateTo(Skill):
    """Déclaré, mais refusé tant que la capacité `navigation` n'est pas servie."""

    def execute(self, ctx) -> Resultat:
        return Resultat(FAILED, "CAPABILITY_INACTIVE",
                        "navigation non pilotable à ce stade (Nav2 non servi)")


class SaveMap(Skill):
    """Déclaré, mais refusé tant que la capacité `mapping` n'est pas servie."""

    def execute(self, ctx) -> Resultat:
        return Resultat(FAILED, "CAPABILITY_INACTIVE",
                        "mapping non pilotable par le service (P07 : unité systemd)")


CLASSES = {
    "stop": Stop,
    "wait": Wait,
    "move_relative": MoveRelative,
    "rotate": Rotate,
    "capture_image": CaptureImage,
    "navigate_to": NavigateTo,
    "save_map": SaveMap,
}


def construire(definition: Definition) -> Skill:
    classe = CLASSES.get(definition.nom)
    if classe is None:
        raise KeyError(f"skill sans implémentation : {definition.nom}")
    return classe(definition)


def _ecart_angle(angle: float) -> float:
    """Ramène un écart de lacet dans ]-π, π]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle
