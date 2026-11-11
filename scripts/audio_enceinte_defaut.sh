#!/usr/bin/env bash
# Route la sortie audio par défaut vers l'enceinte Bluetooth A2DP, en la reconnectant si besoin.
#
# Trois pièges constatés le 2026-11-11 :
#  - un redémarrage de bluetooth.service conserve l'appairage mais ne reconnecte pas l'enceinte ;
#  - PulseAudio perd la carte bluez quand bluetoothd redémarre : il faut recharger ses modules ;
#  - `pactl set-default-sink` n'est pas persistant après un redémarrage de PulseAudio.
#
# Usage : ./scripts/audio_enceinte_defaut.sh [AA:BB:CC:DD:EE:FF]
set -uo pipefail

MAC="${1:-40:72:18:F0:2C:C9}"

# 1. Connexion si l'enceinte est appairée mais pas connectée.
if bluetoothctl info "$MAC" 2>/dev/null | grep -q "Paired: yes" \
   && ! bluetoothctl info "$MAC" 2>/dev/null | grep -q "Connected: yes"; then
    echo "connexion à $MAC…"
    bluetoothctl connect "$MAC" >/dev/null 2>&1 || true
    sleep 3
fi

# 2. Carte bluez absente (PulseAudio a perdu l'enceinte) : recharger la découverte Bluetooth.
if ! pactl list cards short 2>/dev/null | grep -q bluez_card; then
    echo "carte bluez absente : rechargement des modules PulseAudio"
    pactl unload-module module-bluez5-discover 2>/dev/null || true
    pactl load-module module-bluetooth-discover >/dev/null 2>&1 || true
    sleep 2
fi

CARTE=$(pactl list cards short 2>/dev/null | awk '/bluez_card/ {print $2; exit}')
SINK=$(pactl list sinks short 2>/dev/null | awk '/bluez_sink/ {print $2; exit}')
if [ -z "${SINK:-}" ]; then
    echo "aucun sink bluez : enceinte non connectée ou profil audio non disponible"
    exit 1
fi

# 3. Profil A2DP et sink par défaut.
if [ -n "${CARTE:-}" ]; then
    pactl set-card-profile "$CARTE" a2dp-sink 2>/dev/null || true
fi
pactl set-default-sink "$SINK"
echo "sink par défaut : $SINK"
