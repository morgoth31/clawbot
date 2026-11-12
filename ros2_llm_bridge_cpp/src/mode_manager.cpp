// mode_manager.cpp — Mode management for the Clawbot
// Implements 4 modes: STANDBY, NAVIGATION, MANIPULATION, EVOLUTION
// Each mode restricts which tools are available and manages transitions.

#include "ros2_llm_bridge_cpp/mode_manager.hpp"
#include <nlohmann/json.hpp>
#include <sstream>

using json = nlohmann::json;

namespace ros2_llm_bridge_cpp {

ModeManager::ModeManager() {
    // ── STANDBY: attente, tools minimum ──────────────────────────────
    mode_tools_[RobotMode::STANDBY] = {
        "Stop", "GetBatteryVoltage", "Beep", "SetLamps",
        "SetVelocity", "Speak", "Listen", "SetArmPose"
    };

    // ── NAVIGATION: deplacement + cartographie ──────────────────────
    mode_tools_[RobotMode::NAVIGATION] = {
        "SetVelocity", "Stop", "NavigateTo",
        "CaptureCamera", "AnalyzeScene", "RecognizeObject", "RecognizeQRCode",
        "DetectObjects",
        "GetBatteryVoltage", "Beep", "SetLamps",
        "SetArmPose",  // pose 1 only (anti-collision)
        "Speak", "Listen"
    };

    // ── MANIPULATION: bras + pince + perception ──────────────────────
    mode_tools_[RobotMode::MANIPULATION] = {
        "Stop",  // stop = return to anti-collision pose
        "CaptureCamera", "AnalyzeScene", "RecognizeObject",
        "RecognizeFace", "RecognizeQRCode",
        "DetectObjects",
        "ControlServo", "ControlArm", "ControlClaw", "SetArmPose",
        "Beep", "SetLamps", "GetBatteryVoltage",
        "Speak", "Listen"
    };

    // ── EVOLUTION: dev only, robot immobile ──────────────────────────
    mode_tools_[RobotMode::EVOLUTION] = {
        "Stop", "GetBatteryVoltage", "Beep", "SetLamps",
        "CaptureCamera"  // for visual verification if needed
    };
}

bool ModeManager::is_tool_available(const std::string& tool_name) const {
    auto mode = mode_.load();
    auto it = mode_tools_.find(mode);
    if (it == mode_tools_.end()) return false;
    return it->second.count(tool_name) > 0;
}

std::set<std::string> ModeManager::get_tools_for_mode(RobotMode mode) {
    static ModeManager instance;  // singleton for lookup
    auto it = instance.mode_tools_.find(mode);
    if (it == instance.mode_tools_.end()) return {};
    return it->second;
}

std::set<std::string> ModeManager::get_available_tools() const {
    auto mode = mode_.load();
    auto it = mode_tools_.find(mode);
    if (it == mode_tools_.end()) return {};
    return it->second;
}

std::string ModeManager::request_transition(
    RobotMode target_mode,
    std::function<std::string(RobotMode, RobotMode)> transition_callback
) {
    std::lock_guard<std::mutex> lock(mutex_);

    RobotMode current = mode_.load();
    if (current == target_mode) {
        return "";  // already in target mode
    }

    // Execute transition pre-conditions if callback provided
    if (transition_callback) {
        std::string err = transition_callback(current, target_mode);
        if (!err.empty()) {
            return err;
        }
    }

    // Apply the transition
    mode_.store(target_mode);
    return "";
}

std::string ModeManager::get_status_json() const {
    auto mode = mode_.load();
    json status;
    status["mode"] = mode_to_string(mode);
    status["mode_id"] = static_cast<int>(mode);

    json tools_arr = json::array();
    auto tools = get_available_tools();
    for (const auto& t : tools) {
        tools_arr.push_back(t);
    }
    status["available_tools"] = tools_arr;
    status["available_tool_count"] = tools.size();

    // List all modes
    json modes = json::array();
    for (int i = 0; i <= 3; ++i) {
        auto m = static_cast<RobotMode>(i);
        json mode_info;
        mode_info["name"] = mode_to_string(m);
        mode_info["id"] = i;
        mode_info["active"] = (m == mode);
        modes.push_back(mode_info);
    }
    status["all_modes"] = modes;

    return status.dump();
}

} // namespace ros2_llm_bridge_cpp