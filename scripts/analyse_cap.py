#!/usr/bin/env python3
"""La cap de l'EKF derive-t-elle par rapport a la cap physique du lidar ?

Compare deux caps cumulees sur un meme parcours :
  - lidar : increments d'appariement polaire entre scans consecutifs (reference physique) ;
  - EKF   : lacet de /odom, enregistre pendant le meme rejeu.

Sortie : ecart cumule par tranche de 30 s. Un ecart qui croit lineairement designe la
prediction (odometrie/IMU) ; un ecart qui saute brutalement designe l'appariement.

    /usr/bin/python3 analyse_cap.py <bag.db3> <odom.csv>
"""
from __future__ import annotations

import math
import sys

import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

BINS = 720
R_MIN, R_MAX = 0.20, 8.0
SHIFT_MAX_BINS = 24
STEP = 0.25


def image_portee(m):
    r = np.asarray(m.ranges, dtype=float)
    ang = m.angle_min + np.arange(r.size) * m.angle_increment
    ok = np.isfinite(r) & (r > R_MIN) & (r < R_MAX)
    if ok.sum() < 80:
        return None
    idx = np.clip(((ang[ok] + math.pi) / (2 * math.pi) * BINS).astype(int), 0, BINS - 1)
    somme = np.bincount(idx, weights=r[ok], minlength=BINS)
    compte = np.bincount(idx, minlength=BINS)
    img = np.full(BINS, np.nan)
    plein = compte > 0
    img[plein] = somme[plein] / compte[plein]
    return img


def cout(a, b, delta):
    k = np.arange(BINS, dtype=float) + delta
    bas = np.floor(k).astype(int)
    frac = k - bas
    img = (1 - frac) * a[bas % BINS] + frac * a[(bas + 1) % BINS]
    val = ~np.isnan(img) & ~np.isnan(b)
    if val.sum() < 120:
        return float("inf")
    return float(np.mean(np.abs(img[val] - b[val])))


def main() -> int:
    lecteur = rosbag2_py.SequentialReader()
    lecteur.open(rosbag2_py.StorageOptions(uri=sys.argv[1], storage_id="sqlite3"),
                 rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {t.name: t.type for t in lecteur.get_all_topics_and_types()}
    cls = get_message(types["/scan"])
    scans = []
    while lecteur.has_next():
        nom, brut, t = lecteur.read_next()
        if nom == "/scan":
            scans.append((t / 1e9, deserialize_message(brut, cls)))
    print(f"{len(scans)} scans")

    tm, dl = [], []
    prec = None
    for t, m in scans:
        img = image_portee(m)
        if prec is not None and 0.05 <= t - prec[0] <= 0.25:
            deltas = np.arange(-SHIFT_MAX_BINS, SHIFT_MAX_BINS + STEP, STEP)
            couts = np.array([cout(prec[1], img, d) for d in deltas])
            if np.isfinite(couts).sum() >= 5:
                j = int(np.nanargmin(couts))
                tm.append((prec[0] + t) / 2)
                dl.append(deltas[j] * 2 * math.pi / BINS)
        prec = (t, img)
    tm = np.array(tm)
    dl = np.array(dl)
    lidar = np.cumsum(dl)

    d = np.loadtxt(sys.argv[2], delimiter=",", skiprows=1, ndmin=2)
    if d.size == 0 or d.shape[0] < 2:
        print("NON CONCLUANT : le CSV /odom est vide ou quasi vide — l'EKF n'a rien publie "
              "(typiquement un ekf_node en use_sim_time lance avant /clock). "
              "Aucun ecart de cap ne peut etre calcule.")
        return 3
    t_o, yaw = d[:, 0], d[:, 3]
    yaw = np.unwrap(yaw)
    ok = (t_o >= tm.min()) & (t_o <= tm.max())
    ekf = np.interp(tm, t_o[ok], yaw[ok])
    ekf = ekf - ekf[0]
    lidar = lidar - lidar[0]

    diff = ekf - lidar
    print(f"paires : {len(tm)} · duree : {tm[-1] - tm[0]:.1f} s")
    print(f"cap lidar sur le parcours : {math.degrees(lidar[-1]):+8.1f} deg")
    print(f"cap EKF   sur le parcours : {math.degrees(ekf[-1]):+8.1f} deg")
    print(f"ecart final               : {math.degrees(diff[-1]):+8.1f} deg")
    print()
    print("ecart cumule par tranche (deg) :")
    debut = tm[0]
    while debut < tm[-1]:
        fin = debut + 30.0
        sel = (tm >= debut) & (tm < fin)
        if sel.any():
            print(f"  t+{debut - tm[0]:5.0f} a {min(fin, tm[-1]) - tm[0]:5.0f} s : "
                  f"{math.degrees(diff[sel][-1]):+7.1f}")
        debut = fin
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
