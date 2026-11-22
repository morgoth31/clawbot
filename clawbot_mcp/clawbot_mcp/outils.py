"""Les douze outils du §9, sans accès direct aux actionneurs (REQ-MCP-001, 002).

Chaque outil reçoit un contexte injecté (clients ROS, éditeur d'e-stop, registre) :
aucun d'eux ne crée de publisher de vitesse, ni de client de réarmement, ni ne lance
de commande shell. Les tests d'inspection le vérifient sur ce source.
"""
from __future__ import annotations

import json
import time

TIMEOUT_S = 5.0


def ok(**champs) -> dict:
    return {"ok": True, **champs}


def erreur(code: str, message: str) -> dict:
    from clawbot_common.errors import category

    return {"ok": False, "error_code": code, "error_category": category(code),
            "message": message}


# ── descriptions (REQ-MCP-006) ───────────────────────────────────────────────
DESCRIPTIONS = {
    "get_robot_status": (
        "État complet du robot : santé, capacités actives, mission en cours, e-stop. "
        "À utiliser avant toute action pour savoir ce qui est possible. Renvoie "
        "{ok, health, capabilities, mission, estop_latched}."),
    "list_capabilities": (
        "Liste les capacités (base, lidar, navigation…) avec leur état et leurs unités "
        "systemd. À utiliser pour savoir si une action est possible. Renvoie "
        "{ok, capabilities:[{name, state, units, requires}]}."),
    "set_capability": (
        "Active ou désactive une capacité. Les capacités always_on (base, lidar) refusent "
        "l'arrêt. À utiliser pour préparer une mission. Renvoie {ok, name, state} ou "
        "error_code CAPABILITY_CONFLICT / ALWAYS_ON / UNKNOWN_CAPABILITY."),
    "list_skills": (
        "Liste les skills disponibles avec leur schéma de paramètres et leurs capacités "
        "requises. À appeler avant start_skill : les paramètres doivent respecter le "
        "schéma. Renvoie {ok, skills:[{name, description, params_schema, requires}]}."),
    "start_skill": (
        "Lance un skill unique (mission à une étape) et rend la main immédiatement avec "
        "un mission_id. Suivre avec get_mission_status. Renvoie {ok, mission_id}."),
    "start_mission": (
        "Lance une mission de 1 à 20 étapes de skills et rend un mission_id "
        "immédiatement ; suivre avec get_mission_status. En état WAITING_DECISION, "
        "lire get_failure_report puis submit_decision. Renvoie {ok, mission_id}."),
    "get_mission_status": (
        "État d'une mission : état, étape courante, progression, dernières erreurs. "
        "À interroger après start_mission. Renvoie {ok, state, step_index, step_count, "
        "progress, error_code}."),
    "cancel_mission": (
        "Annule la mission en cours ; le robot reçoit une consigne nulle. À utiliser si "
        "la situation change. Renvoie {ok, mission_id, state}."),
    "get_failure_report": (
        "Rapport d'échec de la dernière mission (schéma §6.2) : code, catégorie, "
        "décisions autorisées, budget. À lire avant submit_decision. Renvoie "
        "{ok, failure_report}."),
    "submit_decision": (
        "Répond à une mission en WAITING_DECISION : RETRY_STEP, RETRY_WITH_PARAMS, "
        "SKIP_STEP, REPLACE_REMAINING ou ABORT, avec un rationale obligatoire. Renvoie "
        "{ok, accepted, escalations_left}."),
    "stop_robot": (
        "Arrêt d'urgence immédiat : publie /safety/estop=true, sans dépendre de "
        "l'exécutif. À utiliser dès qu'un mouvement est dangereux. Renvoie {ok}; le "
        "réarmement est un geste humain au tableau de bord."),
    "get_snapshot": (
        "Prend une image de la caméra demandée (wrist ou astra) via le skill "
        "capture_image, réduite à 640 px de large en JPEG. Renvoie {ok, path} ou "
        "error_code CAPABILITY_INACTIVE / TIMEOUT."),
}

