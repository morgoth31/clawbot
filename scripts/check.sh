#!/usr/bin/env bash
# Vérification unique du dépôt Clawbot (P00, REQ-TEST-001 à 005).
#
#   scripts/check.sh                     # lint, unitaires, cpp, traçabilité, interdits, doublons
#   scripts/check.sh tests               # idem, en limitant pytest au chemin donné
#   scripts/check.sh --self-test         # annonce les étapes et sort 0
#   scripts/check.sh --integration       # pytest -m integration en domaine 99
#   scripts/check.sh --strict-duplicates # échec sur tout doublon hors allowlist
#
# Garde de domaine : refuse ROS_DOMAIN_ID=28 (robot en production), impose 98
# quand la variable est absente.
#
# Codes de sortie : 0 conforme, 2 usage, 3 domaine 28, 4 téléopération active,
#                   sinon le code de l'étape en échec (pytest : 1 ou 2).
set -euo pipefail

cd "$(dirname "$0")/.."

SELF_TEST=0
INTEGRATION=0
STRICT_DUPLICATES=0
TARGETS=()

usage() {
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
    case "$arg" in
        --self-test)          SELF_TEST=1 ;;
        --integration)        INTEGRATION=1 ;;
        --strict-duplicates)  STRICT_DUPLICATES=1 ;;
        -h|--help)            usage; exit 0 ;;
        -*)                   echo "check.sh : option inconnue '$arg'" >&2; exit 2 ;;
        *)                    TARGETS+=("$arg") ;;
    esac
done

# ── 1. Garde de domaine DDS (REQ-TEST-002) ───────────────────────────────────
if [[ "${ROS_DOMAIN_ID:-}" == "28" ]]; then
    echo "ERREUR : ROS_DOMAIN_ID=28 est le domaine du robot en production." >&2
    echo "         Aucun test ne doit y publier. Utilisez 98 (unitaire) ou 99 (intégration)." >&2
    exit 3
fi
if [[ -z "${ROS_DOMAIN_ID:-}" ]]; then
    export ROS_DOMAIN_ID=98
    echo "ROS_DOMAIN_ID=98 (variable absente : domaine de test unitaire imposé)"
fi

if [[ $INTEGRATION -eq 1 ]]; then
    export ROS_DOMAIN_ID=99
    echo "ROS_DOMAIN_ID=99 (intégration)"
fi

# ── 2. Environnement de test sain ────────────────────────────────────────────
# Le python du venv Hermes casse rclpy et n'a pas pytest : on force le système.
# Les plugins pytest de Humble (launch_testing, launch_ros) déclarent des hooks
# que pytest 9 refuse : on coupe l'autochargement.
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
if [[ -f /opt/ros/humble/setup.bash ]]; then
    set +u
    # shellcheck disable=SC1091
    source /opt/ros/humble/setup.bash
    # Interfaces générées (clawbot_interfaces/srv) : sans cet overlay, les tests
    # d'intégration ne peuvent pas importer DirectorCommand.
    if [[ -f install/setup.bash ]]; then
        # shellcheck disable=SC1091
        source install/setup.bash
    else
        echo "AVERTISSEMENT : install/setup.bash absent, interfaces non générées." >&2
    fi
    set -u
else
    echo "AVERTISSEMENT : /opt/ros/humble/setup.bash absent, tests ROS non garantis." >&2
fi
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

# ── 3. Auto-test (REQ-TEST-001/003/005 : les étapes sont annoncées) ──────────
if [[ $SELF_TEST -eq 1 ]]; then
    echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
    echo "Étapes prévues :"
    echo "  lint      ruff check sur les paquets maison (avertissement si ruff absent)"
    echo "  unit      pytest -q en domaine ${ROS_DOMAIN_ID}"
    echo "  trace     scripts/trace_check.py --max-untraced <requirements/.untraced_baseline>"
    echo "  doublons  sha256 des *.py, doublons entre paquets (avertissement)"
    echo "Auto-test terminé : code 0"
    exit 0
fi

# ── 4. Étapes ────────────────────────────────────────────────────────────────
run_lint() {
    echo "── lint ────────────────────────────────────────────────────────────"
    if command -v ruff >/dev/null 2>&1; then
        # Paquets maison seulement : les paquets vendor (yahboomcar_*) restent hors périmètre.
        ruff check clawbot_* bridge_mcp tests scripts joy_teleop
    else
        echo "AVERTISSEMENT : ruff absent, étape lint ignorée (rien n'a été installé)." >&2
    fi
}

