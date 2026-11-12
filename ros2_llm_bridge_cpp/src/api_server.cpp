// api_server.cpp — Minimal HTTP server + ROS2 node lifecycle + tool dispatch
// C++ equivalent of Python api_server.py (FastAPI + rclpy)
//
// Endpoints:
//   GET  /health        — liveness probe
//   GET  /tools         — list tool schemas (format=openai|anthropic|raw)
//   POST /command       — execute a tool: {"function":"...","arguments":{...}}
//
// Optional auth: set API_KEY env var, then X-API-Key header is required.

#include "ros2_llm_bridge_cpp/api_server.hpp"
#include "ros2_llm_bridge_cpp/bridge_node.hpp"
#include "ros2_llm_bridge_cpp/action_handler.hpp"
#include "ros2_llm_bridge_cpp/tool_schemas.hpp"
#include "ros2_llm_bridge_cpp/mode_manager.hpp"
#include <rclcpp/rclcpp.hpp>
#include <nlohmann/json.hpp>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <signal.h>
#include <sstream>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <chrono>
#include <thread>
#include <future>
#include <atomic>
#include <iostream>

using json = nlohmann::json;
using namespace ros2_llm_bridge_cpp;

// ── Globals ─────────────────────────────────────────────────────────────────

static std::atomic<bool> g_should_stop{false};
static BridgeNode* g_bridge_node = nullptr;
static ActionHandler* g_action_handler = nullptr;
static ToolRegistry* g_tool_registry = nullptr;
static ModeManager* g_mode_manager = nullptr;

// ── Signal handler ──────────────────────────────────────────────────────────

static void signal_handler(int sig) {
    (void)sig;
    g_should_stop = true;
}

// ── HTTP response helpers ────────────────────────────────────────────────────

std::string ApiServer::build_response(int status_code,
                                       const std::string& content_type,
                                       const std::string& body,
                                       const std::map<std::string, std::string>& extra_headers) {
    std::ostringstream oss;
    oss << "HTTP/1.1 " << status_code << " ";
    switch (status_code) {
        case 200: oss << "OK"; break;
        case 400: oss << "Bad Request"; break;
        case 401: oss << "Unauthorized"; break;
        case 404: oss << "Not Found"; break;
        case 503: oss << "Service Unavailable"; break;
        case 504: oss << "Gateway Timeout"; break;
        default: oss << "OK"; break;
    }
    oss << "\r\n";
    oss << "Content-Type: " << content_type << "\r\n";
    oss << "Content-Length: " << body.size() << "\r\n";
    oss << "Access-Control-Allow-Origin: *\r\n";
    oss << "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n";
    oss << "Access-Control-Allow-Headers: Content-Type, X-API-Key\r\n";
    for (const auto& [k, v] : extra_headers) {
        oss << k << ": " << v << "\r\n";
    }
    oss << "Connection: close\r\n";
    oss << "\r\n";
    oss << body;
    return oss.str();
}

// ── URL parsing ──────────────────────────────────────────────────────────────

static std::string url_decode(const std::string& str) {
    std::string result;
    for (size_t i = 0; i < str.size(); ++i) {
        if (str[i] == '%' && i + 2 < str.size()) {
            int hex = std::stoi(str.substr(i + 1, 2), nullptr, 16);
            result += static_cast<char>(hex);
            i += 2;
        } else if (str[i] == '+') {
            result += ' ';
        } else {
            result += str[i];
        }
    }
    return result;
}

std::string ApiServer::parse_path(const std::string& request_line,
                                   std::string& method, std::string& query) {
    // request_line: "GET /tools?format=openai HTTP/1.1"
    size_t space1 = request_line.find(' ');
    size_t space2 = request_line.rfind(' ');
    method = request_line.substr(0, space1);
    std::string full_path = request_line.substr(space1 + 1, space2 - space1 - 1);

    size_t q = full_path.find('?');
    if (q != std::string::npos) {
        query = full_path.substr(q + 1);
        return full_path.substr(0, q);
    }
    query = "";
    return full_path;
}

std::string ApiServer::parse_header_value(const std::string& raw,
                                           const std::string& header_name) {
    std::string search = header_name + ":";
    auto pos = raw.find(search);
    if (pos == std::string::npos) return "";
    pos += search.size();
    while (pos < raw.size() && (raw[pos] == ' ' || raw[pos] == '\t')) pos++;
    auto end = raw.find("\r\n", pos);
    if (end == std::string::npos) end = raw.find("\n", pos);
    return raw.substr(pos, end - pos);
}

std::string ApiServer::parse_body(const std::string& raw, size_t header_end,
                                   size_t content_length) {
    if (content_length == 0) return "";
    if (header_end + content_length > raw.size()) return "";
    return raw.substr(header_end, content_length);
}

