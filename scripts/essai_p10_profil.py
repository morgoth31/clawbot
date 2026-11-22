#!/usr/bin/python3
"""Essai sans mouvement du profil `clawbot-pilot` (P10 §8).

Lance le serveur MCP exactement comme la configuration du profil le déclare (stdio,
`ros2 run clawbot_mcp server`), se connecte avec le client du SDK, et déroule :

    get_robot_status → list_skills → start_mission → get_mission_status
    → get_snapshot → stop_robot

Aucun outil n'est appelé directement : tout passe par le protocole MCP.
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

COMMANDE = ("source /opt/ros/humble/setup.bash && "
            "source /home/jetson/clawbot/install/setup.bash && "
            "exec ros2 run clawbot_mcp server --transport stdio")
PARAMETRES = StdioServerParameters(
    command="/bin/bash", args=["-c", COMMANDE],
    env={"ROS_DOMAIN_ID": "28", "HOME": "/home/jetson", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})


def charge(resultat) -> dict:
    """Le serveur renvoie du JSON en texte : on le relit."""
    contenus = getattr(resultat, "content", None) or []
    for contenu in contenus:
        texte = getattr(contenu, "text", None)
        if texte:
            try:
                return json.loads(texte)
            except ValueError:
                return {"ok": False, "raw": texte[:300]}
    return {"ok": False, "raw": "réponse vide"}


async def essai() -> int:
    async with stdio_client(PARAMETRES) as (lecture, ecriture):
        async with ClientSession(lecture, ecriture) as session:
            await session.initialize()
            outils = await session.list_tools()
            noms = sorted(outil.name for outil in outils.tools)
            print(f"OUTILS n={len(noms)} {noms}")

            etat = charge(await session.call_tool("get_robot_status", {}))
            print("ETAT", json.dumps(etat, ensure_ascii=False)[:400])

            skills = charge(await session.call_tool("list_skills", {}))
            print("SKILLS", [s["name"] for s in skills.get("skills", [])])

            mission = charge(await session.call_tool("start_mission", {
                "objective": "essai P10 sans mouvement",
                "steps": [{"skill": "wait", "params": {"seconds": 1}}]}))
            print("MISSION", json.dumps(mission, ensure_ascii=False))
            mission_id = mission.get("mission_id")

            for _ in range(20):
                await asyncio.sleep(0.5)
                suivi = charge(await session.call_tool("get_mission_status",
                                                       {"mission_id": mission_id}))
                if suivi.get("state") in ("SUCCEEDED", "FAILED", "ABORTED", "CANCELED"):
                    break
            print("SUIVI", json.dumps(suivi, ensure_ascii=False))

            image = charge(await session.call_tool("get_snapshot", {"camera": "wrist"}))
            print("SNAPSHOT", json.dumps(image, ensure_ascii=False)[:300])

            arret = charge(await session.call_tool("stop_robot", {"reason": "essai P10"}))
            print("STOP", json.dumps(arret, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(essai()))
