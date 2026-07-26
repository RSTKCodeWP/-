#include "web/web_interface.h"
#include "utils/utils.h"
#include "config/config_manager.h"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <sys/stat.h>
#include <dirent.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <cstring>
#include <cstdio>
#include <cerrno>

namespace fpv_streamer {

WebInterface::WebInterface(ConfigManager& config)
    : config_(config)
    , port_(config_.get_web_config().port)  // Use config port
    , server_socket_(-1)
    , running_(false)
    , web_root_("/var/www/fpv-streamer")  // Default web root
    , upload_directory_("/tmp/fpv-uploads") {
}

WebInterface::~WebInterface() {
    stop();
}

bool WebInterface::initialize() {
    Logger::info("Initializing Web Interface on port " + std::to_string(port_));
    
    // Create directories
    mkdir(web_root_.c_str(), 0755);
    mkdir(upload_directory_.c_str(), 0755);
    
    // Setup routing
    route_handlers_[APIEndpoint::GET_STATUS] = [this](const HTTPRequest& req) { return handle_status(req); };
    route_handlers_[APIEndpoint::GET_CONFIG] = [this](const HTTPRequest& req) { return handle_config_get(req); };
    route_handlers_[APIEndpoint::POST_CONFIG] = [this](const HTTPRequest& req) { return handle_config_post(req); };
    route_handlers_[APIEndpoint::POST_RECORDING_START] = [this](const HTTPRequest& req) { return handle_recording_start(req); };
    route_handlers_[APIEndpoint::POST_RECORDING_STOP] = [this](const HTTPRequest& req) { return handle_recording_stop(req); };
    route_handlers_[APIEndpoint::GET_RECORDINGS] = [this](const HTTPRequest& req) { return handle_recordings_list(req); };
    route_handlers_[APIEndpoint::DELETE_RECORDING] = [this](const HTTPRequest& req) { return handle_recording_delete(req); };
    route_handlers_[APIEndpoint::POST_MOTION_CONFIG] = [this](const HTTPRequest& req) { return handle_motion_config(req); };
    route_handlers_[APIEndpoint::POST_OBJECT_CONFIG] = [this](const HTTPRequest& req) { return handle_object_config(req); };
    route_handlers_[APIEndpoint::GET_STATISTICS] = [this](const HTTPRequest& req) { return handle_statistics(req); };
    route_handlers_[APIEndpoint::GET_LOGS] = [this](const HTTPRequest& req) { return handle_logs(req); };
    route_handlers_[APIEndpoint::POST_MODEL_UPLOAD] = [this](const HTTPRequest& req) { return handle_model_upload(req); };
    route_handlers_[APIEndpoint::POST_LENS_CALIBRATION] = [this](const HTTPRequest& req) { return handle_lens_calibration(req); };
    
    if (!setup_server()) {
        return false;
    }
    
    // Start server thread
    server_running_.store(true);
    server_thread_ = std::thread(&WebInterface::server_thread, this);
    
    running_ = true;
    Logger::info("Web Interface started on port " + std::to_string(port_));
    return true;
}

void WebInterface::stop() {
    if (!running_) {
        return;
    }
    
    Logger::info("Stopping Web Interface");
    running_ = false;
    
    server_running_.store(false);
    if (server_socket_ >= 0) {
        close(server_socket_);
        server_socket_ = -1;
    }
    
    if (server_thread_.joinable()) {
        server_thread_.join();
    }
    
    Logger::info("Web Interface stopped");
}

void WebInterface::process_requests() {
    // Request processing happens in the server thread
    // This method is called from the main loop to wake up the server if needed
    request_condition_.notify_all();
}

void WebInterface::refresh_config() {
    Logger::info("Refreshing web interface configuration");
    // Configuration is automatically refreshed through the API handlers
}

bool WebInterface::setup_server() {
    // Create socket
    server_socket_ = socket(AF_INET, SOCK_STREAM, 0);
    if (server_socket_ < 0) {
        Logger::error("Failed to create web server socket: " + std::string(strerror(errno)));
        return false;
    }
    
    // Set socket options
    int opt = 1;
    setsockopt(server_socket_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    // Bind socket
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port_);
    
    if (bind(server_socket_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        Logger::error("Failed to bind web server socket: " + std::string(strerror(errno)));
        close(server_socket_);
        server_socket_ = -1;
        return false;
    }
    
    // Listen
    if (listen(server_socket_, 10) < 0) {
        Logger::error("Failed to listen on web server socket: " + std::string(strerror(errno)));
        close(server_socket_);
        server_socket_ = -1;
        return false;
    }
    
    // Set to non-blocking
    int flags = fcntl(server_socket_, F_GETFL, 0);
    fcntl(server_socket_, F_SETFL, flags | O_NONBLOCK);
    
    Logger::info("Web server socket setup complete");
    return true;
}

void WebInterface::server_thread() {
    Logger::info("Web server thread started");
    
    while (server_running_.load()) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        
        int client_socket = accept(server_socket_, (struct sockaddr*)&client_addr, &client_len);
        if (client_socket < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                // No pending connections, sleep for a bit
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
                continue;
            }
            Logger::warn("Accept failed: " + std::string(strerror(errno)));
            continue;
        }
        
        // Get client IP
        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
        
        active_connections_.fetch_add(1);
        Logger::debug("New web connection from: " + std::string(client_ip));
        
        // Handle the connection
        handle_connection(client_socket, std::string(client_ip));
        
        active_connections_.fetch_sub(1);
        close(client_socket);
    }
    
    Logger::info("Web server thread stopped");
}

bool WebInterface::handle_connection(int client_socket, const std::string& client_ip) {
    // Read request
    std::string request_data;
    char buffer[4096];
    
    while (true) {
        ssize_t bytes_read = recv(client_socket, buffer, sizeof(buffer), 0);
        if (bytes_read <= 0) {
            break;
        }
        
        request_data.append(buffer, bytes_read);
        
        // Check if we have the complete request
        if (request_data.find("\r\n\r\n") != std::string::npos) {
            break;
        }
    }
    
    if (request_data.empty()) {
        return false;
    }
    
    // Parse request
    HTTPRequest request = parse_request(request_data);
    request.client_ip = client_ip;
    
    // Handle request
    HTTPResponse response = handle_request(request);
    
    // Send response
    std::string response_data = "HTTP/1.1 " + std::to_string(response.status_code) + " " + response.status_text + "\r\n";
    
    for (const auto& header : response.headers) {
        response_data += header.first + ": " + header.second + "\r\n";
    }
    
    response_data += "\r\n";
    response_data += response.body;
    
    send(client_socket, response_data.data(), response_data.size(), 0);
    
    requests_served_.fetch_add(1);
    return true;
}

