#!/usr/bin/env python3
"""
Clawbot Non-Regression Test Suite
==================================
Teste les 43 fonctionnalites du bridge (port 8000) et du hardware_service (port 8001).
Genere un rapport JSON + texte avec PASS/FAIL/SKIP pour chaque test.

Usage:
    python3 /home/jetson/clawbot/tests/test_regression.py
    python3 /home/jetson/clawbot/tests/test_regression.py --skip-motion   # ne pas bouger le robot
    python3 /home/jetson/clawbot/tests/test_regression.py --skip-slam     # ne pas lancer SLAM
    python3 /home/jetson/clawbot/tests/test_regression.py --skip-camera   # ne pas capturer
    python3 /home/jetson/clawbot/tests/test_regression.py --skip-hardware # bridge uniquement

Notes d'exécution
-----------------
Les étapes qui reçoivent la configuration de ``main()`` s'appellent ``check_*`` :
ce ne sont pas des tests pytest mais des vérifications du lanceur manuel, qui
exigent le bridge HTTP sur le port 8000 et le hardware_service sur 8001. Elles
prenaient un paramètre positionnel ``args`` que pytest interprétait comme une
fixture, ce qui faisait échouer 19 collectes (audit S43).
"""

import argparse
import json
import os
import sys
import time
import base64
from datetime import datetime

try:
    import httpx
except ImportError:
    print("ERREUR: httpx non installe. pip3 install httpx")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────

BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://localhost:8000")
HW_URL = "http://localhost:8001"
TIMEOUT = 10.0

# ── Result tracking ───────────────────────────────────────────────────────────

results = []

def record(test_id: str, category: str, name: str, status: str, detail: str = "", response: dict = None):
    """Record a test result. status = PASS|FAIL|SKIP|WARN"""
    entry = {
        "id": test_id,
        "category": category,
        "name": name,
        "status": status,
        "detail": detail,
        "timestamp": datetime.now().isoformat(),
    }
    if response and len(str(response)) < 500:
        entry["response"] = response
    results.append(entry)
    symbol = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️", "WARN": "⚠️"}[status]
    print(f"  {symbol} [{test_id}] {name}: {status}" + (f" -- {detail}" if detail else ""))


