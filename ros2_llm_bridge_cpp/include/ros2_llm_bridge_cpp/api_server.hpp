#pragma once

#include <string>
#include <atomic>
#include <thread>
#include <functional>
#include <map>

namespace ros2_llm_bridge_cpp {

/// Minimal HTTP server for the bridge API.
/// Uses raw socket I/O with a thread-per-connection model.
/// Supports GET and POST routes with JSON.
class ApiServer {
public:
    using RequestHandler = std::function<std::string(
        const std::string& method,
        const std::string& path,
        const std::string& query,
        const std::string& body,
        std::map<std::string, std::string>& response_headers
    )>;

    ApiServer(int port = 8000);
    ~ApiServer();

    /// Set the request handler callback.
    void set_handler(RequestHandler handler);

    /// Start the server (blocking). Returns when stopped.
    void run();

    /// Stop the server.
    void stop();

    /// Check if running.
    bool is_running() const { return running_.load(); }

    /// Build HTTP response string.
    static std::string build_response(int status_code,
                               const std::string& content_type,
                               const std::string& body,
                               const std::map<std::string, std::string>& extra_headers = {});

private:
    int port_;
    int server_fd_ = -1;
    std::atomic<bool> running_{false};
    RequestHandler handler_;

    void handle_client(int client_fd);
    std::string parse_path(const std::string& request_line,
                           std::string& method, std::string& query);
    std::string parse_body(const std::string& raw_request, size_t header_end,
                           size_t content_length);
    std::string parse_header_value(const std::string& raw_request,
                                    const std::string& header_name);
};

} // namespace ros2_llm_bridge_cpp