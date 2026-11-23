#!/usr/bin/env python3
"""Essai libre : 60 s de conduite, puis arbitrage du lacet SANS sens annonce.

Quatre series enregistrees en direct : /scan, /imu/data_raw, /odom_raw (roues), /odom (EKF).
La reference physique est le lidar, par appariement polaire entre scans consecutifs
(methode validee sur bag : pente 1,01 avec les roues, -1,00 avec l'IMU).

Aucune consigne : l'operateur roule librement. L'outil refuse de conclure si le robot n'a
pas tourne assez (un zero sans activite ne prouve rien).

    ROS_DOMAIN_ID=28 /usr/bin/python3 essai_libre.py --seconds 60
"""
from __future__ import annotations

import argparse
import math
import time

import numpy as np
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, LaserScan

BINS = 720
R_MIN, R_MAX = 0.20, 8.0
SHIFT_MAX_BINS = 24
STEP = 0.25


def image_portee(m) -> np.ndarray | None:
    r = np.asarray(m.ranges, dtype=float)
    if r.size == 0:
        return None
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


def cout(img_a, img_b, delta_bins) -> float:
    k = np.arange(BINS, dtype=float) + delta_bins
    bas = np.floor(k).astype(int)
    frac = k - bas
    a = (1 - frac) * img_a[bas % BINS] + frac * img_a[(bas + 1) % BINS]
    val = ~np.isnan(a) & ~np.isnan(img_b)
    if val.sum() < 120:
        return float("inf")
    return float(np.mean(np.abs(a[val] - img_b[val])))


