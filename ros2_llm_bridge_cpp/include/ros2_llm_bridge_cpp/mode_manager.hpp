#pragma once

#include <string>
#include <map>
#include <set>
#include <mutex>
#include <atomic>
#include <functional>

namespace ros2_llm_bridge_cpp {

/// Robot operating modes.
enum class RobotMode {
    STANDBY = 0,
    NAVIGATION = 1,
    MANIPULATION = 2,
    EVOLUTION = 3,
};

/// Convert mode to string.
inline std::string mode_to_string(RobotMode m) {
    switch (m) {
        case RobotMode::STANDBY:       return "standby";
        case RobotMode::NAVIGATION:    return "navigation";
        case RobotMode::MANIPULATION:  return "manipulation";
        case RobotMode::EVOLUTION:     return "evolution";
    }
    return "unknown";
}

/// Convert string to mode. Returns STANDBY for unknown.
inline RobotMode string_to_mode(const std::string& s) {
    if (s == "navigation" || s == "NAVIGATION") return RobotMode::NAVIGATION;
    if (s == "manipulation" || s == "MANIPULATION") return RobotMode::MANIPULATION;
    if (s == "evolution" || s == "EVOLUTION") return RobotMode::EVOLUTION;
    return RobotMode::STANDBY;
}

/// Mode manager: tracks current mode, enforces tool availability per mode,
/// and manages transitions with pre-conditions.
class ModeManager {
public:
    ModeManager();

    /// Get current mode.
    RobotMode get_current_mode() const { return mode_.load(); }

    /// Get current mode as string.
    std::string get_mode_string() const { return mode_to_string(mode_.load()); }

    /// Check if a tool is available in the current mode.
    bool is_tool_available(const std::string& tool_name) const;

    /// Get the set of available tools for a given mode.
    static std::set<std::string> get_tools_for_mode(RobotMode mode);

    /// Get the set of available tools for the current mode.
    std::set<std::string> get_available_tools() const;

    /// Request a mode transition. Returns empty string on success,
    /// error message on failure.
    /// The transition_callback is called to execute pre-conditions
    /// (e.g., stop robot, set arm pose, start/stop SLAM).
    /// transition_callback receives (from_mode, to_mode) and returns
    /// empty string on success or error message.
    std::string request_transition(
        RobotMode target_mode,
        std::function<std::string(RobotMode, RobotMode)> transition_callback = nullptr
    );

    /// Get a JSON status string describing the current mode and available tools.
    std::string get_status_json() const;

private:
    std::atomic<RobotMode> mode_{RobotMode::STANDBY};
    mutable std::mutex mutex_;

    // Tool availability per mode (initialized in constructor)
    std::map<RobotMode, std::set<std::string>> mode_tools_;
};

} // namespace ros2_llm_bridge_cpp