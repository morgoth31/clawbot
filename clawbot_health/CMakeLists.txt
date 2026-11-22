cmake_minimum_required(VERSION 3.8)
project(clawbot_health)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(clawbot_interfaces REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(ament_cmake_gtest REQUIRED)

add_executable(health_monitor src/main.cpp)
target_include_directories(health_monitor PRIVATE src)
ament_target_dependencies(health_monitor rclcpp ament_index_cpp clawbot_interfaces diagnostic_msgs std_msgs)
target_link_libraries(health_monitor yaml-cpp nlohmann_json::nlohmann_json)

install(TARGETS health_monitor DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config DESTINATION share/${PROJECT_NAME})
install(FILES package.xml DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  # logique pure, sans ROS : estimateur et niveau
  ament_add_gtest(test_estimateur test/test_estimateur.cpp)
  target_include_directories(test_estimateur PRIVATE src)

  ament_add_gtest(test_niveau test/test_niveau.cpp)
  target_include_directories(test_niveau PRIVATE src)

  # abonnements du nœud réel : manifeste fourni par le dépôt, pas par install/
  ament_add_gtest(test_abonnements test/test_abonnements.cpp)
  target_include_directories(test_abonnements PRIVATE src)
  target_compile_definitions(test_abonnements PRIVATE RACINE_SOURCE="${CMAKE_CURRENT_SOURCE_DIR}")
  ament_target_dependencies(test_abonnements rclcpp ament_index_cpp clawbot_interfaces diagnostic_msgs std_msgs)
  target_link_libraries(test_abonnements yaml-cpp nlohmann_json::nlohmann_json)
endif()

ament_package()
