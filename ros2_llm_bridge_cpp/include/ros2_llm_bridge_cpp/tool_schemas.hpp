#pragma once

#include <string>
#include <map>
#include <vector>
#include <set>
#include <functional>

namespace ros2_llm_bridge_cpp {

/// Tool parameter definition for JSON schema generation.
struct ToolParam {
    std::string name;
    std::string type;          // "number", "integer", "string", "array"
    std::string description;
    bool required = false;
    double min_val = 0;        // for numeric ranges
    double max_val = 0;        // for numeric ranges
    bool has_min = false;
    bool has_max = false;
    std::string default_str;   // JSON-encoded default (e.g. "0.0", "\"front\"")
    std::string enum_json;    // JSON array for enum values (e.g. ["front","claw"])
    int array_min = 0;        // for arrays
    int array_max = 0;        // for arrays
    std::string array_item_type; // "number", "integer", "string"
};

/// Tool definition: name, description, parameters, timeout, max execution duration.
struct ToolDef {
    std::string name;
    std::string description;
    std::vector<ToolParam> params;
    double timeout_sec = 10.0;       // API timeout (HTTP response wait)
    double max_duration_sec = 0.0;    // Max physical execution time (0 = no limit)
    bool auto_stop = false;           // If true, call Stop/anti-collision after duration
};

/// Registry of all 17 tools with their schema definitions.
class ToolRegistry {
public:
    ToolRegistry();

    /// Get all tool definitions.
    const std::vector<ToolDef>& get_tools() const { return tools_; }

    /// Get a specific tool by name. Returns nullptr if not found.
    const ToolDef* get_tool(const std::string& name) const;

    /// Get the timeout for a tool (default 10s if not found).
    double get_timeout(const std::string& name) const;

    /// Get the max physical execution duration for a tool (0 = no limit).
    double get_max_duration(const std::string& name) const;

    /// Check if a tool requires auto-stop after its duration.
    bool get_auto_stop(const std::string& name) const;

    /// Generate JSON schema array for all tools in the given format.
    /// format: "openai", "anthropic", or "raw"
    std::string get_tools_json(const std::string& format = "openai") const;

    /// Generate JSON schema for a single tool.
    std::string get_tool_json(const std::string& tool_name,
                               const std::string& format = "openai") const;

    /// Validate JSON arguments against a tool's parameter definitions.
    /// Returns empty string on success, error message on failure.
    std::string validate_args(const std::string& tool_name,
                               const std::string& args_json) const;

    /// Get all tool names as a comma-separated string.
    std::string get_tool_names() const;

private:
    std::vector<ToolDef> tools_;
    std::map<std::string, size_t> name_index_;

    void register_tool(const ToolDef& def);
    std::string format_openai(const ToolDef& def) const;
    std::string format_anthropic(const ToolDef& def) const;
    std::string format_raw(const ToolDef& def) const;
    std::string build_properties_json(const ToolDef& def) const;
    std::string build_required_json(const ToolDef& def) const;
};

} // namespace ros2_llm_bridge_cpp