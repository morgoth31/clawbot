"""Capture Astra couleur + profondeur, et rend la position 3D d'un pixel donne en base_link."""
import sys

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from tf2_ros import Buffer, TransformListener


class Duo(Node):
    def __init__(self):
        super().__init__("astra_duo")
        self.rgb = None
        self.depth = None
        self.info = None
        self.create_subscription(Image, "/camera/color/image_raw", lambda m: setattr(self, "rgb", m), 10)
        self.create_subscription(Image, "/camera/depth/image_raw", lambda m: setattr(self, "depth", m), 10)
        self.create_subscription(CameraInfo, "/camera/depth/camera_info", lambda m: setattr(self, "info", m), 10)
        self.tf = Buffer()
        self.listener = TransformListener(self.tf, self)


def main():
    from PIL import Image as PILImage
    rclpy.init()
    n = Duo()
    import time
    fin = time.monotonic() + 10
    while time.monotonic() < fin and not (n.rgb and n.depth and n.info):
        rclpy.spin_once(n, timeout_sec=0.1)
    if not (n.rgb and n.depth):
        print("ECHEC : flux Astra incomplet")
        return 2

    rgb = np.frombuffer(bytes(n.rgb.data), np.uint8).reshape(n.rgb.height, n.rgb.width, -1)[:, :, :3]
    PILImage.fromarray(rgb).save("/home/jetson/.hermes/cache/scratch/astra_main.png")
    prof = np.frombuffer(bytes(n.depth.data), np.uint16).reshape(n.depth.height, n.depth.width).astype(np.float64) / 1000.0
    print(f"astra : {n.rgb.width}x{n.rgb.height} {n.rgb.encoding}, profondeur min valide "
          f"{prof[prof > 0].min():.3f} m")

    if len(sys.argv) >= 3:
        u, v = int(sys.argv[1]), int(sys.argv[2])
        k = n.info.k
        d = prof[v, u]
        print(f"pixel ({u},{v}) : profondeur = {('invalide (< 1,16 m)' if d <= 0 else f'{d:.3f} m')}")
        if d > 0:
            xr = (u - k[2]) * d / k[0]
            yr = (v - k[5]) * d / k[4]
            tr = None
            import time as _t
            fin = _t.monotonic() + 8
            while _t.monotonic() < fin and tr is None:
                try:
                    tr = n.tf.lookup_transform("base_link", n.depth.header.frame_id, rclpy.time.Time())
                except Exception:
                    rclpy.spin_once(n, timeout_sec=0.2)
            if tr is None:
                print("TF indisponible")
                return 3
            q = tr.transform.rotation
            import numpy as _np
            r = _np.array([
                [1 - 2 * (q.y ** 2 + q.z ** 2), 2 * (q.x * q.y - q.z * q.w), 2 * (q.x * q.z + q.y * q.w)],
                [2 * (q.x * q.y + q.z * q.w), 1 - 2 * (q.x ** 2 + q.z ** 2), 2 * (q.y * q.z - q.x * q.w)],
                [2 * (q.x * q.z - q.y * q.w), 2 * (q.y * q.z + q.x * q.w), 1 - 2 * (q.x ** 2 + q.y ** 2)]])
            t = _np.array([tr.transform.translation.x, tr.transform.translation.y, tr.transform.translation.z])
            p = r @ _np.array([xr, yr, d]) + t
            print(f"position dans base_link : x={p[0]:+.3f} y={p[1]:+.3f} z={p[2]:+.3f} m")
    n.destroy_node()
    rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
