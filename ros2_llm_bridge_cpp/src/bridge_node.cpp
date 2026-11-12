// bridge_node.cpp — ROS2 node bridging tool calls to hardware service
// C++ equivalent of Python bridge_node.py

#include "ros2_llm_bridge_cpp/bridge_node.hpp"
#include <nlohmann/json.hpp>
#include <sstream>
#include <stdexcept>
#include <chrono>
#include <thread>
#include <cmath>
#include <cstdlib>

using json = nlohmann::json;

namespace ros2_llm_bridge_cpp {

BridgeNode::BridgeNode() : rclcpp::Node("llm_bridge_node") {
    cmd_vel_pub_ = create_publisher<geometry_msgs::msg::Twist>("cmd_vel", 10);

    const std::string hw_url = std::getenv("HARDWARE_SERVICE_URL")
        ? std::getenv("HARDWARE_SERVICE_URL") : "http://localhost:8001";
    double hw_timeout = 10.0;
    if (const char* t = std::getenv("HARDWARE_SERVICE_TIMEOUT")) {
        hw_timeout = std::stod(t);
    }

    hw_ = std::make_unique<HttpClient>(hw_url, static_cast<long>(hw_timeout));
    RCLCPP_INFO(get_logger(), "BridgeNode initialised. Hardware service: %s", hw_url.c_str());

    // YOLO inference service
    const std::string yolo_url = std::getenv("YOLO_SERVICE_URL")
        ? std::getenv("YOLO_SERVICE_URL") : "http://localhost:8003";
    yolo_ = std::make_unique<HttpClient>(yolo_url, 15);
    RCLCPP_INFO(get_logger(), "YOLO service: %s", yolo_url.c_str());
}

BridgeNode::~BridgeNode() = default;

void BridgeNode::log_cid(const std::string& cid, const std::string& msg) {
    RCLCPP_INFO(get_logger(), "[CID: %s] %s", cid.c_str(), msg.c_str());
}

std::string BridgeNode::hw_get(const std::string& path, const std::string& params) {
    return hw_->get(path, params);
}

std::string BridgeNode::hw_post(const std::string& path, const std::string& body,
                                 const std::string& params) {
    return hw_->post(path, body, params);
}

// ── Motion ──────────────────────────────────────────────────────────────

std::string BridgeNode::execute_set_velocity(const std::string& cid,
                                             double linear_x, double linear_y,
                                             double angular_z, double duration) {
    std::ostringstream oss;
    oss << "SetVelocity: linear_x=" << linear_x << ", linear_y=" << linear_y
        << ", angular_z=" << angular_z << ", duration=" << duration << "s";
    log_cid(cid, oss.str());

    json body = {{"linear_x", linear_x}, {"linear_y", linear_y}, {"angular_z", angular_z}};
    try {
        std::string resp = hw_post("/motion", body.dump());
        json data = json::parse(resp);
        bool clamped = data.value("clamped", false);
        std::string note = clamped ? " [speed was clamped to safe limit]" : "";

        // Schedule auto-stop after duration
        if (duration > 0) {
            // We use a detached thread to avoid blocking the API response
            std::thread([this, cid, duration]() {
                std::this_thread::sleep_for(
                    std::chrono::duration<double>(duration));
                execute_stop(cid + "-autostop");
            }).detach();
        }

        return "Velocity set: vx=" + std::to_string(data["linear_x"].get<double>()) +
               ", vy=" + std::to_string(data["linear_y"].get<double>()) +
               ", wz=" + std::to_string(data["angular_z"].get<double>()) +
               " for " + std::to_string(duration) + "s (auto-stop)." + note;
    } catch (const std::exception& e) {
        return std::string("ERROR: hardware service unreachable — ") + e.what() + ". Robot not moved.";
    }
}

std::string BridgeNode::execute_stop(const std::string& cid) {
    log_cid(cid, "Stop: zeroing all velocities");
    try {
        std::string resp = hw_post("/motion/stop");
        json data = json::parse(resp);
        return "Stop command sent. status=" + data.value("status", std::string("unknown"));
    } catch (const std::exception& e) {
        // Fallback: publish empty Twist to /cmd_vel
        cmd_vel_pub_->publish(geometry_msgs::msg::Twist());
        return "Stop sent to /cmd_vel (hardware service unreachable).";
    }
}

// ── Audio / Navigation (stubs) ──────────────────────────────────────────

std::string BridgeNode::execute_speak(const std::string& cid, const std::string& text) {
    log_cid(cid, "Speak: '" + text + "'");
    // Use espeak-ng for text-to-speech
    std::string cmd = "espeak-ng \"" + text + "\" 2>/dev/null";
    int rc = std::system(cmd.c_str());
    if (rc == 0) {
        return "Speak: \"" + text + "\" (TTS via espeak-ng)";
    } else {
        return "Speak acknowledged: \"" + text + "\" (TTS failed, espeak-ng error)";
    }
}

std::string BridgeNode::execute_navigate_to(const std::string& cid,
                                            double target_x, double target_y) {
    std::ostringstream oss;
    oss << "NavigateTo: (" << target_x << ", " << target_y << ")";
    log_cid(cid, oss.str());

    // Try Nav2 action client first. If Nav2 is not running, fall back to
    // simple dead-reckoning (calculate distance + heading, move, rotate).
    // For now, we implement dead-reckoning since Nav2 requires an active map + AMCL.

    // Simple dead-reckoning navigation:
    // 1. Calculate distance to target
    // 2. Move forward at max speed for calculated duration
    // 3. Stop
    // Note: This is inaccurate without odometry but provides basic functionality.

    double distance = std::sqrt(target_x * target_x + target_y * target_y);
    double angle = std::atan2(target_y, target_x);  // radians

    // Clamp to safe limits
    double max_speed = 0.05;  // m/s (slightly under 0.06 limit)
    double max_angular = 0.2;  // rad/s

    // Calculate durations
    double move_duration = (distance > 0.01) ? (distance / max_speed) : 0.0;
    double rotate_duration = (std::abs(angle) > 0.05) ? (std::abs(angle) / max_angular) : 0.0;

    // Clamp durations to safe limits
    move_duration = std::min(move_duration, 10.0);   // max 10s move
    rotate_duration = std::min(rotate_duration, 5.0); // max 5s rotate

    json result;
    result["status"] = "dead_reckoning";
    result["target_x"] = target_x;
    result["target_y"] = target_y;
    result["distance_m"] = round(distance * 1000) / 1000;
    result["angle_rad"] = round(angle * 1000) / 1000;
    result["move_duration_s"] = round(move_duration * 100) / 100;
    result["rotate_duration_s"] = round(rotate_duration * 100) / 100;

    // Step 1: Rotate to face the target
    if (rotate_duration > 0.01) {
        double angular_z = (angle > 0) ? max_angular : -max_angular;
        log_cid(cid, "NavigateTo: rotating " + std::to_string(rotate_duration) + "s");
        execute_set_velocity(cid, 0.0, 0.0, angular_z, rotate_duration);
        // Wait for rotation to complete
        std::this_thread::sleep_for(std::chrono::duration<double>(rotate_duration + 0.2));
    }

    // Step 2: Move forward
    if (move_duration > 0.01) {
        log_cid(cid, "NavigateTo: moving forward " + std::to_string(move_duration) + "s");
        execute_set_velocity(cid, max_speed, 0.0, 0.0, move_duration);
        // Wait for movement to complete
        std::this_thread::sleep_for(std::chrono::duration<double>(move_duration + 0.2));
    }

    // Step 3: Stop
    execute_stop(cid);

    result["message"] = "Dead-reckoning navigation completed. For accurate navigation, "
                         "activate Nav2 with a SLAM map.";
    return result.dump();
}

std::string BridgeNode::execute_listen(const std::string& cid) {
    log_cid(cid, "Listen: recording 3 seconds...");
    // Record 3 seconds of audio via arecord with timeout
    std::string wav_path = "/tmp/clawbot_listen.wav";
    std::string cmd = "timeout 5 arecord -d 3 -f cd -r 16000 -c 1 \"" + wav_path + "\" 2>/dev/null";
    int rc = std::system(cmd.c_str());
    if (rc != 0) {
        json err = {{"status", "error"}, {"message", "Audio recording failed (arecord error or no microphone)."}};
        return err.dump();
    }
    // STT not yet available (whisper not installed)
    // Return the recorded file path for manual transcription
    json result;
    result["status"] = "recorded";
    result["message"] = "Audio recorded to " + wav_path + ". STT not available yet (install whisper).";
    result["audio_path"] = wav_path;
    result["duration_s"] = 3;
    return result.dump();
}

// ── Vision ──────────────────────────────────────────────────────────────

std::string BridgeNode::execute_capture_camera(const std::string& cid,
                                               const std::string& camera) {
    log_cid(cid, "CaptureCamera: " + camera);
    try {
        std::string resp = hw_get("/capture", "camera=" + camera + "&save=true");
        json data = json::parse(resp);
        log_cid(cid, "CaptureCamera done: saved_path=" + data.value("saved_path", ""));
        json result = {
            {"camera", data.value("camera", camera)},
            {"saved_path", data.value("saved_path", "")},
            {"image_base64", data.value("image_base64", "")},
            {"format", "jpeg"}
        };
        return result.dump();
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_analyze_scene(const std::string& cid) {
    log_cid(cid, "AnalyzeScene -> CaptureCamera(front)");
    try {
        std::string resp = hw_get("/capture", "camera=front&save=true");
        json data = json::parse(resp);
        json result = {
            {"instruction", "Scene captured. Use the image tool with the saved_path to analyse "
                            "what is in the scene and describe the environment."},
            {"saved_path", data.value("saved_path", "")},
            {"image_base64", data.value("image_base64", "")},
            {"format", "jpeg"}
        };
        return result.dump();
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_recognize_face(const std::string& cid) {
    log_cid(cid, "RecognizeFace -> CaptureCamera(front)");
    try {
        std::string resp = hw_get("/capture", "camera=front&save=true");
        json data = json::parse(resp);
        json result = {
            {"instruction", "Use the image tool on saved_path to identify any faces."},
            {"saved_path", data.value("saved_path", "")},
            {"image_base64", data.value("image_base64", "")}
        };
        return result.dump();
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_recognize_object(const std::string& cid) {
    log_cid(cid, "RecognizeObject -> CaptureCamera(front)");
    try {
        std::string resp = hw_get("/capture", "camera=front&save=true");
        json data = json::parse(resp);
        json result = {
            {"instruction", "Use the image tool on saved_path to detect and list all objects."},
            {"saved_path", data.value("saved_path", "")},
            {"image_base64", data.value("image_base64", "")}
        };
        return result.dump();
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_recognize_qrcode(const std::string& cid) {
    log_cid(cid, "RecognizeQRCode -> CaptureCamera(front)");
    try {
        std::string resp = hw_get("/capture", "camera=front&save=true");
        json data = json::parse(resp);
        json result = {
            {"instruction", "Use the image tool on saved_path to decode any QR codes."},
            {"saved_path", data.value("saved_path", "")},
            {"image_base64", data.value("image_base64", "")}
        };
        return result.dump();
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

// ── Arm & Claw ──────────────────────────────────────────────────────────

std::string BridgeNode::execute_control_servo(const std::string& cid,
                                              int servo_id, double angle) {
    std::ostringstream oss;
    oss << "ControlServo: id=" << servo_id << ", angle=" << angle << "deg";
    log_cid(cid, oss.str());
    try {
        json body = {{"servo_id", servo_id}, {"angle", angle}};
        std::string resp = hw_post("/servo", body.dump());
        json data = json::parse(resp);
        return "Servo " + std::to_string(servo_id) + " -> " +
               std::to_string(angle) + "deg. status=" + data.value("status", std::string("ok"));
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_control_arm(const std::string& cid,
                                            const std::vector<double>& joints) {
    std::ostringstream oss;
    oss << "ControlArm: joints=[";
    for (size_t i = 0; i < joints.size(); ++i) {
        if (i > 0) oss << ", ";
        oss << joints[i];
    }
    oss << "]";
    log_cid(cid, oss.str());
    try {
        json jarr = json::array();
        for (auto j : joints) jarr.push_back(j);
        json body = {{"joints", jarr}};
        std::string resp = hw_post("/arm", body.dump());
        json data = json::parse(resp);
        return "Arm moved to joints (deg): [" + std::to_string(joints[0]) +
               ", " + std::to_string(joints[1]) + ", " + std::to_string(joints[2]) +
               ", " + std::to_string(joints[3]) + ", " + std::to_string(joints[4]) +
               "]. status=" + data.value("status", std::string("ok"));
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_control_claw(const std::string& cid,
                                             const std::string& state) {
    log_cid(cid, "ControlClaw: " + state);
    try {
        json body = {{"state", state}};
        std::string resp = hw_post("/claw", body.dump());
        json data = json::parse(resp);
        return "Claw is now " + state + " (angle=" +
               std::to_string(data.value("angle", 0)) + "deg).";
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_set_arm_pose(const std::string& cid, int pose_id) {
    log_cid(cid, "SetArmPose: pose_id=" + std::to_string(pose_id));
    try {
        std::string resp = hw_post("/arm/pose/" + std::to_string(pose_id));
        json data = json::parse(resp);
        return "Arm pose set to '" + data.value("pose_name", std::string("")) +
               "' (angles: " + data.value("angles", json::array()).dump() +
               "). status=" + data.value("status", std::string("ok"));
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

// ── Peripherals ──────────────────────────────────────────────────────────

std::string BridgeNode::execute_beep(const std::string& cid, int delay_ms) {
    log_cid(cid, "Beep: " + std::to_string(delay_ms) + " ms");
    try {
        std::string resp = hw_post("/beep", "", "delay_ms=" + std::to_string(delay_ms));
        json data = json::parse(resp);
        return "Buzzer sounded for " + std::to_string(delay_ms) +
               " ms. status=" + data.value("status", std::string("ok"));
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_set_lamps(const std::string& cid,
                                          int r, int g, int b) {
    std::ostringstream oss;
    oss << "SetLamps: r=" << r << ", g=" << g << ", b=" << b;
    log_cid(cid, oss.str());
    try {
        json body = {{"r", r}, {"g", g}, {"b", b}};
        std::string resp = hw_post("/lamps", body.dump());
        json data = json::parse(resp);
        return "LEDs set to RGB(" + std::to_string(r) + ", " +
               std::to_string(g) + ", " + std::to_string(b) +
               "). status=" + data.value("status", std::string("ok"));
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

std::string BridgeNode::execute_get_battery_voltage(const std::string& cid) {
    log_cid(cid, "GetBatteryVoltage");
    try {
        std::string resp = hw_get("/battery");
        return resp; // already JSON
    } catch (const std::exception& e) {
        return std::string("ERROR: ") + e.what();
    }
}

// ── Vision Detection (via YOLO service) ──────────────────────────────────

std::string BridgeNode::execute_detect_objects(const std::string& cid,
                                               const std::string& camera) {
    std::ostringstream oss;
    oss << "DetectObjects: camera=" << camera;
    log_cid(cid, oss.str());
    try {
        std::string resp = yolo_->get("/detect_raw", "camera=" + camera);
        json data = json::parse(resp);
        int count = data.value("detection_count", 0);
        int ms = data.value("inference_ms", 0);
        auto dets = data.value("detections", json::array());

        std::ostringstream result;
        result << "{\"camera\":\"" << camera << "\","
               << "\"detection_count\":" << count << ","
               << "\"inference_ms\":" << ms << ","
               << "\"detections\":";
        if (count > 0) {
            // Include detection details
            result << dets.dump();
        } else {
            result << "[]";
        }
        result << "}";
        return result.str();
    } catch (const std::exception& e) {
        return std::string("ERROR: YOLO service unreachable — ") + e.what();
    }
}

} // namespace ros2_llm_bridge_cpp