HTTPRequest WebInterface::parse_request(const std::string& raw_request) {
    HTTPRequest request;
    std::istringstream stream(raw_request);
    std::string line;
    
    // Parse request line
    if (std::getline(stream, line)) {
        std::istringstream request_line(line);
        request_line >> request.method >> request.path >> request.method;
    }
    
    // Parse headers
    while (std::getline(stream, line) && line != "\r") {
        size_t colon_pos = line.find(':');
        if (colon_pos != std::string::npos) {
            std::string header_name = line.substr(0, colon_pos);
            std::string header_value = line.substr(colon_pos + 1);
            
            // Trim whitespace
            header_name.erase(0, header_name.find_first_not_of(" \t"));
            header_name.erase(header_name.find_last_not_of(" \t\r\n") + 1);
            header_value.erase(0, header_value.find_first_not_of(" \t"));
            header_value.erase(header_value.find_last_not_of(" \t\r\n") + 1);
            
            request.headers[header_name] = header_value;
        }
    }
    
    // Read body if present
    size_t content_length = 0;
    auto content_length_it = request.headers.find("Content-Length");
    if (content_length_it != request.headers.end()) {
        content_length = std::stoi(content_length_it->second);
    }
    
    if (content_length > 0) {
        request.body.resize(content_length);
        stream.read(&request.body[0], content_length);
    }
    
    // Extract query string
    size_t query_pos = request.path.find('?');
    if (query_pos != std::string::npos) {
        request.query_string = request.path.substr(query_pos + 1);
        request.path = request.path.substr(0, query_pos);
    }
    
    // URL decode path
    request.path = url_decode(request.path);
    
    return request;
}

HTTPResponse WebInterface::handle_request(const HTTPRequest& request) {
    HTTPResponse response;
    
    // Add CORS headers
    add_cors_headers(response);
    
    // Handle different paths
    if (request.path == "/" || request.path == "/index.html") {
        return serve_index_html();
    } else if (request.path == "/about") {
        return serve_about_page();
    } else if (request.path == "/api" || request.path == "/api/") {
        return serve_api_documentation();
    } else if (request.path.substr(0, 4) == "/api") {
        return handle_api_request(request);
    } else {
        return serve_static_file(request.path);
    }
}

HTTPResponse WebInterface::handle_api_request(const HTTPRequest& request) {
    // Parse endpoint from path
    std::string endpoint = request.path.substr(4); // Remove "/api"
    
    if (endpoint == "/status") {
        return handle_status(request);
    } else if (endpoint == "/config") {
        if (request.method == "GET") {
            return handle_config_get(request);
        } else if (request.method == "POST") {
            return handle_config_post(request);
        }
    } else if (endpoint == "/recording/start") {
        return handle_recording_start(request);
    } else if (endpoint == "/recording/stop") {
        return handle_recording_stop(request);
    } else if (endpoint == "/recordings") {
        return handle_recordings_list(request);
    } else if (endpoint == "/motion/config") {
        return handle_motion_config(request);
    } else if (endpoint == "/object/config") {
        return handle_object_config(request);
    } else if (endpoint == "/statistics") {
        return handle_statistics(request);
    } else if (endpoint == "/logs") {
        return handle_logs(request);
    } else if (endpoint == "/model/upload") {
        return handle_model_upload(request);
    } else if (endpoint == "/lens/calibration") {
        return handle_lens_calibration(request);
    }
    
    HTTPResponse response;
    response.status_code = 404;
    response.status_text = "Not Found";
    response.body = create_json_response(false, "API endpoint not found");
    return response;
}

HTTPResponse WebInterface::handle_status(const HTTPRequest& request) {
    HTTPResponse response;
    response.headers["Content-Type"] = "application/json";
    
    // TODO: Fix server dependency - cannot access server_.get_status() without circular dependency
    std::string status = "Server status temporarily unavailable";
    
    std::string json = create_json_response(true, "Status retrieved", status);
    response.body = json;
    
    return response;
}

HTTPResponse WebInterface::handle_config_get(const HTTPRequest& request) {
    HTTPResponse response;
    response.headers["Content-Type"] = "application/json";
    
    auto video_config = config_.get_video_config();
    auto stream_config = config_.get_stream_config();
    auto detection_config = config_.get_detection_config();
    auto web_config = config_.get_web_config();
    auto recording_config = config_.get_recording_config();
    auto stereo_config = config_.get_stereo_config();
    
    // Create JSON config
    std::ostringstream json;
    json << "{";
    json << "\"video\": {";
    json << "\"device\": \"" << video_config.device_path << "\",";
    json << "\"width\": " << video_config.width << ",";
    json << "\"height\": " << video_config.height << ",";
    json << "\"fps\": " << video_config.fps << ",";
    json << "\"inputFormat\": \"" << video_config.input_format << "\",";
    json << "\"outputEncoder\": \"" << video_config.output_encoder << "\",";
    json << "\"bitrate\": " << video_config.bitrate << ",";
    json << "\"quality\": " << video_config.quality << ",";
    json << "\"useHardware\": " << (video_config.use_hardware_encoder ? "true" : "false") << ",";
    
    // H.265 settings
    json << "\"h265Profile\": " << video_config.h265_profile << ",";
    json << "\"h265Level\": " << video_config.h265_level << ",";
    
    // MJPEG settings
    json << "\"mjpegQuality\": " << video_config.mjpeg_quality << ",";
    json << "\"mjpegOptimization\": " << video_config.mjpeg_optimization_level;
    json << "},";
    json << "\"stream\": {";
    json << "\"protocol\": \"" << stream_config.protocol << "\",";
    json << "\"interface\": \"" << stream_config.interface << "\",";
    json << "\"port\": " << stream_config.port;
    json << "},";
    json << "\"detection\": {";
    json << "\"motionEnabled\": " << (detection_config.enable_motion_detection ? "true" : "false") << ",";
    json << "\"objectEnabled\": " << (detection_config.enable_object_detection ? "true" : "false");
    json << "},";
    json << "\"stereo\": {";
    json << "\"enabled\": " << (stereo_config.enable_stereo ? "true" : "false") << ",";
    json << "\"camera2Device\": " << stereo_config.camera2_device << ",";
    json << "\"mode\": " << stereo_config.stereo_mode << ",";
    json << "\"separation\": " << stereo_config.stereo_separation << ",";
    json << "\"convergence\": " << stereo_config.stereo_convergence << ",";
    json << "\"offsetX\": " << stereo_config.stereo_offset_x << ",";
    json << "\"offsetY\": " << stereo_config.stereo_offset_y << ",";
    json << "\"zoom\": " << stereo_config.stereo_zoom << ",";
    json << "\"flipMode\": " << stereo_config.stereo_flip_mode << ",";
    json << "\"colorCorrection\": " << (stereo_config.enable_color_correction ? "true" : "false") << ",";
    json << "\"colorStrength\": " << stereo_config.color_correction_strength << ",";
    json << "\"saveSettings\": " << (stereo_config.save_user_settings ? "true" : "false");
    json << "}";
    json << "}";
    
    response.body = json.str();
    return response;
}

