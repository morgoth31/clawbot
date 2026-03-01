#!/usr/bin/env python3
"""
Identifier le mapping axes/boutons d'une manette via /joy topic.
Lance: ROS_DOMAIN_ID=28 python3 identify_mapping.py

Affiche les axes et boutons actifs en temps réel.
Ctrl+C pour quitter.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy

AXIS_NAMES_PRO = {
    0: "LX",
    1: "LY",
    2: "RX",
    3: "RY",
    4: "FX",
    5: "FY",
}

BTN_NAMES_PRO = {
    0: "B",  1: "A",  2: "X",  3: "Y",
    4: "O",  5: "L",  6: "R", 7: "ZL",
    8: "ZR",  9: "-",  10: "+", 11: "Home",
    12: "JL", 13: "JR",
}


class JoyIdentifier(Node):
    def __init__(self):
        super().__init__("joy_identifier")
        self._prev_axes = []
        self._prev_btns = []
        self.create_subscription(Joy, "/joy", self._cb, 10)
        self.get_logger().info("🎮 Identifiant la manette — bougez les sticks et appuyez sur les boutons")

    def _cb(self, msg: Joy):
        axes = list(msg.axes)
        btns = list(msg.buttons)

        # Afficher axes qui ont changé significativement
        for i, (a, p) in enumerate(zip(axes, self._prev_axes or [0.0]*len(axes))):
            if abs(a - p) > 0.1:
                name = AXIS_NAMES_PRO.get(i, f"Axe {i}")
                print(f"  Axe [{i:2d}] {name:20s}  →  {a:+.3f}")

        # Afficher boutons pressés
        for i, (b, p) in enumerate(zip(btns, self._prev_btns or [0]*len(btns))):
            if b != p:
                name = BTN_NAMES_PRO.get(i, f"Btn {i}")
                state = "▼ PRESS" if b else "▲ release"
                print(f"  Btn [{i:2d}] {name:10s}  {state}")

        self._prev_axes = axes
        self._prev_btns = btns


def main():
    rclpy.init()
    node = JoyIdentifier()
    print(f"\n  Axes: {len([])} | Boutons: {len([])}")
    print("  (le premier message affichera les dimensions)\n")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()


if __name__ == "__main__":
    main()
