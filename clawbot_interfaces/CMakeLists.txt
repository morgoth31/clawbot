cmake_minimum_required(VERSION 3.8)
project(clawbot_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)

# Une seule requête/réponse JSON : le contrat du directeur évolue sans regénérer d'interface.
# RobotHealth (P05) est la seule interface typée : elle est lue par l'exécutif et l'humain.
rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/DirectorCommand.srv"
  "msg/RobotHealth.msg"
  DEPENDENCIES builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime builtin_interfaces)
ament_package()
