"""Découverte des capacités matérielles : bitmaps sysfs, LEDs, vibration.

Aucune capacité n'est supposée : chaque fonction lit une source et rend un verdict,
y compris « non disponible » avec la source consultée.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "joy_teleop"))

from manette_materiel import decoder_bitmap, leds_du_pad, vibration_supportee  # noqa: E402


def test_decoder_bitmap_trouve_les_codes():
    # Bitmap réel du pad (2026-11-15) : 14 boutons BTN_SOUTH.. avec BTN_C absent.
    codes = decoder_bitmap("7ffb000000000000 0 0 0 0")
    assert 304 in codes and 305 in codes
    assert 306 not in codes                 # BTN_C non exposé
    assert 316 in codes                     # BTN_MODE = Home
    assert len(codes) == 14


def test_decoder_bitmap_des_effets_de_vibration():
    # Bitmap réel : FF_RUMBLE(80), FF_PERIODIC(81), FF_SQUARE(88), FF_TRIANGLE(89),
    # FF_SINE(90), FF_GAIN(96).
    codes = decoder_bitmap("107030000 0")
    assert codes == [80, 81, 88, 89, 90, 96]


def test_vibration_detectee(tmp_path):
    (tmp_path / "ff").write_text("107030000 0", encoding="utf-8")
    assert vibration_supportee(tmp_path / "ff") is True


def test_vibration_absente(tmp_path):
    (tmp_path / "ff").write_text("0", encoding="utf-8")
    assert vibration_supportee(tmp_path / "ff") is False


def test_vibration_fichier_illisible(tmp_path):
    assert vibration_supportee(tmp_path / "inexistant") is False


def test_bitmap_vide_ne_leve_pas():
    assert decoder_bitmap("") == []
    assert decoder_bitmap("0") == []


def test_leds_du_pad(tmp_path):
    (tmp_path / "leds" / "nintendo_player1").mkdir(parents=True)
    (tmp_path / "leds" / "nintendo_player2").mkdir(parents=True)
    leds = leds_du_pad(tmp_path)
    assert [p.name for p in leds] == ["nintendo_player1", "nintendo_player2"]


def test_leds_absentes(tmp_path):
    assert leds_du_pad(tmp_path) == []
