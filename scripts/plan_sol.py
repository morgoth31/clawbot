"""Hauteur du sol dans base_link, mesuree sur toute l'image de profondeur.

Le sol est le plan horizontal dominant de la scene. On transforme tous les points valides dans
base_link et on regarde l'histogramme des z : le pic bas est le sol. Pas de percentile sur une bande
d'image — c'est justement ce qui a donne deux valeurs contradictoires (-0,414 puis -0,097) le meme
jour, selon l'inclinaison de la camera.
"""
import time

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from tf2_ros import Buffer, TransformListener


rclpy.init()
n = Node("plan_sol")
etat = {}
n.create_subscription(Image, "/camera/depth/image_raw", lambda m: etat.update(d=m), 10)
n.create_subscription(CameraInfo, "/camera/depth/camera_info", lambda m: etat.update(k=m), 10)
tf = Buffer()
listener = TransformListener(tf, n)
fin = time.monotonic() + 10
while time.monotonic() < fin and not ("d" in etat and "k" in etat):
    rclpy.spin_once(n, timeout_sec=0.1)

m, info = etat["d"], etat["k"]
z = np.frombuffer(bytes(m.data), np.uint16).reshape(m.height, m.width).astype(np.float64) / 1000.0
tr = None
fin = time.monotonic() + 10
while time.monotonic() < fin and tr is None:
    try:
        tr = tf.lookup_transform("base_link", m.header.frame_id, rclpy.time.Time())
    except Exception:
        rclpy.spin_once(n, timeout_sec=0.2)
q = tr.transform.rotation
r = np.array([
    [1 - 2 * (q.y ** 2 + q.z ** 2), 2 * (q.x * q.y - q.z * q.w), 2 * (q.x * q.z + q.y * q.w)],
    [2 * (q.x * q.y + q.z * q.w), 1 - 2 * (q.x ** 2 + q.z ** 2), 2 * (q.y * q.z - q.x * q.w)],
    [2 * (q.x * q.z - q.y * q.w), 2 * (q.y * q.z + q.x * q.w), 1 - 2 * (q.x ** 2 + q.y ** 2)]])
t = np.array([tr.transform.translation.x, tr.transform.translation.y, tr.transform.translation.z])

k = info.k
ys, xs = np.mgrid[0:m.height, 0:m.width]
ok = np.isfinite(z) & (z > 0.3)
u = (xs[ok] - k[2]) / k[0]
v = (ys[ok] - k[5]) / k[4]
dirs = np.stack([u, v, np.ones_like(u)], axis=1)
dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
pts = z[ok][:, None] * dirs @ r.T + t
print(f"points valides : {ok.sum()} ({ok.mean()*100:.1f} %)")
print(f"z dans base_link : min {pts[:,2].min():+.3f}  median {np.median(pts[:,2]):+.3f}  max {pts[:,2].max():+.3f}")
hist, bords = np.histogram(pts[:, 2], bins=40, range=(-0.8, 0.4))
pic = int(np.argmax(hist))
centre = (bords[pic] + bords[pic + 1]) / 2
masse = hist[pic] / hist.sum() * 100
print(f"pic d'histogramme des z : {centre:+.3f} m ({masse:.0f} % des points)")
bande = pts[np.abs(pts[:, 2] - centre) < 0.02]
print(f"plan retenu : z = {np.median(bande[:,2]):+.3f} m sur {len(bande)} points, "
      f"etendue en x {bande[:,0].min():+.2f} a {bande[:,0].max():+.2f} m")
n.destroy_node()
rclpy.try_shutdown()
