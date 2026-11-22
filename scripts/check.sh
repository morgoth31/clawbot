#!/usr/bin/env bash
# Vérification unique du dépôt Clawbot (P00, REQ-TEST-001 à 005).
#
#   scripts/check.sh                     # lint, unitaires, cpp, traçabilité, interdits, doublons
#   scripts/check.sh tests               # idem, en limitant pytest au chemin donné
#   scripts/check.sh --self-test         # annonce les étapes et sort 0
#   scripts/check.sh --integration       # pytest -m integration en domaine 99
#   scripts/check.sh --strict-duplicates # échec sur tout doublon hors allowlist
#   scripts/check.sh --build             # + construction propre des paquets (env -i, /tmp)
#   scripts/check.sh --etape <nom>       # une seule étape : lint|unit|cpp|trace|interdits|doublons|cliquets|build
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
BUILD=0
ETAPE=
TARGETS=()

usage() {
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --self-test)          SELF_TEST=1 ;;
        --integration)        INTEGRATION=1 ;;
        --strict-duplicates)  STRICT_DUPLICATES=1 ;;
        --build)              BUILD=1 ;;
        --etape)              shift; ETAPE="${1:-}"
                              [[ -n "$ETAPE" ]] || { echo "check.sh : --etape attend un nom" >&2; exit 2; } ;;
        -h|--help)            usage; exit 0 ;;
        -*)                   echo "check.sh : option inconnue '$1'" >&2; exit 2 ;;
        *)                    TARGETS+=("$1") ;;
    esac
    shift
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
    echo "  lint      flake8 (ou ruff) sur les paquets maison, plafonné par requirements/.lint_baseline"
    echo "  unit      pytest -q en domaine ${ROS_DOMAIN_ID}"
    echo "  cpp       binaires gtest de build/"
    echo "  trace     scripts/trace_check.py --max-untraced <requirements/.untraced_baseline>"
    echo "  interdits pkill/killall/pgrep -f hors exception nommée"
    echo "  doublons  sha256 des *.py, doublons entre paquets (avertissement)"
    echo "  cliquets  .untraced_baseline et .lint_baseline comparés à main"
    if [[ $BUILD -eq 1 ]]; then
        echo "  build     colcon build depuis zéro, env -i, /tmp/clawbot_check_build"
    fi
    echo "Auto-test terminé : code 0"
    exit 0
fi

# ── 4. Étapes ────────────────────────────────────────────────────────────────
# Paquets maison seulement : les vendor (yahboomcar_*), attic/ et install/ restent dehors.
CIBLES_LINT=(clawbot_* yolo_node tests scripts joy_teleop)
LINT_BASELINE=requirements/.lint_baseline

run_lint() {
    echo "── lint ────────────────────────────────────────────────────────────"
    local outil="" nb=0 code=0 sortie base=0
    if command -v flake8 >/dev/null 2>&1; then
        outil="flake8"
    elif python3 -m flake8 --version >/dev/null 2>&1; then
        outil="python3 -m flake8"
    elif command -v ruff >/dev/null 2>&1; then
        outil="ruff"
    fi
    # Point d'injection pour les tests : flake8 vient du paquet système python3-flake8 et
    # reste importable même sans PYTHONPATH, il n'existe donc pas d'environnement « sans
    # outil » reproductible. La variable force la branche d'échec.
    if [[ "${CLAWBOT_LINT_SANS_OUTIL:-0}" == "1" ]]; then
        outil=""
    fi
    if [[ -z "$outil" ]]; then
        echo "ERREUR : aucun outil de lint disponible (ni flake8, ni ruff)." >&2
        echo "         L'étape ne s'ignore pas : /usr/bin/python3 -m pip install --user ruff" >&2
        exit 1
    fi
    echo "outil : $outil"
    if [[ "$outil" == "ruff" ]]; then
        sortie=$(ruff check "${CIBLES_LINT[@]}" 2>&1) || code=$?
        nb=$(printf '%s\n' "$sortie" | grep -cE '^[^ :]+:[0-9]+:[0-9]+')
    else
        # flake8 rend 1 quand il trouve des erreurs : ce n'est pas une panne, et
        # `set -e` tuerait le script sur cette affectation.
        sortie=$($outil --count --max-line-length=120 --extend-ignore=E203,W503 \
                 --statistics "${CIBLES_LINT[@]}" 2>&1) || code=$?
        printf '%s\n' "$sortie" | tail -12
        nb=$(printf '%s\n' "$sortie" | tail -1 | tr -dc '0-9')
    fi
    [[ -n "$nb" ]] || nb=0
    if [[ -f "$LINT_BASELINE" ]]; then
        base=$(tr -dc '0-9' < "$LINT_BASELINE") ; [[ -n "$base" ]] || base=0
    fi
    if [[ "$nb" -gt "$base" ]]; then
        echo "ERREUR : $nb erreurs de lint > plafond $base ($LINT_BASELINE)." >&2
        echo "         Corriger les nouvelles erreurs, ne relevez pas le plafond." >&2
        exit 1
    fi
    echo "lint : $nb erreur(s), plafond $base (code outil $code)"
}

