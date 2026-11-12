// tool_schemas.cpp — Tool registry and JSON schema generation (17 tools)
// C++ equivalent of Python schemas.py + action_handler.py schema formatting

#include "ros2_llm_bridge_cpp/tool_schemas.hpp"
#include <nlohmann/json.hpp>
#include <sstream>
#include <stdexcept>

using json = nlohmann::json;

namespace ros2_llm_bridge_cpp {

ToolRegistry::ToolRegistry() {
    // ── Motion ──────────────────────────────────────────────────────────
    {
        ToolDef t;
        t.name = "SetVelocity";
        t.description = "Set the robot's velocity for a bounded duration. "
                        "The robot moves for 'duration' seconds then auto-stops. "
                        "SAFETY LIMITS: linear ±0.06 m/s, angular ±0.25 rad/s. "
                        "MAX DURATION: 10 seconds (auto-stop after).";
        t.timeout_sec = 15.0;
        t.max_duration_sec = 10.0;  // max 10s of continuous movement
        t.auto_stop = true;         // auto-stop after duration
        t.params.push_back({"linear_x", "number",
            "Forward/backward velocity in m/s. Positive = forward. HARD LIMIT: ±0.06 m/s.",
            true, -0.06, 0.06, true, true, "", "", 0, 0, ""});
        t.params.push_back({"linear_y", "number",
            "Lateral velocity in m/s. Positive = left (Mecanum). HARD LIMIT: ±0.06 m/s.",
            false, -0.06, 0.06, true, true, "0.0", "", 0, 0, ""});
        t.params.push_back({"angular_z", "number",
            "Rotational velocity in rad/s. Positive = counter-clockwise. HARD LIMIT: ±0.25 rad/s.",
            true, -0.25, 0.25, true, true, "", "", 0, 0, ""});
        t.params.push_back({"duration", "number",
            "How long to move in seconds (0.1 to 10). The robot auto-stops after this duration. "
            "If omitted, moves for 1.0 second by default.",
            false, 0.1, 10.0, true, true, "1.0", "", 0, 0, ""});
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "Stop";
        t.description = "Stop the robot immediately by publishing zero velocity on /cmd_vel. "
                        "Always call this after a timed movement.";
        t.timeout_sec = 2.0;
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "Speak";
        t.description = "Command the robot to speak a sentence via espeak-ng text-to-speech.";
        t.timeout_sec = 15.0;
        t.max_duration_sec = 10.0;
        t.params.push_back({"text", "string", "The sentence the robot should say aloud.",
            true, 0, 0, false, false, "", "", 0, 0, ""});
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "NavigateTo";
        t.description = "Navigate to a Cartesian coordinate using dead-reckoning. "
                        "Calculates distance and heading, rotates to face target, then moves forward. "
                        "For accurate navigation, activate Nav2 with a SLAM map.";
        t.timeout_sec = 60.0;
        t.max_duration_sec = 30.0;  // max 30s for navigation
        t.auto_stop = true;
        t.params.push_back({"target_x", "number", "Target X coordinate in the map frame (meters).",
            true, 0, 0, false, false, "", "", 0, 0, ""});
        t.params.push_back({"target_y", "number", "Target Y coordinate in the map frame (meters).",
            true, 0, 0, false, false, "", "", 0, 0, ""});
        register_tool(t);
    }

    // ── Vision ──────────────────────────────────────────────────────────
    {
        ToolDef t;
        t.name = "CaptureCamera";
        t.description = "Capture a JPEG frame from one of the robot's cameras and save it. "
                        "Returns saved file path and base64-encoded image. "
                        "Cameras: 'front' (/dev/video0), 'claw' (/dev/video2).";
        t.timeout_sec = 10.0;
        t.max_duration_sec = 3.0;  // capture takes max 3s
        t.auto_stop = false;
        t.params.push_back({"camera", "string", "Which camera: 'front' (chassis) or 'claw' (arm).",
            false, 0, 0, false, false, "\"front\"", "[\"front\",\"claw\"]", 0, 0, ""});
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "AnalyzeScene";
        t.description = "Capture the front camera and return the frame for full scene analysis.";
        t.timeout_sec = 15.0;
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "RecognizeFace";
        t.description = "Capture the front camera frame and return it for face recognition.";
        t.timeout_sec = 10.0;
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "RecognizeObject";
        t.description = "Capture the front camera frame and return it for object detection.";
        t.timeout_sec = 10.0;
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "RecognizeQRCode";
        t.description = "Capture the front camera frame and return it for QR code decoding.";
        t.timeout_sec = 10.0;
        register_tool(t);
    }

    // ── Audio ────────────────────────────────────────────────────────────
    {
        ToolDef t;
        t.name = "Listen";
        t.description = "Record 3 seconds of audio from the microphone. "
                        "Returns the audio file path. STT transcription requires whisper (not yet installed).";
        t.timeout_sec = 10.0;
        t.max_duration_sec = 5.0;
        register_tool(t);
    }

    // ── Arm & Claw ──────────────────────────────────────────────────────
    {
        ToolDef t;
        t.name = "ControlServo";
        t.description = "Directly set a single servo to a target angle. "
                        "Servo map: 1=Base, 2=Shoulder, 3=Elbow, 4=Wrist tilt, 5=Wrist rotate, 6=Claw.";
        t.timeout_sec = 5.0;
        t.max_duration_sec = 3.0;  // servo reaches position within 3s
        t.auto_stop = false;
        t.params.push_back({"servo_id", "integer", "Servo ID to control (1–6).",
            true, 1, 6, true, true, "", "", 0, 0, ""});
        t.params.push_back({"angle", "number", "Target angle in degrees (0–180).",
            true, 0, 180, true, true, "", "", 0, 0, ""});
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "ControlArm";
        t.description = "Send joint angles (degrees) to the 5-DOF robotic arm servos 1–5. "
                        "Provide exactly 5 values: [base, shoulder, elbow, wrist-tilt, wrist-rotate].";
        t.timeout_sec = 10.0;
        t.max_duration_sec = 5.0;  // arm movement takes max 5s (5 servos x 60ms + travel)
        t.auto_stop = false;
        t.params.push_back({"joints_array", "array",
            "5 joint angles in degrees [base, shoulder, elbow, wrist-tilt, wrist-rotate]. "
            "Each value 0–180. Use ControlClaw for servo 6.",
            true, 0, 0, false, false, "", "", 5, 5, "number"});
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "ControlClaw";
        t.description = "Open or close the robot's end-effector claw (servo 6). "
                        "open → 0° (fully open), close → 180° (fully closed).";
        t.timeout_sec = 5.0;
        t.max_duration_sec = 2.0;
        t.auto_stop = false;
        t.params.push_back({"state", "string", "Desired claw state: 'open' or 'close'.",
            true, 0, 0, false, false, "", "[\"open\",\"close\"]", 0, 0, ""});
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "SetArmPose";
        t.description = "Move the robot arm to a named predefined pose by ID. "
                        "1=Anti-collision, 2=Dance, 3=Line-tracking.";
        t.timeout_sec = 10.0;
        t.max_duration_sec = 5.0;
        t.auto_stop = false;
        t.params.push_back({"pose_id", "integer",
            "Pose ID: 1 (Anti-collision), 2 (Dance), 3 (Line-tracking).",
            true, 1, 3, true, true, "", "", 0, 0, ""});
        register_tool(t);
    }

    // ── Peripherals ──────────────────────────────────────────────────────
    {
        ToolDef t;
        t.name = "Beep";
        t.description = "Sound the robot's buzzer for a fixed duration.";
        t.timeout_sec = 5.0;
        t.max_duration_sec = 5.0;  // max 5s buzzer
        t.auto_stop = false;       // buzzer auto-stops by itself in HW
        t.params.push_back({"delay_ms", "integer", "Duration in milliseconds to sound the buzzer.",
            false, 1, 5000, true, true, "200", "", 0, 0, ""});
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "SetLamps";
        t.description = "Set the colour of the robot's RGB LED lamps (all lamps at once).";
        t.timeout_sec = 2.0;
        t.params.push_back({"r", "integer", "Red channel intensity (0–255).",
            false, 0, 255, true, true, "0", "", 0, 0, ""});
        t.params.push_back({"g", "integer", "Green channel intensity (0–255).",
            false, 0, 255, true, true, "0", "", 0, 0, ""});
        t.params.push_back({"b", "integer", "Blue channel intensity (0–255).",
            false, 0, 255, true, true, "0", "", 0, 0, ""});
        register_tool(t);
    }
    {
        ToolDef t;
        t.name = "GetBatteryVoltage";
        t.description = "Read the current battery voltage. Returns voltage in volts and "
                        "estimated charge percentage based on the 3S LiPo curve (9.6V–12.6V).";
        t.timeout_sec = 3.0;
        register_tool(t);
    }

    // ── Vision Detection (YOLO) ─────────────────────────────────────────
    {
        ToolDef t;
        t.name = "DetectObjects";
        t.description = "Run YOLOv5 object detection on a camera frame. Returns detected "
                        "objects with class names, confidence scores, and bounding boxes. "
                        "Uses local GPU (CUDA) inference. Cameras: 'front' or 'claw'.";
        t.timeout_sec = 15.0;
        t.max_duration_sec = 1.0;
        t.auto_stop = false;
        t.params.push_back({"camera", "string",
            "Which camera to detect on: 'front' (chassis) or 'claw' (arm).",
            false, 0, 0, false, false, "\"front\"", "[\"front\",\"claw\"]", 0, 0, ""});
        register_tool(t);
    }
}

void ToolRegistry::register_tool(const ToolDef& def) {
    name_index_[def.name] = tools_.size();
    tools_.push_back(def);
}

const ToolDef* ToolRegistry::get_tool(const std::string& name) const {
    auto it = name_index_.find(name);
    if (it == name_index_.end()) return nullptr;
    return &tools_[it->second];
}

double ToolRegistry::get_timeout(const std::string& name) const {
    auto* t = get_tool(name);
    return t ? t->timeout_sec : 10.0;
}

double ToolRegistry::get_max_duration(const std::string& name) const {
    auto* t = get_tool(name);
    return t ? t->max_duration_sec : 0.0;
}

bool ToolRegistry::get_auto_stop(const std::string& name) const {
    auto* t = get_tool(name);
    return t ? t->auto_stop : false;
}

std::string ToolRegistry::get_tool_names() const {
    std::ostringstream oss;
    for (size_t i = 0; i < tools_.size(); ++i) {
        if (i > 0) oss << ", ";
        oss << tools_[i].name;
    }
    return oss.str();
}

// ── JSON schema generation ───────────────────────────────────────────────

std::string ToolRegistry::build_properties_json(const ToolDef& def) const {
    json props = json::object();
    for (const auto& p : def.params) {
        json prop;
        prop["type"] = p.type;
        prop["description"] = p.description;
        if (p.has_min) prop["minimum"] = p.min_val;
        if (p.has_max) prop["maximum"] = p.max_val;
        if (!p.default_str.empty()) prop["default"] = json::parse(p.default_str);
        if (!p.enum_json.empty()) prop["enum"] = json::parse(p.enum_json);
        if (p.type == "array") {
            prop["minItems"] = p.array_min;
            prop["maxItems"] = p.array_max;
            if (!p.array_item_type.empty()) {
                prop["items"] = json::object();
            prop["items"]["type"] = p.array_item_type;
            }
        }
        props[p.name] = prop;
    }
    return props.dump();
}

std::string ToolRegistry::build_required_json(const ToolDef& def) const {
    json req = json::array();
    for (const auto& p : def.params) {
        if (p.required) req.push_back(p.name);
    }
    return req.dump();
}

std::string ToolRegistry::format_openai(const ToolDef& def) const {
    json tool;
    tool["type"] = "function";
    json func;
    func["name"] = def.name;
    func["description"] = def.description;
    json params;
    params["type"] = "object";
    params["properties"] = json::parse(build_properties_json(def));
    params["required"] = json::parse(build_required_json(def));
    func["parameters"] = params;
    tool["function"] = func;
    return tool.dump();
}

std::string ToolRegistry::format_anthropic(const ToolDef& def) const {
    json tool;
    tool["name"] = def.name;
    tool["description"] = def.description;
    json schema;
    schema["type"] = "object";
    schema["properties"] = json::parse(build_properties_json(def));
    schema["required"] = json::parse(build_required_json(def));
    tool["input_schema"] = schema;
    return tool.dump();
}

std::string ToolRegistry::format_raw(const ToolDef& def) const {
    json schema;
    schema["title"] = def.name;
    schema["description"] = def.description;
    schema["type"] = "object";
    schema["properties"] = json::parse(build_properties_json(def));
    schema["required"] = json::parse(build_required_json(def));
    return schema.dump();
}

std::string ToolRegistry::get_tool_json(const std::string& name,
                                         const std::string& format) const {
    auto* t = get_tool(name);
    if (!t) return "null";
    if (format == "anthropic") return format_anthropic(*t);
    if (format == "raw") return format_raw(*t);
    return format_openai(*t); // default
}

std::string ToolRegistry::get_tools_json(const std::string& format) const {
    json arr = json::array();
    for (const auto& t : tools_) {
        if (format == "anthropic") {
            arr.push_back(json::parse(format_anthropic(t)));
        } else if (format == "raw") {
            arr.push_back(json::parse(format_raw(t)));
        } else {
            arr.push_back(json::parse(format_openai(t)));
        }
    }
    return arr.dump();
}

// ── Argument validation ──────────────────────────────────────────────────

std::string ToolRegistry::validate_args(const std::string& tool_name,
                                          const std::string& args_json) const {
    auto* t = get_tool(tool_name);
    if (!t) {
        return "Unknown tool '" + tool_name + "'. Available: " + get_tool_names();
    }

    json args;
    try {
        args = json::parse(args_json.empty() ? "{}" : args_json);
    } catch (const std::exception& e) {
        return std::string("Invalid JSON arguments: ") + e.what();
    }

    if (!args.is_object()) {
        return "Arguments must be a JSON object.";
    }

    for (const auto& p : t->params) {
        if (p.required && !args.contains(p.name)) {
            return "Missing required parameter: " + p.name;
        }
        if (!args.contains(p.name)) continue;

        const auto& val = args[p.name];

        // Type checking
        if (p.type == "number" && !val.is_number()) {
            return "Parameter '" + p.name + "' must be a number.";
        }
        if (p.type == "integer" && !val.is_number_integer()) {
            return "Parameter '" + p.name + "' must be an integer.";
        }
        if (p.type == "string" && !val.is_string()) {
            return "Parameter '" + p.name + "' must be a string.";
        }
        if (p.type == "array") {
            if (!val.is_array()) return "Parameter '" + p.name + "' must be an array.";
            if (p.array_min > 0 && (int)val.size() < p.array_min)
                return "Parameter '" + p.name + "' must have at least " +
                       std::to_string(p.array_min) + " elements.";
            if (p.array_max > 0 && (int)val.size() > p.array_max)
                return "Parameter '" + p.name + "' must have at most " +
                       std::to_string(p.array_max) + " elements.";
        }

        // Range checking
        if (p.has_min && val.is_number()) {
            double v = val;
            if (v < p.min_val)
                return "Parameter '" + p.name + "' must be >= " + std::to_string(p.min_val);
        }
        if (p.has_max && val.is_number()) {
            double v = val;
            if (v > p.max_val)
                return "Parameter '" + p.name + "' must be <= " + std::to_string(p.max_val);
        }

        // Enum checking
        if (!p.enum_json.empty()) {
            auto allowed = json::parse(p.enum_json);
            bool found = false;
            for (const auto& e : allowed) {
                if (val == e) { found = true; break; }
            }
            if (!found) {
                return "Parameter '" + p.name + "' must be one of: " + p.enum_json;
            }
        }
    }

    return ""; // valid
}

} // namespace ros2_llm_bridge_cpp