#!/bin/bash
# Test A/B du SLAM 2D hors robot : rejoue un bag en domaine 99 avec deux jeux de parametres
# slam_toolbox, EKF identique dans les deux cas. Aucun acces au robot, aucun topic de commande.
#
# Usage : scripts/ab_slam_toolbox.sh <A|B> [duree_s] [options]
#   A = avant : minimum_time_interval 0,5 s, noeuds tous les 10 cm, recherche 0,5 m
#   B = apres : 0,1 s, 5 cm, recherche 0,8 m  (REQ-DRV-012)
# Options :
#   --bag <dossier>     bag a rejouer (defaut /var/lib/clawbot/test_data/slam2d_piece)
#   --out <dossier>     dossier de sortie (defaut /tmp/ab_slam)
#   --ekf <yaml>        configuration de l'EKF (defaut <depot>/config/ekf.yaml)
#
# Enseignements integres (mesures du 2026-11-23, voir
# docs/audit/2026-11-23-ab-slam/rapport.md) :
#   * les noeuds sont lances sous `timeout` : `kill` ne tue que le lanceur `ros2 run`, pas
#     l'enfant, et les orphelins faussent la variante suivante ;
#   * la carte est sauvegardee PENDANT le rejeu : une fois le bag fini, /clock s'arrete, les
#     noeuds en temps simule gelent et le map_saver rend result=255 ;
#   * le map_saver interne de slam_toolbox echoue en rejeu : on ecrit la carte nous-memes
#     (scripts/sauve_carte.py, abonnement TRANSIENT_LOCAL).
set -u

VAR="${1:?A ou B}"
shift || true
DUREE=0
BAG=/var/lib/clawbot/test_data/slam2d_piece
OUT=/tmp/ab_slam
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EKF="$(dirname "$ICI")/config/ekf.yaml"

while [ $# -gt 0 ]; do
    case "$1" in
        --bag) BAG="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        --ekf) EKF="$2"; shift 2 ;;
        *) [ "$1" -eq "$1" ] 2>/dev/null && DUREE="$1"; shift ;;
    esac
done

if [ "$VAR" = "A" ]; then
    P=(-p minimum_time_interval:=0.5 -p minimum_travel_distance:=0.1
       -p minimum_travel_heading:=0.1 -p correlation_search_space_dimension:=0.5)
else
    P=(-p minimum_time_interval:=0.1 -p minimum_travel_distance:=0.05
       -p minimum_travel_heading:=0.05 -p correlation_search_space_dimension:=0.8)
fi

mkdir -p "$OUT"
rm -f "$OUT"/carte_"$VAR".*
SHIM="" ; EKF_PID="" ; SLAM="" ; BAGPID=""

if [ "$DUREE" -gt 0 ]; then
    SAVE_AT=$(( DUREE > 10 ? DUREE - 6 : DUREE / 2 ))
else
    SAVE_AT=292
fi

command -v ros2 >/dev/null || { echo "ERREUR : ros2 introuvable (sourcer /opt/ros/humble/setup.bash)"; exit 3; }
echo "domaine ${ROS_DOMAIN_ID:-?} (doit etre 99), bag $BAG, EKF $EKF"

echo "=== variante $VAR (duree ${DUREE:-complete}, sauvegarde a t+${SAVE_AT}s) ==="
# Verification par /proc, pas par `ros2 node list` : le demon ROS cache les noeuds morts.
pour_domaine() {
    local cible="$1" reste=0 p d
    for p in $(ps -eo pid,args | grep -E "$cible" | grep -v grep | awk '{print $1}'); do
        d=$(tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep '^ROS_DOMAIN_ID=' | cut -d= -f2)
        [ "$d" = "${ROS_DOMAIN_ID:-}" ] && reste=$(( reste + 1 ))
    done
    echo "$reste"
}

if [ "$(pour_domaine async_slam_toolbox_node)" -gt 0 ]; then
    echo "ERREUR : un slam_toolbox tourne deja en domaine ${ROS_DOMAIN_ID:-?}"
    exit 5
fi

# Shim de rejeu : certains bags sont enregistres avec le cadre 'laser', l'arbre TF ne connait
# que 'laser_link'. Ce shim n'existe qu'en rejeu, jamais sur le robot.
timeout "$(( SAVE_AT + 60 ))" ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 \
    laser_link laser > "$OUT/shim_$VAR.log" 2>&1 &
SHIM=$!
trap 'kill $SHIM $EKF_PID $SLAM $BAGPID 2>/dev/null' EXIT
timeout "$(( SAVE_AT + 60 ))" ros2 run robot_localization ekf_node --ros-args \
    -r __node:=ekf_filter_node --params-file "$EKF" -p use_sim_time:=true \
    > "$OUT/ekf_$VAR.log" 2>&1 &
EKF_PID=$!
sleep 3
timeout "$(( SAVE_AT + 60 ))" ros2 run slam_toolbox async_slam_toolbox_node --ros-args \
    -p base_frame:=base_link -p odom_frame:=odom -p map_frame:=map \
    -p scan_topic:=/scan -p mode:=mapping -p use_sim_time:=true \
    -p resolution:=0.05 -p min_laser_range:=0.15 -p max_laser_range:=8.0 \
    -p map_update_interval:=2.0 "${P[@]}" > "$OUT/slam_$VAR.log" 2>&1 &
SLAM=$!
sleep 6

# Ne pas juger un demarrage sur `Registering sensor` (ecrit au premier scan) mais sur
# `Using solver plugin` (ecrit a l'initialisation).
if ! grep -q "Using solver plugin" "$OUT/slam_$VAR.log" 2>/dev/null; then
    echo "ERREUR : /slam_toolbox n'a pas demarre"; tail -n 4 "$OUT/slam_$VAR.log"; exit 4
fi

ros2 bag play "$BAG" --clock -r 1.0 --topics /scan /odom_raw /imu/data_raw /tf_static \
    > "$OUT/play_$VAR.log" 2>&1 &
BAGPID=$!

sleep "$SAVE_AT"
echo "sauvegarde de la carte (temps simule encore actif)"
/usr/bin/python3 "$ICI/sauve_carte.py" "$OUT/carte_$VAR" 20 > "$OUT/save_$VAR.log" 2>&1
sleep 3
kill "$BAGPID" 2>/dev/null
wait "$BAGPID" 2>/dev/null
kill $SHIM $EKF_PID $SLAM 2>/dev/null
sleep 4

echo "=== fin $VAR ==="
if [ -f "$OUT/carte_$VAR.pgm" ]; then
    ls -l "$OUT/carte_$VAR".*
    md5sum "$OUT/carte_$VAR.pgm"
else
    echo "ECHEC : aucune carte ecrite"
    tail -n 4 "$OUT/save_$VAR.log"
fi
echo "scans rejetes : $(grep -c 'dropping message' "$OUT/slam_$VAR.log" 2>/dev/null || echo 0)"
