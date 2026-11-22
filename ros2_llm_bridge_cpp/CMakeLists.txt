cmake_minimum_required(VERSION 3.8)
project(ros2_llm_bridge_cpp)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 20)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

# ── Dependencies ──────────────────────────────────────────────────────────────

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(clawbot_interfaces REQUIRED)
find_package(Threads REQUIRED)

# nlohmann/json (header-only, system-installed)
find_path(NLOHMANN_JSON_INCLUDE_DIR nlohmann/json.hpp
  PATHS /usr/include
  REQUIRED)

# libcurl
find_package(CURL REQUIRED)

# ── Library: tool schemas ───────────────────────────────────────────────────

add_library(${PROJECT_NAME}_schemas STATIC src/tool_schemas.cpp)
target_include_directories(${PROJECT_NAME}_schemas PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${NLOHMANN_JSON_INCLUDE_DIR}
)

# ── Library: HTTP client (libcurl) ─────────────────────────────────────────

add_library(${PROJECT_NAME}_http STATIC src/http_client.cpp)
target_include_directories(${PROJECT_NAME}_http PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(${PROJECT_NAME}_http ${CURL_LIBRARIES})

# ── Library: bridge node (ROS2 + tool execution) ────────────────────────────

add_library(${PROJECT_NAME}_node STATIC
  src/bridge_node.cpp
  src/action_handler.cpp
  src/mode_manager.cpp
)
target_include_directories(${PROJECT_NAME}_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${NLOHMANN_JSON_INCLUDE_DIR}
)
ament_target_dependencies(${PROJECT_NAME}_node
  rclcpp rclcpp_action clawbot_interfaces geometry_msgs std_msgs sensor_msgs nav_msgs
)
target_link_libraries(${PROJECT_NAME}_node
  ${PROJECT_NAME}_schemas
  ${PROJECT_NAME}_http
  Threads::Threads
)

# ── Executable: API server ──────────────────────────────────────────────────

add_executable(api_server src/api_server.cpp)
target_include_directories(api_server PRIVATE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  ${NLOHMANN_JSON_INCLUDE_DIR}
)
ament_target_dependencies(api_server
  rclcpp geometry_msgs std_msgs
)
target_link_libraries(api_server
  ${PROJECT_NAME}_node
  ${PROJECT_NAME}_schemas
  ${PROJECT_NAME}_http
  Threads::Threads
)

# ── Install ──────────────────────────────────────────────────────────────────

install(TARGETS api_server
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

ament_package()