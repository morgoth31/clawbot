#!/usr/bin/env python3
"""Publie le support de la camera Orbbec comme objet de collision dans la scene MoveIt.

Le maillage de collision de `base_link` ne contient que la plaque haute du support
(z = 0,382) : la structure verticale entre le châssis et cette plaque est absente, ce qui
fait accepter au planificateur des trajectoires qui touchent reellement le mat.

L'objet est une boite (ou un cylindre) rattachee a `base_link`, elargie d'une marge de
securite `margin` sur toutes ses faces. Les valeurs par defaut enveloppent l'empreinte de
la plaque relevee dans le maillage : x de -0,057 a -0,037, y de -0,083 a +0,083, du haut
du chassis (z = 0,10) a la plaque (z = 0,382).

Le noeud publie l'objet puis **verifie** qu'il est present dans la scene (service
/get_planning_scene) : au demarrage, move_group n'est pas encore pret et une publication
unique se perd. Il reessaie jusqu'a confirmation, puis s'arrete.

Parametres ROS (fichier `config/mast.yaml`) :
  shape        box | cylinder
  x, y         centre de l'empreinte dans base_link
  z_min, z_max hauteur couverte
  size_x, size_y  dimensions de la boite (shape: box)
  diameter     diametre du cylindre (shape: cylinder)
  margin       marge de securite ajoutee sur toutes les faces (m)
  timeout      duree maximale des tentatives (s)
  remove       true pour retirer l'objet au lieu de l'ajouter
"""

import time

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Pose
from moveit_msgs.msg import CollisionObject, PlanningScene, PlanningSceneComponents
from moveit_msgs.srv import ApplyPlanningScene, GetPlanningScene
from shape_msgs.msg import SolidPrimitive


class MastCollision(Node):
    """Publie le volume du support camera et confirme sa presence dans la scene."""

    def __init__(self):
        super().__init__('mast_collision')

        self.declare_parameter('object_id', 'camera_support')
        self.declare_parameter('frame_id', 'base_link')
        self.declare_parameter('shape', 'box')
        self.declare_parameter('x', -0.047)
        self.declare_parameter('y', 0.0)
        self.declare_parameter('z_min', 0.10)
        self.declare_parameter('z_max', 0.382)
        self.declare_parameter('size_x', 0.020)
        self.declare_parameter('size_y', 0.166)
        self.declare_parameter('diameter', 0.040)
        self.declare_parameter('margin', 0.02)
        self.declare_parameter('timeout', 120.0)
        self.declare_parameter('remove', False)

        self.publisher = self.create_publisher(CollisionObject, '/planning_scene', 10)
        self.client = self.create_client(GetPlanningScene, '/get_planning_scene')
        self.apply_client = self.create_client(ApplyPlanningScene, '/apply_planning_scene')
        self.object_id = str(self.get_parameter('object_id').value)

    def present_in_scene(self):
        if not self.client.service_is_ready():
            return None
        request = GetPlanningScene.Request()
        request.components.components = PlanningSceneComponents.WORLD_OBJECT_GEOMETRY
        future = self.client.call_async(request)
        deadline = time.time() + 5.0
        while not future.done() and time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
        if not future.done():
            return None
        scene = future.result().scene
        return self.object_id in [obj.id for obj in scene.world.collision_objects]

    def apply_object(self):
        """Applique l'objet par le service ; la voie topic n'est pas honoree ici."""
        if not self.apply_client.service_is_ready():
            return None
        request = ApplyPlanningScene.Request()
        request.scene = PlanningScene()
        request.scene.is_diff = True
        request.scene.world.collision_objects = [self.build_object()]
        future = self.apply_client.call_async(request)
        deadline = time.time() + 5.0
        while not future.done() and time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
        if not future.done():
            return None
        return bool(future.result().success)

    def run(self):
        deadline = time.time() + float(self.get_parameter('timeout').value)
        retirer = bool(self.get_parameter('remove').value)
        tentative = 0
        while time.time() < deadline and rclpy.ok():
            tentative += 1
            applied = self.apply_object()
            if applied is None:
                self.publisher.publish(self.build_object())  # secours tant que le service n'est pas pret
            elif applied is False:
                self.get_logger().warning('apply_planning_scene a refuse l objet')
            rclpy.spin_once(self, timeout_sec=0.2)
            present = self.present_in_scene()
            if present is True and not retirer:
                self.get_logger().info(
                    'support camera present dans la scene (tentative %d) : %s'
                    % (tentative, self.describe()))
                return True
            if present is False and retirer:
                self.get_logger().info('support camera retire de la scene (tentative %d)'
                                       % tentative)
                return True
            time.sleep(1.0)
        self.get_logger().error(
            'support camera NON confirme dans la scene apres %d tentatives' % tentative)
        return False

    def describe(self):
        shape = str(self.get_parameter('shape').value)
        margin = float(self.get_parameter('margin').value)
        z_min = float(self.get_parameter('z_min').value)
        z_max = float(self.get_parameter('z_max').value)
        if shape == 'cylinder':
            dims = 'cylindre h=%.3f r=%.3f' % (z_max - z_min + 2 * margin,
                                               0.5 * float(self.get_parameter('diameter').value) + margin)
        else:
            dims = 'boite %.3f x %.3f x %.3f' % (
                float(self.get_parameter('size_x').value) + 2 * margin,
                float(self.get_parameter('size_y').value) + 2 * margin,
                z_max - z_min + 2 * margin)
        return '%s x=%.3f y=%.3f z=[%.3f ; %.3f] marge %.3f' % (
            dims, self.get_parameter('x').value, self.get_parameter('y').value,
            z_min, z_max, margin)

    def build_object(self):
        shape = str(self.get_parameter('shape').value)
        margin = float(self.get_parameter('margin').value)
        z_min = float(self.get_parameter('z_min').value)
        z_max = float(self.get_parameter('z_max').value)

        primitive = SolidPrimitive()
        pose = Pose()
        pose.position.x = float(self.get_parameter('x').value)
        pose.position.y = float(self.get_parameter('y').value)
        pose.position.z = 0.5 * (z_min + z_max)
        pose.orientation.w = 1.0

        if shape == 'cylinder':
            primitive.type = SolidPrimitive.CYLINDER
            primitive.dimensions = [
                float(z_max - z_min) + 2.0 * margin,
                0.5 * float(self.get_parameter('diameter').value) + margin,
            ]
        else:
            primitive.type = SolidPrimitive.BOX
            primitive.dimensions = [
                float(self.get_parameter('size_x').value) + 2.0 * margin,
                float(self.get_parameter('size_y').value) + 2.0 * margin,
                float(z_max - z_min) + 2.0 * margin,
            ]

        obj = CollisionObject()
        obj.header.frame_id = str(self.get_parameter('frame_id').value)
        obj.header.stamp = self.get_clock().now().to_msg()
        obj.id = self.object_id
        obj.primitives = [primitive]
        obj.primitive_poses = [pose]
        obj.operation = (CollisionObject.REMOVE
                         if bool(self.get_parameter('remove').value)
                         else CollisionObject.ADD)
        return obj


def main(args=None):
    rclpy.init(args=args)
    node = MastCollision()
    try:
        ok = node.run()
    except KeyboardInterrupt:
        ok = False
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
