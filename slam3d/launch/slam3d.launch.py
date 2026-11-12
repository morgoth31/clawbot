"""Cartographie 3D de la piece : odometrie ICP + RTAB-Map, en lecture seule.

Ne publie aucune commande de mouvement. Le robot n'est que capteur + source de nuage.
Tout est place dans le namespace /slam3d pour ne pas se melanger aux topics du robot
(/map, /odom, /cloud_map ne sont donc pas touches).

  ros2 launch slam3d.launch.py                 # carte 3D, base conservee
Pour repartir d'une base vide, le script slam3d.sh --fresh supprime le fichier avant
de lancer (RTAB-Map refuse de repartir sur une base d'une autre version).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    ns = LaunchConfiguration('ns')
    cloud = LaunchConfiguration('cloud')
    db = LaunchConfiguration('db')

    # Pas de noeud de limitation de debit : topic_tools/throttle s'abonne en RELIABLE
    # alors que le pilote Astra publie le nuage en BEST_EFFORT, donc aucune donnee ne
    # passe. On baisse la charge autrement : voxel plus gros (0.10) cote ICP.
    icp = Node(
        package='rtabmap_odom',
        executable='icp_odometry',
        name='icp_odometry',
        namespace=ns,
        output='screen',
        parameters=[{
            'frame_id': 'base_footprint',
            'odom_frame_id': 'odom',
            'publish_tf': True,
            'wait_for_transform': 0.3,
            # RTAB-Map declare ces parametres en chaine de caracteres : les passer en
            # float fait lever InvalidParameterTypeException au demarrage du noeud.
            # frame-to-frame : le robot est plat et lent, pas besoin de fenetre glissante
            'Odom/Strategy': '0',
            'Odom/ResetCountdown': '1',
            # recalage geometrique : insensible a l'absence de texture des murs
            'Icp/PointToPlane': 'true',
            'Icp/Iterations': '10',
            'Icp/VoxelSize': '0.10',
            'Icp/MaxCorrespondenceDistance': '0.1',
            'Icp/Epsilon': '0.001',
            'Icp/CorrespondenceRatio': '0.2',
            'Odom/ScanKeyFrameThr': '0.6',
            'OdomF2M/MaxSize': '3000',
        }],
        remappings=[('scan_cloud', cloud)],
    )

    slam = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        namespace=ns,
        output='screen',
        parameters=[{
            'frame_id': 'base_footprint',
            'database_path': db,
            'subscribe_scan_cloud': True,
            'subscribe_depth': False,
            'subscribe_rgb': False,
            'approx_sync': True,
            'queue_size': 20,
            # geometrie seule : pas de RGB, donc pas de mots visuels
            'Reg/Strategy': '1',
            'Reg/Force3DoF': 'true',
            'Icp/VoxelSize': '0.05',
            'Icp/MaxCorrespondenceDistance': '0.15',
            'RGBD/ProximityBySpace': 'true',
            # 0.05 m creait un noeud par seconde robot immobile (87 Mo de base en
            # une minute) : 15 cm / 15 degres ne gardent que les vraies avancees
            'RGBD/AngularUpdate': '0.15',
            'RGBD/LinearUpdate': '0.15',
            # grille 2D pour reutiliser la navigation existante
            'Grid/RayTracing': 'true',
            'Grid/CellSize': '0.05',
            'Grid/RangeMax': '6.0',
            # budget Jetson Orin NX : on garde la carte legere
            'Kp/MaxFeatures': '400',
            'Vis/MaxFeatures': '600',
            'Rtabmap/DetectionRate': '1.0',
            'Rtabmap/TimeThr': '700',
            'Mem/RehearsalSimilarity': '0.45',
            'Mem/ReduceGraph': 'true',
        }],
        remappings=[('scan_cloud', cloud)],
    )

    return LaunchDescription([
        DeclareLaunchArgument('ns', default_value='slam3d'),
        DeclareLaunchArgument('cloud', default_value='/camera/depth/points',
                             description='nuage de points utilise comme source'),
        DeclareLaunchArgument('db', default_value='/home/jetson/.ros/rtabmap_slam3d.db'),
        icp,
        slam,
    ])