NOMS_OUTILS = tuple(DESCRIPTIONS)


# ── appels ROS avec délai ────────────────────────────────────────────────────
def _attendre(futur, timeout_s: float = TIMEOUT_S) -> bool:
    fin = time.monotonic() + timeout_s
    while not futur.done() and time.monotonic() < fin:
        time.sleep(0.02)
    return futur.done()


def _appeler_service(client, requete, timeout_s: float = TIMEOUT_S):
    """Appel de service borné ; None si le service ne répond pas."""
    if client is None:
        return None
    if not client.wait_for_service(timeout_sec=min(2.0, timeout_s)):
        return None
    futur = client.call_async(requete)
    return futur.result() if _attendre(futur, timeout_s) else None


# ── outils ───────────────────────────────────────────────────────────────────
def get_robot_status(ctx) -> dict:
    sante = ctx.sante()
    capacites = _appeler_service(ctx.client("capacites_list"),
                                 ctx.requete("capacites_list"))
    if capacites is None:
        return erreur("TIMEOUT", "service /clawbot/capabilities/list muet")
    suivi = ctx.mission_en_cours()
    return ok(health=sante, capabilities=json.loads(capacites.capabilities_json),
              mission=suivi, estop_latched=bool(sante.get("estop_latched", False)))


def list_capabilities(ctx) -> dict:
    reponse = _appeler_service(ctx.client("capacites_list"), ctx.requete("capacites_list"))
    if reponse is None:
        return erreur("TIMEOUT", "service /clawbot/capabilities/list muet")
    return ok(capabilities=json.loads(reponse.capabilities_json))


def set_capability(ctx, name: str, active: bool) -> dict:
    if not isinstance(name, str) or not name:
        return erreur("INVALID_PARAMS", "name requis")
    requete = ctx.requete("capacites_set")
    requete.name, requete.active = name, bool(active)
    reponse = _appeler_service(ctx.client("capacites_set"), requete, timeout_s=30.0)
    if reponse is None:
        return erreur("TIMEOUT", "service /clawbot/capabilities/set muet")
    if not reponse.success:
        code = str(reponse.message).split(":")[0].strip() or "UNHANDLED_EXCEPTION"
        if code not in ("ALWAYS_ON", "UNKNOWN_CAPABILITY", "CAPABILITY_CONFLICT",
                        "CAPABILITY_NOT_MANAGED", "UNIT_FAILED"):
            code = "CAPABILITY_INACTIVE"
        return erreur(code, reponse.message)
    return ok(name=name, state=reponse.state)


def list_skills(ctx) -> dict:
    return ok(skills=[{"name": nom,
                       "description": definition.description,
                       "params_schema": definition.params_schema,
                       "requires": list(definition.requires)}
                      for nom, definition in ctx.registre.items()])


def _parser_params(params) -> tuple[dict | None, str | None]:
    if params is None:
        return {}, None
    if isinstance(params, dict):
        return params, None
    if isinstance(params, str):
        try:
            charge = json.loads(params or "{}")
        except ValueError as exc:
            return None, f"params illisibles : {exc}"
        return (charge, None) if isinstance(charge, dict) else (None, "objet attendu")
    return None, "params doit être un objet"


def start_mission(ctx, objective: str, steps, max_duration_s: float = 0.0) -> dict:
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        return erreur("INVALID_PARAMS", "steps doit contenir 1 à 20 étapes")
    etapes = []
    for entree in steps:
        if not isinstance(entree, dict) or not isinstance(entree.get("skill"), str):
            return erreur("INVALID_PARAMS", "chaque étape doit porter un champ skill")
        params, probleme = _parser_params(entree.get("params"))
        if probleme:
            return erreur("INVALID_PARAMS", probleme)
        if entree["skill"] not in ctx.registre:
            return erreur("UNKNOWN_SKILL", f"skill inconnu : {entree['skill']}")
        etapes.append({"skill": entree["skill"], "params": params,
                       "timeout_s": float(entree.get("timeout_s", 0.0))})
    return ctx.lancer_mission(objective or "", etapes, float(max_duration_s or 0.0))


