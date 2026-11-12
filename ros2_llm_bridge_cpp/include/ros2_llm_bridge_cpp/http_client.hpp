#pragma once

#include <string>
#include <functional>

namespace ros2_llm_bridge_cpp {

/// Simple synchronous HTTP client using libcurl.
class HttpClient {
public:
    HttpClient(const std::string& base_url = "http://localhost:8001",
               long timeout_sec = 10);

    /// GET request. Returns body. Throws std::runtime_error on failure.
    /// Query params are appended to the URL as ?key=value&key=value.
    std::string get(const std::string& path,
                    const std::string& query_params = "");

    /// POST request with JSON body. Returns body.
    std::string post(const std::string& path,
                     const std::string& json_body = "",
                     const std::string& query_params = "");

    /// POST request with no body (for endpoints that take query params only).
    std::string post_empty(const std::string& path,
                           const std::string& query_params = "");

    /// Get the last HTTP response code.
    long get_last_status_code() const { return last_status_code_; }

private:
    std::string base_url_;
    long timeout_sec_;
    long last_status_code_ = 0;

    std::string execute(const std::string& url, const std::string& method,
                        const std::string& body = "");
    static size_t write_callback(void* contents, size_t size, size_t nmemb,
                                  void* userp);
};

} // namespace ros2_llm_bridge_cpp