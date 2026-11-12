#pragma once

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include "ros2_llm_bridge_cpp/http_client.hpp"

namespace ros2_llm_bridge_cpp {

/// ROS 2 Node that bridges LLM tool calls to ROS 2 topics and the hardware service.
/// This is the C++ equivalent of the Python BridgeNode.
class BridgeNode : public rclcpp::Node {
public:
    BridgeNode();
    ~BridgeNode() override;

    // ── Motion ──────────────────────────────────────────────────────────────
    std::string execute_set_velocity(const std::string& cid,
                                     double linear_x, double linear_y,
                                     double angular_z, double duration = 1.0);
    std::string execute_stop(const std::string& cid);

    // ── Audio / Navigation (stubs) ──────────────────────────────────────────
    std::string execute_speak(const std::string& cid, const std::string& text);
    std::string execute_navigate_to(const std::string& cid,
                                    double target_x, double target_y);
    std::string execute_listen(const std::string& cid);

    // ── Vision (via hardware service) ───────────────────────────────────────
    std::string execute_capture_camera(const std::string& cid,
                                       const std::string& camera);
    std::string execute_analyze_scene(const std::string& cid);
    std::string execute_recognize_face(const std::string& cid);
    std::string execute_recognize_object(const std::string& cid);
    std::string execute_recognize_qrcode(const std::string& cid);

    // ── Arm & Claw (via hardware service) ────────────────────────────────────
    std::string execute_control_servo(const std::string& cid,
                                      int servo_id, double angle);
    std::string execute_control_arm(const std::string& cid,
                                    const std::vector<double>& joints);
    std::string execute_control_claw(const std::string& cid,
                                     const std::string& state);
    std::string execute_set_arm_pose(const std::string& cid, int pose_id);

    // ── Peripherals (via hardware service) ─────────────────────────────────
    std::string execute_beep(const std::string& cid, int delay_ms);
    std::string execute_set_lamps(const std::string& cid,
                                  int r, int g, int b);
    std::string execute_get_battery_voltage(const std::string& cid);

    // ── Vision Detection (via YOLO service, port 8003) ──────────────────────
    std::string execute_detect_objects(const std::string& cid,
                                       const std::string& camera);

private:
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_pub_;
    std::unique_ptr<HttpClient> hw_;
    std::unique_ptr<HttpClient> yolo_;

    void log_cid(const std::string& cid, const std::string& msg);
    std::string hw_get(const std::string& path, const std::string& params = "");
    std::string hw_post(const std::string& path, const std::string& body = "",
                        const std::string& params = "");
};

} // namespace ros2_llm_bridge_cpp