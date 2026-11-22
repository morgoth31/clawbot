#!/usr/bin/env bash
# Point d'entrée documenté des tests : délègue tout à scripts/check.sh.
#
#   scripts/run_tests.sh            # suite complète + lint + traçabilité + doublons
#   scripts/run_tests.sh tests      # idem, pytest limité à tests/
#
# La garde de domaine, l'environnement python système, la désactivation des
# plugins ROS et le contrôle de téléopération sont dans scripts/check.sh.
set -euo pipefail
exec "$(dirname "$0")/check.sh" "$@"
