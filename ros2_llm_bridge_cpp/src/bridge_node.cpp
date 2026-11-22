// bridge_node.cpp — ROS2 node bridging tool calls to hardware service
// C++ equivalent of Python bridge_node.py

#include "ros2_llm_bridge_cpp/bridge_node.hpp"
#include <nlohmann/json.hpp>
#include <sstream>
#include <stdexcept>
#include <chrono>
#include <thread>
#include <cmath>
#include <algorithm>
#include <cstdlib>

using json = nlohmann::json;

namespace ros2_llm_bridge_cpp {

BridgeNode::BridgeNode() : rclcpp::Node("llm_bridge_node") {
    skills_ = rclcpp_action::create_client<ExecuteSkillAction>(this, "/clawbot/execute_skill");

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

std::string BridgeNode::envoyer_skill(const std::string& cid, const std::string& skill,
                                      const std::string& params_json) {
    log_cid(cid, "skill " + skill + " params=" + params_json);
    if (!skills_->wait_for_action_server(std::chrono::seconds(2))) {
        return "ERROR: executif injoignable (/clawbot/execute_skill) - robot non deplace.";
    }
    ExecuteSkillAction::Goal goal;
    goal.skill = skill;
    goal.params_json = params_json;
    goal.timeout_s = 0.0f;

    rclcpp_action::Client<ExecuteSkillAction>::SendGoalOptions options;
    options.result_callback = [this, cid](const GoalHandleSkill::WrappedResult& result) {
        const int issue = result.result ? static_cast<int>(result.result->outcome) : -1;
        RCLCPP_INFO(get_logger(), "[CID: %s] %s termine : outcome %d", cid.c_str(),
                    result.result ? result.result->error_code.c_str() : "?", issue);
    };
    skills_->async_send_goal(goal, options);
    return "Skill " + skill + " transmis a l'executif (" + params_json +
           "). Suivi : /clawbot/mission/events.";
}

std::string BridgeNode::execute_set_velocity(const std::string& cid,
                                             double linear_x, double linear_y,
                                             double angular_z, double duration) {
    log_cid(cid, "SetVelocity -> skill borne");
    // L'executif n'accepte pas de vitesse continue : la consigne devient une distance
    // ou un angle relatifs, bornes par le registre des skills (2 m, 2*pi rad).
    std::ostringstream params;
    if (std::abs(angular_z) >= std::abs(linear_x)) {
        params << "{\"angle_rad\": " << (angular_z * duration) << "}";
        return envoyer_skill(cid, "rotate", params.str());
    }
    const double dx = std::clamp(linear_x * duration, -2.0, 2.0);
    const double dy = std::clamp(linear_y * duration, -2.0, 2.0);
    params << "{\"dx_m\": " << dx << ", \"dy_m\": " << dy << "}";
    return envoyer_skill(cid, "move_relative", params.str());
}

std::string BridgeNode::execute_stop(const std::string& cid) {
    log_cid(cid, "Stop -> skill stop");
    return envoyer_skill(cid, "stop", "{}");
}

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
    log_cid(cid, "NavigateTo -> skill navigate_to");
    // Plus de navigation a l'estime : la cible part a l'executif, qui refuse tant que la
    // capacite `navigation` n'est pas servie (CAPABILITY_INACTIVE) au lieu de bouger.
    std::ostringstream params;
    params << "{\"x\": " << target_x << ", \"y\": " << target_y << "}";
    return envoyer_skill(cid, "navigate_to", params.str());
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