def call_bridge(function: str, arguments: dict = None) -> dict:
    """POST /command on the bridge."""
    resp = httpx.post(
        f"{BRIDGE_URL}/command",
        json={"function": function, "arguments": arguments or {}},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def call_hw(method: str, path: str, **kwargs) -> dict:
    """Call hardware_service."""
    resp = httpx.request(method, f"{HW_URL}{path}", timeout=TIMEOUT, **kwargs)
    return resp


# ── Tests: Bridge Meta Endpoints ─────────────────────────────────────────────

def test_bridge_health():
    """M1: Bridge /health"""
    try:
        r = httpx.get(f"{BRIDGE_URL}/health", timeout=5.0)
        if r.status_code == 200 and r.json().get("status") == "healthy":
            record("M1", "Bridge-Meta", "GET /health", "PASS", response=r.json())
        else:
            record("M1", "Bridge-Meta", "GET /health", "FAIL", f"status={r.status_code}, body={r.text[:200]}")
    except Exception as e:
        record("M1", "Bridge-Meta", "GET /health", "FAIL", str(e))


def test_bridge_tools():
    """M2: Bridge /tools -- doit retourner 17 tools"""
    for fmt in ["openai", "anthropic", "raw"]:
        try:
            r = httpx.get(f"{BRIDGE_URL}/tools", params={"format": fmt}, timeout=5.0)
            if r.status_code == 200:
                tools = r.json()
                count = len(tools)
                if count == 18:
                    record(f"M2-{fmt}", "Bridge-Meta", f"GET /tools?format={fmt}", "PASS",
                           f"17 tools trouves", tools[0] if tools else None)
                else:
                    record(f"M2-{fmt}", "Bridge-Meta", f"GET /tools?format={fmt}", "FAIL",
                           f"{count} tools (attendu 17)")
            else:
                record(f"M2-{fmt}", "Bridge-Meta", f"GET /tools?format={fmt}", "FAIL",
                       f"HTTP {r.status_code}")
        except Exception as e:
            record(f"M2-{fmt}", "Bridge-Meta", f"GET /tools?format={fmt}", "FAIL", str(e))


def test_bridge_tools_names():
    """M2-verify: verifier que les 17 noms de tools sont corrects"""
    expected = {
        "SetVelocity", "Stop", "Speak", "NavigateTo",
        "CaptureCamera", "AnalyzeScene", "RecognizeFace", "RecognizeObject", "RecognizeQRCode",
        "Listen", "ControlServo", "ControlArm", "ControlClaw", "SetArmPose",
        "Beep", "SetLamps", "GetBatteryVoltage",
        "DetectObjects",
    }
    try:
        r = httpx.get(f"{BRIDGE_URL}/tools", params={"format": "openai"}, timeout=5.0)
        tools = r.json()
        names = {t["function"]["name"] for t in tools}
        missing = expected - names
        extra = names - expected
        if not missing and not extra:
            record("M2-names", "Bridge-Meta", "Tool names verification", "PASS",
                   f"Les 18 noms correspondent")
        else:
            detail = f"manquants: {missing}, extras: {extra}"
            record("M2-names", "Bridge-Meta", "Tool names verification", "FAIL", detail)
    except Exception as e:
        record("M2-names", "Bridge-Meta", "Tool names verification", "FAIL", str(e))


# ── Tests: Hardware Service Meta ──────────────────────────────────────────────

def test_hw_health():
    """H1: HW /health"""
    try:
        r = httpx.get(f"{HW_URL}/health", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "ok" and data.get("ros2") == True:
                record("H1", "HW-Meta", "GET /health", "PASS", response=data)
            else:
                record("H1", "HW-Meta", "GET /health", "WARN", f"ros2={data.get('ros2')}", data)
        else:
            record("H1", "HW-Meta", "GET /health", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H1", "HW-Meta", "GET /health", "FAIL", str(e))


def test_hw_system_status():
    """H2: HW /system/status"""
    try:
        r = httpx.get(f"{HW_URL}/system/status", timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            services = data.get("services", {})
            nodes = data.get("ros2_nodes", [])
            topics = data.get("ros2_topics", [])
            record("H2", "HW-Meta", "GET /system/status", "PASS",
                   f"services={len(services)}, nodes={len(nodes)}, topics={len(topics)}")
        else:
            record("H2", "HW-Meta", "GET /system/status", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H2", "HW-Meta", "GET /system/status", "FAIL", str(e))


def test_hw_telemetry():
    """H3: HW /telemetry"""
    try:
        r = httpx.get(f"{HW_URL}/telemetry", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            has_imu = "imu" in data
            has_vel = "velocity" in data
            has_servos = "servos" in data
            has_battery = "battery" in data
            if all([has_imu, has_vel, has_servos, has_battery]):
                record("H3", "HW-Meta", "GET /telemetry", "PASS",
                       f"imu={has_imu}, vel={has_vel}, servos={has_servos}, bat={has_battery}")
            else:
                record("H3", "HW-Meta", "GET /telemetry", "WARN", f"champs manquants")
        else:
            record("H3", "HW-Meta", "GET /telemetry", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H3", "HW-Meta", "GET /telemetry", "FAIL", str(e))


# ── Tests: Motion (via bridge) ────────────────────────────────────────────────

def check_set_velocity(args):
    """Tool 1: SetVelocity"""
    if args.skip_motion or args.skip_hardware:
        record("T1", "Motion", "SetVelocity", "SKIP", "skip-motion active")
        return
    try:
        # Test: petite vitesse vers l'avant
        result = call_bridge("SetVelocity", {"linear_x": 0.03, "linear_y": 0.0, "angular_z": 0.0})
        if "Velocity set" in result.get("result", "") or "ok" in result.get("result", "").lower():
            record("T1", "Motion", "SetVelocity (forward 0.03 m/s)", "PASS",
                   result.get("result", "")[:200])
        else:
            record("T1", "Motion", "SetVelocity", "FAIL", result.get("result", "")[:200])
        # Arret immediat
        time.sleep(0.5)
        call_bridge("Stop", {})
    except httpx.HTTPStatusError as e:
        record("T1", "Motion", "SetVelocity", "FAIL", f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        record("T1", "Motion", "SetVelocity", "FAIL", str(e))


def check_set_velocity_clamp(args):
    """Tool 1b: SetVelocity clamping (valeur excessive doit etre clampée)"""
    if args.skip_motion or args.skip_hardware:
        record("T1b", "Motion", "SetVelocity clamping", "SKIP", "skip-motion active")
        return
    try:
        # Valeur excessive: 1.0 m/s doit etre clampé a 0.06
        r = httpx.post(f"{HW_URL}/motion", json={"linear_x": 1.0, "linear_y": 0, "angular_z": 0}, timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            if abs(data.get("linear_x", 0)) <= 0.06:
                record("T1b", "Motion", "SetVelocity clamping (1.0 -> 0.06)", "PASS",
                       f"clamped a {data.get('linear_x')}")
            else:
                record("T1b", "Motion", "SetVelocity clamping", "FAIL",
                       f"non-clampe: {data.get('linear_x')}")
        else:
            record("T1b", "Motion", "SetVelocity clamping", "FAIL", f"HTTP {r.status_code}")
        # Stop
        httpx.post(f"{HW_URL}/motion/stop", timeout=5.0)
    except Exception as e:
        record("T1b", "Motion", "SetVelocity clamping", "FAIL", str(e))


def check_stop(args):
    """Tool 2: Stop"""
    if args.skip_hardware:
        record("T2", "Motion", "Stop", "SKIP", "skip-hardware active")
        return
    try:
        result = call_bridge("Stop", {})
        if "stop" in result.get("result", "").lower() or "ok" in result.get("result", "").lower():
            record("T2", "Motion", "Stop", "PASS", result.get("result", "")[:200])
        else:
            record("T2", "Motion", "Stop", "FAIL", result.get("result", "")[:200])
    except Exception as e:
        record("T2", "Motion", "Stop", "FAIL", str(e))


def test_hw_stop():
    """H5: HW /motion/stop"""
    try:
        r = httpx.post(f"{HW_URL}/motion/stop", timeout=5.0)
        if r.status_code == 200 and r.json().get("status") == "ok":
            record("H5", "Motion", "POST /motion/stop", "PASS", response=r.json())
        else:
            record("H5", "Motion", "POST /motion/stop", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H5", "Motion", "POST /motion/stop", "FAIL", str(e))


# ── Tests: Stubs (Speak, NavigateTo, Listen) ──────────────────────────────────

def test_speak():
    """Tool 3: Speak (stub attendu)"""
    try:
        result = call_bridge("Speak", {"text": "Bonjour je suis Clawbot"})
        if "stub" in result.get("result", "").lower() or "acknowledged" in result.get("result", "").lower() or "tts" in result.get("result", "").lower():
            record("T3", "Stub", "Speak (stub)", "PASS", "retourne stub attendu")
        else:
            record("T3", "Stub", "Speak", "WARN", "retour inattendu: " + result.get("result", "")[:200])
    except Exception as e:
        record("T3", "Stub", "Speak", "FAIL", str(e))


def test_navigate_to():
    """Tool 4: NavigateTo (stub attendu)"""
    try:
        result = httpx.post(f"{BRIDGE_URL}/command", json={"function":"NavigateTo","arguments":{"target_x":0.01,"target_y":0}}, timeout=30.0).json()
        import json as _json
        text = result.get("result", "")
        try:
            parsed = _json.loads(text)
            if parsed.get("status") in ("stub", "dead_reckoning"):
                record("T4", "Stub", "NavigateTo (stub)", "PASS", "retourne stub attendu")
            else:
                record("T4", "Stub", "NavigateTo", "WARN", f"status={parsed.get('status')}")
        except:
            record("T4", "Stub", "NavigateTo", "WARN", "retour non-JSON: " + text[:200])
    except Exception as e:
        record("T4", "Stub", "NavigateTo", "FAIL", str(e))


def test_listen():
    """Tool 10: Listen (stub attendu)"""
    try:
        result = httpx.post(f"{BRIDGE_URL}/command", json={"function":"Listen","arguments":{}}, timeout=15.0).json()
        import json as _json
        text = result.get("result", "")
        try:
            parsed = _json.loads(text)
            if parsed.get("status") in ("stub", "dead_reckoning"):
                record("T10", "Stub", "Listen (stub)", "PASS", "retourne stub attendu")
            else:
                record("T10", "Stub", "Listen", "WARN", f"status={parsed.get('status')}")
        except:
            record("T10", "Stub", "Listen", "WARN", "retour non-JSON: " + text[:200])
    except Exception as e:
        record("T10", "Stub", "Listen", "FAIL", str(e))


# ── Tests: Vision ─────────────────────────────────────────────────────────────

def check_capture_camera(args):
    """Tool 5: CaptureCamera (front)"""
    if args.skip_camera or args.skip_hardware:
        record("T5", "Vision", "CaptureCamera front", "SKIP", "skip-camera active")
        return
    try:
        result = call_bridge("CaptureCamera", {"camera": "front"})
        import json as _json
        text = result.get("result", "")
        try:
            parsed = _json.loads(text)
            has_b64 = "image_base64" in parsed
            has_path = "saved_path" in parsed
            b64_len = len(parsed.get("image_base64", ""))
            if has_b64 and b64_len > 100:
                record("T5", "Vision", "CaptureCamera (front)", "PASS",
                       f"base64={b64_len} chars, path={parsed.get('saved_path')}")
            else:
                record("T5", "Vision", "CaptureCamera (front)", "FAIL",
                       f"base64 manquant ou trop court ({b64_len} chars)")
        except:
            record("T5", "Vision", "CaptureCamera (front)", "FAIL", "retour non-JSON: " + text[:200])
    except Exception as e:
        record("T5", "Vision", "CaptureCamera (front)", "FAIL", str(e))


def check_capture_camera_claw(args):
    """Tool 5b: CaptureCamera (claw)"""
    if args.skip_camera or args.skip_hardware:
        record("T5b", "Vision", "CaptureCamera claw", "SKIP", "skip-camera active")
        return
    try:
        result = call_bridge("CaptureCamera", {"camera": "claw"})
        import json as _json
        text = result.get("result", "")
        try:
            parsed = _json.loads(text)
            b64_len = len(parsed.get("image_base64", ""))
            if b64_len > 100:
                record("T5b", "Vision", "CaptureCamera (claw)", "PASS",
                       f"base64={b64_len} chars")
            else:
                record("T5b", "Vision", "CaptureCamera (claw)", "WARN",
                       f"base64 court ({b64_len} chars) -- camera claw peut-etre deconnectee")
        except:
            record("T5b", "Vision", "CaptureCamera (claw)", "WARN", "retour non-JSON")
    except Exception as e:
        record("T5b", "Vision", "CaptureCamera (claw)", "WARN", str(e))


def check_analyze_scene(args):
    """Tool 6: AnalyzeScene"""
    if args.skip_camera or args.skip_hardware:
        record("T6", "Vision", "AnalyzeScene", "SKIP", "skip-camera active")
        return
    try:
        result = call_bridge("AnalyzeScene", {})
        import json as _json
        parsed = _json.loads(result.get("result", ""))
        if "saved_path" in parsed and "image_base64" in parsed:
            record("T6", "Vision", "AnalyzeScene", "PASS",
                   f"path={parsed.get('saved_path')}, b64={len(parsed.get('image_base64',''))} chars")
        else:
            record("T6", "Vision", "AnalyzeScene", "FAIL", "champs manquants")
    except Exception as e:
        record("T6", "Vision", "AnalyzeScene", "FAIL", str(e))


def check_recognize_face(args):
    """Tool 7: RecognizeFace"""
    if args.skip_camera or args.skip_hardware:
        record("T7", "Vision", "RecognizeFace", "SKIP", "skip-camera active")
        return
    try:
        result = call_bridge("RecognizeFace", {})
        import json as _json
        parsed = _json.loads(result.get("result", ""))
        if "saved_path" in parsed:
            record("T7", "Vision", "RecognizeFace", "PASS", "capture + instruction OK")
        else:
            record("T7", "Vision", "RecognizeFace", "FAIL", "champs manquants")
    except Exception as e:
        record("T7", "Vision", "RecognizeFace", "FAIL", str(e))


def check_recognize_object(args):
    """Tool 8: RecognizeObject"""
    if args.skip_camera or args.skip_hardware:
        record("T8", "Vision", "RecognizeObject", "SKIP", "skip-camera active")
        return
    try:
        result = call_bridge("RecognizeObject", {})
        import json as _json
        parsed = _json.loads(result.get("result", ""))
        if "saved_path" in parsed:
            record("T8", "Vision", "RecognizeObject", "PASS", "capture + instruction OK")
        else:
            record("T8", "Vision", "RecognizeObject", "FAIL", "champs manquants")
    except Exception as e:
        record("T8", "Vision", "RecognizeObject", "FAIL", str(e))


def check_recognize_qrcode(args):
    """Tool 9: RecognizeQRCode"""
    if args.skip_camera or args.skip_hardware:
        record("T9", "Vision", "RecognizeQRCode", "SKIP", "skip-camera active")
        return
    try:
        result = call_bridge("RecognizeQRCode", {})
        import json as _json
        parsed = _json.loads(result.get("result", ""))
        if "saved_path" in parsed:
            record("T9", "Vision", "RecognizeQRCode", "PASS", "capture + instruction OK")
        else:
            record("T9", "Vision", "RecognizeQRCode", "FAIL", "champs manquants")
    except Exception as e:
        record("T9", "Vision", "RecognizeQRCode", "FAIL", str(e))


# ── Tests: Arm & Claw ─────────────────────────────────────────────────────────

def check_control_servo(args):
    """Tool 11: ControlServo"""
    if args.skip_hardware:
        record("T11", "Arm", "ControlServo", "SKIP", "skip-hardware active")
        return
    try:
        # Mettre servo 1 (base) a 90 degres (centre)
        result = call_bridge("ControlServo", {"servo_id": 1, "angle": 90})
        if "ok" in result.get("result", "").lower() or "90" in result.get("result", ""):
            record("T11", "Arm", "ControlServo (servo 1 -> 90°)", "PASS",
                   result.get("result", "")[:200])
        else:
            record("T11", "Arm", "ControlServo", "FAIL", result.get("result", "")[:200])
    except Exception as e:
        record("T11", "Arm", "ControlServo", "FAIL", str(e))


def check_control_arm(args):
    """Tool 12: ControlArm"""
    if args.skip_hardware:
        record("T12", "Arm", "ControlArm", "SKIP", "skip-hardware active")
        return
    try:
        # Position neutre: [90, 90, 90, 90, 90]
        result = call_bridge("ControlArm", {"joints_array": [90, 90, 90, 90, 90]})
        if "ok" in result.get("result", "").lower() or "90" in result.get("result", ""):
            record("T12", "Arm", "ControlArm ([90,90,90,90,90])", "PASS",
                   result.get("result", "")[:200])
        else:
            record("T12", "Arm", "ControlArm", "FAIL", result.get("result", "")[:200])
    except Exception as e:
        record("T12", "Arm", "ControlArm", "FAIL", str(e))


def check_control_claw(args):
    """Tool 13: ControlClaw (open + close)"""
    if args.skip_hardware:
        record("T13", "Arm", "ControlClaw", "SKIP", "skip-hardware active")
        return
    try:
        # Open
        result_open = call_bridge("ControlClaw", {"state": "open"})
        ok_open = "open" in result_open.get("result", "").lower()
        time.sleep(0.5)
        # Close
        result_close = call_bridge("ControlClaw", {"state": "close"})
        ok_close = "close" in result_close.get("result", "").lower()
        time.sleep(0.5)
        # Re-open pour safety
        call_bridge("ControlClaw", {"state": "open"})
        if ok_open and ok_close:
            record("T13", "Arm", "ControlClaw (open + close + open)", "PASS",
                   "cycle complet OK")
        else:
            record("T13", "Arm", "ControlClaw", "FAIL",
                   f"open={ok_open}, close={ok_close}")
    except Exception as e:
        record("T13", "Arm", "ControlClaw", "FAIL", str(e))


def check_set_arm_pose(args):
    """Tool 14: SetArmPose (pose 1: anti-collision)"""
    if args.skip_hardware:
        record("T14", "Arm", "SetArmPose", "SKIP", "skip-hardware active")
        return
    try:
        result = call_bridge("SetArmPose", {"pose_id": 1})
        if "anti-collision" in result.get("result", "").lower() or "ok" in result.get("result", "").lower():
            record("T14", "Arm", "SetArmPose (1=Anti-collision)", "PASS",
                   result.get("result", "")[:200])
        else:
            record("T14", "Arm", "SetArmPose", "FAIL", result.get("result", "")[:200])
    except Exception as e:
        record("T14", "Arm", "SetArmPose", "FAIL", str(e))


# ── Tests: Peripherals ────────────────────────────────────────────────────────

def check_beep(args):
    """Tool 15: Beep"""
    if args.skip_hardware:
        record("T15", "Peripherals", "Beep", "SKIP", "skip-hardware active")
        return
    try:
        result = call_bridge("Beep", {"delay_ms": 100})
        if "ok" in result.get("result", "").lower() or "100" in result.get("result", ""):
            record("T15", "Peripherals", "Beep (100ms)", "PASS",
                   result.get("result", "")[:200])
        else:
            record("T15", "Peripherals", "Beep", "FAIL", result.get("result", "")[:200])
    except Exception as e:
        record("T15", "Peripherals", "Beep", "FAIL", str(e))


def check_set_lamps(args):
    """Tool 16: SetLamps (rouge, puis vert, puis bleu, puis eteint)"""
    if args.skip_hardware:
        record("T16", "Peripherals", "SetLamps", "SKIP", "skip-hardware active")
        return
    try:
        colors = [("255,0,0", "rouge"), ("0,255,0", "vert"), ("0,0,255", "bleu"), ("0,0,0", "eteint")]
        all_ok = True
        for rgb, name in colors:
            r, g, b = map(int, rgb.split(","))
            result = call_bridge("SetLamps", {"r": r, "g": g, "b": b})
            if "ok" not in result.get("result", "").lower():
                all_ok = False
            time.sleep(0.3)
        if all_ok:
            record("T16", "Peripherals", "SetLamps (R,G,B,off)", "PASS", "4 couleurs OK")
        else:
            record("T16", "Peripherals", "SetLamps", "FAIL", "une ou plusieurs couleurs ont echoue")
    except Exception as e:
        record("T16", "Peripherals", "SetLamps", "FAIL", str(e))


def check_get_battery(args):
    """Tool 17: GetBatteryVoltage"""
    if args.skip_hardware:
        record("T17", "Peripherals", "GetBatteryVoltage", "SKIP", "skip-hardware active")
        return
    try:
        result = call_bridge("GetBatteryVoltage", {})
        import json as _json
        text = result.get("result", "")
        try:
            parsed = _json.loads(text)
            v = parsed.get("voltage", 0)
            pct = parsed.get("percentage", 0)
            if 9.0 <= v <= 13.0:
                record("T17", "Peripherals", "GetBatteryVoltage", "PASS",
                       f"{v}V ({pct}%)")
            elif v == 0:
                record("T17", "Peripherals", "GetBatteryVoltage", "WARN",
                       f"voltage=0 -- driver_node peut-etre non demarre")
            else:
                record("T17", "Peripherals", "GetBatteryVoltage", "WARN",
                       f"voltage={v}V hors plage attendue")
        except:
            record("T17", "Peripherals", "GetBatteryVoltage", "FAIL", "retour non-JSON: " + text[:200])
    except Exception as e:
        record("T17", "Peripherals", "GetBatteryVoltage", "FAIL", str(e))


# ── Tests: HW direct endpoints ────────────────────────────────────────────────

def test_hw_battery():
    """H12: GET /battery"""
    try:
        r = httpx.get(f"{HW_URL}/battery", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            record("H12", "HW-Direct", "GET /battery", "PASS",
                   f"{data.get('voltage')}V ({data.get('percentage')}%)")
        else:
            record("H12", "HW-Direct", "GET /battery", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H12", "HW-Direct", "GET /battery", "FAIL", str(e))


def check_hw_capture(args):
    """H21: GET /capture?camera=front&save=true"""
    if args.skip_camera or args.skip_hardware:
        record("H21", "HW-Vision", "GET /capture (front)", "SKIP", "skip-camera active")
        return
    try:
        r = httpx.get(f"{HW_URL}/capture", params={"camera": "front", "save": "true"}, timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            b64_len = len(data.get("image_base64", ""))
            path = data.get("saved_path", "")
            if b64_len > 100:
                record("H21", "HW-Vision", "GET /capture (front)", "PASS",
                       f"b64={b64_len} chars, path={path}")
            else:
                record("H21", "HW-Vision", "GET /capture (front)", "FAIL", "base64 trop court")
        else:
            record("H21", "HW-Vision", "GET /capture (front)", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H21", "HW-Vision", "GET /capture (front)", "FAIL", str(e))


def test_hw_yolo_status():
    """H23: GET /yolo/status"""
    try:
        r = httpx.get(f"{HW_URL}/yolo/status", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            record("H23", "HW-Vision", "GET /yolo/status", "PASS",
                   f"service={data.get('service')}, active={data.get('active')}")
        else:
            record("H23", "HW-Vision", "GET /yolo/status", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H23", "HW-Vision", "GET /yolo/status", "FAIL", str(e))


def test_hw_yolo_frame():
    """H22: GET /yolo/frame (peut retourner 204 si YOLO non actif)"""
    try:
        r = httpx.get(f"{HW_URL}/yolo/frame", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            b64_len = len(data.get("image_base64", ""))
            record("H22", "HW-Vision", "GET /yolo/frame", "PASS",
                   f"b64={b64_len} chars, detections={len(data.get('detections', []))}")
        elif r.status_code == 204:
            record("H22", "HW-Vision", "GET /yolo/frame", "SKIP",
                   "YOLO non actif (204 No Content)")
        else:
            record("H22", "HW-Vision", "GET /yolo/frame", "WARN", f"HTTP {r.status_code}")
    except Exception as e:
        record("H22", "HW-Vision", "GET /yolo/frame", "WARN", str(e))


# ── Tests: SLAM & Maps ────────────────────────────────────────────────────────

def test_slam_status():
    """H15: GET /slam/status"""
    try:
        r = httpx.get(f"{HW_URL}/slam/status", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            record("H15", "SLAM", "GET /slam/status", "PASS",
                   f"active={data.get('active')}")
        else:
            record("H15", "SLAM", "GET /slam/status", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H15", "SLAM", "GET /slam/status", "FAIL", str(e))


def test_list_maps():
    """H17: GET /maps"""
    try:
        r = httpx.get(f"{HW_URL}/maps", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            maps = data.get("maps", [])
            record("H17", "SLAM", "GET /maps", "PASS",
                   f"{len(maps)} carte(s) sauvegardee(s)")
        else:
            record("H17", "SLAM", "GET /maps", "FAIL", f"HTTP {r.status_code}")
    except Exception as e:
        record("H17", "SLAM", "GET /maps", "FAIL", str(e))


def test_live_map():
    """H16: GET /map/live (peut 404 si SLAM non lance)"""
    try:
        r = httpx.get(f"{HW_URL}/map/live", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            record("H16", "SLAM", "GET /map/live", "PASS",
                   f"{data.get('width')}x{data.get('height')}, res={data.get('resolution')}")
        elif r.status_code == 404:
            record("H16", "SLAM", "GET /map/live", "SKIP",
                   "pas de carte (SLAM non lance)")
        else:
            record("H16", "SLAM", "GET /map/live", "WARN", f"HTTP {r.status_code}")
    except Exception as e:
        record("H16", "SLAM", "GET /map/live", "WARN", str(e))


# ── Tests: Validation d'erreurs ───────────────────────────────────────────────

def test_unknown_tool():
    """M3-error: POST /command avec tool inexistant -> 400"""
    try:
        r = httpx.post(f"{BRIDGE_URL}/command",
                       json={"function": "InexistantTool", "arguments": {}},
                       timeout=5.0)
        if r.status_code == 400:
            record("M3-err", "Bridge-Validation", "Unknown tool -> 400", "PASS",
                   "rejette correctement tool inconnu")
        else:
            record("M3-err", "Bridge-Validation", "Unknown tool", "FAIL",
                   f"HTTP {r.status_code} au lieu de 400")
    except Exception as e:
        record("M3-err", "Bridge-Validation", "Unknown tool", "FAIL", str(e))


def test_invalid_args():
    """M3-error2: POST /command avec args invalides -> 400"""
    try:
        # SetVelocity avec linear_x hors range (1.0 > 0.06)
        r = httpx.post(f"{BRIDGE_URL}/command",
                       json={"function": "SetVelocity",
                             "arguments": {"linear_x": 999, "linear_y": 0, "angular_z": 0}},
                       timeout=5.0)
        if r.status_code == 400:
            record("M3-args", "Bridge-Validation", "Invalid args -> 400", "PASS",
                   "rejette args hors range")
        else:
            record("M3-args", "Bridge-Validation", "Invalid args", "FAIL",
                   f"HTTP {r.status_code} au lieu de 400")
    except Exception as e:
        record("M3-args", "Bridge-Validation", "Invalid args", "FAIL", str(e))


# ── Tests: Instruction haut niveau (end-to-end) ───────────────────────────────

def test_high_level_instruction_battery():
    """E2E-1: Instruction haut niveau "quelle est ta batterie" via bridge"""
    try:
        # Simule ce que ferait un LLM: GetBatteryVoltage
        result = call_bridge("GetBatteryVoltage", {})
        import json as _json
        parsed = _json.loads(result.get("result", ""))
        v = parsed.get("voltage", 0)
        pct = parsed.get("percentage", 0)
        if v > 0:
            record("E2E-1", "End-to-End", "Instruction 'batterie' -> GetBatteryVoltage", "PASS",
                   f"Reponse: {v}V ({pct}%)")
        else:
            record("E2E-1", "End-to-End", "Instruction 'batterie'", "WARN",
                   f"voltage=0 (driver_node peut-etre arrete)")
    except Exception as e:
        record("E2E-1", "End-to-End", "Instruction 'batterie'", "FAIL", str(e))


def test_high_level_instruction_telemetry():
    """E2E-2: Instruction haut niveau "telemetrie complete" via HW"""
    try:
        r = httpx.get(f"{HW_URL}/telemetry", timeout=5.0)
        data = r.json()
        # Verifier qu'on a toutes les donnees capteur
        imu = data.get("imu", {})
        vel = data.get("velocity", {})
        servos = data.get("servos", {})
        bat = data.get("battery", {})
        all_present = all([imu, vel, servos, bat])
        if all_present:
            record("E2E-2", "End-to-End", "Instruction 'telemetrie' -> /telemetry", "PASS",
                   f"IMU+vel+servos+battery OK")
        else:
            record("E2E-2", "End-to-End", "Instruction 'telemetrie'", "WARN",
                   "certaines donnees manquantes")
    except Exception as e:
        record("E2E-2", "End-to-End", "Instruction 'telemetrie'", "FAIL", str(e))


def check_high_level_instruction_pose_then_stop(args):
    """E2E-3: Instruction haut niveau "mets-toi en position anti-collision puis arrete-toi" """
    if args.skip_hardware:
        record("E2E-3", "End-to-End", "Instruction 'pose + stop'", "SKIP", "skip-hardware active")
        return
    try:
        # Etape 1: SetArmPose(1) -- anti-collision
        r1 = call_bridge("SetArmPose", {"pose_id": 1})
        ok1 = "anti-collision" in r1.get("result", "").lower() or "ok" in r1.get("result", "").lower()
        # Etape 2: Stop
        r2 = call_bridge("Stop", {})
        ok2 = "stop" in r2.get("result", "").lower() or "ok" in r2.get("result", "").lower()
        if ok1 and ok2:
            record("E2E-3", "End-to-End", "Instruction 'pose + stop' (2 tools en sequence)", "PASS",
                   "sequence SetArmPose -> Stop OK")
        else:
            record("E2E-3", "End-to-End", "Instruction 'pose + stop'", "FAIL",
                   f"pose={ok1}, stop={ok2}")
    except Exception as e:
        record("E2E-3", "End-to-End", "Instruction 'pose + stop'", "FAIL", str(e))


def check_high_level_instruction_lamp_signal(args):
    """E2E-4: Instruction haut niveau "fais un signal lumineux rouge puis eteint" """
    if args.skip_hardware:
        record("E2E-4", "End-to-End", "Instruction 'signal lumineux'", "SKIP", "skip-hardware active")
        return
    try:
        # Rouge
        r1 = call_bridge("SetLamps", {"r": 255, "g": 0, "b": 0})
        ok1 = "ok" in r1.get("result", "").lower() or "255" in r1.get("result", "")
        time.sleep(0.5)
        # Eteint
        r2 = call_bridge("SetLamps", {"r": 0, "g": 0, "b": 0})
        ok2 = "ok" in r2.get("result", "").lower()
        if ok1 and ok2:
            record("E2E-4", "End-to-End", "Instruction 'signal lumineux' (SetLamps x2)", "PASS",
                   "rouge puis eteint OK")
        else:
            record("E2E-4", "End-to-End", "Instruction 'signal lumineux'", "FAIL",
                   f"red={ok1}, off={ok2}")
    except Exception as e:
        record("E2E-4", "End-to-End", "Instruction 'signal lumineux'", "FAIL", str(e))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Clawbot Non-Regression Test Suite")
    parser.add_argument("--skip-motion", action="store_true", help="Ne pas tester le mouvement")
    parser.add_argument("--skip-slam", action="store_true", help="Ne pas tester SLAM")
    parser.add_argument("--skip-camera", action="store_true", help="Ne pas tester les cameras")
    parser.add_argument("--skip-hardware", action="store_true", help="Bridge uniquement (skip HW direct)")
    parser.add_argument("--output", type=str, default=None, help="Fichier sortie JSON")
    args = parser.parse_args()

    print("=" * 70)
    print("  CLAWBOT NON-REGRESSION TEST SUITE")
    print(f"  Bridge: {BRIDGE_URL} | Hardware: {HW_URL}")
    print(f"  Date: {datetime.now().isoformat()}")
    print(f"  Flags: motion={'OFF' if args.skip_motion else 'ON'}"
          f" camera={'OFF' if args.skip_camera else 'ON'}"
          f" hw={'OFF' if args.skip_hardware else 'ON'}")
    print("=" * 70)

    # ── Bridge Meta ──
    print("\n--- Bridge Meta Endpoints ---")
    test_bridge_health()
    test_bridge_tools()
    test_bridge_tools_names()
    test_unknown_tool()
    test_invalid_args()

    # ── HW Meta ──
    if not args.skip_hardware:
        print("\n--- Hardware Service Meta ---")
        test_hw_health()
        test_hw_system_status()
        test_hw_telemetry()
        test_hw_battery()

    # ── Motion ──
    print("\n--- Motion ---")
    check_set_velocity(args)
    check_set_velocity_clamp(args)
    check_stop(args)
    test_hw_stop()

    # Set mode to NAVIGATION for NavigateTo
    try:
        httpx.post(f"{BRIDGE_URL}/mode", json={"mode":"navigation"}, timeout=5)
    except: pass

    # ── Stubs ──
    print("\n--- Stubs (Speak, NavigateTo, Listen) ---")
    test_speak()
    test_navigate_to()
    test_listen()

    # Set mode to MANIPULATION for vision tests
    try:
        httpx.post(f"{BRIDGE_URL}/mode", json={"mode":"manipulation"}, timeout=5)
    except: pass

    # ── Vision ──
    print("\n--- Vision ---")
    check_capture_camera(args)
    check_capture_camera_claw(args)
    check_analyze_scene(args)
    check_recognize_face(args)
    check_recognize_object(args)
    check_recognize_qrcode(args)
    if not args.skip_hardware:
        check_hw_capture(args)
        test_hw_yolo_status()
        test_hw_yolo_frame()

    # Set mode to MANIPULATION for arm/camera tests
    try:
        httpx.post(f"{BRIDGE_URL}/mode", json={"mode":"manipulation"}, timeout=5)
    except: pass

    # ── Arm & Claw ──
    print("\n--- Arm & Claw ---")
    check_control_servo(args)
    check_control_arm(args)
    check_control_claw(args)
    check_set_arm_pose(args)

    # ── Peripherals ──
    print("\n--- Peripherals ---")
    check_beep(args)
    check_set_lamps(args)
    check_get_battery(args)

    # ── SLAM & Maps ──
    print("\n--- SLAM & Maps ---")
    test_slam_status()
    test_list_maps()
    test_live_map()

    # ── End-to-End (instructions haut niveau) ──
    print("\n--- End-to-End (instructions haut niveau) ---")
    test_high_level_instruction_battery()
    test_high_level_instruction_telemetry()
    check_high_level_instruction_pose_then_stop(args)
    check_high_level_instruction_lamp_signal(args)

    # Reset to standby
    try:
        httpx.post(f"{BRIDGE_URL}/mode", json={"mode":"standby"}, timeout=5)
    except: pass

    # ── Summary ──
    print("\n" + "=" * 70)
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "WARN": 0}
    for r in results:
        counts[r["status"]] += 1
    total = len(results)
    print(f"  RESULTATS: {total} tests")
    print(f"  PASS: {counts['PASS']}  FAIL: {counts['FAIL']}  SKIP: {counts['SKIP']}  WARN: {counts['WARN']}")
    if counts["FAIL"] == 0:
        print("  STATUT GLOBAL: SUCCES (aucun echec)")
    else:
        print(f"  STATUT GLOBAL: ECHEC ({counts['FAIL']} test(s) echoue(s))")
    print("=" * 70)

    # ── Save JSON ──
    output_path = args.output or f"/home/jetson/clawbot/tests/test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "suite": "Clawbot Non-Regression",
            "date": datetime.now().isoformat(),
            "bridge_url": BRIDGE_URL,
            "hw_url": HW_URL,
            "flags": {
                "skip_motion": args.skip_motion,
                "skip_camera": args.skip_camera,
                "skip_hardware": args.skip_hardware,
                "skip_slam": args.skip_slam,
            },
            "summary": counts,
            "total": total,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Rapport JSON sauvegarde: {output_path}")

    # Exit code: 0 si aucun FAIL, 1 sinon
    sys.exit(1 if counts["FAIL"] > 0 else 0)


if __name__ == "__main__":
    main()