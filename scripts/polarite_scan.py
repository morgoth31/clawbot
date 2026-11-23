#!/usr/bin/env python3
"""Polarite de /scan, version decisive : avance ET deplacement lateral.

En repere FIDELE, un deplacement du capteur de (dx, dy) produit
    dr(phi) ~ -(dx*cos(phi) + dy*sin(phi))
Le terme en cos(phi) est aveugle au miroir selon x (phi -> -phi) ; le terme en sin(phi) ne
l'est pas. Un robot mecanum strafe : les deux termes sont mesurables sur le meme bag.

  kx = pente sur cos(phi) pendant une avance pure   -> detecte miroir selon y (phi -> pi-phi)
  ky = pente sur sin(phi) pendant un strafe pur      -> detecte miroir selon x (phi -> -phi)

Signes attendus en repere FIDELE : kx < 0 avec vx > 0 ; ky < 0 avec vy > 0.
"""
from __future__ import annotations

import math
import sys

import numpy as np

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

NBINS = 72
R_MIN, R_MAX = 0.20, 8.0


def lire(chemin: str):
    lecteur = rosbag2_py.SequentialReader()
    lecteur.open(rosbag2_py.StorageOptions(uri=chemin, storage_id="sqlite3"),
                 rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {t.name: t.type for t in lecteur.get_all_topics_and_types()}
    classes = {n: get_message(t) for n, t in types.items() if n in ("/scan", "/odom_raw")}
    don: dict[str, list] = {n: [] for n in classes}
    while lecteur.has_next():
        nom, brut, t = lecteur.read_next()
        if nom in don:
            don[nom].append((t / 1e9, deserialize_message(brut, classes[nom])))
    return don


def profil(m):
    r = np.asarray(m.ranges, dtype=float)
    if r.size == 0:
        return np.full(NBINS, np.nan), np.full(NBINS, np.nan)
    ang = m.angle_min + np.arange(r.size) * m.angle_increment
    ok = np.isfinite(r) & (r > R_MIN) & (r < R_MAX)
    idx = np.clip(((ang[ok] + math.pi) / (2 * math.pi) * NBINS).astype(int), 0, NBINS - 1)
    somme = np.bincount(idx, weights=r[ok], minlength=NBINS)
    compte = np.bincount(idx, minlength=NBINS)
    portee = np.full(NBINS, np.nan)
    plein = compte > 0
    portee[plein] = somme[plein] / compte[plein]
    centre = -math.pi + (np.arange(NBINS) + 0.5) * (2 * math.pi / NBINS)
    return portee, centre


def main() -> int:
    d = lire(sys.argv[1])
    scans, roues = d["/scan"], d["/odom_raw"]
    t_r = np.array([t for t, _ in roues])
    vx = np.array([m.twist.twist.linear.x for _, m in roues])
    vy = np.array([m.twist.twist.linear.y for _, m in roues])
    wz = np.array([m.twist.twist.angular.z for _, m in roues])

    acc = {"avance": [0.0, 0, []], "strafe": [0.0, 0, []]}
    precedente = None
    for t, m in scans:
        p1, c = profil(m)
        if precedente is not None:
            t0, p0 = precedente
            dt = t - t0
            if 0.05 <= dt <= 0.25:
                i = int(np.argmin(np.abs(t_r - (t0 + t) / 2)))
                if abs(wz[i]) < 0.06:
                    val = ~np.isnan(p0) & ~np.isnan(p1)
                    if val.sum() >= 20:
                        dr = p1[val] - p0[val]
                        cf, sf = np.cos(c[val]), np.sin(c[val])
                        if abs(vx[i]) > 0.08 and abs(vy[i]) < 0.05:
                            a = np.vstack([cf, sf, np.ones_like(cf)]).T
                            coef, *_ = np.linalg.lstsq(a, dr, rcond=None)
                            acc["avance"][0] += coef[0]
                            acc["avance"][1] += 1
                            acc["avance"][2].append(abs(vx[i]) * dt)
                        elif abs(vy[i]) > 0.08 and abs(vx[i]) < 0.05:
                            a = np.vstack([cf, sf, np.ones_like(cf)]).T
                            coef, *_ = np.linalg.lstsq(a, dr, rcond=None)
                            acc["strafe"][0] += coef[1]
                            acc["strafe"][1] += 1
                            acc["strafe"][2].append(abs(vy[i]) * dt)
        precedente = (t, p1)

    verdicts = []
    for nom, (somme, n, deplacements) in acc.items():
        if n < 30:
            print(f"{nom:<7} : NON CONCLUANT ({n} paires)")
            verdicts.append(None)
            continue
        k = somme / n
        dd = float(np.mean(deplacements)) * 1000
        etiquette = "FIDELE" if k < 0 else "MIROIR"
        print(f"{nom:<7} : {n:4d} paires · deplacement moyen {dd:.1f} mm · "
              f"pente k = {k * 1000:+.2f} mm/pair -> {etiquette}")
        verdicts.append(k < 0)

    print()
    avance, strafe = verdicts[0], verdicts[1]
    if avance is None and strafe is None:
        print("NON CONCLUANT : aucune paire exploitable.")
        return 2
    if avance is False:
        print("POLARITE : MIROIR selon y (phi -> pi-phi). L'appariement doit etre retourne.")
        return 0
    if strafe is False:
        print("POLARITE : MIROIR selon x (phi -> -phi). L'appariement doit etre retourne.")
        return 0
    if avance is True and strafe is True:
        print("POLARITE : FIDELE dans les deux axes. /scan est directement comparable a")
        print("REP-103 ; l'appariement polaire ne doit pas etre retourne.")
    elif avance is True and strafe is None:
        print("POLARITE : ni retourne d'un demi-tour, ni miroir selon y (avance pure, k < 0).")
        print("Le miroir GAUCHE-DROITE (phi -> -phi) reste NON TRANCHE : il est invisible a")
        print("l'avance pure, et ce bag ne contient aucun deplacement lateral (|vy| max 2 cm/s).")
        print("=> seule une rotation dans un sens connu le tranche (tests/hardware/HW-DRV-002.md).")
        return 4
    print("POLARITE : incoherente entre les axes — ne rien conclure.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
