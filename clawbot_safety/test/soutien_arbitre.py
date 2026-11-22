"""Outils de test de l'arbitre multiplexeur (P04).

Contexte rclpy privé (le contexte global est partagé par tout le processus
pytest), horloge simulée, capteurs sains injectés directement.
"""
from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.parameter import Parameter
from sensor_msgs.msg import Imu, LaserScan
from std_msgs.msg import Float32


def contexte():
    ctx = rclpy.Context()
    rclpy.init(context=ctx)
    return ctx


def fermer(node, ctx):
    node.destroy_node()
    rclpy.shutdown(context=ctx)


def scan_sain():
    msg = LaserScan()
    msg.angle_min = -0.5
    msg.angle_increment = 0.01
    msg.range_min = 0.05
    msg.range_max = 10.0
    msg.ranges = [5.0] * 100
    return msg


def imu_saine():
    msg = Imu()
    msg.orientation.w = 1.0
    return msg


def capteurs_sains(arb, t):
    """Alimente scan, imu et tension pour que decide() rende OK, à l'instant t."""
    arb._now = lambda: float(t)
    arb.on_scan(scan_sain())
    arb.on_imu(imu_saine())
    for _ in range(20):
        arb.on_volt(Float32(data=11.9))


def twist(vx):
    msg = Twist()
    msg.linear.x = vx
    return msg


def parametre_lecture_seule(node, nom):
    """Vrai si le paramètre est déclaré read_only (set refusé)."""
    essai = node.set_parameters([Parameter(nom, value=node.get_parameter(nom).value)])
    return not essai[0].successful and "read-only" in essai[0].reason.lower()
