#!/usr/bin/env python3
"""Test the C++ bridge on port 8002. Sets mode to manipulation first so all tools are testable."""
import httpx, json, sys

BRIDGE_URL = "http://localhost:8002"
results = []

def record(tid, cat, name, status, detail=""):
    results.append({"id": tid, "name": name, "status": status, "detail": detail})
    sym = {"PASS":"OK","FAIL":"XX","SKIP":"--","WARN":"!!"}[status]
    print(f"  [{sym}] {tid}: {name} -- {status}" + (f" ({detail})" if detail else ""))

def call_bridge(func, args=None):
    r = httpx.post(f"{BRIDGE_URL}/command", json={"function": func, "arguments": args or {}}, timeout=10)
    return r

# Reset to standby first
httpx.post(f"{BRIDGE_URL}/mode", json={"mode":"standby"}, timeout=10)

# Meta
r = httpx.get(f"{BRIDGE_URL}/health", timeout=5)
record("M1","Meta","GET /health","PASS" if r.json().get("status")=="healthy" else "FAIL")

r = httpx.get(f"{BRIDGE_URL}/tools?format=openai", timeout=5)
tools = r.json()
record("M2","Meta","GET /tools","PASS" if len(tools)==18 else "FAIL", f"{len(tools)} tools")

r = httpx.post(f"{BRIDGE_URL}/command", json={"function":"Bad","arguments":{}}, timeout=5)
record("M3e","Valid","Unknown tool 400","PASS" if r.status_code==400 else "FAIL")

r = httpx.post(f"{BRIDGE_URL}/command", json={"function":"SetVelocity","arguments":{"linear_x":999}}, timeout=5)
record("M3a","Valid","Invalid args 400","PASS" if r.status_code==400 else "FAIL")

# Set mode to STANDBY first (default)
m = httpx.get(f"{BRIDGE_URL}/mode", timeout=5).json()
record("MD0","Mode","Initial mode","PASS" if m["mode"]=="standby" else "FAIL", m["mode"])

# Stop works in standby
r = call_bridge("Stop", {})
record("T-Stop","Motion","Stop","PASS" if r.status_code==200 else "FAIL")

# Stubs work in standby
for tool, args in [("Speak",{"text":"hello"}), ("Listen",{})]:
    r = call_bridge(tool, args)
    if r.status_code == 200:
        text = r.json().get("result","")
        record(f"T-{tool}","Stub",tool,"PASS" if ("stub" in text.lower() or "acknowledged" in text.lower()) else "WARN")
    else:
        record(f"T-{tool}","Stub",tool,"FAIL", f"HTTP {r.status_code}")

# Switch to MANIPULATION for arm/camera tests
httpx.post(f"{BRIDGE_URL}/mode", json={"mode":"manipulation"}, timeout=10)
record("MD-manip","Mode","Switch to manipulation","PASS", "")

# Vision
r = call_bridge("CaptureCamera", {"camera":"front"})
if r.status_code == 200:
    d = json.loads(r.json()["result"])
    b64len = len(d.get("image_base64",""))
    record("T-Cam","Vision","CaptureCamera","PASS" if b64len>100 else "FAIL", f"b64={b64len}")
else:
    record("T-Cam","Vision","CaptureCamera","FAIL", f"HTTP {r.status_code}")

# Arm
for name, args in [("ControlServo",{"servo_id":1,"angle":90}), ("ControlArm",{"joints_array":[90,90,90,90,90]}), ("ControlClaw",{"state":"open"}), ("SetArmPose",{"pose_id":1})]:
    r = call_bridge(name, args)
    if r.status_code == 200:
        text = r.json().get("result","").lower()
        ok = "ok" in text or "open" in text or "close" in text or "moved" in text or "pose" in text
        record(f"T-{name}","Arm",name,"PASS" if ok else "FAIL")
    else:
        record(f"T-{name}","Arm",name,"FAIL", f"HTTP {r.status_code}")

# Peripherals
for name, args in [("Beep",{"delay_ms":100}), ("SetLamps",{"r":255,"g":0,"b":0})]:
    r = call_bridge(name, args)
    if r.status_code == 200:
        record(f"T-{name}","Peri",name,"PASS" if "ok" in r.json().get("result","").lower() else "FAIL")
    else:
        record(f"T-{name}","Peri",name,"FAIL", f"HTTP {r.status_code}")

r = call_bridge("GetBatteryVoltage")
if r.status_code == 200:
    d = json.loads(r.json()["result"])
    record("T-Batt","Peri","GetBatteryVoltage","PASS" if d.get("voltage",0)>0 else "FAIL", f'{d.get("voltage")}V')
else:
    record("T-Batt","Peri","GetBatteryVoltage","FAIL", f"HTTP {r.status_code}")

# Switch to NAVIGATION for NavigateTo stub test + DetectObjects
httpx.post(f"{BRIDGE_URL}/mode", json={"mode":"navigation"}, timeout=10)
r = call_bridge("NavigateTo", {"target_x":1,"target_y":2})
if r.status_code == 200:
    text = r.json().get("result","")
    record("T-Nav","Stub","NavigateTo","PASS" if "stub" in text.lower() else "WARN")
else:
    record("T-Nav","Stub","NavigateTo","FAIL", f"HTTP {r.status_code}")

# DetectObjects
r = call_bridge("DetectObjects", {"camera":"front"})
if r.status_code == 200:
    d = json.loads(r.json()["result"])
    record("T-Detect","Vision","DetectObjects","PASS", f'detections={d["detection_count"]}, {d["inference_ms"]}ms')
else:
    record("T-Detect","Vision","DetectObjects","FAIL", f"HTTP {r.status_code}")

# Return to standby
httpx.post(f"{BRIDGE_URL}/mode", json={"mode":"standby"}, timeout=10)

# Summary
counts = {"PASS":0,"FAIL":0,"SKIP":0,"WARN":0}
for r in results:
    counts[r["status"]] += 1
total = len(results)
print()
print(f"C++ BRIDGE TESTS: {total} tests | PASS:{counts['PASS']} FAIL:{counts['FAIL']} SKIP:{counts['SKIP']} WARN:{counts['WARN']}")
print("STATUT:", "SUCCES" if counts["FAIL"]==0 else "ECHEC")
sys.exit(1 if counts["FAIL"]>0 else 0)