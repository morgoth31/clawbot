#!/usr/bin/env bash
# Collecte DYNAMIQUE, lecture seule, domaine 28. Aucune commande mutante.
# Usage : collect_runtime.sh <repertoire_sortie>
set -uo pipefail
OUT="${1:?usage: collect_runtime.sh <repertoire_sortie>}"
mkdir -p "$OUT"
unset VIRTUAL_ENV PYTHONPATH PYTHONHOME
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
export ROS_DOMAIN_ID=28
# setup.bash de Humble lit des variables non definies : -u doit etre suspendu le temps du source
set +u
# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash || { echo "ROS introuvable" > "$OUT/00_ERREUR.txt"; exit 1; }
# shellcheck disable=SC1091
[ -f /home/jetson/clawbot/install/setup.bash ] && source /home/jetson/clawbot/install/setup.bash
set -u

{
  echo "collecte=runtime"
  echo "horodatage=$(date -Iseconds)"
  echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
  echo "ROS_DISTRO=$ROS_DISTRO"
  echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-non defini (defaut rmw_fastrtps_cpp)}"
  echo "FASTRTPS_DEFAULT_PROFILES_FILE=${FASTRTPS_DEFAULT_PROFILES_FILE:-non defini}"
  echo "CYCLONEDDS_URI=${CYCLONEDDS_URI:-non defini}"
  echo "uptime=$(uptime -p)"
  echo "charge=$(cat /proc/loadavg)"
} > "$OUT/00_meta.txt"

timeout 15 ros2 node list > "$OUT/01_nodes.txt" 2>&1
: > "$OUT/02_node_info.txt"
while IFS= read -r n; do
  echo "=== $n"
  timeout 10 ros2 node info "$n" 2>&1
done < "$OUT/01_nodes.txt" > "$OUT/02_node_info.txt"

timeout 15 ros2 topic list -t    > "$OUT/03_topics_types.txt" 2>&1
timeout 15 ros2 service list -t  > "$OUT/04_services.txt" 2>&1
timeout 15 ros2 action list -t   > "$OUT/05_actions.txt" 2>&1
timeout 15 ros2 param list       > "$OUT/06_params_liste.txt" 2>&1

# QoS effectif par topic (editeurs et abonnes)
: > "$OUT/07_topics_info_v.txt"
while IFS= read -r t; do
  echo "=== $t"
  timeout 10 ros2 topic info -v "$t" 2>&1
done < <(awk '{print $1}' "$OUT/03_topics_types.txt") > "$OUT/07_topics_info_v.txt"

# Cadence : topics images/points exclus (bande passante)
: > "$OUT/08_topics_hz.txt"
while IFS= read -r t; do
  case "$t" in
    *image*|*compressed*|*points*|*scan*|*camera_info*) continue ;;
  esac
  echo "=== $t"
  timeout 7 ros2 topic hz "$t" 2>&1 | tail -3
done < <(awk '{print $1}' "$OUT/03_topics_types.txt") > "$OUT/08_topics_hz.txt"

timeout 10 ros2 topic echo /tf_static --once > "$OUT/09_tf_static.txt" 2>&1
timeout 10 ros2 topic echo /tf --once        > "$OUT/09_tf_dynamique.txt" 2>&1
grep -h -E 'child_frame_id|frame_id' "$OUT/09_tf_static.txt" "$OUT/09_tf_dynamique.txt" \
  > "$OUT/09_tf_cadres.txt" 2>/dev/null

ps -eo pid,ppid,pcpu,pmem,rss,etimes,comm,args --sort=-pcpu | head -40 \
  > "$OUT/10_processus.txt" 2>&1
df -h / /dev/shm > "$OUT/11_disque_shm.txt" 2>&1
ss -uan 2>/dev/null | grep -E ':(7400|7401|7410|7411|7412|7413|7414|7415)' \
  > "$OUT/12_udp_rtps.txt" 2>&1
ip -s link show > "$OUT/12_net.txt" 2>&1
cat /proc/interrupts > "$OUT/13_interrupts.txt" 2>&1
timeout 6 tegrastats --interval 1000 > "$OUT/14_tegrastats.txt" 2>&1 \
  || echo "[NON OBSERVÉ / À VÉRIFIER] → obtenir : sudo tegrastats --interval 1000" \
     >> "$OUT/14_tegrastats.txt"
timeout 25 ros2 doctor --report > "$OUT/15_doctor.txt" 2>&1

: > "$OUT/16_journaux.txt"
for u in $(systemctl list-units --type=service --state=running --no-legend --no-pager \
           | awk '{print $1}' | grep -E '^(clawbot|ros2-|yolo)' || true); do
  echo "=== $u"
  journalctl -u "$u" -n 40 --no-pager 2>&1 | tail -40
done > "$OUT/16_journaux.txt"
journalctl -k -n 80 --no-pager > "$OUT/16_journal_noyau.txt" 2>&1

{
  for f in "$OUT"/*; do
    [ "$(basename "$f")" = "MANIFEST.txt" ] && continue
    printf '%s\t%s\t%s\n' "$(basename "$f")" "$(stat -c %s "$f")" "$(head -1 "$f")"
  done
} > "$OUT/MANIFEST.txt"

echo "collecte dynamique terminee dans $OUT"
wc -l < "$OUT/MANIFEST.txt"