// ── HTTP server ──────────────────────────────────────────────────────────────

ApiServer::ApiServer(int port) : port_(port) {}

ApiServer::~ApiServer() {
    stop();
}

void ApiServer::set_handler(RequestHandler handler) {
    handler_ = std::move(handler);
}

void ApiServer::run() {
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd_ < 0) {
        std::cerr << "Cannot create socket" << std::endl;
        return;
    }

    int opt = 1;
    setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port_);

    if (bind(server_fd_, (sockaddr*)&addr, sizeof(addr)) < 0) {
        std::cerr << "Cannot bind port " << port_ << std::endl;
        close(server_fd_);
        return;
    }

    listen(server_fd_, 16);
    running_ = true;
    std::cout << "C++ LLM Bridge API listening on port " << port_ << std::endl;

    // Set socket to non-blocking so we can check g_should_stop
    int flags = fcntl(server_fd_, F_GETFL, 0);
    fcntl(server_fd_, F_SETFL, flags | O_NONBLOCK);

    while (!g_should_stop && running_) {
        sockaddr_in client_addr{};
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(server_fd_, (sockaddr*)&client_addr, &client_len);

        if (client_fd < 0) {
            if (errno == EWOULDBLOCK || errno == EAGAIN) {
                std::this_thread::sleep_for(std::chrono::milliseconds(50));
                continue;
            }
            break;
        }

        // Handle in a detached thread
        std::thread([this, client_fd] { handle_client(client_fd); }).detach();
    }

    close(server_fd_);
    running_ = false;
}

void ApiServer::stop() {
    if (running_) {
        g_should_stop = true;
        running_ = false;
    }
}

