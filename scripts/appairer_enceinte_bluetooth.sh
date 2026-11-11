#!/usr/bin/env bash
# Appairage d'une enceinte BR/EDR quand l'hôte ne répond pas à IO_Capability_Request.
#
# Contexte mesuré le 2026-11-11 sur Clawbot X3 Plus (L4T R36.4.7, noyau 5.15.148-tegra,
# adaptateur Realtek RTL8822CU) : la capture btmon montre l'Autentication Requested, la
# demande de clé, puis IO_Capability_Request — et AUCUNE réponse de l'hôte (ni positive ni
# négative), alors que `bondable` est actif. L'appairage échoue donc toujours côté hôte.
#
# Ce script fournit la réponse manquante au niveau HCI : il injecte
#   IO_Capability_Request_Reply   (OGF 0x01, OCF 0x002b) : IO cap 0x03 = NoInputNoOutput,
#                                                       OOB 0x00, AuthReq 0x04 = bonding sans MITM
#   User_Confirmation_Request_Reply (OGF 0x01, OCF 0x002c) : valide le « Just Works »
# en boucle courte pendant que btmgmt lance l'appairage.
#
# Usage : sudo ./scripts/appairer_enceinte_bluetooth.sh 40:72:18:F0:2C:C9
# Prérequis : enceinte en mode appairage (voyant rapide), bluetooth.service actif.
# Effet : appairage + trust + connexion. La clé est stockée par BlueZ
# (/var/lib/bluetooth/<adaptateur>/<mac>/info) : inutile de relancer, sauf après
# désappairage ou reset de l'enceinte.
set -uo pipefail

MAC="${1:?usage: $0 AA:BB:CC:DD:EE:FF}"
IFS=':' read -r b1 b2 b3 b4 b5 b6 <<< "$MAC"
LE="$b6 $b5 $b4 $b3 $b2 $b1"   # adresse en little-endian pour les commandes HCI

echo "[1/4] Tentative de désactivation de Secure Connections (souvent refusée : status 0x0c)"
sudo hcitool -i hci0 cmd 0x03 0x007a 0x00 || true

echo "[2/4] Répondeur IO_Capability / User_Confirmation en tâche de fond (12 s)"
(
    for _ in $(seq 1 40); do
        sudo hcitool -i hci0 cmd 0x01 0x002b $LE 0x03 0x00 0x04 >/dev/null 2>&1 || true
        sudo hcitool -i hci0 cmd 0x01 0x002c $LE >/dev/null 2>&1 || true
        sleep 0.3
    done
) &
REPONDEUR=$!

echo "[3/4] Appairage BR/EDR (NoInputNoOutput)"
sudo btmgmt --index 0 pair -c 3 -t 0 "$MAC" || true
kill "$REPONDEUR" 2>/dev/null || true
wait "$REPONDEUR" 2>/dev/null || true

echo "[4/4] Confiance et connexion"
bluetoothctl trust "$MAC" >/dev/null 2>&1 || true
bluetoothctl connect "$MAC" >/dev/null 2>&1 || true
bluetoothctl info "$MAC" | grep -E "Name|Paired|Trusted|Connected"
