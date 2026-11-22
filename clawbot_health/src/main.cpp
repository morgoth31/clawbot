// Exécutable du moniteur de santé (unité clawbot-health-monitor).
#include <exception>
#include <memory>

#include <rclcpp/rclcpp.hpp>

#include "health_monitor.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<HealthMonitor>();
  try {
    rclcpp::spin(node);
  } catch (const std::exception &) {
    // arrêt demandé par SIGINT/SIGTERM : sortie propre
  }
  rclcpp::shutdown();
  return 0;
}
