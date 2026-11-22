"""Façade du directeur : `op` → mission (REQ-EXEC-018).

Les trois appelants du directeur ne changent pas (C11) : la traduction vit ici, et
le mode `legacy` (défaut) laisse le comportement historique intact.
"""
from __future__ import annotations

# op du schéma P06 → type de mission
SKILLS_SIMPLE = {"start_skill": "skill"}


def traduire(document: dict | None) -> list[dict] | None:
    """Étapes de mission équivalentes à la requête, ou None si le traitement reste historique."""
    if not isinstance(document, dict):
        return None
    operation = document.get("op")
    if operation == "start_skill":
        skill = document.get("skill")
        if not isinstance(skill, str) or not skill:
            return None
        args = document.get("args") or {}
        if not isinstance(args, dict):
            return None
        return [{"skill": skill, "params": args}]

    if operation == "start_sequence":
        etapes = document.get("steps")
        if not isinstance(etapes, list) or not 1 <= len(etapes) <= 20:
            return None
        mission = []
        for entree in etapes:
            if not isinstance(entree, dict) or not isinstance(entree.get("skill"), str):
                return None
            mission.append({"skill": entree["skill"],
                            "params": dict(entree.get("args") or {})})
        return mission

    # get_task, cancel_task, confirm et tout op inconnu : traitement historique
    return None


def resume_lisible(document: dict | None) -> str:
    etapes = traduire(document) or []
    return " → ".join(f"{e['skill']}" for e in etapes)