run_cliquets() {
    echo "── cliquets ────────────────────────────────────────────────────────"
    local f actuel reference code=0
    for f in requirements/.untraced_baseline "$LINT_BASELINE"; do
        [[ -f "$f" ]] || continue
        actuel=$(tr -dc '0-9' < "$f") ; [[ -n "$actuel" ]] || actuel=0
        if ! git cat-file -e "main:$f" 2>/dev/null; then
            echo "OK     $f : absent de main, valeur de départ $actuel acceptée"
            continue
        fi
        reference=$(git show "main:$f" | tr -dc '0-9') ; [[ -n "$reference" ]] || reference=0
        if [[ "$actuel" -gt "$reference" ]]; then
            echo "ERREUR : $f a augmenté ($reference sur main -> $actuel)." >&2
            code=1
        else
            echo "OK     $f : $actuel <= $reference (main)"
        fi
    done
    [[ $code -eq 0 ]] || exit 1
}

run_build() {
    echo "── build ───────────────────────────────────────────────────────────"
    # Construction depuis zéro, dans un environnement qui ne contient QUE l'underlay ROS :
    # c'est la seule qui prouve que les package.xml déclarent leurs dépendances. Le code
    # de sortie est celui de colcon (jamais celui d'un `tail` : piège de D20).
    local code=0
    rm -rf /tmp/clawbot_check_build
    env -i HOME="$HOME" PATH=/usr/bin:/bin LANG=C.UTF-8 bash -c \
        'source /opt/ros/humble/setup.bash && colcon build \
            --build-base /tmp/clawbot_check_build/build \
            --install-base /tmp/clawbot_check_build/install \
            --event-handlers console_cohesion+' || code=$?
    if [[ $code -ne 0 ]]; then
        echo "ERREUR : construction propre en échec (colcon code $code)." >&2
        exit "$code"
    fi
    echo "Construction propre : conforme"
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

# ── 4 bis. Une seule étape, pour les tests et le diagnostic ──────────────────
case "$ETAPE" in
    "")      ;;
    lint)    run_lint;     echo "Étape lint terminée : code 0";     exit 0 ;;
    unit)    run_unit;     echo "Étape unit terminée : code 0";     exit 0 ;;
    cpp)     run_cpp;      echo "Étape cpp terminée : code 0";      exit 0 ;;
    trace)   run_trace;    echo "Étape trace terminée : code 0";    exit 0 ;;
    interdits) run_interdits; echo "Étape interdits terminée : code 0"; exit 0 ;;
    doublons) run_duplicates; echo "Étape doublons terminée : code 0";  exit 0 ;;
    cliquets) run_cliquets; echo "Étape cliquets terminée : code 0"; exit 0 ;;
    build)   run_build;    echo "Étape build terminée : code 0";    exit 0 ;;
    *) echo "check.sh : étape inconnue '$ETAPE'" >&2; exit 2 ;;
esac

[[ $BUILD -eq 1 ]] && run_build
run_lint
run_unit
run_cpp
run_trace
run_interdits
run_duplicates
run_cliquets

echo "Vérification terminée : code 0"
