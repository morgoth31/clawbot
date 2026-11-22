#!/usr/bin/env python3
# SCRIPT MANUEL — pas un test pytest (REQ-TEST-004).
#
# Attend un service : le pont C++ doit écouter sur http://localhost:8002
# (il expose /mode, /health, /tools et /command).
# Sans service, l'import échoue en httpx.ConnectError et toute la collecte
# pytest tomberait (constat S42).
#
# Lancement :
#     python3 tests/manual/manual_modes.py
#
# Hors collecte : pytest.ini contient norecursedirs = tests/manual, et le
# fichier n'a plus le préfixe test_.

"""Vérification manuelle des modes du pont C++ (STANDBY, NAVIGATION, MANIPULATION, EVOLUTION)."""
import httpx, json, sys

BRIDGE_URL = "http://localhost:8002"
results = []

def record(tid, name, status, detail=""):
    results.append({"id": tid, "name": name, "status": status, "detail": detail})
    sym = {"PASS":"OK","FAIL":"XX","SKIP":"--","WARN":"!!"}[status]
    print(f"  [{sym}] {tid}: {name} -- {status}" + (f" ({detail})" if detail else ""))

def call_bridge(func, args=None):
    r = httpx.post(f"{BRIDGE_URL}/command", json={"function": func, "arguments": args or {}}, timeout=10)
    return r

def set_mode(mode):
    r = httpx.post(f"{BRIDGE_URL}/mode", json={"mode": mode}, timeout=10)
    return r

def get_mode():
    r = httpx.get(f"{BRIDGE_URL}/mode", timeout=5)
    return r.json()

# ── Test 1: Initial mode is STANDBY ──────────────────────────────────────
m = get_mode()
record("MD1", "Initial mode = standby", "PASS" if m["mode"] == "standby" else "FAIL", m["mode"])
record("MD2", "Standby has 8 tools", "PASS" if m["available_tool_count"] == 8 else "FAIL",
       f'{m["available_tool_count"]} tools')

# ── Test 2: Tool filtering in STANDBY ───────────────────────────────────
# ControlArm should be 403 in STANDBY
r = call_bridge("ControlArm", {"joints_array": [90,90,90,90,90]})
record("MD3", "ControlArm blocked in standby (403)", "PASS" if r.status_code == 403 else "FAIL",
       f"HTTP {r.status_code}")

# GetBatteryVoltage should work in STANDBY
r = call_bridge("GetBatteryVoltage", {})
record("MD4", "GetBatteryVoltage allowed in standby", "PASS" if r.status_code == 200 else "FAIL",
       f"HTTP {r.status_code}")

# Stop should work in STANDBY
r = call_bridge("Stop", {})
record("MD5", "Stop allowed in standby", "PASS" if r.status_code == 200 else "FAIL",
       f"HTTP {r.status_code}")

# ── Test 3: Transition to MANIPULATION ──────────────────────────────────
r = set_mode("manipulation")
m = r.json()
record("MD6", "Transition to manipulation", "PASS" if m.get("mode") == "manipulation" else "FAIL",
       m.get("mode",""))

# ControlArm should now work
r = call_bridge("ControlArm", {"joints_array": [90,90,90,90,90]})
record("MD7", "ControlArm allowed in manipulation", "PASS" if r.status_code == 200 else "FAIL",
       f"HTTP {r.status_code}")

# SetVelocity should be blocked
r = call_bridge("SetVelocity", {"linear_x": 0.03, "linear_y": 0, "angular_z": 0})
record("MD8", "SetVelocity blocked in manipulation (403)", "PASS" if r.status_code == 403 else "FAIL",
       f"HTTP {r.status_code}")

# ── Test 4: Transition to NAVIGATION ────────────────────────────────────
r = set_mode("navigation")
m = r.json()
record("MD9", "Transition to navigation", "PASS" if m.get("mode") == "navigation" else "FAIL",
       m.get("mode",""))

# Stop should work in navigation
r = call_bridge("Stop", {})
record("MD10", "Stop allowed in navigation", "PASS" if r.status_code == 200 else "FAIL",
       f"HTTP {r.status_code}")

# ControlClaw should be blocked
r = call_bridge("ControlClaw", {"state": "open"})
record("MD11", "ControlClaw blocked in navigation (403)", "PASS" if r.status_code == 403 else "FAIL",
       f"HTTP {r.status_code}")

# ── Test 5: Transition to EVOLUTION ────────────────────────────────────
r = set_mode("evolution")
m = r.json()
record("MD12", "Transition to evolution", "PASS" if m.get("mode") == "evolution" else "FAIL",
       m.get("mode",""))

# GetBatteryVoltage should work
r = call_bridge("GetBatteryVoltage", {})
record("MD13", "GetBatteryVoltage allowed in evolution", "PASS" if r.status_code == 200 else "FAIL",
       f"HTTP {r.status_code}")

# ControlServo should be blocked
r = call_bridge("ControlServo", {"servo_id": 1, "angle": 90})
record("MD14", "ControlServo blocked in evolution (403)", "PASS" if r.status_code == 403 else "FAIL",
       f"HTTP {r.status_code}")

# ── Test 6: Return to STANDBY ───────────────────────────────────────────
r = set_mode("standby")
m = r.json()
record("MD15", "Return to standby", "PASS" if m.get("mode") == "standby" else "FAIL",
       m.get("mode",""))

# ── Test 7: Invalid mode ───────────────────────────────────────────────
r = set_mode("invalid_mode")
m = r.json()
record("MD16", "Invalid mode -> defaults to standby", "PASS" if m.get("mode") == "standby" else "WARN",
       m.get("mode",""))

# ── Summary ─────────────────────────────────────────────────────────────
counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "WARN": 0}
for r in results:
    counts[r["status"]] += 1
total = len(results)
print()
print(f"MODE TESTS: {total} tests | PASS:{counts['PASS']} FAIL:{counts['FAIL']} SKIP:{counts['SKIP']} WARN:{counts['WARN']}")
print("STATUT:", "SUCCES" if counts["FAIL"] == 0 else "ECHEC")
sys.exit(1 if counts["FAIL"] > 0 else 0)