void ApiServer::handle_client(int client_fd) {
    // Set receive timeout
    struct timeval tv;
    tv.tv_sec = 10;
    tv.tv_usec = 0;
    setsockopt(client_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    // Read request
    char buf[65536];
    std::string raw_request;
    size_t total_read = 0;

    while (total_read < sizeof(buf) - 1) {
        ssize_t n = recv(client_fd, buf, sizeof(buf) - 1 - total_read, 0);
        if (n <= 0) break;
        buf[n] = '\0';
        raw_request.append(buf, n);
        total_read += n;

        // Check if we got the full header
        if (raw_request.find("\r\n\r\n") != std::string::npos) {
            // Check if we need to read body
            std::string cl = parse_header_value(raw_request, "Content-Length");
            if (!cl.empty()) {
                size_t needed = std::stoul(cl);
                size_t header_end = raw_request.find("\r\n\r\n") + 4;
                size_t body_have = total_read - header_end;
                while (body_have < needed && total_read < sizeof(buf) - 1) {
                    n = recv(client_fd, buf, sizeof(buf) - 1 - total_read, 0);
                    if (n <= 0) break;
                    buf[n] = '\0';
                    raw_request.append(buf, n);
                    total_read += n;
                    body_have = total_read - header_end;
                }
            }
            break;
        }
    }

    if (raw_request.empty()) {
        close(client_fd);
        return;
    }

    // Parse request
    size_t first_line_end = raw_request.find("\r\n");
    std::string request_line = raw_request.substr(0, first_line_end);

    std::string method, query;
    std::string path = parse_path(request_line, method, query);
    query = url_decode(query);

    size_t header_end = raw_request.find("\r\n\r\n") + 4;
    std::string cl_str = parse_header_value(raw_request, "Content-Length");
    size_t content_length = cl_str.empty() ? 0 : std::stoul(cl_str);
    std::string body = parse_body(raw_request, header_end, content_length);

    // Handle OPTIONS (CORS preflight)
    if (method == "OPTIONS") {
        std::string resp = build_response(200, "text/plain", "");
        send(client_fd, resp.c_str(), resp.size(), 0);
        close(client_fd);
        return;
    }

    // Call handler, passing headers for auth
    std::map<std::string, std::string> resp_headers;
    // Extract API key header for auth
    std::string api_key_header = parse_header_value(raw_request, "X-API-Key");
    resp_headers["_x_api_key"] = api_key_header;
    std::string response_body;
    try {
        response_body = handler_(method, path, query, body, resp_headers);
    } catch (const std::exception& e) {
        std::string err = json({{"detail", e.what()}}).dump();
        response_body = build_response(503, "application/json", err);
        send(client_fd, response_body.c_str(), response_body.size(), 0);
        close(client_fd);
        return;
    }

    // response_body is already a full HTTP response from handler
    send(client_fd, response_body.c_str(), response_body.size(), 0);
    close(client_fd);
}

// ── Main ────────────────────────────────────────────────────────────────────

int main(int argc, char** argv) {
    // Init ROS2
    rclcpp::init(argc, argv);

    // Create bridge node and spin in a separate thread
    auto node = std::make_shared<BridgeNode>();
    g_bridge_node = node.get();

    ToolRegistry registry;
    g_tool_registry = &registry;

    ActionHandler handler(*g_bridge_node);
    g_action_handler = &handler;

    ModeManager mode_manager;
    g_mode_manager = &mode_manager;

    std::thread ros_thread([&node]() {
        rclcpp::spin(node);
    });

    // Determine port
    int port = 8000;
    if (const char* p = std::getenv("BRIDGE_PORT")) {
        port = std::atoi(p);
    }

    // Create HTTP server
    ApiServer server(port);

    server.set_handler([&](const std::string& method,
                           const std::string& path,
                           const std::string& query,
                           const std::string& body,
                           std::map<std::string, std::string>& resp_headers) -> std::string {
        // Auth check (optional API key)
        static std::string api_key_env;
        if (api_key_env.empty()) {
            if (const char* k = std::getenv("API_KEY")) api_key_env = k;
        }
        if (!api_key_env.empty()) {
            std::string provided;
            auto it = resp_headers.find("_x_api_key");
            if (it != resp_headers.end()) provided = it->second;
            if (provided != api_key_env) {
                json err = {{"detail", "Missing or invalid X-API-Key header."}};
                return server.build_response(401, "application/json", err.dump());
            }
        }

        // GET /health
        if (method == "GET" && path == "/health") {
            json health = {{"status", "healthy"}};
            return server.build_response(200, "application/json", health.dump());
        }

        // GET /tools
        if (method == "GET" && path == "/tools") {
            // Parse format from query
            std::string format = "openai";
            if (query.find("format=anthropic") != std::string::npos) format = "anthropic";
            else if (query.find("format=raw") != std::string::npos) format = "raw";

            std::string tools_json = registry.get_tools_json(format);
            return server.build_response(200, "application/json", tools_json);
        }

        // GET /durations — return max execution durations per tool
        if (method == "GET" && path == "/durations") {
            json durations = json::array();
            for (const auto& t : registry.get_tools()) {
                json d;
                d["tool"] = t.name;
                d["max_duration_sec"] = t.max_duration_sec;
                d["auto_stop"] = t.auto_stop;
                d["timeout_sec"] = t.timeout_sec;
                durations.push_back(d);
            }
            return server.build_response(200, "application/json", durations.dump());
        }

        // POST /evolution/build — rebuild the C++ bridge
        if (method == "POST" && path == "/evolution/build") {
            json req;
            try { req = json::parse(body); } catch (...) {}
            std::string pkg = req.value("package", "ros2_llm_bridge_cpp");
            std::string cmd = "cd /home/jetson/clawbot && source /opt/ros/humble/setup.bash && "
                              "colcon build --packages-select " + pkg +
                              " --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1";
            int rc = std::system(cmd.c_str());
            json resp;
            resp["status"] = (rc == 0) ? "ok" : "failed";
            resp["package"] = pkg;
            resp["return_code"] = rc;
            return server.build_response(200, "application/json", resp.dump());
        }

        // POST /evolution/test — run test suite
        if (method == "POST" && path == "/evolution/test") {
            json req;
            try { req = json::parse(body); } catch (...) {}
            std::string suite = req.value("suite", "cpp");
            std::string cmd;
            if (suite == "cpp") {
                cmd = "cd /home/jetson/clawbot && python3 tests/test_cpp_bridge.py 2>&1";
            } else if (suite == "modes") {
                cmd = "cd /home/jetson/clawbot && python3 tests/test_modes.py 2>&1";
            } else if (suite == "regression") {
                cmd = "cd /home/jetson/clawbot && python3 tests/test_regression.py --skip-motion --skip-camera 2>&1";
            } else {
                json err = {{"detail", "Unknown suite: " + suite + ". Use: cpp, modes, regression"}};
                return server.build_response(400, "application/json", err.dump());
            }
            int rc = std::system(cmd.c_str());
            json resp;
            resp["status"] = (rc == 0) ? "pass" : "fail";
            resp["suite"] = suite;
            resp["return_code"] = rc;
            return server.build_response(200, "application/json", resp.dump());
        }

        // GET /mode — return current mode and available tools
        if (method == "GET" && path == "/mode") {
            return server.build_response(200, "application/json",
                                          g_mode_manager->get_status_json());
        }

        // POST /mode — change mode: {"mode": "navigation"}
        if (method == "POST" && path == "/mode") {
            json req;
            try {
                req = json::parse(body);
            } catch (const std::exception& e) {
                json err = {{"detail", std::string("Invalid JSON: ") + e.what()}};
                return server.build_response(400, "application/json", err.dump());
            }

            std::string target_str = req.value("mode", "");
            if (target_str.empty()) {
                json err = {{"detail", "Missing 'mode' field."}};
                return server.build_response(400, "application/json", err.dump());
            }

            RobotMode target = string_to_mode(target_str);

            // Transition callback: execute pre-conditions
            auto transition_cb = [](RobotMode from, RobotMode to) -> std::string {
                // Always stop the robot first
                if (g_bridge_node) {
                    g_bridge_node->execute_stop("mode-transition");
                }

                // Set arm to anti-collision for NAVIGATION and STANDBY
                if (to == RobotMode::NAVIGATION || to == RobotMode::STANDBY ||
                    to == RobotMode::EVOLUTION) {
                    if (g_bridge_node) {
                        g_bridge_node->execute_set_arm_pose("mode-transition", 1);
                    }
                }

                // Set LEDs indicator
                if (g_bridge_node) {
                    if (to == RobotMode::STANDBY) {
                        g_bridge_node->execute_set_lamps("mode-transition", 0, 255, 0);  // green
                    } else if (to == RobotMode::NAVIGATION) {
                        g_bridge_node->execute_set_lamps("mode-transition", 255, 255, 0); // yellow
                    } else if (to == RobotMode::MANIPULATION) {
                        g_bridge_node->execute_set_lamps("mode-transition", 255, 100, 0); // orange
                    } else if (to == RobotMode::EVOLUTION) {
                        g_bridge_node->execute_set_lamps("mode-transition", 0, 0, 255);  // blue
                    }
                }

                return "";  // success
            };

            std::string err = g_mode_manager->request_transition(target, transition_cb);
            if (!err.empty()) {
                json err_resp = {{"detail", err}};
                return server.build_response(400, "application/json", err_resp.dump());
            }

            json resp;
            resp["status"] = "ok";
            resp["mode"] = g_mode_manager->get_mode_string();
            resp["available_tools"] = [&]() {
                json arr = json::array();
                for (const auto& t : g_mode_manager->get_available_tools()) {
                    arr.push_back(t);
                }
                return arr;
            }();
            return server.build_response(200, "application/json", resp.dump());
        }

        // POST /command
        if (method == "POST" && path == "/command") {
            json req;
            try {
                req = json::parse(body);
            } catch (const std::exception& e) {
                json err = {{"detail", std::string("Invalid JSON: ") + e.what()}};
                return server.build_response(400, "application/json", err.dump());
            }

            std::string func_name = req.value("function", "");
            std::string args_str = req.value("arguments", json::object()).dump();

            if (func_name.empty()) {
                json err = {{"detail", "Missing 'function' field."}};
                return server.build_response(400, "application/json", err.dump());
            }

            // Validate + execute
            std::string err = registry.validate_args(func_name, args_str);
            if (!err.empty()) {
                json err_resp = {{"detail", err}};
                return server.build_response(400, "application/json", err_resp.dump());
            }

            // Mode check: is this tool available in the current mode?
            if (!g_mode_manager->is_tool_available(func_name)) {
                json err = {{"detail", "Tool '" + func_name + "' is not available in mode '" +
                            g_mode_manager->get_mode_string() + "'. Available: " +
                            [&]() {
                                std::string s;
                                auto tools = g_mode_manager->get_available_tools();
                                for (auto it = tools.begin(); it != tools.end(); ++it) {
                                    if (it != tools.begin()) s += ", ";
                                    s += *it;
                                }
                                return s;
                            }()}};
                return server.build_response(403, "application/json", err.dump());
            }

            try {
                // Timeout handling via async
                double timeout = registry.get_timeout(func_name);
                auto future = std::async(std::launch::async, [&]() {
                    return handler.execute_tool(func_name, args_str);
                });

                if (future.wait_for(std::chrono::duration<double>(timeout)) == std::future_status::timeout) {
                    json err = {{"detail", "Tool '" + func_name + "' timed out after " +
                                std::to_string((int)timeout) + " seconds."}};
                    return server.build_response(504, "application/json", err.dump());
                }

                std::string result = future.get();
                json resp = {{"result", result}};
                return server.build_response(200, "application/json", resp.dump());

            } catch (const std::invalid_argument& e) {
                json err = {{"detail", e.what()}};
                return server.build_response(400, "application/json", err.dump());
            } catch (const std::exception& e) {
                json err = {{"detail", std::string("Robot execution failed: ") + e.what()}};
                return server.build_response(503, "application/json", err.dump());
            }
        }

        // 404
        json err = {{"detail", "Not found: " + method + " " + path}};
        return server.build_response(404, "application/json", err.dump());
    });

    // Run server (blocking until SIGINT)
    server.run();

    // Cleanup
    rclcpp::shutdown();
    if (ros_thread.joinable()) ros_thread.join();

    return 0;
}