run_unit() {
    echo "── unit ────────────────────────────────────────────────────────────"
    # Un nœud de téléopération vivant publie sur les mêmes topics que les tests
    # et fausse leurs assertions (constaté : /cmd_vel à 0.06 au lieu de 0.5).
    if ps -eo args | grep -qE "^python3 /home/jetson/clawbot/joy_teleop/clawbot_joy_teleop\.py"; then
        echo "ERREUR : une téléopération tourne et va polluer /joy et /cmd_vel." >&2
        echo "         Arrêter le service ou les processus de test avant de relancer." >&2
        exit 4
    fi
    rm -rf joy_teleop/__pycache__
    # `-p pytest_asyncio.plugin` : l'autochargement est coupé, mais les tests
    # async de ros2_llm_bridge exigent le plugin (installé, non installé par nous).
    if [[ ${#TARGETS[@]} -gt 0 ]]; then
        python3 -m pytest -q -p pytest_asyncio.plugin "${TARGETS[@]}"
    else
        python3 -m pytest -q -p pytest_asyncio.plugin
    fi
}

run_cpp() {
    echo "── cpp ─────────────────────────────────────────────────────────────"
    # Les paquets C++ (clawbot_health) livrent leurs tests en gtest : trace_check les
    # compte, mais pytest ne les exécute pas. On lance les binaires présents dans
    # build/. Absents (clone neuf, pas encore construit) : avertissement seulement.
    local binaires=() b
    while IFS= read -r b; do
        [[ -n "$b" ]] && binaires+=("$b")
    done < <(find build -maxdepth 2 -type f -perm -u+x -name 'test_*' 2>/dev/null | sort)
    if [[ ${#binaires[@]} -eq 0 ]]; then
        echo "AVERTISSEMENT : aucun binaire de test C++ (build absent) — colcon build d'abord."
        return 0
    fi
    local echec=0
    for b in "${binaires[@]}"; do
        if ! "$b" --gtest_brief=1 >/tmp/cpp_$(basename "$b").log 2>&1; then
            echo "ECHEC : $b (journal /tmp/cpp_$(basename "$b").log)" >&2
            tail -20 /tmp/cpp_$(basename "$b").log >&2 || true
            echec=1
        else
            echo "OK     $(basename "$b")"
        fi
    done
    return $echec
}

run_trace() {
    echo "── trace ───────────────────────────────────────────────────────────"
    local plafond
    if [[ ! -f requirements/.untraced_baseline ]]; then
        echo "ERREUR : requirements/.untraced_baseline absent (cliquet REQ-TEST-005)." >&2
        exit 1
    fi
    plafond="$(tr -d '[:space:]' < requirements/.untraced_baseline)"
    python3 scripts/trace_check.py --repo . --max-untraced "$plafond"
}

run_interdits() {
    echo "── interdits ───────────────────────────────────────────────────────"
    # INV-08 : aucun pilotage de processus par motif. Un motif peut tuer un
    # processus qui n'était pas la cible (S33). Exceptions nommées, et rien d'autre :
    #   - scripts/check.sh et tests/test_units.py portent la règle eux-mêmes ;
    #   - joy_teleop/clawbot_restart_teleop.sh est un outil manuel de l'opérateur,
    #     hors périmètre P07 (fichier modifié hors de la zone de travail) : signalé
    #     dans le rapport, à arbitrer.
    local trouves
    # `pgrep` seul est refusé aussi : la forme liste `["pgrep", "-f"]` échappe à un
    # motif littéral « pgrep -f », et un pgrep sans -f reste un pilotage par motif.
    trouves=$(grep -rnE 'pkill|killall|pgrep' \
        --include='*.py' --include='*.sh' --include='*.service' \
        --exclude-dir=install --exclude-dir=build --exclude-dir=log \
        --exclude-dir=.git --exclude-dir=docs --exclude-dir=manual \
        . 2>/dev/null \
        | grep -vE '^\./(scripts/check\.sh|tests/test_units\.py):' \
        | grep -vE '^\./joy_teleop/clawbot_restart_teleop\.sh:' || true)
    if [[ -n "$trouves" ]]; then
        echo "ERREUR : pilotage de processus par motif interdit (INV-08, S33) :" >&2
        echo "$trouves" | head -10 >&2
        return 1
    fi
    echo "OK     aucun pkill/killall/pgrep hors exceptions nommées"
}

run_duplicates() {
    echo "── doublons ────────────────────────────────────────────────────────"
    local strict=0
    [[ $STRICT_DUPLICATES -eq 1 ]] && strict=1
    python3 - "$strict" <<'PY'
"""Repère les fichiers *.py identiques présents dans deux paquets différents."""
import fnmatch
import hashlib
import sys
from pathlib import Path

strict = sys.argv[1] == "1"
racine = Path(".")
exclus = {"install", "build", "log", ".git", "__pycache__", ".pytest_cache", "site", "manual"}

empreintes = {}
for chemin in racine.rglob("*.py"):
    rel = chemin.relative_to(racine)
    if set(rel.parts) & exclus:
        continue
    if rel.as_posix().startswith("tests/manual/"):
        continue
    digest = hashlib.sha256(chemin.read_bytes()).hexdigest()
    empreintes.setdefault(digest, []).append(rel.as_posix())

def paquet(chemin: str) -> str:
    morceaux = chemin.split("/")
    return morceaux[0] if len(morceaux) > 1 else "."

allowlist = []
fichier = Path("scripts/duplicates_allowlist.txt")
if fichier.is_file():
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#"):
            allowlist.append(ligne)

signales = 0
refuses = 0
for digest, chemins in sorted(empreintes.items()):
    if len({paquet(c) for c in chemins}) < 2:
        continue
    signales += 1
    autorise = all(any(fnmatch.fnmatchcase(c, motif) for motif in allowlist) for c in chemins)
    etiquette = "toléré (allowlist)" if autorise else "À FUSIONNER"
    print(f"  {etiquette} : {' == '.join(sorted(chemins))}")
    if strict and not autorise:
        refuses += 1

if signales == 0:
    print("  aucun doublon entre paquets")
else:
    print(f"  {signales} groupe(s) de doublons — avertissement, code 0 sans --strict-duplicates")
if refuses:
    print(f"ERREUR : {refuses} groupe(s) de doublons non autorise(s) (--strict-duplicates)",
          file=sys.stderr)
    sys.exit(1)
PY
}

if [[ $INTEGRATION -eq 1 ]]; then
    echo "── integration ─────────────────────────────────────────────────────"
    python3 -m pytest -q -p pytest_asyncio.plugin -m integration
    echo "Vérification d'intégration terminée : code 0"
    exit 0
fi

run_lint
run_unit
run_cpp
run_trace
run_interdits
run_duplicates

echo "Vérification terminée : code 0"