def start_skill(ctx, skill: str, params=None, timeout_s: float = 0.0) -> dict:
    if not isinstance(skill, str) or not skill:
        return erreur("INVALID_PARAMS", "skill requis")
    if skill not in ctx.registre:
        return erreur("UNKNOWN_SKILL", f"skill inconnu : {skill}")
    resultat = start_mission(ctx, f"skill {skill}",
                             [{"skill": skill, "params": params, "timeout_s": timeout_s}])
    return resultat


def get_mission_status(ctx, mission_id: str) -> dict:
    suivi = ctx.suivi(mission_id)
    if suivi is None:
        return erreur("INVALID_PARAMS", f"mission inconnue : {mission_id}")
    return ok(**suivi)


def cancel_mission(ctx, mission_id: str) -> dict:
    suivi = ctx.suivi(mission_id)
    if suivi is None:
        return erreur("INVALID_PARAMS", f"mission inconnue : {mission_id}")
    annule = ctx.annuler(mission_id)
    if not annule:
        return erreur("TIMEOUT", "annulation non confirmée par l'exécutif")
    return ok(mission_id=mission_id, state="CANCELED")


def get_failure_report(ctx, mission_id: str = "") -> dict:
    requete = ctx.requete("mission_report")
    requete.mission_id = mission_id or ""
    reponse = _appeler_service(ctx.client("mission_report"), requete)
    if reponse is None:
        return erreur("TIMEOUT", "service /clawbot/mission/report muet")
    if not reponse.found:
        return erreur("INVALID_PARAMS", "aucun rapport disponible")
    rapport = json.loads(reponse.report_json)
    return ok(failure_report=rapport.get("failure_report"), state=rapport.get("state"),
              budget=rapport.get("budget"))


def submit_decision(ctx, mission_id: str, decision: str, params=None,
                    rationale: str = "") -> dict:
    if not rationale.strip():
        return erreur("INVALID_PARAMS", "rationale obligatoire")
    charge, probleme = _parser_params(params)
    if probleme:
        return erreur("INVALID_PARAMS", probleme)
    requete = ctx.requete("mission_decide")
    requete.mission_id = mission_id
    requete.decision = decision
    requete.params_json = json.dumps(charge, ensure_ascii=False)
    requete.rationale = rationale
    reponse = _appeler_service(ctx.client("mission_decide"), requete)
    if reponse is None:
        return erreur("TIMEOUT", "service /clawbot/mission/decide muet")
    if not reponse.accepted:
        code = "INVALID_PARAMS"
        if "escalade" in reponse.message:
            code = "CAPABILITY_CONFLICT"
        return erreur(code, reponse.message)
    return ok(accepted=True, escalations_left=int(reponse.escalations_left))


def stop_robot(ctx, reason: str = "") -> dict:
    """Publie /safety/estop=true, sans dépendre d'aucun service (REQ-MCP-004)."""
    publish = ctx.publier_estop()
    if not publish:
        return erreur("SERIAL_LOST", "éditeur /safety/estop indisponible")
    return ok(stopped=True, reason=reason or "demande de l'opérateur")


def get_snapshot(ctx, camera: str = "wrist") -> dict:
    if camera not in ("wrist", "astra"):
        return erreur("INVALID_PARAMS", "camera doit valoir wrist ou astra")
    return ctx.capture(camera)


OUTILS = {
    "get_robot_status": get_robot_status,
    "list_capabilities": list_capabilities,
    "set_capability": set_capability,
    "list_skills": list_skills,
    "start_skill": start_skill,
    "start_mission": start_mission,
    "get_mission_status": get_mission_status,
    "cancel_mission": cancel_mission,
    "get_failure_report": get_failure_report,
    "submit_decision": submit_decision,
    "stop_robot": stop_robot,
    "get_snapshot": get_snapshot,
}
