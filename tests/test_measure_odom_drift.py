"""La mesure de dérive est le critère de sortie du lot 1 : elle doit être juste avant d'être crue."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from measure_odom_drift import measure_drift  # noqa: E402


def test_drift_zero_on_straight_line():
    result = measure_drift([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    assert result["distance_m"] == 2.0
    assert result["lateral_m"] == 0.0
    assert result["drift_pct"] == 0.0


def test_drift_counts_lateral_error():
    result = measure_drift([[0.0, 0.0, 0.0], [1.0, 0.03, 0.0], [2.0, 0.05, 0.0]])
    assert round(result["drift_pct"], 1) == 2.5


def test_too_few_samples_is_not_a_pass():
    result = measure_drift([[0.0, 0.0, 0.0]])
    assert result["distance_m"] == 0.0
