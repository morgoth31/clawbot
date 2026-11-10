#!/usr/bin/env python3
"""Serveur d'action FollowJointTrajectory du bras Clawbot X3 Plus.

Chaine complete :

    MoveIt  ->  /arm_controller/follow_joint_trajectory   (5 articulations)
                /grip_controller/follow_joint_trajectory  (pince)
            ->  echantillonnage temporel a cadence fixe
            ->  /servo_ctrl          std_msgs/Int32MultiArray  [id_servo, angle_deg]
            ->  driver_node (Mcnamu_driver_X3) -> carte Rosmaster -> servos

    et  /arm/joint_states  sensor_msgs/JointState  (6 articulations, radians)

Le driver ne consomme qu'un servo par message : la sequence est cadencee de quelques
millisecondes pour ne pas noyer la liaison serie du MCU.

Aucune retroaction n'existe : le MCU ne publie pas la position du bras. Les valeurs de
/arm/joint_states sont donc les *consignes* courantes, pas des mesures ; apres un
redemarrage, le noeud repart de `initial_positions` et ignore ou se trouve le bras.
"""

import math
import threading
import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from control_msgs.action import FollowJointTrajectory
from sensor_msgs.msg import JointState
from std_msgs.msg import Int32MultiArray

from clawbot_arm_controller.servo_mapping import (
    default_arm_specs,
    default_gripper_spec,
    interpolate,
    specs_from_parameters,
)

# codes de control_msgs/action/FollowJointTrajectory
SUCCESSFUL = 0
INVALID_GOAL = -1
INVALID_JOINTS = -2
OLD_HEADER_TIMESTAMP = -3
PATH_TOLERANCE_VIOLATED = -4
GOAL_TOLERANCE_VIOLATED = -5


