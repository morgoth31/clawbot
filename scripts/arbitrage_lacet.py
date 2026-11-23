#!/usr/bin/env python3
"""Arbitrage du signe du lacet par une troisieme source : le lidar.

Le lidar est la seule mesure dont la convention angulaire est fixee par REP-103 et
verifiable : un repere tournant de +psi (sens anti-horaire vu de dessus) fait glisser les
amerements vers les angles NEGATIFS du scan. On mesure donc la rotation vraie entre deux
scans consecutifs par appariement polaire (decalage de l'image de portee), puis on compare
son signe a celui de wz(IMU) et wz(roues).

Sortie : CSV par paire + synthese sur stdout. Aucun acces au robot, lecture d'un bag.
"""
from __future__ import annotations

import csv
import math
import sys

import numpy as np

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BINS = 720                      # 0,5 deg par case
R_MIN, R_MAX = 0.20, 8.0
SHIFT_MAX_BINS = 24             # +/- 12 deg de recherche
STEP = 0.25                     # pas de recherche, en case


def lire(chemin: str, topics: set[str]):
    lecteur = rosbag2_py.SequentialReader()
    lecteur.open(rosbag2_py.StorageOptions(uri=chemin, storage_id="sqlite3"),
                 rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {t.name: t.type for t in lecteur.get_all_topics_and_types()}
    classes = {n: get_message(t) for n, t in types.items() if n in topics}
    don: dict[str, list] = {n: [] for n in classes}
    while lecteur.has_next():
        nom, brut, t = lecteur.read_next()
        if nom in don:
            don[nom].append((t / 1e9, deserialize_message(brut, classes[nom])))
    return don


def image_portee(m) -> np.ndarray | None:
    r = np.asarray(m.ranges, dtype=float)
    n = r.size
    if n == 0:
        return None
    ang = m.angle_min + np.arange(n) * m.angle_increment
    ok = np.isfinite(r) & (r > R_MIN) & (r < R_MAX)
    if ok.sum() < 80:
        return None
    idx = np.clip(((ang[ok] - (-math.pi)) / (2 * math.pi) * BINS).astype(int), 0, BINS - 1)
    somme = np.bincount(idx, weights=r[ok], minlength=BINS)
    compte = np.bincount(idx, minlength=BINS)
    img = np.full(BINS, np.nan)
    plein = compte > 0
    img[plein] = somme[plein] / compte[plein]
    return img


def cout(img_a: np.ndarray, img_b: np.ndarray, delta_bins: float) -> float:
    """Cout de l'hypothese 'le repere a tourne de delta vers les angles croissants'."""
    k = np.arange(BINS, dtype=float) + delta_bins
    bas = np.floor(k).astype(int)
    frac = k - bas
    a0 = img_a[bas % BINS]
    a1 = img_a[(bas + 1) % BINS]
    a = (1 - frac) * a0 + frac * a1
    val = ~np.isnan(a) & ~np.isnan(img_b)
    if val.sum() < 120:
        return float("inf")
    return float(np.mean(np.abs(a[val] - img_b[val])))


def main() -> int:
    if len(sys.argv) < 3:
        print("usage : arbitrage_lacet.py <bag> <sortie.csv>")
        return 2
    d = lire(sys.argv[1], {"/scan", "/imu/data_raw", "/odom_raw"})
    scans = d.get("/scan", [])
    imu = d.get("/imu/data_raw", [])
    roues = d.get("/odom_raw", [])
    print(f"scans {len(scans)} · imu {len(imu)} · odom_raw {len(roues)}")
    if not scans or not imu or not roues:
        return 1

    t_imu = np.array([t for t, _ in imu])
    wz_imu = np.array([m.angular_velocity.z for _, m in imu])
    t_roues = np.array([t for t, _ in roues])
    wz_roues = np.array([m.twist.twist.angular.z for _, m in roues])

    # Quantification de gz : 1/1000 (ICM20948) contre 1/3754.9 (MPU9250). Tranche la trame.
    uniques = np.unique(np.round(wz_imu, 6))
    diff_min = np.min(np.diff(uniques)) if uniques.size > 1 else float("nan")
    print(f"quantification de wz(IMU) : plus petit ecart non nul {diff_min:.6f} rad/s "
          f"({'ICM20948 (1/1000)' if abs(diff_min - 0.001) < 2e-4 else 'MPU9250 (1/3754.9) ?'})")

    lignes = []
    precedente = None
    for t, m in scans:
        img = image_portee(m)
        if img is None:
            continue
        if precedente is not None:
            t0, img0 = precedente
            dt = t - t0
            if 0.05 <= dt <= 0.25:
                deltas = np.arange(-SHIFT_MAX_BINS, SHIFT_MAX_BINS + STEP, STEP)
                couts = np.array([cout(img0, img, dlt) for dlt in deltas])
                if np.isfinite(couts).sum() >= 5:
                    i = int(np.nanargmin(couts))
                    delta = deltas[i]
                    hors = np.abs(deltas - delta) > 3.0
                    base = np.nanmin(couts[hors]) if np.isfinite(couts[hors]).any() else np.nan
                    contraste = base - couts[i] if np.isfinite(base) else float("nan")
                    wz_lidar = delta * (2 * math.pi / BINS) / dt
                    a = (t0 + t) / 2
                    mi = int(np.argmin(np.abs(t_imu - a)))
                    mr = int(np.argmin(np.abs(t_roues - a)))
                    lignes.append({
                        "t": f"{a:.3f}", "dt": f"{dt:.3f}",
                        "delta_deg": f"{math.degrees(delta * 2 * math.pi / BINS):.3f}",
                        "wz_lidar": f"{wz_lidar:.4f}",
                        "wz_imu": f"{wz_imu[mi]:.4f}",
                        "wz_roues": f"{wz_roues[mr]:.4f}",
                        "cout": f"{couts[i]:.4f}",
                        "contraste": f"{contraste:.4f}",
                    })
        precedente = (t, img)

    if not lignes:
        print("aucune paire exploitable")
        return 1
    with open(sys.argv[2], "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)

    lid = np.array([float(lg["wz_lidar"]) for lg in lignes])
    imu_ = np.array([float(lg["wz_imu"]) for lg in lignes])
    rou = np.array([float(lg["wz_roues"]) for lg in lignes])
    con = np.array([float(lg["contraste"]) for lg in lignes])
    dt_ = np.array([float(lg["dt"]) for lg in lignes])

    def corr(a, b):
        if a.std() < 1e-9 or b.std() < 1e-9:
            return float("nan")
        return float(np.corrcoef(a, b)[0, 1])

    print(f"\npaires analysees : {len(lid)}")
    print(f"correlation wz(lidar)-wz(IMU)   : {corr(lid, imu_):+.3f}")
    print(f"correlation wz(lidar)-wz(roues) : {corr(lid, rou):+.3f}")
    print(f"correlation wz(IMU)-wz(roues)   : {corr(imu_, rou):+.3f}")

    # Fenetre de rotation franche : les paires ou les deux capteurs sont d'accord en module.
    forte = (np.abs(lid) > 0.10) & (con > 0.05)
    if forte.sum() >= 10:
        print(f"\nrotation franche (|wz_lidar| > 0,10 rad/s et contraste > 0,05) : {forte.sum()} paires")
        accord_imu = 100 * np.mean(np.sign(lid[forte]) == np.sign(imu_[forte]))
        accord_roues = 100 * np.mean(np.sign(lid[forte]) == np.sign(rou[forte]))
        print(f"  signe identique a l'IMU   : {accord_imu:.1f} %")
        print(f"  signe identique aux roues : {accord_roues:.1f} %")
        print(f"  pente lidar->IMU   : {np.polyfit(imu_[forte], lid[forte], 1)[0]:+.3f}")
        print(f"  pente lidar->roues : {np.polyfit(rou[forte], lid[forte], 1)[0]:+.3f}")

    print("\nintegrale sur les paires de la fenetre franche (degres) :")
    if forte.sum() >= 10:
        for nom, w in (("lidar", lid), ("IMU", imu_), ("roues", rou)):
            print(f"  {nom:<7}: {math.degrees(float(np.sum(w[forte] * dt_[forte]))):+8.1f}")
    else:
        print("  NON CONCLUANT : pas assez de rotation (un zero ne prouve rien sans activite)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
