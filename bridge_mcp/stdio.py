#!/usr/bin/env python3
"""Point d'entrée MCP en transport stdio, pour Hermes et tout client local.

L'HTTP streaming (127.0.0.1:8090, jeton porteur) reste la voie réseau. Ce mode stdio sert
le même serveur, ses 22 outils et ses ressources, sur un tuyau local : rien n'est exposé
sur le réseau, donc aucun jeton n'est requis.

    python3 -m bridge_mcp.stdio          # ou : hermes mcp add clawbot --command …

L'environnement ROS est résolu par `ros_layer` (bash -c "source /opt/ros/humble/setup.bash"),
il n'y a donc rien à sourcer avant de lancer ce fichier ; seul `ROS_DOMAIN_ID` compte
(28 par défaut côté robot).
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge_mcp import server as bridge_server  # noqa: E402


def main() -> None:
    os.environ.setdefault("ROS_DOMAIN_ID", "28")
    bridge = bridge_server.create_server(token="stdio-local", host="127.0.0.1", port=8090)
    asyncio.run(bridge.mcp.run_stdio_async())


if __name__ == "__main__":
    main()
