#!/usr/bin/env python3
"""Mesure du signe du lacet : IMU, roues, EKF — outil de l'essai HW-DRV-002.

Lecture seule : le nœud s'abonne et ne publie sur aucun topic. Il peut donc tourner
dans le domaine 28 sans accord d'écriture.

    ROS_DOMAIN_ID=28 /usr/bin/python3 scripts/mesure_signe_lacet.py \
        --seconds 75 --plan ccw,cw,ccw --sortie /tmp/lacet.csv

Convention de référence (REP-103) : +z = rotation anti-horaire vue de dessus.
Critère de l'essai : pendant une rotation ANTI-HORAIRE, wz(IMU), wz(roues) et le lacet
de /odom doivent tous être POSITIFS. Le capteur qui sort négatif est inversé.

L'outil refuse de conclure si aucune rotation n'a été détectée : un zéro sans activité
prouvée ne vaut rien.
"""
from __future__ import annotations

import argparse
import math
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu

SEUIL_ACTIF = 0.08      # rad/s : au-dessus, le robot tourne
SEUIL_SEGMENT = 0.40    # rad : rotation minimale pour juger un segment (~23 deg)
SEUIL_ECART_S = 0.4     # s de repos pour fermer un segment


def yaw_of(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def integrer(bloc: list[tuple[float, float]]) -> float:
    """Intégrale trapézoïdale sur une suite (t, valeur) triée."""
    total = 0.0
    for i in range(1, len(bloc)):
        dt = bloc[i][0] - bloc[i - 1][0]
        if 0.0 < dt < 0.3:
            total += 0.5 * (bloc[i][1] + bloc[i - 1][1]) * dt
    return total


class Mesure(Node):
    def __init__(self) -> None:
        super().__init__("hermes_mesure_signe_lacet")
        self.imu: list[tuple[float, float]] = []
        self.roues: list[tuple[float, float]] = []
        self.odom: list[tuple[float, float]] = []
        self.create_subscription(Imu, "/imu/data_raw",
                                 lambda m: self.imu.append((self.s(), m.angular_velocity.z)),
                                 qos_profile_sensor_data)
        self.create_subscription(
            Odometry, "/odom_raw",
            lambda m: self.roues.append((self.s(), m.twist.twist.angular.z)), 50)
        self.create_subscription(
            Odometry, "/odom",
            lambda m: self.odom.append((self.s(), yaw_of(m.pose.pose.orientation))), 50)

    def s(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9


def segments(serie: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Découpe la série en fenêtres où |wz| dépasse le seuil, séparées par un repos."""
    blocs: list[tuple[float, float]] = []
    debut: float | None = None
    fin: float = 0.0
    for t, w in serie:
        if abs(w) > SEUIL_ACTIF:
            if debut is None:
                debut = t
            fin = t
        elif debut is not None and t - fin > SEUIL_ECART_S:
            blocs.append((debut, fin))
            debut = None
    if debut is not None:
        blocs.append((debut, fin))
    return blocs


def extraire(serie: list[tuple[float, float]], a: float, b: float) -> list[tuple[float, float]]:
    return [(t, w) for t, w in serie if a <= t <= b]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=75.0)
    ap.add_argument("--plan", default="ccw,cw,ccw",
                    help="sens physique annoncé de chaque rotation, séparés par des virgules")
    ap.add_argument("--sortie", default="")
    args = ap.parse_args()
    plan = [p.strip().lower() for p in args.plan.split(",") if p.strip()]

    rclpy.init()
    node = Mesure()
    premier = None
    limite = time.monotonic() + args.seconds + 20.0
    deja = 0
    while time.monotonic() < limite:
        rclpy.spin_once(node, timeout_sec=0.05)
        if node.imu:
            if premier is None:
                premier = time.monotonic()
                node.get_logger().info("premier message recu, chronometre lance")
            if (len(node.imu) // 20) > deja:      # une ligne toutes les 2 s environ
                deja = len(node.imu) // 20
                t, w = node.imu[-1]
                node.get_logger().info(
                    f"t={t - node.imu[0][0]:6.1f} s  wz(IMU)={w:+.3f}  "
                    f"wz(roues)={node.roues[-1][1] if node.roues else float('nan'):+.3f}")
            if time.monotonic() - premier >= args.seconds:
                break
    imu, roues, odom = list(node.imu), list(node.roues), list(node.odom)
    node.destroy_node()
    rclpy.shutdown()

    if not imu or not roues:
        print("ECHEC : aucun message recu (/imu/data_raw ou /odom_raw muet) "
              "— la mesure ne prouve rien.")
        return 1

    t0 = imu[0][0]
    blocs = segments(imu)
    print(f"\n{len(imu)} echantillons IMU sur {imu[-1][0] - t0:.1f} s "
          f"({len(imu) / (imu[-1][0] - t0):.1f} Hz), {len(roues)} roues, {len(odom)} EKF")
    print(f"segments de rotation detectes : {len(blocs)}")

    juges = 0
    lignes = []
    for i, (a, b) in enumerate(blocs):
        seg_imu = extraire(imu, a, b)
        seg_roues = extraire(roues, a, b)
        seg_odom = extraire(odom, a, b)
        int_imu = integrer(seg_imu)
        int_roues = integrer(seg_roues)
        d_yaw = (seg_odom[-1][1] - seg_odom[0][1]) if len(seg_odom) > 1 else float("nan")
        d_yaw = math.atan2(math.sin(d_yaw), math.cos(d_yaw))
        sens = plan[i] if i < len(plan) else "?"
        lignes.append((i + 1, sens, b - a, int_imu, int_roues, d_yaw,
                       max(abs(w) for _, w in seg_imu)))
        if abs(int_imu) >= SEUIL_SEGMENT:
            juges += 1

    print(f"\n{'#':>2} {'sens':>4} {'duree':>6} {'|wz|max':>8} "
          f"{'int IMU':>9} {'int roues':>10} {'d yaw EKF':>10}")
    for n, sens, duree, pi, pr, dy, pm in lignes:
        print(f"{n:>2} {sens:>4} {duree:>5.1f}s {pm:>7.3f} "
              f"{math.degrees(pi):>8.1f}° {math.degrees(pr):>9.1f}° {math.degrees(dy):>9.1f}°")

    if juges < 2:
        print("\nNON CONCLUANT : moins de deux rotations franches detectees "
              "(un zero ne prouve rien sans activite). Refaire l'essai.")
        return 2

    # Jugement : la direction physique vient du plan annoncé, jamais des capteurs.
    attendu = {"ccw": +1, "cw": -1}
    ecarts = []
    for n, sens, duree, pi, pr, dy, pm in lignes:
        if sens not in attendu or abs(pi) < SEUIL_SEGMENT:
            continue
        ok_imu = (pi > 0) == (attendu[sens] > 0)
        ok_roues = (pr > 0) == (attendu[sens] > 0)
        ok_ekf = math.degrees(dy) * attendu[sens] > 20.0 if dy == dy else False
        ecarts.append((n, sens, ok_imu, ok_roues, ok_ekf))

    if not ecarts:
        print("\nNON CONCLUANT : aucune rotation exploitable dans le plan annonce.")
        return 2

    print("\nconformite REP-103 (+z = anti-horaire) :")
    for n, sens, ok_imu, ok_roues, ok_ekf in ecarts:
        print(f"  rotation {n} ({sens}) : IMU {'OK' if ok_imu else 'INVERSE'}, "
              f"roues {'OK' if ok_roues else 'INVERSE'}, "
              f"EKF {'OK' if ok_ekf else 'FAUX'}")

    imu_ok = all(e[2] for e in ecarts)
    roues_ok = all(e[3] for e in ecarts)
    print()
    if imu_ok and roues_ok:
        print("VERDICT : les deux capteurs respectent REP-103 ; le desaccord de signe "
              "n'est pas reproduit dans cet essai.")
        code = 0
    elif not imu_ok and roues_ok:
        print("VERDICT : wz(IMU) est INVERSE, wz(roues) est correct.")
        code = 0
    elif imu_ok and not roues_ok:
        print("VERDICT : wz(roues) est INVERSE, wz(IMU) est correct.")
        code = 0
    else:
        print("VERDICT : les deux sont incoherents avec le sens annonce "
              "(verifier que le sens physique annonce est le bon avant de conclure).")
        code = 3

    if args.sortie:
        with open(args.sortie, "w") as f:
            f.write("segment,sens,duree_s,int_imu_rad,int_roues_rad,dyaw_ekf_rad,wz_max\n")
            for n, sens, duree, pi, pr, dy, pm in lignes:
                f.write(f"{n},{sens},{duree:.3f},{pi:.5f},{pr:.5f},{dy:.5f},{pm:.5f}\n")
        print(f"\nCSV : {args.sortie}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
