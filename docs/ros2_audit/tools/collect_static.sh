#!/usr/bin/env bash
# Collecte STATIQUE du workspace ROS 2. Ne lance aucun noeud, ne modifie rien.
# Usage : collect_static.sh <repertoire_sortie>
set -uo pipefail
WS=/home/jetson/clawbot
OUT="${1:?usage: collect_static.sh <repertoire_sortie>}"
mkdir -p "$OUT"
cd "$WS" || exit 1

{
  echo "collecte=static"
  echo "horodatage=$(date -Iseconds)"
  echo "host=$(hostname)"
  echo "kernel=$(uname -r)"
  echo "user=$(id -un)"
  echo "ws=$WS"
  echo "git_head=$(git rev-parse HEAD)"
  echo "git_branche=$(git rev-parse --abbrev-ref HEAD)"
  echo "git_fichiers_modifies=$(git status --porcelain | wc -l)"
  echo "ros_distro=${ROS_DISTRO:-non-source}"
} > "$OUT/00_meta.txt"

# 01-02 : packages presents sur disque (hors build/install/log)
find . -maxdepth 3 -name package.xml -not -path './build/*' \
     -not -path './install/*' -not -path './log/*' | sort > "$OUT/01_package_xml.txt"
: > "$OUT/02_packages.tsv"
while IFS= read -r p; do
  nom=$(tr -d '\n' < "$p" | sed -n 's:.*<name>\([^<]*\)</name>.*:\1:p;q')
  ver=$(tr -d '\n' < "$p" | sed -n 's:.*<version>\([^<]*\)</version>.*:\1:p;q')
  printf '%s\t%s\t%s\n' "$p" "$nom" "$ver" >> "$OUT/02_packages.tsv"
done < "$OUT/01_package_xml.txt"

# 03 : interfaces .msg/.srv/.action
find . -path ./build -prune -o -path ./install -prune -o -type f \
     \( -name '*.msg' -o -name '*.srv' -o -name '*.action' \) -print \
     | sort > "$OUT/03_interfaces_fichiers.txt"
while IFS= read -r f; do echo "=== $f"; cat "$f"; done \
  < "$OUT/03_interfaces_fichiers.txt" > "$OUT/03_interfaces_contenu.txt"

# 04 : launch files et structures remarquables
find . -path ./build -prune -o -path ./install -prune -o -type f \
     -name '*.launch.py' -print | sort > "$OUT/04_launch_fichiers.txt"
grep -rn --include='*.launch.py' \
  -E "Node\(|ComposableNode|LifecycleNode|TimerAction|executor|namespace|parameters=|remappings=" . \
  2>/dev/null | grep -v '^./build/' | grep -v '^./install/' \
  > "$OUT/04_launch_structures.txt"

# 05 : configuration YAML
find . -path ./build -prune -o -path ./install -prune -o -type f \
     -name '*.yaml' -print | sort > "$OUT/05_yaml_fichiers.txt"
xargs -a "$OUT/05_yaml_fichiers.txt" sha256sum > "$OUT/05_yaml_sha256.txt" 2>/dev/null
grep -rn --include='*.yaml' \
  -E "reliability|durability|history:|depth|use_sim_time|qos_overrides" . \
  2>/dev/null | grep -v '^./build/' | grep -v '^./install/' \
  > "$OUT/05_yaml_qos.txt"

# 06 : unites systemd (lecture seule)
systemctl list-units --type=service --all --no-pager --no-legend \
  > "$OUT/06_units_toutes.txt" 2>&1
systemctl list-units --type=service --state=running --no-pager --no-legend \
  > "$OUT/06_units_actives.txt" 2>&1
: > "$OUT/06_units_proprietes.txt"
for u in $(awk '{print $1}' "$OUT/06_units_actives.txt" \
           | grep -E '^(clawbot|ros2-|yolo|yahboom)' || true); do
  echo "=== $u"
  systemctl show "$u" -p Id -p FragmentPath -p ExecStart -p ExecStop \
    -p Restart -p RestartSec -p Requires -p After -p Conflicts \
    -p Environment -p User -p WorkingDirectory 2>&1
done > "$OUT/06_units_proprietes.txt"
ls -l /etc/systemd/system/ 2>/dev/null \
  | grep -E 'clawbot|ros2-|yolo|yahboom' > "$OUT/06_units_symlinks.txt"

# 07 : URDF / xacro
find . -path ./build -prune -o -path ./install -prune -o -type f \
     \( -name '*.urdf' -o -name '*.xacro' \) -print | sort > "$OUT/07_urdf_fichiers.txt"
grep -rn --include='*.urdf' --include='*.xacro' \
  -E "<joint|<parent|<child|<link name" . 2>/dev/null \
  | grep -v '^./build/' | grep -v '^./install/' > "$OUT/07_urdf_joints.txt"

# 08 : analyse de code (executors, groupes, QoS, entrees/sorties, TF)
mapfile -t SRC < <(xargs -a "$OUT/01_package_xml.txt" -n1 dirname 2>/dev/null | sort -u)
grep -rn --include='*.py' -E "MultiThreadedExecutor|SingleThreadedExecutor|MutuallyExclusive|Reentrant|create_callback_group|create_timer" \
  "${SRC[@]}" > "$OUT/08_executors_py.txt" 2>/dev/null
grep -rn --include='*.cpp' -E "MultiThreadedExecutor|SingleThreadedExecutor|MutuallyExclusive|Reentrant|create_callback_group|create_wall_timer" \
  "${SRC[@]}" > "$OUT/08_executors_cpp.txt" 2>/dev/null
grep -rn --include='*.py' -E "QoSProfile|ReliabilityPolicy|DurabilityPolicy|HistoryPolicy|qos_profile" \
  "${SRC[@]}" > "$OUT/08_qos_py.txt" 2>/dev/null
grep -rn --include='*.py' -E "create_publisher|create_subscription|create_service|ActionServer|ActionClient" \
  "${SRC[@]}" > "$OUT/08_io_py.txt" 2>/dev/null
grep -rn --include='*.py' -E "declare_parameter|get_parameter" \
  "${SRC[@]}" > "$OUT/08_params_py.txt" 2>/dev/null
grep -rn --include='*.py' -E "TransformBroadcaster|StaticTransformBroadcaster|lookup_transform|Buffer\(" \
  "${SRC[@]}" > "$OUT/08_tf_py.txt" 2>/dev/null
grep -rn --include='*.py' -E "time\.sleep|\.result\(\)|cv2\.(imshow|waitKey)|requests\.|subprocess\.|spin_once" \
  "${SRC[@]}" > "$OUT/08_sleeps_py.txt" 2>/dev/null

echo "collecte statique terminee dans $OUT"
ls -1 "$OUT" | wc -l