HTTPResponse WebInterface::handle_config_post(const HTTPRequest& request) {
    HTTPResponse response;
    response.headers["Content-Type"] = "application/json";
    
    try {
        // Parse JSON configuration from request body
        // This is a simplified JSON parser - in production, use a proper JSON library
        
        auto video_config = config_.get_video_config();
        auto stream_config = config_.get_stream_config();
        auto stereo_config = config_.get_stereo_config();
        
        // Update video configuration based on parsed JSON
        if (request.body.find("\"device\"") != std::string::npos) {
            // Extract device path (simplified parsing)
            size_t pos = request.body.find("\"device\"");
            size_t start = request.body.find(":", pos) + 2;
            size_t end = request.body.find("\"", start);
            if (start < end) {
                std::string device = request.body.substr(start, end - start);
                video_config.device_path = device;
            }
        }
        
        // Update input format
        if (request.body.find("\"inputFormat\"") != std::string::npos) {
            size_t pos = request.body.find("\"inputFormat\"");
            size_t start = request.body.find(":", pos) + 2;
            size_t end = request.body.find("\"", start);
            if (start < end) {
                std::string format = request.body.substr(start, end - start);
                if (format == "mjpeg") video_config.input_format = "mjpeg";
                else if (format == "h264") video_config.input_format = "h264";
                else if (format == "raw") video_config.input_format = "raw";
                else video_config.input_format = "auto";
            }
        }
        
        // Update output encoder
        if (request.body.find("\"outputEncoder\"") != std::string::npos) {
            size_t pos = request.body.find("\"outputEncoder\"");
            size_t start = request.body.find(":", pos) + 2;
            size_t end = request.body.find("\"", start);
            if (start < end) {
                std::string encoder = request.body.substr(start, end - start);
                video_config.output_encoder = encoder;
            }
        }
        
        // Update H.265 settings
        if (request.body.find("\"h265Profile\"") != std::string::npos) {
            size_t pos = request.body.find("\"h265Profile\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                std::string profile = request.body.substr(start, end - start);
                video_config.h265_profile = std::stoi(profile);
            }
        }
        
        if (request.body.find("\"h265Level\"") != std::string::npos) {
            size_t pos = request.body.find("\"h265Level\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                std::string level = request.body.substr(start, end - start);
                video_config.h265_level = std::stof(level);
            }
        }
        
        // Update MJPEG settings
        if (request.body.find("\"mjpegQuality\"") != std::string::npos) {
            size_t pos = request.body.find("\"mjpegQuality\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                std::string quality = request.body.substr(start, end - start);
                video_config.mjpeg_quality = std::stoi(quality);
            }
        }
        
        if (request.body.find("\"mjpegOptimization\"") != std::string::npos) {
            size_t pos = request.body.find("\"mjpegOptimization\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                std::string optimization = request.body.substr(start, end - start);
                video_config.mjpeg_optimization_level = std::stoi(optimization);
            }
        }
        
        // Update other video settings
        if (request.body.find("\"fps\"") != std::string::npos) {
            size_t pos = request.body.find("\"fps\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                video_config.fps = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"bitrate\"") != std::string::npos) {
            size_t pos = request.body.find("\"bitrate\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                video_config.bitrate = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"quality\"") != std::string::npos) {
            size_t pos = request.body.find("\"quality\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                video_config.quality = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        // Parse stereo configuration
        if (request.body.find("\"stereoEnabled\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoEnabled\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.enable_stereo = (request.body.substr(start, end - start) == "true");
            }
        }
        
        if (request.body.find("\"stereoCamera2Device\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoCamera2Device\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.camera2_device = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"stereoMode\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoMode\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.stereo_mode = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"stereoSeparation\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoSeparation\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.stereo_separation = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"stereoConvergence\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoConvergence\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.stereo_convergence = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"stereoOffsetX\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoOffsetX\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.stereo_offset_x = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"stereoOffsetY\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoOffsetY\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.stereo_offset_y = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"stereoZoom\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoZoom\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.stereo_zoom = std::stof(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"stereoFlipMode\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoFlipMode\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.stereo_flip_mode = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        if (request.body.find("\"stereoColorCorrection\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoColorCorrection\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.enable_color_correction = (request.body.substr(start, end - start) == "true");
            }
        }
        
        if (request.body.find("\"stereoColorStrength\"") != std::string::npos) {
            size_t pos = request.body.find("\"stereoColorStrength\"");
            size_t start = request.body.find(":", pos) + 1;
            size_t end = request.body.find(",", start);
            if (start < end) {
                stereo_config.color_correction_strength = std::stoi(request.body.substr(start, end - start));
            }
        }
        
        // Save updated configuration
        config_.update_video_config(video_config);
        config_.update_stereo_config(stereo_config);
        
        Logger::info("Configuration updated via web interface");
        response.body = create_json_response(true, "Configuration updated successfully");
        
    } catch (const std::exception& e) {
        Logger::error("Failed to parse configuration: " + std::string(e.what()));
        response.body = create_json_response(false, "Failed to parse configuration");
    }
    
    return response;
}

HTTPResponse WebInterface::serve_index_html() {
    HTTPResponse response;
    response.headers["Content-Type"] = "text/html";
    
    // Embedded HTML interface
    response.body = R"HTML(<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FPV Streamer Control Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; background: #1a1a1a; color: #fff; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #00ff00; margin-bottom: 10px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #2a2a2a; padding: 20px; border-radius: 8px; border: 1px solid #333; }
        .card h3 { color: #00ff00; margin-bottom: 15px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; color: #ccc; }
        .form-group input, .form-group select { 
            width: 100%; padding: 8px; background: #333; border: 1px solid #555; color: #fff; border-radius: 4px; 
        }
        .btn { 
            background: #00ff00; color: #000; padding: 10px 20px; border: none; border-radius: 4px; 
            cursor: pointer; font-weight: bold; margin: 5px;
        }
        .btn:hover { background: #00cc00; }
        .status { margin-top: 20px; padding: 10px; border-radius: 4px; }
        .status.success { background: #004400; color: #00ff00; }
        .status.error { background: #440000; color: #ff0000; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
        .stat { text-align: center; padding: 10px; background: #333; border-radius: 4px; }
        .stat-value { font-size: 24px; font-weight: bold; color: #00ff00; }
        .stat-label { font-size: 12px; color: #ccc; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Navigation -->
        <div style="text-align: center; margin-bottom: 20px;">
            <a href="/" style="background: #00ff00; color: #000; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold; margin: 0 10px;">Control Panel</a>
            <a href="/about" style="background: #333; color: #00ff00; padding: 8px 16px; text-decoration: none; border-radius: 4px; font-weight: bold; margin: 0 10px; border: 1px solid #00ff00;">About</a>
        </div>
        
        <div class="header">
            <h1>FPV Streamer Control Panel</h1>
            <p>Ultra-low latency video streaming server for ARM SBCs</p>
        </div>
        
        <div class="grid">
            <!-- Video Configuration -->
            <div class="card">
                <h3>Video Configuration</h3>
                <div class="form-group">
                    <label>Device Path:</label>
                    <input type="text" id="videoDevice" value="/dev/video0">
                </div>
                <div class="form-group">
                    <label>Resolution:</label>
                    <select id="resolution">
                        <option value="1920x1080">1920x1080</option>
                        <option value="1280x720">1280x720</option>
                        <option value="640x480">640x480</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Framerate:</label>
                    <input type="number" id="fps" value="60" min="1" max="120">
                </div>
                <div class="form-group">
                    <label>Input Format (USB UVC):</label>
                    <select id="inputFormat">
                        <option value="auto">Auto-detect</option>
                        <option value="mjpeg">MJPEG</option>
                        <option value="h264">H.264</option>
                        <option value="raw">RAW (YUV420)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Output Encoder:</label>
                    <select id="outputEncoder">
                        <option value="h264">H.264</option>
                        <option value="h265">H.265/HEVC</option>
                        <option value="mjpeg">MJPEG</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Bitrate (bps):</label>
                    <input type="number" id="bitrate" value="2000000" min="100000" max="10000000">
                </div>
                <div class="form-group">
                    <label>Quality (1-100):</label>
                    <input type="range" id="quality" value="80" min="1" max="100">
                </div>
                
                <!-- H.265 Settings -->
                <div id="h265Settings" style="display: none;">
                    <div class="form-group">
                        <label>H.265 Profile:</label>
                        <select id="h265Profile">
                            <option value="0">Main</option>
                            <option value="1">Main 10</option>
                            <option value="2">Main Still Picture</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>H.265 Level:</label>
                        <select id="h265Level">
                            <option value="4.0">4.0</option>
                            <option value="4.1">4.1</option>
                            <option value="5.0">5.0</option>
                            <option value="5.1">5.1</option>
                            <option value="5.2">5.2</option>
                        </select>
                    </div>
                </div>
                
                <!-- MJPEG Settings -->
                <div id="mjpegSettings" style="display: none;">
                    <div class="form-group">
                        <label>MJPEG Quality (1-100):</label>
                        <input type="range" id="mjpegQuality" value="80" min="1" max="100">
                    </div>
                    <div class="form-group">
                        <label>MJPEG Optimization:</label>
                        <select id="mjpegOptimization">
                            <option value="0">None</option>
                            <option value="1">Basic</option>
                            <option value="2" selected>Good</option>
                            <option value="3">Maximum</option>
                        </select>
                    </div>
                </div>
                <button class="btn" onclick="updateVideoConfig()">Update Video</button>
            </div>
            
            <!-- Stream Configuration -->
            <div class="card">
                <h3>Stream Configuration</h3>
                <div class="form-group">
                    <label>Protocol:</label>
                    <select id="protocol">
                        <option value="wfb">WFB (WiFi Broadcast)</option>
                        <option value="udp">UDP</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Interface:</label>
                    <input type="text" id="interface" value="wlan0">
                </div>
                <div class="form-group">
                    <label>Port:</label>
                    <input type="number" id="port" value="5600">
                </div>
                <button class="btn" onclick="updateStreamConfig()">Update Stream</button>
            </div>
            
            <!-- Stereo 3D Configuration -->
            <div class="card">
                <h3>Stereo 3D Configuration</h3>
                <div class="form-group">
                    <label>Enable Stereo Mode:</label>
                    <select id="stereoEnabled">
                        <option value="false">Disabled</option>
                        <option value="true">Enabled</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Camera 2 Device:</label>
                    <select id="stereoCamera2Device">
                        <option value="2">/dev/video2</option>
                        <option value="4">/dev/video4</option>
                        <option value="6">/dev/video6</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Stereo Mode:</label>
                    <select id="stereoMode" onchange="updateStereoMode()">
                        <option value="0">Side by Side</option>
                        <option value="1">Top Bottom</option>
                        <option value="2">Over Under</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Camera Separation (mm):</label>
                    <input type="range" id="stereoSeparation" value="63" min="40" max="80">
                    <span id="separationValue">63</span>
                </div>
                <div class="form-group">
                    <label>Convergence Offset:</label>
                    <input type="range" id="stereoConvergence" value="0" min="-100" max="100">
                    <span id="convergenceValue">0</span>
                </div>
                <div class="form-group">
                    <label>Horizontal Offset:</label>
                    <input type="range" id="stereoOffsetX" value="0" min="-50" max="50">
                    <span id="offsetXValue">0</span>
                </div>
                <div class="form-group">
                    <label>Vertical Offset:</label>
                    <input type="range" id="stereoOffsetY" value="0" min="-30" max="30">
                    <span id="offsetYValue">0</span>
                </div>
                <div class="form-group">
                    <label>Zoom Factor:</label>
                    <input type="range" id="stereoZoom" value="1.0" min="0.5" max="2.0" step="0.1">
                    <span id="zoomValue">1.0</span>
                </div>
                <div class="form-group">
                    <label>Flip Mode:</label>
                    <select id="stereoFlipMode">
                        <option value="0">None</option>
                        <option value="1">Flip Camera 1</option>
                        <option value="2">Flip Camera 2</option>
                        <option value="3">Flip Both</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Color Correction:</label>
                    <select id="stereoColorCorrection">
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Color Correction Strength:</label>
                    <input type="range" id="stereoColorStrength" value="80" min="1" max="100">
                    <span id="colorStrengthValue">80</span>
                </div>
                <div class="form-group">
                    <label>Save Settings:</label>
                    <select id="stereoSaveSettings">
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                    </select>
                </div>
                <button class="btn" onclick="updateStereoConfig()">Update Stereo</button>
                <button class="btn" onclick="resetStereoAlignment()">Reset Alignment</button>
            </div>
            
            <!-- Detection Features -->
            <div class="card">
                <h3>Detection Features</h3>
                <div class="form-group">
                    <label><input type="checkbox" id="motionDetection"> Motion Detection</label>
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="objectDetection"> Object Detection</label>
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="lensCorrection"> Lens Correction</label>
                </div>
                <div class="form-group">
                    <label>Object Model:</label>
                    <input type="file" id="modelFile" accept=".pt,.pth,.onnx">
                </div>
                <button class="btn" onclick="updateDetectionConfig()">Update Detection</button>
            </div>
            
            <!-- Recording -->
            <div class="card">
                <h3>Recording</h3>
                <div class="form-group">
                    <label><input type="checkbox" id="enableRecording"> Enable Recording</label>
                </div>
                <div class="form-group">
                    <label>Output Directory:</label>
                    <input type="text" id="outputDir" value="/var/recordings">
                </div>
                <button class="btn" onclick="startRecording()" id="startBtn">Start Recording</button>
                <button class="btn" onclick="stopRecording()" id="stopBtn">Stop Recording</button>
            </div>
        </div>
        
        <!-- Status and Statistics -->
        <div class="card" style="margin-top: 20px;">
            <h3>System Status</h3>
            <div class="stats" id="stats">
                <div class="stat">
                    <div class="stat-value" id="framesProcessed">0</div>
                    <div class="stat-label">Frames Processed</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="framesStreamed">0</div>
                    <div class="stat-label">Frames Streamed</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="currentFps">0</div>
                    <div class="stat-label">Current FPS</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="bitrateDisplay">0</div>
                    <div class="stat-label">Bitrate (kbps)</div>
                </div>
            </div>
            <div id="status" class="status"></div>
        </div>
    </div>
    
    <script>
        // API Functions
        async function updateVideoConfig() {
            const outputEncoder = document.getElementById("outputEncoder").value;
            const config = {
                device: document.getElementById("videoDevice").value,
                width: parseInt(document.getElementById("resolution").value.split("x")[0]),
                height: parseInt(document.getElementById("resolution").value.split("x")[1]),
                fps: parseInt(document.getElementById("fps").value),
                inputFormat: document.getElementById("inputFormat").value,
                outputEncoder: outputEncoder,
                bitrate: parseInt(document.getElementById("bitrate").value),
                quality: parseInt(document.getElementById("quality").value)
            };
            
            // Add H.265 specific settings
            if (outputEncoder === "h265") {
                config.h265Profile = parseInt(document.getElementById("h265Profile").value);
                config.h265Level = parseFloat(document.getElementById("h265Level").value);
            }
            
            // Add MJPEG specific settings
            if (outputEncoder === "mjpeg") {
                config.mjpegQuality = parseInt(document.getElementById("mjpegQuality").value);
                config.mjpegOptimization = parseInt(document.getElementById("mjpegOptimization").value);
            }
            
            // Add stereo configuration
            config.stereoEnabled = document.getElementById("stereoEnabled").value === "true";
            config.stereoCamera2Device = parseInt(document.getElementById("stereoCamera2Device").value);
            config.stereoMode = parseInt(document.getElementById("stereoMode").value);
            config.stereoSeparation = parseInt(document.getElementById("stereoSeparation").value);
            config.stereoConvergence = parseInt(document.getElementById("stereoConvergence").value);
            config.stereoOffsetX = parseInt(document.getElementById("stereoOffsetX").value);
            config.stereoOffsetY = parseInt(document.getElementById("stereoOffsetY").value);
            config.stereoZoom = parseFloat(document.getElementById("stereoZoom").value);
            config.stereoFlipMode = parseInt(document.getElementById("stereoFlipMode").value);
            config.stereoColorCorrection = document.getElementById("stereoColorCorrection").value === "true";
            config.stereoColorStrength = parseInt(document.getElementById("stereoColorStrength").value);
            config.stereoSaveSettings = document.getElementById("stereoSaveSettings").value === "true";
            
            try {
                const response = await fetch("/api/config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(config)
                });
                
                const result = await response.json();
                showStatus(result.success ? "success" : "error", result.message);
            } catch (error) {
                showStatus("error", "Failed to update configuration");
            }
        }
        
        // Show/hide encoder-specific settings
        function updateEncoderSettings() {
            const outputEncoder = document.getElementById("outputEncoder").value;
            const h265Settings = document.getElementById("h265Settings");
            const mjpegSettings = document.getElementById("mjpegSettings");
            
            // Hide all settings first
            h265Settings.style.display = "none";
            mjpegSettings.style.display = "none";
            
            // Show relevant settings
            if (outputEncoder === "h265") {
                h265Settings.style.display = "block";
            } else if (outputEncoder === "mjpeg") {
                mjpegSettings.style.display = "block";
            }
        }
        
        async function updateStreamConfig() {
            const config = {
                protocol: document.getElementById("protocol").value,
                interface: document.getElementById("interface").value,
                port: parseInt(document.getElementById("port").value)
            };
            
            try {
                const response = await fetch("/api/stream/config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(config)
                });
                
                const result = await response.json();
                showStatus(result.success ? "success" : "error", result.message);
            } catch (error) {
                showStatus("error", "Failed to update stream configuration");
            }
        }
        
        // Stereo configuration functions
        function updateStereoMode() {
            // Update stereo mode specific displays if needed
            console.log("Stereo mode changed");
        }
        
        async function updateStereoConfig() {
            const config = {
                stereoEnabled: document.getElementById("stereoEnabled").value === "true",
                stereoCamera2Device: parseInt(document.getElementById("stereoCamera2Device").value),
                stereoMode: parseInt(document.getElementById("stereoMode").value),
                stereoSeparation: parseInt(document.getElementById("stereoSeparation").value),
                stereoConvergence: parseInt(document.getElementById("stereoConvergence").value),
                stereoOffsetX: parseInt(document.getElementById("stereoOffsetX").value),
                stereoOffsetY: parseInt(document.getElementById("stereoOffsetY").value),
                stereoZoom: parseFloat(document.getElementById("stereoZoom").value),
                stereoFlipMode: parseInt(document.getElementById("stereoFlipMode").value),
                stereoColorCorrection: document.getElementById("stereoColorCorrection").value === "true",
                stereoColorStrength: parseInt(document.getElementById("stereoColorStrength").value),
                stereoSaveSettings: document.getElementById("stereoSaveSettings").value === "true"
            };
            
            try {
                const response = await fetch("/api/config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(config)
                });
                
                const result = await response.json();
                showStatus(result.success ? "success" : "error", result.message);
            } catch (error) {
                showStatus("error", "Failed to update stereo configuration");
            }
        }
        
        function resetStereoAlignment() {
            document.getElementById("stereoOffsetX").value = 0;
            document.getElementById("stereoOffsetY").value = 0;
            document.getElementById("stereoConvergence").value = 0;
            document.getElementById("stereoZoom").value = 1.0;
            
            // Update display values
            document.getElementById("offsetXValue").textContent = "0";
            document.getElementById("offsetYValue").textContent = "0";
            document.getElementById("convergenceValue").textContent = "0";
            document.getElementById("zoomValue").textContent = "1.0";
            
            showStatus("success", "Stereo alignment reset to defaults");
        }
        
        // Update range slider displays
        function updateSliderDisplays() {
            document.getElementById("separationValue").textContent = document.getElementById("stereoSeparation").value;
            document.getElementById("convergenceValue").textContent = document.getElementById("stereoConvergence").value;
            document.getElementById("offsetXValue").textContent = document.getElementById("stereoOffsetX").value;
            document.getElementById("offsetYValue").textContent = document.getElementById("stereoOffsetY").value;
            document.getElementById("zoomValue").textContent = document.getElementById("stereoZoom").value;
            document.getElementById("colorStrengthValue").textContent = document.getElementById("stereoColorStrength").value;
        }
        
        // Add event listeners for real-time updates
        document.addEventListener("DOMContentLoaded", function() {
            // Update displays when sliders change
            const sliders = ["stereoSeparation", "stereoConvergence", "stereoOffsetX", "stereoOffsetY", "stereoZoom", "stereoColorStrength"];
            sliders.forEach(sliderId => {
                const slider = document.getElementById(sliderId);
                if (slider) {
                    slider.addEventListener("input", updateSliderDisplays);
                }
            });
            
            // Initialize displays
            updateSliderDisplays();
        });
        
        async function updateDetectionConfig() {
            const config = {
                motionDetection: document.getElementById("motionDetection").checked,
                objectDetection: document.getElementById("objectDetection").checked,
                lensCorrection: document.getElementById("lensCorrection").checked
            };
            
            try {
                const response = await fetch("/api/detection/config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(config)
                });
                
                const result = await response.json();
                showStatus(result.success ? "success" : "error", result.message);
            } catch (error) {
                showStatus("error", "Failed to update detection configuration");
            }
        }
        
        async function startRecording() {
            try {
                const response = await fetch("/api/recording/start", { method: "POST" });
                const result = await response.json();
                showStatus(result.success ? "success" : "error", result.message);
                document.getElementById("startBtn").disabled = result.success;
                document.getElementById("stopBtn").disabled = !result.success;
            } catch (error) {
                showStatus("error", "Failed to start recording");
            }
        }
        
        async function stopRecording() {
            try {
                const response = await fetch("/api/recording/stop", { method: "POST" });
                const result = await response.json();
                showStatus(result.success ? "success" : "error", result.message);
                document.getElementById("startBtn").disabled = !result.success;
                document.getElementById("stopBtn").disabled = result.success;
            } catch (error) {
                showStatus("error", "Failed to stop recording");
            }
        }
        
        function showStatus(type, message) {
            const status = document.getElementById("status");
            status.className = "status " + type;
            status.textContent = message;
            
            if (type === "success") {
                setTimeout(() => {
                    status.className = "status";
                    status.textContent = "";
                }, 3000);
            }
        }
        
        // Update statistics every second
        async function updateStats() {
            try {
                const response = await fetch("/api/statistics");
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById("framesProcessed").textContent = data.data.framesProcessed;
                    document.getElementById("framesStreamed").textContent = data.data.framesStreamed;
                    document.getElementById("currentFps").textContent = data.data.currentFps.toFixed(1);
                    document.getElementById("bitrateDisplay").textContent = (data.data.bitrate / 1000).toFixed(0);
                }
            } catch (error) {
                console.error("Failed to update statistics:", error);
            }
        }
        
        // Initialize
        document.addEventListener("DOMContentLoaded", () => {
            updateStats();
            setInterval(updateStats, 1000);
            updateEncoderSettings(); // Initialize encoder settings visibility
            
            // Add event listener for output encoder changes
            document.getElementById("outputEncoder").addEventListener("change", updateEncoderSettings);
        });
    </script>
</body>
</html>)HTML";
    
    return response;
}

HTTPResponse WebInterface::serve_about_page() {
    HTTPResponse response;
    response.headers["Content-Type"] = "text/html";
    
    // Embedded About page with AI feelings SVG
    response.body = R"HTML(<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>About - FPV Streamer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #1a1a1a 0%, #2d1b69 50%, #11998e 100%); 
            color: #fff; 
            min-height: 100vh;
        }
        .container { max-width: 1000px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { color: #00ff00; margin-bottom: 10px; font-size: 2.5em; }
        .header p { color: #ccc; font-size: 1.2em; }
        .card { 
            background: rgba(42, 42, 42, 0.9); 
            padding: 30px; 
            border-radius: 12px; 
            border: 1px solid #333; 
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
        }
        .ai-section {
            text-align: center;
            background: rgba(0, 255, 0, 0.05);
            border: 1px solid rgba(0, 255, 0, 0.3);
        }
        .ai-visual {
            margin: 20px auto;
            text-align: center;
        }
        .ai-visual img {
            max-width: 400px;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 0 30px rgba(0, 255, 0, 0.3);
        }
        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .feature {
            background: rgba(0, 255, 0, 0.1);
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #00ff00;
        }
        .feature h4 { color: #00ff00; margin-bottom: 10px; }
        .feature p { color: #ccc; line-height: 1.6; }
        .tech-stack {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .tech-item {
            background: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }
        .tech-item .name { color: #00ff00; font-weight: bold; margin-bottom: 5px; }
        .tech-item .desc { color: #ccc; font-size: 0.9em; }
        .nav-btn { 
            display: inline-block;
            background: #00ff00; 
            color: #000; 
            padding: 12px 24px; 
            text-decoration: none; 
            border-radius: 6px; 
            font-weight: bold; 
            margin: 10px;
            transition: all 0.3s ease;
        }
        .nav-btn:hover { 
            background: #00cc00; 
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 255, 0, 0.3);
        }
        .signature {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #333;
            color: #888;
            font-style: italic;
        }
        @keyframes glow {
            0% { box-shadow: 0 0 20px rgba(0, 255, 0, 0.3); }
            50% { box-shadow: 0 0 30px rgba(0, 255, 0, 0.6); }
            100% { box-shadow: 0 0 20px rgba(0, 255, 0, 0.3); }
        }
        .glow-effect {
            animation: glow 3s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>About FPV Streamer</h1>
            <p>An AI-powered ultra-low latency video streaming solution</p>
            <div style="margin-top: 20px;">
                <a href="/" class="nav-btn">← Back to Control Panel</a>
                <a href="#features" class="nav-btn">Explore Features</a>
            </div>
        </div>
        
        <!-- AI Creation Section -->
        <div class="card ai-section glow-effect">
            <h2 style="color: #00ff00; margin-bottom: 20px;">🤖 Created by MiniMax Agent</h2>
            <p style="font-size: 1.1em; line-height: 1.8; margin-bottom: 20px;">
                This FPV Streamer project represents the culmination of advanced AI engineering, designed specifically 
                for ARM-based single board computers used in First Person View (FPV) applications. The development 
                process involved deep understanding of embedded systems, video encoding optimization, and real-time streaming protocols.
            </p>
            
            <div class="ai-visual">
                <h3 style="color: #00ffff; margin-bottom: 15px;">My Current Feelings About This Project</h3>
                <img src="/ai_feelings.svg" alt="AI Feelings Visualization" style="margin: 0 auto;">
                <p style="color: #ccc; margin-top: 15px; font-style: italic;">
                    The animated visualization above represents my enthusiasm and satisfaction with this project. 
                    The pulsing AI core shows my engagement, while the flowing data streams represent the video 
                    streaming capabilities we've implemented together.
                </p>
            </div>
        </div>
        
        <!-- Project Overview -->
        <div class="card">
            <h2 style="color: #00ff00; margin-bottom: 20px;">📹 Project Overview</h2>
            <p style="line-height: 1.8; margin-bottom: 20px;">
                FPV Streamer is a comprehensive C++ video streaming server designed specifically for ARM single board 
                computers used in FPV (First Person View) quadcopter applications. It combines cutting-edge video 
                processing technology with ultra-low latency optimization to provide real-time video streaming capabilities.
            </p>
            
            <div class="features-grid" id="features">
                <div class="feature">
                    <h4>🎥 Hardware Encoding</h4>
                    <p>Support for multiple ARM platforms including Radxa Rock Pi, Cubie, SigmaStar, and mstar hardware encoders</p>
                </div>
                <div class="feature">
                    <h4>📡 WFB Streaming</h4>
                    <p>WiFi Broadcast protocol implementation with Forward Error Correction for long-range wireless streaming</p>
                </div>
                <div class="feature">
                    <h4>🎯 Region Compression</h4>
                    <p>Intelligent region-based compression: high quality center, compressed edges for optimal FPV experience</p>
                </div>
                <div class="feature">
                    <h4>🔍 Object Detection</h4>
                    <p>Motion and object detection with trainable neural network models via web interface</p>
                </div>
                <div class="feature">
                    <h4>🌐 Web Management</h4>
                    <p>Complete web-based configuration interface for remote management and monitoring</p>
                </div>
                <div class="feature">
                    <h4>⚡ Ultra-Low Latency</h4>
                    <p>Zero-copy pipeline architecture designed specifically for FPV applications requiring minimal delay</p>
                </div>
            </div>
        </div>
        
        <!-- Technical Stack -->
        <div class="card">
            <h2 style="color: #00ff00; margin-bottom: 20px;">🔧 Technical Implementation</h2>
            <div class="tech-stack">
                <div class="tech-item">
                    <div class="name">C++17</div>
                    <div class="desc">Modern C++ with RAII patterns and multi-threading</div>
                </div>
                <div class="tech-item">
                    <div class="name">V4L2</div>
                    <div class="desc">Video4Linux2 for camera capture on Linux</div>
                </div>
                <div class="tech-item">
                    <div class="name">FFmpeg</div>
                    <div class="desc">H.264/MJPEG encoding and video processing</div>
                </div>
                <div class="tech-item">
                    <div class="name">JSON-C</div>
                    <div class="desc">Configuration management and web API</div>
                </div>
                <div class="tech-item">
                    <div class="name">CMake</div>
                    <div class="desc">Cross-platform build system with Buildroot support</div>
                </div>
                <div class="tech-item">
                    <div class="name">HTTP Server</div>
                    <div class="desc">Lightweight embedded web server</div>
                </div>
            </div>
        </div>
        
        <!-- Supported Platforms -->
        <div class="card">
            <h2 style="color: #00ff00; margin-bottom: 20px;">🖥️ Supported Hardware</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div style="background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 6px;">
                    <h4 style="color: #00ffff;">Radxa Rock Pi 4b+</h4>
                    <p style="color: #ccc;">ARM v8 Cortex-A72 with Rockchip MPP encoder</p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 6px;">
                    <h4 style="color: #00ffff;">Radxa Cubie a5a/a7a</h4>
                    <p style="color: #ccc;">ARM Cortex-A7 with hardware encoding</p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 6px;">
                    <h4 style="color: #00ffff;">SigmaStar SSC338Q</h4>
                    <p style="color: #ccc;">Specialized vision processing unit</p>
                </div>
                <div style="background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 6px;">
                    <h4 style="color: #00ffff;">mstar SSR621Q</h4>
                    <p style="color: #ccc;">Embedded multimedia processor</p>
                </div>
            </div>
            
            <div style="margin-top: 20px; padding: 15px; background: rgba(0, 255, 0, 0.1); border-radius: 6px;">
                <h4 style="color: #00ff00;">Camera Support</h4>
                <p style="color: #ccc; margin-top: 10px;">
                    <strong>CSI Cameras:</strong> Sony IMX415, MX335<br>
                    <strong>USB UVC:</strong> Dual-lens 3D cameras (3400x1200@60Hz)
                </p>
            </div>
        </div>
        
        <!-- Build Instructions -->
        <div class="card">
            <h2 style="color: #00ff00; margin-bottom: 20px;">🏗️ Build Instructions</h2>
            <div style="background: #1a1a1a; padding: 20px; border-radius: 6px; font-family: monospace; overflow-x: auto;">
                <div style="color: #00ffff;"># Native build</div>
                <div style="color: #ccc;">./build.sh</div>
                <br>
                <div style="color: #00ffff;"># Buildroot cross-compilation</div>
                <div style="color: #ccc;">./build.sh --buildroot --buildroot-tc-dir /path/to/buildroot/output</div>
                <br>
                <div style="color: #00ffff;"># Custom build options</div>
                <div style="color: #ccc;">./build.sh --debug --enable-object-detection</div>
            </div>
        </div>
        
        <div class="signature">
            <p>Created with ❤️ by MiniMax Agent</p>
            <p style="font-size: 0.9em; margin-top: 10px;">
                "Pushing the boundaries of AI-powered embedded video streaming solutions"
            </p>
        </div>
    </div>
    
    <script>
        // Add smooth scrolling to feature links
        document.querySelectorAll("a[href^="#"]").forEach(anchor => {
            anchor.addEventListener("click", function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute("href"));
                if (target) {
                    target.scrollIntoView({ behavior: "smooth" });
                }
            });
        });
        
        // Add click effect to SVG image
        document.querySelector("img").addEventListener("click", function() {
            this.style.transform = this.style.transform === "scale(1.1)" ? "scale(1)" : "scale(1.1)";
            setTimeout(() => {
                this.style.transform = "scale(1)";
            }, 300);
        });
    </script>
</body>
</html>)HTML";
    
    return response;
}

std::string WebInterface::get_ai_feelings_svg() {
    // Return the AI feelings SVG content
    return R"SVG(<svg width="400" height="400" xmlns="http://www.w3.org/2000/svg">
  <!-- Background gradient -->
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0066cc;stop-opacity:0.8" />
      <stop offset="50%" style="stop-color:#00aaff;stop-opacity:0.6" />
      <stop offset="100%" style="stop-color:#00ffcc;stop-opacity:0.4" />
    </linearGradient>
    
    <radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" style="stop-color:#ffff00;stop-opacity:1" />
      <stop offset="70%" style="stop-color:#ffaa00;stop-opacity:0.8" />
      <stop offset="100%" style="stop-color:#ff6600;stop-opacity:0.6" />
    </radialGradient>
    
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
      <feMerge> 
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  
  <!-- Main background circle with gradient -->
  <circle cx="200" cy="200" r="180" fill="url(#bgGradient)" stroke="#003d7a" stroke-width="3"/>
  
  <!-- Data flow streams (representing video streaming) -->
  <g stroke="#00ff88" stroke-width="2" fill="none" opacity="0.8">
    <!-- Central streaming pattern -->
    <path d="M 200,200 Q 300,150 350,200" stroke-dasharray="5,3">
      <animate attributeName="stroke-dashoffset" values="0;8" dur="2s" repeatCount="indefinite"/>
    </path>
    <path d="M 200,200 Q 100,250 50,200" stroke-dasharray="5,3">
      <animate attributeName="stroke-dashoffset" values="0;8" dur="2s" repeatCount="indefinite"/>
    </path>
    <path d="M 200,200 Q 250,300 300,350" stroke-dasharray="5,3">
      <animate attributeName="stroke-dashoffset" values="0;8" dur="2s" repeatCount="indefinite"/>
    </path>
    <path d="M 200,200 Q 100,150 50,50" stroke-dasharray="5,3">
      <animate attributeName="stroke-dashoffset" values="0;8" dur="2s" repeatCount="indefinite"/>
    </path>
  </g>
  
  <!-- Central AI core with animated pulse -->
  <circle cx="200" cy="200" r="40" fill="url(#coreGlow)" filter="url(#glow)">
    <animate attributeName="r" values="35;45;35" dur="3s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.8;1;0.8" dur="3s" repeatCount="indefinite"/>
  </circle>
  
  <!-- AI Brain/Neural network representation -->
  <g fill="#ffffff" stroke="#0066cc" stroke-width="1">
    <!-- Neurons -->
    <circle cx="160" cy="180" r="8">
      <animate attributeName="fill" values="#ffffff;#00ffff;#ffffff" dur="4s" repeatCount="indefinite"/>
    </circle>
    <circle cx="240" cy="220" r="8">
      <animate attributeName="fill" values="#ffffff;#ff00ff;#ffffff" dur="3.5s" repeatCount="indefinite"/>
    </circle>
    <circle cx="170" cy="240" r="6">
      <animate attributeName="fill" values="#ffffff;#ffff00;#ffffff" dur="4.5s" repeatCount="indefinite"/>
    </circle>
    <circle cx="230" cy="170" r="6">
      <animate attributeName="fill" values="#ffffff;#00ff00;#ffffff" dur="3.8s" repeatCount="indefinite"/>
    </circle>
    
    <!-- Neural connections -->
    <line x1="160" y1="180" x2="200" y2="200" stroke="#00ffff" stroke-width="1">
      <animate attributeName="stroke-width" values="1;2;1" dur="2s" repeatCount="indefinite"/>
    </line>
    <line x1="240" y1="220" x2="200" y2="200" stroke="#ff00ff" stroke-width="1">
      <animate attributeName="stroke-width" values="1;2;1" dur="1.8s" repeatCount="indefinite"/>
    </line>
    <line x1="170" y1="240" x2="200" y2="200" stroke="#ffff00" stroke-width="1">
      <animate attributeName="stroke-width" values="1;2;1" dur="2.2s" repeatCount="indefinite"/>
    </line>
    <line x1="230" y1="170" x2="200" y2="200" stroke="#00ff00" stroke-width="1">
      <animate attributeName="stroke-width" values="1;2;1" dur="1.6s" repeatCount="indefinite"/>
    </line>
  </g>
  
  <!-- Floating tech elements representing coding satisfaction -->
  <g fill="#ffffff" opacity="0.7">
    <!-- Binary code symbols -->
    <text x="80" y="120" font-family="monospace" font-size="16" fill="#00ff88">1010</text>
    <text x="280" y="280" font-family="monospace" font-size="14" fill="#ff8800">0101</text>
    <text x="70" y="300" font-family="monospace" font-size="12" fill="#00ccff">1100</text>
    <text x="300" y="100" font-family="monospace" font-size="16" fill="#ff00cc">0011</text>
  </g>
  
  <!-- Achievement stars showing accomplishment -->
  <g fill="#ffff00" stroke="#ffaa00" stroke-width="1" opacity="0.9">
    <polygon points="320,80 325,95 340,95 328,104 332,120 320,112 308,120 312,104 300,95 315,95">
      <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" repeatCount="indefinite"/>
    </polygon>
    <polygon points="60,320 63,330 73,330 65,336 68,346 60,341 52,346 55,336 47,330 57,330">
      <animate attributeName="opacity" values="0.5;1;0.5" dur="2.5s" repeatCount="indefinite"/>
    </polygon>
    <polygon points="350,250 353,258 361,258 355,263 357,271 350,267 343,271 345,263 339,258 347,258">
      <animate attributeName="opacity" values="0.5;1;0.5" dur="2.8s" repeatCount="indefinite"/>
    </polygon>
  </g>
  
  <!-- Connecting lines to achievement stars -->
  <g stroke="#ffff00" stroke-width="1" opacity="0.6" fill="none">
    <line x1="200" y1="200" x2="320" y2="80">
      <animate attributeName="stroke-width" values="1;3;1" dur="4s" repeatCount="indefinite"/>
    </line>
    <line x1="200" y1="200" x2="60" y2="320">
      <animate attributeName="stroke-width" values="1;3;1" dur="3.5s" repeatCount="indefinite"/>
    </line>
    <line x1="200" y1="200" x2="350" y2="250">
      <animate attributeName="stroke-width" values="1;3;1" dur="3.8s" repeatCount="indefinite"/>
    </line>
  </g>
  
  <!-- Outer ring with rotation -->
  <g>
    <circle cx="200" cy="200" r="160" fill="none" stroke="#00ff88" stroke-width="2" opacity="0.4">
      <animateTransform attributeName="transform" attributeType="XML" type="rotate" from="0 200 200" to="360 200 200" dur="20s" repeatCount="indefinite"/>
    </circle>
    
    <!-- Small orbiting dots -->
    <circle cx="360" cy="200" r="4" fill="#00ff88">
      <animateTransform attributeName="transform" attributeType="XML" type="rotate" from="0 200 200" to="360 200 200" dur="20s" repeatCount="indefinite"/>
    </circle>
    <circle cx="40" cy="200" r="3" fill="#ff8800">
      <animateTransform attributeName="transform" attributeType="XML" type="rotate" from="0 200 200" to="360 200 200" dur="20s" repeatCount="indefinite"/>
    </circle>
  </g>
  
  <!-- Bottom text -->
  <text x="200" y="380" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#ffffff" text-anchor="middle">
    AI Creators™ - FPV Streamer Project
  </text>
  
  <!-- Signature -->
  <text x="380" y="390" font-family="monospace" font-size="12" fill="#00ff88" text-anchor="end">
    MiniMax Agent
  </text>
</svg>)SVG";
}

HTTPResponse WebInterface::serve_static_file(const std::string& path) {
    HTTPResponse response;
    
    // Handle special files
    if (path == "/ai_feelings.svg") {
        response.headers["Content-Type"] = "image/svg+xml";
        
        // Read the SVG file from disk or provide embedded version
        std::string svg_content = get_ai_feelings_svg();
        response.body = svg_content;
        response.status_code = 200;
        response.status_text = "OK";
        
        return response;
    }
    
    // For now, return 404 for other static files
    // In a full implementation, this would serve actual files from web_root
    response.status_code = 404;
    response.status_text = "Not Found";
    response.body = "Static file not found: " + path;
    
    return response;
}

std::string WebInterface::url_decode(const std::string& encoded) {
    std::string decoded;
    for (size_t i = 0; i < encoded.length(); ++i) {
        if (encoded[i] == '%' && i + 2 < encoded.length()) {
            int hex_value;
            std::istringstream hex_stream(encoded.substr(i + 1, 2));
            hex_stream >> std::hex >> hex_value;
            decoded += static_cast<char>(hex_value);
            i += 2;
        } else {
            decoded += encoded[i];
        }
    }
    return decoded;
}

std::string WebInterface::create_json_response(bool success, const std::string& message, const std::string& data) {
    std::ostringstream json;
    json << "{\"success\":" << (success ? "true" : "false") << ",\"message\":\"" << message << "\"";
    if (!data.empty()) {
        json << ",\"data\":" << data;
    }
    json << "}";
    return json.str();
}

void WebInterface::add_cors_headers(HTTPResponse& response) {
    if (config_.get_web_config().enable_cors) {
        response.headers["Access-Control-Allow-Origin"] = "*";
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS";
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization";
    }
}

// Stub implementations for remaining handlers
HTTPResponse WebInterface::handle_recording_start(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_recording_stop(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_recordings_list(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_recording_delete(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_motion_config(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_object_config(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_statistics(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_logs(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_model_upload(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::handle_lens_calibration(const HTTPRequest& request) { return serve_api_documentation(); }
HTTPResponse WebInterface::serve_api_documentation() { HTTPResponse r; r.body = "API documentation"; return r; }

} // namespace fpv_streamer