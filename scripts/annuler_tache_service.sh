#!/bin/bash
# Annule la tâche en cours du directeur — appelé par ExecStop de clawbot-director.service.
#
# Pourquoi : un redémarrage ou un arrêt de l'unité laissait la tâche en cours dans l'état `RUNNING`
# côté serveurs d'action, et le goal continuait sa vie dans le vide : plus personne ne l'attendait,
# plus personne ne pouvait le voir, et l'arbitre ne le connaissait pas. `ExecStop` parle au nœud
# encore vivant, avant que systemd ne l'arrête.
#
# Le script ne bloque jamais l'arrêt : toute erreur sort en 0. Un service qu'on n'arrive pas à
# arrêter parce que son script d'annulation a échoué est un service qu'on ne peut pas éteindre.
#
# Pas de `set -u` : les scripts `setup.bash` de ROS 2 lisent des variables non définies et font
# sortir le shell qui les source — le script s'arrêtait alors sans rien annuler.
#
# Le motif « arret_service » n'appartient pas à la famille « safety » : la tâche finit en
# CANCELLED, pas en CANCELLED_SAFETY. Une annulation d'exploitation ne doit pas se déguiser en
# arrêt de sécurité dans l'historique.

RACINE="/home/jetson/clawbot"
cd "$RACINE" || exit 0

if [ -f /opt/ros/humble/setup.bash ]; then
    . /opt/ros/humble/setup.bash
fi
if [ -f "$RACINE/install/setup.bash" ]; then
    . "$RACINE/install/setup.bash"
fi

reponse=$(echo '{"op":"cancel_task","reason":"arret_service"}' \
          | timeout 10 python3 -m bridge_mcp.director_client 2>&1 | tail -c 300)
echo "ExecStop directeur : ${reponse:-aucune reponse}" >&2
exit 0
