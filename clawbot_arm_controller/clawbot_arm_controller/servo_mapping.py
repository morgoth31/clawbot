"""Conversion articulation URDF <-> consigne servo bus serie, et interpolation.

Le zero mecanique de chaque servo du bras n'est pas identifie sur ce robot : la base de
connaissances (01_Hardware/bras_6dof.md) enregistre des angles lus sur la carte sans
correspondance etablie avec les articulations de l'URDF. Les conversions ci-dessous sont
donc des *parametres*, jamais des constantes cachees :

    angle_servo_deg = zero_deg + scale_deg_par_rad * q        (q en radians)
    angle_servo_deg borne a [min_deg, max_deg]

Les valeurs par defaut appliquent la convention documentee :
  - servos 1 a 5 : 90 deg a q = 0, 57,2958 deg/rad (donc -90..+90 -> 0..180, et
    0..180 deg pour arm_joint5 -> 90..270) ;
  - servo 6 (pince) : 180 deg a q = 0 (ferme), 0 deg a q = -1,54 rad (ouvert), ce qui
    correspond aux consignes deja utilisees par /claw sur le service materiel.

Tant que ces offsets ne sont pas verifies servo par servo, la consigne est *coherente*
mais son origine mecanique reste inconnue : c'est inscrit dans les limites du noeud.
"""

from dataclasses import dataclass
import math

RAD_TO_DEG = 180.0 / math.pi


@dataclass(frozen=True)
class ServoSpec:
    """Correspondance d'une articulation vers un servo du bus serie."""

    joint: str
    servo_id: int
    zero_deg: float
    scale_deg_per_rad: float
    min_deg: float
    max_deg: float

    def to_servo_deg(self, q_rad: float) -> float:
        """Angle servo (°) pour une position articulaire en radians, borne."""
        raw = self.zero_deg + self.scale_deg_per_rad * q_rad
        return min(self.max_deg, max(self.min_deg, raw))

    def to_joint_rad(self, servo_deg: float) -> float:
        """Position articulaire (rad) pour un angle servo en degres."""
        return (servo_deg - self.zero_deg) / self.scale_deg_per_rad


def default_arm_specs() -> list:
    """Servos 1 a 5 du bras, plage materielle 0-180° (0-270° pour le servo 5)."""
    specs = []
    for index in range(1, 6):
        upper_deg = 270.0 if index == 5 else 180.0
        specs.append(
            ServoSpec(
                joint=f'arm_joint{index}',
                servo_id=index,
                zero_deg=90.0,
                scale_deg_per_rad=RAD_TO_DEG,
                min_deg=0.0,
                max_deg=upper_deg,
            )
        )
    return specs


def default_gripper_spec() -> ServoSpec:
    """Servo 6 : pince, 0° ouvert a q = -1,54 rad, 180° ferme a q = 0."""
    return ServoSpec(
        joint='grip_joint',
        servo_id=6,
        zero_deg=180.0,
        scale_deg_per_rad=180.0 / 1.54,
        min_deg=0.0,
        max_deg=180.0,
    )


def specs_from_parameters(joint_names, servo_ids, zero_deg, scale_deg_per_rad,
                          min_deg, max_deg) -> list:
    """Construit les correspondances depuis les parametres ROS, avec verification."""
    lengths = {len(joint_names), len(servo_ids), len(zero_deg),
               len(scale_deg_per_rad), len(min_deg), len(max_deg)}
    if len(lengths) != 1:
        raise ValueError(
            'les listes joints/servo_ids/zero_deg/scale/min/max doivent avoir la meme '
            f'longueur, recu {sorted(lengths)}')
    specs = []
    for i, joint in enumerate(joint_names):
        if scale_deg_per_rad[i] == 0:
            raise ValueError(f'scale_deg_per_rad nul pour {joint}')
        if min_deg[i] > max_deg[i]:
            raise ValueError(f'bornes inversees pour {joint}: {min_deg[i]} > {max_deg[i]}')
        specs.append(ServoSpec(
            joint=str(joint),
            servo_id=int(servo_ids[i]),
            zero_deg=float(zero_deg[i]),
            scale_deg_per_rad=float(scale_deg_per_rad[i]),
            min_deg=float(min_deg[i]),
            max_deg=float(max_deg[i]),
        ))
    return specs


def interpolate(waypoints, sample_period_s):
    """Echantillonne une liste de points de passage.

    waypoints : sequence de (t_s, [q...]) triee par t croissant, t en secondes depuis le
    debut de la trajectoire. Retourne [(t, [q...])] echantillonne a sample_period_s,
    incluant le dernier point exact (t final toujours present).

    Une liste a un seul point est tenue : c'est une consigne de maintien.
    """
    if not waypoints:
        return []
    if sample_period_s <= 0:
        raise ValueError('sample_period_s doit etre > 0')

    cleaned = [(float(t), [float(q) for q in positions]) for t, positions in waypoints]
    width = len(cleaned[0][1])
    for t, positions in cleaned:
        if len(positions) != width:
            raise ValueError('tous les points doivent avoir la meme dimension')
    for previous, current in zip(cleaned, cleaned[1:]):
        if current[0] < previous[0]:
            raise ValueError('les dates des points doivent etre croissantes')

    if len(cleaned) == 1:
        return [(cleaned[0][0], list(cleaned[0][1]))]

    samples = []
    t_end = cleaned[-1][0]
    steps = int(math.floor(t_end / sample_period_s))
    for step in range(steps + 1):
        t = step * sample_period_s
        samples.append((t, _positions_at(cleaned, t)))
    if abs(samples[-1][0] - t_end) > 1e-9:
        samples.append((t_end, _positions_at(cleaned, t_end)))
    return samples


def _positions_at(waypoints, t):
    """Interpolation lineaire par morceaux d'un instant donne."""
    if t <= waypoints[0][0]:
        return list(waypoints[0][1])
    for (t0, q0), (t1, q1) in zip(waypoints, waypoints[1:]):
        if t <= t1:
            if t1 - t0 <= 0:
                return list(q1)
            ratio = (t - t0) / (t1 - t0)
            return [a + (b - a) * ratio for a, b in zip(q0, q1)]
    return list(waypoints[-1][1])
