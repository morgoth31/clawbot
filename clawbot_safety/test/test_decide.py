import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clawbot_safety.arbitrator import decide  # noqa: E402


def test_passes_command_when_all_is_well():
    etat, cmd = decide((0.05, 0.0, 0.0), 1.0, 0.0, 0.0, 96, [11.9] * 20, 0.1, 0.1)
    assert etat == "OK" and cmd == (0.05, 0.0, 0.0)


def test_stops_on_close_obstacle():
    etat, cmd = decide((0.05, 0.0, 0.0), 0.12, 0.0, 0.0, 96, [11.9] * 20, 0.1, 0.1)
    assert etat == "STOP" and cmd == (0.0, 0.0, 0.0)


def test_stale_scan_is_an_alert_not_silence():
    etat, cmd = decide((0.05, 0.0, 0.0), 1.0, 0.0, 0.0, 96, [11.9] * 20, 3.0, 0.1)
    assert etat == "SENSOR_STALE" and cmd == (0.0, 0.0, 0.0)


def test_tilt_holds_even_without_command():
    etat, cmd = decide((0.0, 0.0, 0.0), 1.0, 9.0, 0.0, 96, [11.9] * 20, 0.1, 0.1)
    assert etat == "HOLD" and cmd == (0.0, 0.0, 0.0)

def test_zero_command_when_no_recent_input():
    # le chien de garde vit dans le nœud, mais la décision doit rester sûre avec une consigne nulle
    etat, cmd = decide((0.0, 0.0, 0.0), 1.0, 0.0, 0.0, 96, [11.9] * 20, 0.1, 0.1)
    assert etat == "OK" and cmd == (0.0, 0.0, 0.0)
