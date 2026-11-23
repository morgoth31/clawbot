#!/usr/bin/env python
# encoding: utf-8

#public lib
import os
import sys
import math
import random
import threading
from math import pi
from time import sleep
from Rosmaster_Lib import Rosmaster

#ros lib
import threading

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.node import Node
from std_msgs.msg import String,Float32,Int32,Bool,Int32MultiArray
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu,MagneticField
from nav_msgs.msg import Odometry
import time as _time
try:
    from .cmd_scaling import RAMP_STEP, feedback, kick_boost, ramp_cmd, scale_cmd_vel
    from .imu_covariances import (
        covariance_accel, covariance_gyro, covariance_orientation)
except ImportError:  # exécution directe du fichier
    from cmd_scaling import RAMP_STEP, feedback, kick_boost, ramp_cmd, scale_cmd_vel
from rclpy.clock import Clock
from rclpy.executors import ExternalShutdownException
from rcl_interfaces.msg import ParameterDescriptor
try:
    from .port_lock import PortBusyError, PortLock, chemin_verrou
except ImportError:  # execution directe du fichier
    from port_lock import PortBusyError, PortLock, chemin_verrou

#from dynamic_reconfigure.server import Server
# Chemin stable du MCU, releve en P01-M05 (REQ-DRV-003).
MCU_PAR_DEFAUT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"
car_type_dic={
    'R2':5,
    'X3':1,
    'NONE':-1
}
class yahboomcar_driver(Node):
    def __init__(self, name, rosmaster_factory=None, context=None):
        super().__init__(name, context=context)
        global car_type_dic
        self.RA2DE = 180 / pi
        # Port serie nomme (REQ-DRV-003) et delai d'arret (REQ-DRV-002), declares avant
        # toute ouverture de port.
        self.declare_parameter('device_path', MCU_PAR_DEFAUT)
        self.device_path = self.get_parameter('device_path').get_parameter_value().string_value
        self.declare_parameter(
            'cmd_timeout_s', 0.3,
            ParameterDescriptor(read_only=True,
                                description="Delai sans consigne avant arret des moteurs (s)"))
        self.cmd_timeout_s = float(self.get_parameter('cmd_timeout_s').value)
        self._last_cmd_t = None
        self._derniere_consigne_nulle = True
    
        # Un seul proprietaire du port : deux lecteurs se volent les octets (C08).
        self._verrou = PortLock(chemin_verrou())
        try:
            self._verrou.acquerir()
        except PortBusyError as exc:
            self.get_logger().fatal(str(exc))
            sys.exit(1)
    
        # X3 Plus : moteurs 520, cinématique Mecanum. La trame de set_car_motion embarque ce
        # type ; avec le type par défaut (1 = X3, moteurs 370) le PID interne du STM32 recevait
        # les encodeurs à l'envers et partait en contre-réaction positive (ERR-010).
        fabrique = rosmaster_factory or Rosmaster
        self.car = fabrique(car_type=2, com=self.device_path)
        # Séquence validée sur le matériel : le fil de réception doit tourner et le report
        # automatique doit être armé AVANT set_car_type, sinon le STM32 ignore la trame.
        self.car.create_receive_threading()
        self.car.set_auto_report_state(True, forever=False)
        self.car.set_car_type(2)
        sleep(0.2)
        self._car_type_ok = False
        for _ in range(20):
            # renvoye a chaque tour : la premiere trame tombe pendant le boot du STM32
            self.car.set_car_type(2)
            sleep(0.15)
            if self.car.get_car_type_from_machine() == 2:
                self._car_type_ok = True
                break
        if not self._car_type_ok:
            self.get_logger().error("car_type != 2 : mouvement refuse (ERR-010)")

        #get parameter
        self.declare_parameter('car_type', 'X3PLUS')
        self.car_type = self.get_parameter('car_type').get_parameter_value().string_value
        print (self.car_type)
        self.declare_parameter('imu_link', 'imu_link')
        self.imu_link = self.get_parameter('imu_link').get_parameter_value().string_value
        print (self.imu_link)
        self.declare_parameter('Prefix', "")
        self.Prefix = self.get_parameter('Prefix').get_parameter_value().string_value
        print (self.Prefix)
        self.declare_parameter('xlinear_limit', 1.0)
        self.xlinear_limit = self.get_parameter('xlinear_limit').get_parameter_value().double_value
        print (self.xlinear_limit)
        self.declare_parameter('ylinear_limit', 1.0)
        self.ylinear_limit = self.get_parameter('ylinear_limit').get_parameter_value().double_value
        print (self.ylinear_limit)
        self.declare_parameter('angular_limit', 5.0)
        # Cadence de publication. Le timer valait 0,1 s en dur. Mesure du 2026-11-23 : le
        # MCU rafraichit vers 25 Hz (a 50 Hz demandes, 82 % des messages repetent la valeur
        # precedente ; a 25 Hz, 12 % seulement). Mais la cadence elevee n'a pas ete validee
        # en conduite : le defaut reste donc a 10 Hz, comportement d'origine, et le
        # parametre permet de l'elever quand la saccade sera elucidee (REQ-DRV-014).
        self.declare_parameter('imu_rate_hz', 10.0)
        self.angular_limit = self.get_parameter('angular_limit').get_parameter_value().double_value
        print (self.angular_limit)

        #create subcriber
        # Groupe separe : une lecture de capteur dans pub_data ne doit plus retarder
        # l'arrivee d'une consigne ni le garde-fou de silence (REQ-DRV-015).
        self.groupe_commande = MutuallyExclusiveCallbackGroup()
        self._verrou_consigne = threading.Lock()
        self.sub_cmd_vel = self.create_subscription(Twist,"cmd_vel_safe",self.cmd_vel_callback,1, callback_group=self.groupe_commande)
        self.sub_RGBLight = self.create_subscription(Int32,"RGBLight",self.RGBLightcallback,100)
        self.sub_BUzzer = self.create_subscription(Bool,"Buzzer",self.Buzzercallback,100)
        self.sub_Servo = self.create_subscription(Int32MultiArray,"servo_ctrl",self.Servocallback,10)

        #create publisher
        self.EdiPublisher = self.create_publisher(Float32,"edition",100)
        self.volPublisher = self.create_publisher(Float32,"voltage",100)
        # Pas d'editeur /joint_states ici (P13, REQ-ARM-001) : il etait declare mais
        # jamais publie, ce qui faisait croire a deux sources. La seule source est
        # joint_state_publisher (source_list /arm/joint_states, voir
        # launch/robot_description.launch.py).
        self.velPublisher = self.create_publisher(Twist,"vel_raw",50)
        self.imuPublisher = self.create_publisher(Imu,"imu/data_raw",100)
        self.magPublisher = self.create_publisher(MagneticField,"imu/mag",100)
        self.odomPublisher = self.create_publisher(Odometry,"odom_raw",20)

        #create timer
        self.timer = self.create_timer(self._periode(), self.pub_data)
        self.add_on_set_parameters_callback(self._sur_parametre)

        #create and init variable
        self.edition = Float32()
        self.edition.data = 1.0
        self.car.create_receive_threading()
        # Enable UART Servo Torque (Required for Arm)
        self.car.set_uart_servo_torque(True)
        # Garde de silence a 20 Hz (REQ-DRV-002).
        self.timer_silence = self.create_timer(
            0.05, self._surveiller_silence, callback_group=self.groupe_commande)
    def _periode(self):
        try:
            cadence = float(self.get_parameter('imu_rate_hz').value)
        except (TypeError, ValueError):
            cadence = 10.0
        if not 1.0 <= cadence <= 200.0:
            cadence = 10.0
        return 1.0 / cadence

    def _sur_parametre(self, parametres):
        """Change la cadence a chaud : detruit et recree le timer."""
        from rcl_interfaces.msg import SetParametersResult
        resultat = SetParametersResult(successful=True)
        for parametre in parametres:
            if parametre.name != 'imu_rate_hz':
                continue
            try:
                cadence = float(parametre.value)
            except (TypeError, ValueError):
                resultat.successful = False
                resultat.reason = 'cadence non numerique'
                return resultat
            if not 1.0 <= cadence <= 200.0:
                resultat.successful = False
                resultat.reason = f'cadence {cadence} hors de [1, 200] Hz'
                return resultat
            self.destroy_timer(self.timer)
            self.timer = self.create_timer(1.0 / cadence, self.pub_data)
            self.get_logger().info(f'cadence de publication : {cadence} Hz')
        return resultat

    #callback function
    def cmd_vel_callback(self,msg):
        # 小车运动控制，订阅者回调函数
        # Car motion control, subscriber callback function
        if not isinstance(msg, Twist): return
        # 下发线速度和角速度
        # Issue linear vel and angular vel
        # ERR-009 : bande morte et butées appliquées avant le MCU
        # rampe : un echelon brutal fait winduper l'integrateur du MCU (pic 4,9x mesuré)
        with self._verrou_consigne:
            r = ramp_cmd(getattr(self, "_ramp", (0.0, 0.0, 0.0)),
                         (msg.linear.x, msg.linear.y, msg.angular.z), RAMP_STEP)
            self._ramp = r
        if r[0] != 0.0 and getattr(self, "_moving", False) is False:
            self._kick_start = _time.monotonic()
            self._moving = True
        elif r[0] == 0.0:
            self._moving = False
        r = (kick_boost(r[0], _time.monotonic() - getattr(self, "_kick_start", 0.0)), r[1], r[2])
        vx, vy, angular = scale_cmd_vel(*r)
        self._last_cmd_t = self.now_s()
        self._derniere_consigne_nulle = (vx == 0.0 and vy == 0.0 and angular == 0.0)
        self.car.set_car_motion(vx, vy, angular)
        '''print("cmd_vx: ",vx)
        print("cmd_vy: ",vy)
        print("cmd_angular: ",angular)'''
        #rospy.loginfo("nav_use_rot:{}".format(self.nav_use_rotvel))
        #print(self.nav_use_rotvel)
    def RGBLightcallback(self,msg):
        # 流水灯控制，服务端回调函数 RGBLight control
        if not isinstance(msg, Int32): return
        # print ("RGBLight: ", msg.data)
        for i in range(3): self.car.set_colorful_effect(msg.data, 6, parm=1)
    def Buzzercallback(self,msg):
        if not isinstance(msg, Bool): return
        if msg.data:
            for i in range(3): self.car.set_beep(1)
        else:
            for i in range(3): self.car.set_beep(0)

    def Servocallback(self, msg):
        # msg.data[0] = servo_id (1-6 for UART Arm)
        # msg.data[1] = angle
        if not isinstance(msg, Int32MultiArray): return
        if len(msg.data) >= 2:
            servo_id = msg.data[0]
            angle = msg.data[1]
            
            # X3 Plus Arm uses UART servos 1-6
            if 1 <= servo_id <= 6:
                self.car.set_uart_servo_angle(servo_id, angle)
            else:
                # Fallback for PWM servos if any (e.g. camera pan/tilt might be PWM on some models, 
                # but X3 Plus usually has the arm. If camera is on arm, it's UART).
                # Just in case, keep PWM for other IDs.
                self.car.set_pwm_servo(servo_id, angle)

    #pub data
    def pub_data(self):
        if not getattr(self, "_type_logged", False):
            # lu sur la carte, une fois la boucle stable
            self._type_logged = True
            try:
                self.get_logger().info(
                    f"carte : car_type={self.car.get_car_type_from_machine()} "
                    f"firmware={self.car.get_version()} pid={self.car.get_motion_pid()}")
            except Exception as exc:  # noqa: BLE001
                self.get_logger().warn(f"lecture carte impossible : {exc}")
        time_stamp = Clock().now()
        imu = Imu()
        twist = Twist()
        battery = Float32()
        edition = Float32()
        mag = MagneticField()
        # Le JointState construit ici n'etait publie par personne (P01-M13) : retire
        # avec l'editeur mort, pour qu'aucun code ne laisse croire a une seconde source.
        
        #print ("mag: ",self.car.get_magnetometer_data())		
        # get_version(), la tension et le magnetometre coutent chacun une transaction
        # serie : a 10 Hz ils occupaient le lien pour rien. La version est lue une
        # fois, les deux autres une fois par seconde (REQ-DRV-015).
        if not hasattr(self, '_edition_lue'):
            self._edition_lue = True
            self._version = self.car.get_version()*1.0
            self._tension = self.car.get_battery_voltage()*1.0
            self._mag = self.car.get_magnetometer_data()
            self._t_lente = self.now_s()
        elif self.now_s() - self._t_lente >= 1.0:
            self._tension = self.car.get_battery_voltage()*1.0
            self._mag = self.car.get_magnetometer_data()
            self._t_lente = self.now_s()
        edition.data = self._version
        battery.data = self._tension
        ax, ay, az = self.car.get_accelerometer_data()
        gx, gy, gz = self.car.get_gyroscope_data()
        mx, my, mz = self._mag
        mx = mx * 1.0
        my = my * 1.0
        mz = mz * 1.0
        vx, vy, angular = self.car.get_motion_data()
        '''print("vx: ",vx)
        print("vy: ",vy)
        print("angular: ",angular)'''
        # 发布陀螺仪的数据
        # Publish gyroscope data
        imu.header.stamp = time_stamp.to_msg()
        imu.header.frame_id = self.imu_link
        imu.linear_acceleration.x = ax*1.0
        imu.linear_acceleration.y = ay*1.0
        imu.linear_acceleration.z = az*1.0
        imu.angular_velocity.x = gx*1.0
        imu.angular_velocity.y = gy*1.0
        imu.angular_velocity.z = gz*1.0
        # Sans ces trois lignes, tout restait a zero : variance nulle = confiance
        # infinie pour l'EKF, et orientation declaree valide alors qu'elle est absente.
        imu.orientation_covariance = covariance_orientation()
        imu.angular_velocity_covariance = covariance_gyro()
        imu.linear_acceleration_covariance = covariance_accel()

        mag.header.stamp = time_stamp.to_msg()
        mag.header.frame_id = self.imu_link
        mag.magnetic_field.x = mx*1.0
        mag.magnetic_field.y = my*1.0
        mag.magnetic_field.z = mz*1.0
        
        # 将小车当前的线速度和角速度发布出去
        # Publish the current linear vel and angular vel of the car
        twist.linear.x = feedback(vx)
        twist.linear.y = feedback(vy)
        twist.angular.z = angular*1.0    
        self.velPublisher.publish(twist)
        # /odom_raw : Odometry pour robot_localization (Twist nu inutilisable par l'EKF)
        odom = Odometry()
        odom.header.stamp = time_stamp.to_msg()
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.twist.twist = twist
        # covariances : encodeurs mecanum, glissement réel non modélisé
        for i, var in enumerate([0.02, 0.02, 1e6, 1e6, 1e6, 0.05]):
            odom.twist.covariance[i * 7] = var
        # la pose n'est pas mesurée : variance énorme pour que l'EKF ne la fusionne pas
        for i in range(6):
            odom.pose.covariance[i * 7] = 1e6
        self.odomPublisher.publish(odom)
        # print("ax: %.5f, ay: %.5f, az: %.5f" % (ax, ay, az))
        # print("gx: %.5f, gy: %.5f, gz: %.5f" % (gx, gy, gz))
        # print("mx: %.5f, my: %.5f, mz: %.5f" % (mx, my, mz))
        # rospy.loginfo("battery: {}".format(battery))
        # rospy.loginfo("vx: {}, vy: {}, angular: {}".format(twist.linear.x, twist.linear.y, twist.angular.z))
        self.imuPublisher.publish(imu)
        self.magPublisher.publish(mag)
        # proprietary : une lecture de servo par tick (15-20 ms), cycle complet ~600 ms
        if not hasattr(self, "_rr"):
            self._rr = 0
            self._angles = [-1, -1, -1, -1, -1, -1]
            self._servo_pub = self.create_publisher(Int32MultiArray, "arm/servo_angles", 10)
        sid = (self._rr % 6) + 1
        self._rr += 1
        try:
            self._angles[sid - 1] = int(self.car.get_uart_servo_angle(sid))
        except Exception:
            self._angles[sid - 1] = -1
        _msg_angles = Int32MultiArray()
        _msg_angles.data = list(self._angles)
        self._servo_pub.publish(_msg_angles)
        self.volPublisher.publish(battery)
        self.EdiPublisher.publish(edition)

    def now_s(self):
        """Horloge du noeud, en secondes : simulable dans les tests (REQ-DRV-002)."""
        return self.get_clock().now().nanoseconds / 1e9

    def _surveiller_silence(self):
        """Arret des moteurs si aucune consigne non nulle n'arrive depuis cmd_timeout_s.

        Un seul zero par silence : sinon le MCU recevrait 20 trames nulles par seconde,
        ce qui masquerait la perte du flux au lieu de la signaler.
        """
        if self._last_cmd_t is None or self._derniere_consigne_nulle:
            return
        ecoule = self.now_s() - self._last_cmd_t
        if ecoule <= self.cmd_timeout_s:
            return
        try:
            self.car.set_car_motion(0.0, 0.0, 0.0)
        except Exception as exc:  # liaison serie perdue : on le dit, on ne masque pas
            self.get_logger().error(f"arret moteurs impossible : {exc}")
        self._ramp = (0.0, 0.0, 0.0)
        self._moving = False
        self._derniere_consigne_nulle = True
        self.get_logger().warn(f"consigne absente depuis {ecoule:.2f} s, arret")

    def destroy_node(self):
        """Rend le port : le verrou ne doit pas survivre au noeud."""
        verrou = getattr(self, "_verrou", None)
        if verrou is not None:
            try:
                verrou.relacher()
            except Exception:
                pass
            self._verrou = None
        return super().destroy_node()


def main():
    rclpy.init()
    driver = yahboomcar_driver('driver_node')
    # Executeur mono-thread conserve : les groupes de callbacks sont en place, mais
    # Rosmaster_Lib n'est pas documente thread-safe et la bibliotheque partage le meme port
    # serie pour les lectures et l'envoi des consignes. Deux fils pourraient entrelacer des
    # trames sur le chemin d'actionnement — risque non pris. Le gain vient de la reduction
    # du travail serie par tick, pas du parallelisme (REQ-DRV-015).
    try:
        rclpy.spin(driver)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        driver.destroy_node()
        rclpy.try_shutdown()
    return 0
