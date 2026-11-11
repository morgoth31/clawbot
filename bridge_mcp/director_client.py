"""Client ponctuel du directeur, exécuté sous l'environnement ROS 2.

Le pont MCP n'embarque pas de contexte rclpy : il lance ce module, lui passe une requête JSON
sur stdin et lit la réponse JSON sur stdout. Pas de `ros2 service call` : le CLI réinterprète
l'argument en YAML et mange les guillemets du JSON.

Codes de sortie : 0 réponse reçue, 2 requête locale invalide, 3 service indisponible,
4 délai dépassé. Le JSON de réponse est toujours écrit, même en cas d'échec.
"""

from __future__ import annotations

import json
import os
import sys

import rclpy
from rclpy.node import Node

from clawbot_interfaces.srv import DirectorCommand

SERVICE = "/director/command"


def _repondre(charge: dict, code: int) -> int:
    sys.stdout.write(json.dumps(charge, ensure_ascii=False))
    return code


def main() -> int:
    try:
        demande = json.loads(sys.stdin.read())
    except ValueError as exc:
        return _repondre({"status": "INVALID", "reason": f"requete JSON invalide : {exc}"}, 2)
    if not isinstance(demande, dict):
        return _repondre({"status": "INVALID", "reason": "objet JSON attendu"}, 2)

    timeout = float(os.environ.get("DIRECTOR_CLIENT_TIMEOUT_S", "8"))
    rclpy.init()
    node = Node("director_client")
    try:
        client = node.create_client(DirectorCommand, SERVICE)
        if not client.wait_for_service(timeout_sec=timeout):
            return _repondre({"status": "ROS_UNAVAILABLE",
                              "reason": f"{SERVICE} absent du domaine"}, 3)
        requete = DirectorCommand.Request()
        requete.request_json = json.dumps(demande, ensure_ascii=False)
        futur = client.call_async(requete)
        rclpy.spin_until_future_complete(node, futur, timeout_sec=timeout)
        if not futur.done():
            return _repondre({"status": "ROS_TIMEOUT",
                              "reason": f"aucune reponse de {SERVICE} en {timeout:g} s"}, 4)
        return _repondre(json.loads(futur.result().response_json), 0)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
