#!/bin/bash
# pair_procontroller.sh — Pair and connect Nintendo Switch Pro Controller
# Usage: sudo bash pair_procontroller.sh
#
# Before running: HOLD the SYNC button (small button on the back of the controller)
# until the LEDs cycle rapidly (pairing mode).

set -e

MAC="98:B6:1F:49:26:F3"

echo "============================================"
echo "  Pro Controller Bluetooth Pairing Script"
echo "============================================"
echo ""
echo ">>> HOLD the SYNC button on the back of the"
echo ">>> Pro Controller until LEDs cycle rapidly!"
echo ""
echo "Scanning for $MAC ..."

# Ensure adapter is ready
bluetoothctl power on
bluetoothctl agent on
bluetoothctl default-agent

# Start scan in background
bluetoothctl scan on &
SCAN_PID=$!

# Wait until we find the controller (up to 30 seconds)
FOUND=0
for i in $(seq 1 30); do
    sleep 1
    if bluetoothctl devices 2>/dev/null | grep -q "$MAC"; then
        echo ""
        echo ">>> FOUND Pro Controller!"
        FOUND=1
        break
    fi
    echo -n "."
done

# Stop scan
bluetoothctl scan off 2>/dev/null || true
kill $SCAN_PID 2>/dev/null || true
wait $SCAN_PID 2>/dev/null || true

if [ "$FOUND" -eq 0 ]; then
    echo ""
    echo "ERROR: Pro Controller not found!"
    echo "Make sure:  1) Controller is charged"
    echo "            2) You are HOLDING the SYNC button"
    echo "            3) Controller is not already connected to a Switch"
    exit 1
fi

echo ""
echo ">>> Step 1: Pairing..."
bluetoothctl pair "$MAC" 2>&1 || echo "(pair may auto-complete)"
sleep 2

echo ">>> Step 2: Trusting..."
bluetoothctl trust "$MAC" 2>&1
sleep 1

echo ">>> Step 3: Connecting..."
bluetoothctl connect "$MAC" 2>&1
sleep 3

echo ""
echo ">>> Checking connection status..."
bluetoothctl info "$MAC" | grep -E "Name|Paired|Trusted|Connected|Icon"

echo ""
echo ">>> Checking joystick device..."
sleep 2
if ls /dev/input/js* 2>/dev/null; then
    echo ""
    echo "✅ SUCCESS! Joystick device found!"
    echo "You can test with: jstest /dev/input/js0"
else
    echo ""
    echo "⚠ No /dev/input/js* device yet."
    echo "Checking /proc/bus/input/devices for Pro Controller..."
    if grep -qi "pro.controller\|nintendo" /proc/bus/input/devices 2>/dev/null; then
        echo "✅ Controller detected in input subsystem!"
        grep -A8 -i "pro.controller\|nintendo" /proc/bus/input/devices
    else
        echo ""
        echo "❌ Controller not registered as input device."
        echo ""
        echo "Troubleshooting:"
        echo "  1. Check dmesg:  sudo dmesg | tail -30"
        echo "  2. Verify hid_nintendo module: lsmod | grep hid_nintendo"
        echo "  3. Try: sudo modprobe -r hid_nintendo && sudo modprobe hid_nintendo"
        echo "  4. Restart bluetooth: sudo systemctl restart bluetooth"
        echo "  5. Reconnect: bluetoothctl disconnect $MAC && bluetoothctl connect $MAC"
    fi
fi