class InvalidGoal(Exception):
    """Objectif refusable sans mouvement : porte le code de resultat a renvoyer."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class ArmTrajectoryServer(Node):
    """Execute les trajectoires MoveIt sur les servos du bras."""

    def __init__(self):
        super().__init__('arm_trajectory_server')

        arm_defaults = default_arm_specs()
        grip_default = default_gripper_spec()

        # --- correspondance articulations -> servos (voir servo_mapping) ---------
        self.declare_parameter('arm_joints', [s.joint for s in arm_defaults])
        self.declare_parameter('arm_servo_ids', [s.servo_id for s in arm_defaults])
        self.declare_parameter('arm_zero_deg', [s.zero_deg for s in arm_defaults])
        self.declare_parameter('arm_scale_deg_per_rad',
                               [s.scale_deg_per_rad for s in arm_defaults])
        self.declare_parameter('arm_min_deg', [s.min_deg for s in arm_defaults])
        self.declare_parameter('arm_max_deg', [s.max_deg for s in arm_defaults])

        self.declare_parameter('grip_joints', [grip_default.joint])
        self.declare_parameter('grip_servo_ids', [grip_default.servo_id])
        self.declare_parameter('grip_zero_deg', [grip_default.zero_deg])
        self.declare_parameter('grip_scale_deg_per_rad', [grip_default.scale_deg_per_rad])
        self.declare_parameter('grip_min_deg', [grip_default.min_deg])
        self.declare_parameter('grip_max_deg', [grip_default.max_deg])

        # --- execution -----------------------------------------------------------
        self.declare_parameter('publish_rate_hz', 10.0)
        self.declare_parameter('joint_state_rate_hz', 20.0)
        self.declare_parameter('servo_stagger_s', 0.005)
        self.declare_parameter('max_duration_s', 30.0)
        self.declare_parameter('initial_positions', [0.0] * len(arm_defaults))
        self.declare_parameter('initial_grip_position', 0.0)
        # Articulations dont la consigne n'est PAS publiee sur /servo_ctrl : elles restent
        # dans /arm/joint_states (donc dans le modele MoveIt) mais le servo n'est pas
        # touche. Usage : un axe dont le retour d'angle est invalide (servo 4 de ce bras,
        # qui renvoie -5 deg) ne peut pas etre commande sans risquer un saut.
        # Type declare par une valeur sentinelle : rclpy deduit BYTE_ARRAY d'une liste
        # vide et refuse alors une surcharge STRING_ARRAY. La chaine vide est filtree.
        self.declare_parameter('passive_joints', [''])
        self.declare_parameter('servo_topic', '/servo_ctrl')
        self.declare_parameter('joint_states_topic', '/arm/joint_states')

        self.publish_rate_hz = float(self.get_parameter('publish_rate_hz').value)
        if self.publish_rate_hz <= 0.0:
            raise ValueError('publish_rate_hz doit etre > 0')
        self.sample_period_s = 1.0 / self.publish_rate_hz
        self.servo_stagger_s = float(self.get_parameter('servo_stagger_s').value)
        self.max_duration_s = float(self.get_parameter('max_duration_s').value)

        self.arm_specs = specs_from_parameters(
            self.get_parameter('arm_joints').value,
            self.get_parameter('arm_servo_ids').value,
            self.get_parameter('arm_zero_deg').value,
            self.get_parameter('arm_scale_deg_per_rad').value,
            self.get_parameter('arm_min_deg').value,
            self.get_parameter('arm_max_deg').value,
        )
        self.grip_specs = specs_from_parameters(
            self.get_parameter('grip_joints').value,
            self.get_parameter('grip_servo_ids').value,
            self.get_parameter('grip_zero_deg').value,
            self.get_parameter('grip_scale_deg_per_rad').value,
            self.get_parameter('grip_min_deg').value,
            self.get_parameter('grip_max_deg').value,
        )
        initial = [float(q) for q in self.get_parameter('initial_positions').value]
        if len(initial) != len(self.arm_specs):
            raise ValueError('initial_positions doit avoir une valeur par articulation du bras')

        known = {spec.joint for spec in self.arm_specs + self.grip_specs}
        self._passive = {j for j in self.get_parameter('passive_joints').value if j}
        inconnues = self._passive - known
        if inconnues:
            raise ValueError('passive_joints inconnues : %s' % sorted(inconnues))
        if self._passive:
            self.get_logger().warning(
                'articulations non commandees (servo jamais pilote) : %s'
                % ', '.join(sorted(self._passive)))

        # consigne courante de chaque articulation (radians)
        self._q = {spec.joint: q for spec, q in zip(self.arm_specs, initial)}
        self._q[self.grip_specs[0].joint] = float(
            self.get_parameter('initial_grip_position').value)
        self._last_sent_deg = {}
        self._lock = threading.Lock()
        self._active = {'arm': None, 'grip': None}

        self._servo_pub = self.create_publisher(
            Int32MultiArray, self.get_parameter('servo_topic').value, 10)
        self._joint_pub = self.create_publisher(
            JointState, self.get_parameter('joint_states_topic').value, 10)

        group = ReentrantCallbackGroup()
        self._joint_timer = self.create_timer(
            1.0 / float(self.get_parameter('joint_state_rate_hz').value),
            self._publish_joint_states)

        self._arm_server = ActionServer(
            self, FollowJointTrajectory, 'arm_controller/follow_joint_trajectory',
            execute_callback=lambda gh: self._execute(gh, 'arm'),
            goal_callback=self._make_goal_callback('arm'),
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            handle_accepted_callback=lambda gh: self._handle_accepted(gh, 'arm'),
            callback_group=group)
        self._grip_server = ActionServer(
            self, FollowJointTrajectory, 'grip_controller/follow_joint_trajectory',
            execute_callback=lambda gh: self._execute(gh, 'grip'),
            goal_callback=self._make_goal_callback('grip'),
            cancel_callback=lambda gh: CancelResponse.ACCEPT,
            handle_accepted_callback=lambda gh: self._handle_accepted(gh, 'grip'),
            callback_group=group)

        self.get_logger().info(
            'bras: %s | pince: %s | cadence servo %.1f Hz'
            % (', '.join(s.joint for s in self.arm_specs),
               ', '.join(s.joint for s in self.grip_specs),
               self.publish_rate_hz))

    # ------------------------------------------------------------------ action
    def _specs(self, which):
        return self.arm_specs if which == 'arm' else self.grip_specs

    def _make_goal_callback(self, which):
        """Refuse les objectifs dont les articulations ne sont pas celles du controleur."""
        expected = [spec.joint for spec in self._specs(which)]

        def callback(goal_request):
            names = list(goal_request.trajectory.joint_names)
            if names != expected:
                self.get_logger().warning(
                    'objectif %s refuse : articulations %s, attendu %s'
                    % (which, names, expected))
                return GoalResponse.REJECT
            return GoalResponse.ACCEPT

        return callback

    def _handle_accepted(self, goal_handle, which):
        with self._lock:
            previous = self._active[which]
            self._active[which] = goal_handle
        if previous is not None and getattr(previous, 'is_active', False):
            previous.abort()
        goal_handle.execute()

    def _execute(self, goal_handle, which):
        result = FollowJointTrajectory.Result()
        try:
            waypoints = self._build_waypoints(goal_handle, which)
        except InvalidGoal as exc:
            goal_handle.abort()
            result.error_code = exc.code
            result.error_string = exc.message
            self.get_logger().error('objectif invalide : %s' % exc.message)
            return result

        specs = self._specs(which)
        samples = interpolate(waypoints, self.sample_period_s)
        self.get_logger().info(
            'execution %s : %d echantillons sur %.2f s'
            % (which, len(samples), samples[-1][0] if samples else 0.0))

        origin = time.monotonic()
        sent = 0
        for t_sample, positions in samples:
            remaining = (origin + t_sample) - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.error_code = SUCCESSFUL
                result.error_string = 'annule apres %d echantillons' % sent
                self.get_logger().warning('trajectoire %s annulee' % which)
                return result
            with self._lock:
                for spec, q in zip(specs, positions):
                    self._q[spec.joint] = q
            sent += self._publish_servos(specs, positions)

        goal_handle.succeed()
        result.error_code = SUCCESSFUL
        self.get_logger().info('trajectoire %s terminee, %d consignes servo' % (which, sent))
        return result

    def _build_waypoints(self, goal_handle, which):
        trajectory = goal_handle.request.trajectory
        expected = [spec.joint for spec in self._specs(which)]
        if list(trajectory.joint_names) != expected:
            raise InvalidGoal(INVALID_JOINTS,
                              'articulations %s, attendu %s'
                              % (list(trajectory.joint_names), expected))
        if not trajectory.points:
            raise InvalidGoal(INVALID_GOAL, 'trajectoire vide')

        waypoints = []
        for point in trajectory.points:
            if len(point.positions) != len(expected):
                raise InvalidGoal(
                    INVALID_GOAL,
                    'point de dimension %d pour %d articulations'
                    % (len(point.positions), len(expected)))
            t = point.time_from_start.sec + point.time_from_start.nanosec * 1e-9
            if any(not math.isfinite(q) for q in point.positions):
                raise InvalidGoal(INVALID_GOAL, 'position non finie')
            waypoints.append((t, list(point.positions)))

        if waypoints[-1][0] > self.max_duration_s:
            raise InvalidGoal(
                INVALID_GOAL,
                'duree %.2f s > max_duration_s %.2f s'
                % (waypoints[-1][0], self.max_duration_s))
        return waypoints

    def _publish_servos(self, specs, positions):
        """Publie une consigne par servo actif dont l'angle arrondi a change.

        Les articulations listees dans `passive_joints` sont sautees : leur position est
        suivie dans /arm/joint_states mais aucun ordre n'est envoye au servo.
        """
        count = 0
        for spec, q in zip(specs, positions):
            if spec.joint in self._passive:
                continue
            degrees = int(round(spec.to_servo_deg(q)))
            if self._last_sent_deg.get(spec.joint) == degrees:
                continue
            msg = Int32MultiArray()
            msg.data = [spec.servo_id, degrees]
            self._servo_pub.publish(msg)
            self._last_sent_deg[spec.joint] = degrees
            count += 1
            if self.servo_stagger_s > 0:
                time.sleep(self.servo_stagger_s)
        return count

    def _publish_joint_states(self):
        with self._lock:
            names = [spec.joint for spec in self.arm_specs] + \
                    [spec.joint for spec in self.grip_specs]
            positions = [self._q[name] for name in names]
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = names
        msg.position = positions
        self._joint_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ArmTrajectoryServer()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        # SIGTERM (systemctl stop) declenche deja rcl_shutdown : un second appel leve
        # RCLError et laisse une trace alors que l arret est normal.
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
