cmake_minimum_required(VERSION 3.16)
project(clawbot_moveit_config)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME})

install(PROGRAMS tools/apply_mast.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME apply_mast)

ament_package()