def yaw_of(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class Essai(Node):
    def __init__(self):
        super().__init__("hermes_essai_libre")
        self.scans: list[tuple[float, np.ndarray]] = []
        self.imu: list[tuple[float, float]] = []
        self.roues: list[tuple[float, float]] = []
        self.ekf_rate: list[tuple[float, float]] = []
        self.ekf_yaw: list[tuple[float, float]] = []
        self.create_subscription(LaserScan, "/scan", self._scan, qos_profile_sensor_data)
        self.create_subscription(Imu, "/imu/data_raw",
                                 lambda m: self.imu.append((self.s(), m.angular_velocity.z)),
                                 qos_profile_sensor_data)
        self.create_subscription(Odometry, "/odom_raw",
                                 lambda m: self.roues.append((self.s(), m.twist.twist.angular.z)), 50)
        self.create_subscription(Odometry, "/odom", self._odom, 50)

    def _scan(self, m):
        img = image_portee(m)
        if img is not None:
            self.scans.append((self.s(), img))

    def _odom(self, m):
        t = self.s()
        self.ekf_rate.append((t, m.twist.twist.angular.z))
        self.ekf_yaw.append((t, yaw_of(m.pose.pose.orientation)))

    def s(self):
        return self.get_clock().now().nanoseconds / 1e9


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60.0)
    args = ap.parse_args()

    rclpy.init()
    n = Essai()
    premier = None
    limite = time.monotonic() + args.seconds + 25.0
    dernier = 0
    while time.monotonic() < limite:
        rclpy.spin_once(n, timeout_sec=0.05)
        if n.imu and premier is None:
            premier = time.monotonic()
            n.get_logger().info("premier message recu — chronometre lance")
        if premier is not None:
            ecoule = time.monotonic() - premier
            if int(ecoule // 10) > dernier:
                dernier = int(ecoule // 10)
                n.get_logger().info(f"{ecoule:5.0f} s  scans={len(n.scans)}  "
                                    f"wz(IMU)={n.imu[-1][1]:+.3f}  "
                                    f"wz(roues)={n.roues[-1][1] if n.roues else 0:+.3f}  "
                                    f"wz(EKF)={n.ekf_rate[-1][1]:+.3f}")
            if ecoule >= args.seconds:
                break
    scans, imu, roues = list(n.scans), list(n.imu), list(n.roues)
    ekf_r, ekf_y = list(n.ekf_rate), list(n.ekf_yaw)
    n.destroy_node()
    rclpy.shutdown()

    if len(scans) < 50 or len(imu) < 50 or len(roues) < 50 or not ekf_r:
        print(f"ECHEC : flux insuffisants (scans {len(scans)}, IMU {len(imu)}, "
              f"roues {len(roues)}, EKF {len(ekf_r)}) — la mesure ne prouve rien.")
        return 1

    t_imu = np.array([t for t, _ in imu])
    w_imu = np.array([w for _, w in imu])
    t_rou = np.array([t for t, _ in roues])
    w_rou = np.array([w for _, w in roues])
    t_ekr = np.array([t for t, _ in ekf_r])
    w_ekr = np.array([w for _, w in ekf_r])
    w_eky = np.array([w for _, w in ekf_y])

    tm, dt, wl, contraste = [], [], [], []
    for i in range(1, len(scans)):
        (t0, a), (t1, b) = scans[i - 1], scans[i]
        d = t1 - t0
        if not 0.05 <= d <= 0.25:
            continue
        deltas = np.arange(-SHIFT_MAX_BINS, SHIFT_MAX_BINS + STEP, STEP)
        couts = np.array([cout(a, b, x) for x in deltas])
        if np.isfinite(couts).sum() < 5:
            continue
        j = int(np.nanargmin(couts))
        hors = np.abs(deltas - deltas[j]) > 3.0
        base = np.nanmin(couts[hors]) if np.isfinite(couts[hors]).any() else np.nan
        tm.append((t0 + t1) / 2)
        dt.append(d)
        wl.append(deltas[j] * 2 * math.pi / BINS / d)
        contraste.append(base - couts[j] if np.isfinite(base) else 0.0)

    if len(wl) < 30:
        print(f"NON CONCLUANT : {len(wl)} paires exploitables.")
        return 2

    tm = np.array(tm)
    dt = np.array(dt)
    wl = np.array(wl)
    contraste = np.array(contraste)
    w_imu_s = w_imu[np.abs(t_imu[None, :] - tm[:, None]).argmin(axis=1)]
    w_rou_s = w_rou[np.abs(t_rou[None, :] - tm[:, None]).argmin(axis=1)]
    w_ekr_s = w_ekr[np.abs(t_ekr[None, :] - tm[:, None]).argmin(axis=1)]

    def corr(a, b):
        return float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-9 and b.std() > 1e-9 else float("nan")

    fort = (np.abs(wl) > 0.10) & (contraste > 0.05)
    print(f"\npaires : {len(wl)} · rotation franche : {int(fort.sum())}")
    if fort.sum() < 20:
        print("NON CONCLUANT : trop peu de rotation (un zero ne prouve rien sans activite).")
        return 2

    for nom, s in (("IMU", w_imu_s), ("roues", w_rou_s), ("EKF (twist)", w_ekr_s)):
        pente = np.polyfit(s[fort], wl[fort], 1)[0]
        accord = 100 * np.mean(np.sign(wl[fort]) == np.sign(s[fort]))
        integ = math.degrees(np.sum(s[fort] * dt[fort]))
        print(f"{nom:<13} corr {corr(wl, s):+.3f} · pente {pente:+.3f} · "
              f"signe {accord:5.1f} % · integrale {integ:+7.1f} deg")
    print(f"{'lidar':<13} integrale sur la meme fenetre : "
          f"{math.degrees(np.sum(wl[fort] * dt[fort])):+7.1f} deg")
    print(f"lacet EKF de bout en bout : {math.degrees(w_eky[-1] - w_eky[0]):+.1f} deg")

    print("\nlecture : reference = lidar. Pente ~ -1 et <10 % de signes communs = capteur")
    print("INVERSE par rapport au sens physique ; pente ~ +1 et >90 % = capteur correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
