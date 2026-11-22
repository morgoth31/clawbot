#!/bin/bash
# pair_procontroller.sh — appairer une manette Nintendo en Bluetooth (BR/EDR)
#
# Usage : sudo bash pair_procontroller.sh [adresse]
#
# À faire avant : maintenir le bouton SYNC (petit bouton à l'arrière) jusqu'à ce
# que les voyants défilent vite.
#
# Deux corrections par rapport à la version précédente, mesurées le 2026-11-15 :
#   1. L'adresse n'est plus codée en dur. Le pad se présentait sous
#      98:B6:E9:43:94:AA alors que le script visait 98:B6:1F:49:26:F3 : toutes les
#      tentatives étaient mortes avant de commencer. On découvre le pad par son
#      nom à chaque appairage.
#   2. `bluetoothctl pair` seul n'aboutit jamais sur ce noyau : il n'émet aucune
#      réponse à IO_Capability_Request (même cause que l'enceinte SRS-XB100).
#      L'appairage passe par l'injection HCI de
#      scripts/appairer_enceinte_bluetooth.sh.

set -u

ICI=$(cd "$(dirname "$0")" && pwd)
INJECTION="$ICI/../scripts/appairer_enceinte_bluetooth.sh"
MAX_SCAN=${MAX_SCAN:-30}

MAC="${1:-}"

echo "============================================"
echo "  Appairage manette Nintendo (Bluetooth)"
echo "============================================"

if [ ! -x "$INJECTION" ]; then
    echo "ERREUR : $INJECTION introuvable ou non exécutable" >&2
    exit 1
fi

if [ -z "$MAC" ]; then
    echo
    echo ">>> Maintenir le bouton SYNC de la manette (voyants qui défilent)"
    echo ">>> Recherche pendant ${MAX_SCAN}s..."
    bluetoothctl power on >/dev/null 2>&1
    bluetoothctl pairable on >/dev/null 2>&1
    timeout $((MAX_SCAN + 2)) bluetoothctl scan on >/dev/null 2>&1
    MAC=$(bluetoothctl devices 2>/dev/null \
        | grep -iE "pro controller|nintendo" \
        | head -1 | awk '{print $2}')
fi

if [ -z "$MAC" ]; then
    echo "ERREUR : aucune manette Nintendo vue pendant le scan." >&2
    echo "  - bouton SYNC maintenu jusqu'au défilement des voyants ?" >&2
    echo "  - manette déjà connectée à une Switch ?" >&2
    echo "  - bluetoothctl devices pour lister ce qui est réellement vu." >&2
    exit 1
fi

echo
echo ">>> Manette : $MAC"
echo ">>> Appairage avec réponse IO_Capability injectée"
sudo bash "$INJECTION" "$MAC"

echo
echo ">>> État final"
bluetoothctl info "$MAC" | grep -E "Name|Paired|Trusted|Connected"

echo
echo ">>> Nœuds d'entrée"
if ls /dev/input/js* >/dev/null 2>&1; then
    for js in /dev/input/js*; do
        echo -n "$js : "
        cat "/sys/class/input/$(basename "$js")/device/name" 2>/dev/null
    done
    echo
    echo "Le pad est le nœud dont le nom ne contient pas « IMU »."
    echo "Test : jstest --normal /dev/input/js0"
else
    echo "Aucun /dev/input/js* — vérifier que hidp est chargé :"
    echo "  sudo modprobe hidp && lsmod | grep hidp"
fi
