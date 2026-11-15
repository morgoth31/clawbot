#!/usr/bin/env bash
# Lance la suite de tests du dépôt dans un environnement sain.
#
# Trois pièges de ce poste sont neutralisés ici, et aucun ne peut l'être depuis
# conftest.py :
#   1. Le python du venv Hermes (3.14) casse rclpy → on force /usr/bin/python3.
#   2. Les plugins pytest de Humble (launch_testing, launch_testing_ros) déclarent
#      un hook que pytest 9 refuse : `-p no:...` ne suffit pas, il faut couper
#      l'autochargement AVANT le démarrage de pytest.
#   3. Un `__pycache__` périmé rejoue le module d'hier contre le fichier
#      d'aujourd'hui.
#
# Usage : scripts/run_tests.sh [options pytest]
#         scripts/run_tests.sh tests/test_manette_config.py -q

set -u

cd "$(dirname "$0")/.."

unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
# `set -u` fait échouer setup.bash (« AMENT_TRACE_SETUP_FILES: unbound variable ») :
# on le suspend le temps du source.
set +u
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash
set -u

# Domaine dédié aux tests : ni le robot (28) ni la simulation (99).
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID_TEST:-98}
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

# Un nœud de téléopération vivant publie sur les mêmes topics que les tests et
# fausse leurs assertions (constaté : un /cmd_vel à 0.06 au lieu de 0.5).
if ps -eo args | grep -q "[c]lawbot_joy_teleop.py"; then
    echo "ERREUR : une téléopération tourne et va polluer /joy et /cmd_vel." >&2
    echo "        Arrêter le service ou les processus de test avant de relancer." >&2
    exit 4
fi

rm -rf joy_teleop/__pycache__

exec python3 -m pytest "$@"
