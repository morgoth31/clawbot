#pragma once

#include <string>
#include <functional>
#include <nlohmann/json.hpp>
#include "ros2_llm_bridge_cpp/tool_schemas.hpp"

namespace ros2_llm_bridge_cpp {

class BridgeNode;

/// Action handler that maps tool names to BridgeNode execution methods.
/// Validates arguments against schemas and dispatches to the appropriate
/// bridge method. This is the C++ equivalent of the Python ActionHandler.
class ActionHandler {
public:
    explicit ActionHandler(BridgeNode& node);

    /// Execute a tool by name with JSON arguments.
    /// Returns the result string.
    /// Throws std::invalid_argument for unknown tools or invalid args.
    std::string execute_tool(const std::string& func_name,
                             const std::string& args_json);

    /// Get the tool registry.
    const ToolRegistry& registry() const { return registry_; }

    /// Generate a UUID-like correlation ID.
    static std::string generate_cid();

private:
    BridgeNode& node_;
    ToolRegistry registry_;

    // Dispatch to the right BridgeNode method based on tool name.
    std::string dispatch(const std::string& cid, const std::string& func_name,
                         const nlohmann::json& args);
};

} // namespace ros2_llm_bridge_cpp