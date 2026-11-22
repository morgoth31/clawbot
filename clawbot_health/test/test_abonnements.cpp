// Abonnements du nœud réel : un seul par topic, génériques, avec le type réel
// (REQ-HEALTH-004). Ce test attrape les deux défauts constatés en production :
// double abonnement sur /voltage, et type générique sur un topic typé.
#include <gtest/gtest.h>

#include <algorithm>
#include <memory>
#include <string>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include "health_monitor.hpp"

namespace
{
const std::string RACINE(RACINE_SOURCE);

std::shared_ptr<HealthMonitor> construit(const std::string & manifeste,
  std::vector<std::string> capacites)
{
  rclcpp::NodeOptions options;
  options.parameter_overrides({
    rclcpp::Parameter("flows_file", manifeste),
    rclcpp::Parameter("assume_active_capabilities", capacites),
  });
  return std::make_shared<HealthMonitor>(options);
}
}  // namespace

// REQ-HEALTH-004
TEST(Abonnements, chaque_flux_brut_en_best_effort)
{
  const auto manifeste = RACINE + "/test/manifeste_test.yaml";
  auto node = construit(manifeste, {"base"});

  const auto & vus = node->abonnements();
  ASSERT_EQ(vus.size(), 1U);
  EXPECT_EQ(vus[0].topic, "/test_flux");
  EXPECT_TRUE(vus[0].brut);
  EXPECT_EQ(vus[0].type, "std_msgs/msg/String");
  EXPECT_EQ(node->flux().size(), 1U);
}

// REQ-HEALTH-004
TEST(Abonnements, manifeste_reel_un_seul_abonnement_par_topic)
{
  const auto manifeste = RACINE + "/config/expected_flows.yaml";
  auto node = construit(manifeste, {"base", "lidar", "depth_vision"});

  std::vector<std::string> topics;
  for (const auto & a : node->abonnements()) {
    topics.push_back(a.topic);
  }
  auto tries = topics;
  std::sort(tries.begin(), tries.end());
  EXPECT_EQ(std::unique(tries.begin(), tries.end()), tries.end()) << "topic abonné deux fois";

  for (const auto & a : node->abonnements()) {
    if (a.topic == "/voltage") {
      EXPECT_FALSE(a.brut) << "/voltage porte une valeur lue dans RobotHealth";
      EXPECT_EQ(a.type, "std_msgs/msg/Float32");
    } else {
      EXPECT_TRUE(a.brut) << a.topic;
    }
  }
}

// REQ-HEALTH-004
TEST(Abonnements, type_reel_par_flux)
{
  const auto manifeste = RACINE + "/config/expected_flows.yaml";
  auto node = construit(manifeste, {"base", "lidar", "depth_vision"});

  const std::vector<std::pair<std::string, std::string>> attendus{
    {"/scan", "sensor_msgs/msg/LaserScan"},
    {"/odom", "nav_msgs/msg/Odometry"},
    {"/cmd_vel_safe", "geometry_msgs/msg/Twist"},
    {"/imu/data_raw", "sensor_msgs/msg/Imu"},
    {"/camera/depth/image_raw", "sensor_msgs/msg/Image"},
  };
  for (const auto & [topic, type] : attendus) {
    auto it = std::find_if(node->abonnements().begin(), node->abonnements().end(),
        [&topic](const AbonnementVu & a) {return a.topic == topic;});
    ASSERT_NE(it, node->abonnements().end()) << topic;
    EXPECT_EQ(it->type, type) << topic;
  }
}

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  testing::InitGoogleTest(&argc, argv);
  const int resultat = RUN_ALL_TESTS();
  rclcpp::shutdown();
  return resultat;
}
