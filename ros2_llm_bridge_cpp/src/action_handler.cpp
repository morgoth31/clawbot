// action_handler.cpp — Tool dispatch with validation
// C++ equivalent of Python action_handler.py

#include "ros2_llm_bridge_cpp/action_handler.hpp"
#include "ros2_llm_bridge_cpp/bridge_node.hpp"
#include <nlohmann/json.hpp>
#include <sstream>
#include <random>
#include <iomanip>
#include <stdexcept>
#include <chrono>

using json = nlohmann::json;

namespace ros2_llm_bridge_cpp {

ActionHandler::ActionHandler(BridgeNode& node) : node_(node) {}

std::string ActionHandler::generate_cid() {
    // Simple UUID v4-like generation
    static std::random_device rd;
    static std::mt19937 gen(rd());
    static std::uniform_int_distribution<uint32_t> dist(0, 0xFFFFFFFF);

    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    oss << std::setw(8) << dist(gen) << "-";
    oss << std::setw(4) << (dist(gen) & 0xFFFF) << "-";
    oss << "4" << std::setw(3) << (dist(gen) & 0xFFF) << "-";
    oss << std::setw(4) << (dist(gen) & 0xFFFF) << "-";
    oss << std::setw(8) << dist(gen);
    oss << std::setw(4) << (dist(gen) & 0xFFFF);
    return oss.str();
}

std::string ActionHandler::execute_tool(const std::string& func_name,
                                         const std::string& args_json) {
    // Validate
    std::string err = registry_.validate_args(func_name, args_json);
    if (!err.empty()) {
        throw std::invalid_argument(err);
    }

    // Generate correlation ID
    std::string cid = generate_cid();

    // Parse args for dispatch
    json args = json::parse(args_json.empty() ? "{}" : args_json);

    // Dispatch
    return dispatch(cid, func_name, args);
}

std::string ActionHandler::dispatch(const std::string& cid,
                                     const std::string& func_name,
                                     const json& args) {
    if (func_name == "SetVelocity") {
        return node_.execute_set_velocity(cid,
            args.value("linear_x", 0.0),
            args.value("linear_y", 0.0),
            args.value("angular_z", 0.0),
            args.value("duration", 1.0));
    }
    if (func_name == "Stop") {
        return node_.execute_stop(cid);
    }
    if (func_name == "Speak") {
        return node_.execute_speak(cid, args.value("text", ""));
    }
    if (func_name == "NavigateTo") {
        return node_.execute_navigate_to(cid,
            args.value("target_x", 0.0),
            args.value("target_y", 0.0));
    }
    if (func_name == "CaptureCamera") {
        return node_.execute_capture_camera(cid, args.value("camera", "front"));
    }
    if (func_name == "AnalyzeScene") {
        return node_.execute_analyze_scene(cid);
    }
    if (func_name == "RecognizeFace") {
        return node_.execute_recognize_face(cid);
    }
    if (func_name == "RecognizeObject") {
        return node_.execute_recognize_object(cid);
    }
    if (func_name == "RecognizeQRCode") {
        return node_.execute_recognize_qrcode(cid);
    }
    if (func_name == "Listen") {
        return node_.execute_listen(cid);
    }
    if (func_name == "ControlServo") {
        return node_.execute_control_servo(cid,
            args.value("servo_id", 0),
            args.value("angle", 0.0));
    }
    if (func_name == "ControlArm") {
        std::vector<double> joints;
        if (args.contains("joints_array") && args["joints_array"].is_array()) {
            for (const auto& j : args["joints_array"]) {
                joints.push_back(j.get<double>());
            }
        }
        return node_.execute_control_arm(cid, joints);
    }
    if (func_name == "ControlClaw") {
        return node_.execute_control_claw(cid, args.value("state", "open"));
    }
    if (func_name == "SetArmPose") {
        return node_.execute_set_arm_pose(cid, args.value("pose_id", 1));
    }
    if (func_name == "Beep") {
        return node_.execute_beep(cid, args.value("delay_ms", 200));
    }
    if (func_name == "SetLamps") {
        return node_.execute_set_lamps(cid,
            args.value("r", 0),
            args.value("g", 0),
            args.value("b", 0));
    }
    if (func_name == "GetBatteryVoltage") {
        return node_.execute_get_battery_voltage(cid);
    }
    if (func_name == "DetectObjects") {
        return node_.execute_detect_objects(cid, args.value("camera", "front"));
    }

    throw std::invalid_argument("Unknown tool '" + func_name + "'. Available: " +
                                registry_.get_tool_names());
}

} // namespace ros2_llm_bridge_cpp