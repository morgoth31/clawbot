// http_client.cpp — libcurl wrapper for HTTP GET/POST
// C++ equivalent of Python httpx.AsyncClient

#include "ros2_llm_bridge_cpp/http_client.hpp"
#include <curl/curl.h>
#include <stdexcept>
#include <sstream>

namespace ros2_llm_bridge_cpp {

HttpClient::HttpClient(const std::string& base_url, long timeout_sec)
    : base_url_(base_url), timeout_sec_(timeout_sec) {
    curl_global_init(CURL_GLOBAL_DEFAULT);
}

size_t HttpClient::write_callback(void* contents, size_t size, size_t nmemb,
                                   void* userp) {
    auto* str = static_cast<std::string*>(userp);
    size_t total = size * nmemb;
    str->append(static_cast<char*>(contents), total);
    return total;
}

std::string HttpClient::execute(const std::string& url, const std::string& method,
                                const std::string& body) {
    CURL* curl = curl_easy_init();
    if (!curl) throw std::runtime_error("Cannot init curl");

    std::string response_data;
    struct curl_slist* headers = nullptr;

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, timeout_sec_);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_data);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);

    if (method == "POST") {
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        if (!body.empty()) {
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.c_str());
            headers = curl_slist_append(headers, "Content-Type: application/json");
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        }
    }

    CURLcode res = curl_easy_perform(curl);

    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    last_status_code_ = http_code;

    if (headers) curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        throw std::runtime_error("HTTP request failed: " + std::string(curl_easy_strerror(res)));
    }

    // Throw on 4xx/5xx (equivalent to raise_for_status)
    if (http_code >= 400) {
        throw std::runtime_error("HTTP " + std::to_string(http_code) + ": " + response_data);
    }

    return response_data;
}

std::string HttpClient::get(const std::string& path, const std::string& query_params) {
    std::string url = base_url_ + path;
    if (!query_params.empty()) {
        url += (url.find('?') == std::string::npos ? "?" : "&") + query_params;
    }
    return execute(url, "GET");
}

std::string HttpClient::post(const std::string& path, const std::string& json_body,
                              const std::string& query_params) {
    std::string url = base_url_ + path;
    if (!query_params.empty()) {
        url += (url.find('?') == std::string::npos ? "?" : "&") + query_params;
    }
    return execute(url, "POST", json_body);
}

std::string HttpClient::post_empty(const std::string& path, const std::string& query_params) {
    std::string url = base_url_ + path;
    if (!query_params.empty()) {
        url += (url.find('?') == std::string::npos ? "?" : "&") + query_params;
    }
    return execute(url, "POST", "");
}

} // namespace ros2_llm_bridge_cpp