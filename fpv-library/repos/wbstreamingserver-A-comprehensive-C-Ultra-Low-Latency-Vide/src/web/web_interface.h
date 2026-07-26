#pragma once

#include <memory>
#include <string>
#include <vector>
#include <map>
#include <atomic>
#include <functional>
#include <thread>
#include <mutex>
#include <condition_variable>

// Forward declarations
struct json_object;
namespace fpv_streamer {
    class Server;
}

// Include the actual ConfigManager
#include "config/config_manager.h"

using fpv_streamer::ConfigManager;

namespace fpv_streamer {

// HTTP request/response structures
struct HTTPRequest {
    std::string method;
    std::string path;
    std::string query_string;
    std::map<std::string, std::string> headers;
    std::string body;
    std::string client_ip;
};

struct HTTPResponse {
    int status_code = 200;
    std::string status_text = "OK";
    std::map<std::string, std::string> headers;
    std::string body;
    
    HTTPResponse() {
        headers["Content-Type"] = "text/html";
        headers["Access-Control-Allow-Origin"] = "*";
        headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE";
        headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization";
    }
};

// Web API endpoints
enum class APIEndpoint {
    GET_STATUS,
    POST_CONFIG,
    GET_CONFIG,
    POST_RECORDING_START,
    POST_RECORDING_STOP,
    GET_RECORDINGS,
    DELETE_RECORDING,
    POST_MOTION_CONFIG,
    POST_OBJECT_CONFIG,
    GET_STATISTICS,
    GET_LOGS,
    POST_MODEL_UPLOAD,
    POST_LENS_CALIBRATION
};

// Request handler function type
using RequestHandler = std::function<HTTPResponse(const HTTPRequest&)>;

// Web interface class
class WebInterface {
public:
    WebInterface(ConfigManager& config);
    ~WebInterface();
    
    bool initialize();
    void stop();
    
    // Request processing
    void process_requests();
    
    // Configuration refresh
    void refresh_config();
    
    // Web server status
    std::atomic<bool>& get_running() { return server_running_; }
    
private:
    // HTTP server implementation
    bool setup_server();
    void server_thread();
    bool handle_connection(int client_socket, const std::string& client_ip);
    
    // Request parsing
    HTTPRequest parse_request(const std::string& raw_request);
    HTTPResponse handle_request(const HTTPRequest& request);
    
    // API handlers
    HTTPResponse handle_api_request(const HTTPRequest& request);
    
    // Endpoint handlers
    HTTPResponse handle_status(const HTTPRequest& request);
    HTTPResponse handle_config_get(const HTTPRequest& request);
    HTTPResponse handle_config_post(const HTTPRequest& request);
    HTTPResponse handle_recording_start(const HTTPRequest& request);
    HTTPResponse handle_recording_stop(const HTTPRequest& request);
    HTTPResponse handle_recordings_list(const HTTPRequest& request);
    HTTPResponse handle_recording_delete(const HTTPRequest& request);
    HTTPResponse handle_motion_config(const HTTPRequest& request);
    HTTPResponse handle_object_config(const HTTPRequest& request);
    HTTPResponse handle_statistics(const HTTPRequest& request);
    HTTPResponse handle_logs(const HTTPRequest& request);
    HTTPResponse handle_model_upload(const HTTPRequest& request);
    HTTPResponse handle_lens_calibration(const HTTPRequest& request);
    
    // Static file serving
    HTTPResponse serve_static_file(const std::string& path);
    HTTPResponse serve_index_html();
    HTTPResponse serve_about_page();
    HTTPResponse serve_api_documentation();
    
    // SVG content for AI feelings
    std::string get_ai_feelings_svg();
    
    // Utility functions
    std::string url_decode(const std::string& encoded);
    std::string json_encode(const std::map<std::string, std::string>& data);
    std::string create_json_response(bool success, const std::string& message, const std::string& data = "");
    
    // File upload handling
    bool handle_file_upload(const HTTPRequest& request, const std::string& upload_path);
    
    // CORS handling
    void add_cors_headers(HTTPResponse& response);
    
    // WebSocket for real-time updates
    bool handle_websocket(const HTTPRequest& request, int client_socket);
    
    ConfigManager& config_;
    
    // Server configuration
    int port_;
    int server_socket_;
    bool running_;
    std::atomic<bool> server_running_{false};
    
    // Threading
    std::thread server_thread_;
    std::mutex request_mutex_;
    std::condition_variable request_condition_;
    
    // Request routing
    std::map<APIEndpoint, RequestHandler> route_handlers_;
    
    // Statistics
    std::atomic<uint64_t> requests_served_{0};
    std::atomic<uint64_t> active_connections_{0};
    
    // Web root directory
    std::string web_root_;
    
    // Recent logs buffer
    std::vector<std::string> recent_logs_;
    std::mutex logs_mutex_;
    
    // Upload handling
    std::string upload_directory_;
};

} // namespace fpv_streamer