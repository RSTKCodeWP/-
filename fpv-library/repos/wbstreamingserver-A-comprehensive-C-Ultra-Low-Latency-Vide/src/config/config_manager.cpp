#include "config/config_manager.h"
#include "utils/utils.h"
#include <iostream>
#include <fstream>
#include <algorithm>
#include <sstream>
#include <unistd.h>
#include <sys/utsname.h>

namespace fpv_streamer {

ConfigManager::ConfigManager() {
    load_defaults();
    detect_hardware_capabilities();
}

bool ConfigManager::initialize(int argc, char* argv[]) {
    load_defaults();
    parse_arguments(argc, argv);
    
    if (!config_file_.empty()) {
        if (!load_from_file(config_file_)) {
            Logger::warn("Failed to load config file: " + config_file_);
        }
    }
    
    validate_config();
    Logger::info("Configuration initialized successfully");
    Logger::info("Platform: " + hardware_caps_.platform_type);
    Logger::info("Hardware encoder available: " + std::string(hardware_caps_.has_hardware_encoder ? "yes" : "no"));
    
    return true;
}

bool ConfigManager::load_from_file(const std::string& file_path) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    
    std::ifstream file(file_path);
    if (!file.is_open()) {
        Logger::error("Cannot open config file: " + file_path);
        return false;
    }
    
    try {
        // Simple JSON-like parsing for basic config
        std::string line;
        while (std::getline(file, line)) {
            // Remove whitespace
            line.erase(std::remove_if(line.begin(), line.end(), ::isspace), line.end());
            
            if (line.empty() || line[0] == '#') continue;
            
            size_t pos = line.find('=');
            if (pos == std::string::npos) continue;
            
            std::string key = line.substr(0, pos);
            std::string value = line.substr(pos + 1);
            
            // Remove quotes if present
            if (value.front() == '"' && value.back() == '"') {
                value = value.substr(1, value.length() - 2);
            }
            
            // Parse specific config values
            if (key == "video.device_path") {
                video_config_.device_path = value;
            } else if (key == "video.width") {
                video_config_.width = std::stoi(value);
            } else if (key == "video.height") {
                video_config_.height = std::stoi(value);
            } else if (key == "video.fps") {
                video_config_.fps = std::stoi(value);
            } else if (key == "video.bitrate") {
                video_config_.bitrate = std::stoi(value);
            } else if (key == "stream.port") {
                stream_config_.port = std::stoi(value);
            } else if (key == "web.port") {
                web_config_.port = std::stoi(value);
            } else if (key == "recording.enable") {
                recording_config_.enable_recording = (value == "true");
            } else if (key == "stereo.enable") {
                stereo_config_.enable_stereo = (value == "true");
            } else if (key == "stereo.camera2_device") {
                stereo_config_.camera2_device = std::stoi(value);
            } else if (key == "stereo.mode") {
                stereo_config_.stereo_mode = std::stoi(value);
            } else if (key == "stereo.separation") {
                stereo_config_.stereo_separation = std::stoi(value);
            } else if (key == "stereo.convergence") {
                stereo_config_.stereo_convergence = std::stoi(value);
            } else if (key == "stereo.offset_x") {
                stereo_config_.stereo_offset_x = std::stoi(value);
            } else if (key == "stereo.offset_y") {
                stereo_config_.stereo_offset_y = std::stoi(value);
            } else if (key == "stereo.zoom") {
                stereo_config_.stereo_zoom = std::stof(value);
            } else if (key == "stereo.flip_mode") {
                stereo_config_.stereo_flip_mode = std::stoi(value);
            } else if (key == "stereo.color_correction") {
                stereo_config_.enable_color_correction = (value == "true");
            } else if (key == "stereo.color_strength") {
                stereo_config_.color_correction_strength = std::stoi(value);
            } else if (key == "stereo.save_settings") {
                stereo_config_.save_user_settings = (value == "true");
            }
        }
        
        Logger::info("Config loaded from: " + file_path);
        return true;
        
    } catch (const std::exception& e) {
        Logger::error("Error parsing config file: " + std::string(e.what()));
        return false;
    }
}

bool ConfigManager::save_to_file(const std::string& file_path) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    
    std::ofstream file(file_path);
    if (!file.is_open()) {
        Logger::error("Cannot create config file: " + file_path);
        return false;
    }
    
    // Simple key=value format
    file << "# FPV Streamer Configuration\n";
    file << "# Generated: " << std::time(nullptr) << "\n\n";
    
    file << "video.device_path=" << video_config_.device_path << "\n";
    file << "video.width=" << video_config_.width << "\n";
    file << "video.height=" << video_config_.height << "\n";
    file << "video.fps=" << video_config_.fps << "\n";
    file << "video.bitrate=" << video_config_.bitrate << "\n";
    file << "video.quality=" << video_config_.quality << "\n";
    file << "video.use_hardware_encoder=" << (video_config_.use_hardware_encoder ? "true" : "false") << "\n";
    
    file << "stream.port=" << stream_config_.port << "\n";
    file << "stream.interface=" << stream_config_.interface << "\n";
    file << "stream.enable_fec=" << (stream_config_.enable_fec ? "true" : "false") << "\n";
    
    file << "web.port=" << web_config_.port << "\n";
    file << "web.enable_api=" << (web_config_.enable_api ? "true" : "false") << "\n";
    
    file << "recording.enable=" << (recording_config_.enable_recording ? "true" : "false") << "\n";
    file << "recording.output_directory=" << recording_config_.output_directory << "\n";
    
    file << "detection.motion=" << (detection_config_.enable_motion_detection ? "true" : "false") << "\n";
    file << "detection.object=" << (detection_config_.enable_object_detection ? "true" : "false") << "\n";
    
    // Stereo settings
    file << "stereo.enable=" << (stereo_config_.enable_stereo ? "true" : "false") << "\n";
    file << "stereo.camera2_device=" << stereo_config_.camera2_device << "\n";
    file << "stereo.mode=" << stereo_config_.stereo_mode << "\n";
    file << "stereo.separation=" << stereo_config_.stereo_separation << "\n";
    file << "stereo.convergence=" << stereo_config_.stereo_convergence << "\n";
    file << "stereo.offset_x=" << stereo_config_.stereo_offset_x << "\n";
    file << "stereo.offset_y=" << stereo_config_.stereo_offset_y << "\n";
    file << "stereo.zoom=" << stereo_config_.stereo_zoom << "\n";
    file << "stereo.flip_mode=" << stereo_config_.stereo_flip_mode << "\n";
    file << "stereo.color_correction=" << (stereo_config_.enable_color_correction ? "true" : "false") << "\n";
    file << "stereo.color_strength=" << stereo_config_.color_correction_strength << "\n";
    file << "stereo.save_settings=" << (stereo_config_.save_user_settings ? "true" : "false") << "\n";
    
    Logger::info("Config saved to: " + file_path);
    return true;
}

void ConfigManager::load_defaults() {
    // Generic defaults
    config_file_ = "/etc/wbstreamingserver.conf";

    // Video defaults
    video_config_ = VideoConfig{
        .device_path = "/dev/video0",
        .width = 1920,
        .height = 1080,
        .fps = 60,
        .input_format = "auto",
        .input_pixel_format = 0,
        .use_hardware_encoder = true,
        .output_encoder = "h264",
        .bitrate = 1000000,
        .quality = 80,
        .enable_region_compression = true,
        .center_quality_factor = 0.8f,
        .edge_compression_factor = 0.6f,
        .enable_mjpeg_compression = false,
        .mjpeg_quality = 80,
        .mjpeg_optimization_level = 2,
        .enable_h265_profile = true,
        .h265_profile = 1,
        .h265_level = 4,
        .pixel_format = 0,
        .enable_dual_camera = false,
        .camera2_width = 1920,
        .camera2_height = 1080,
        .camera2_fps = 60,
        .camera2_input_format = "auto",
        .enable_frame_sync = true,
        .frame_sync_timeout_ms = 100
    };
    
    // Stereo defaults
    stereo_config_ = StereoConfig{
        .enable_stereo = false,
        .camera2_device = 2,
        .stereo_mode = 0,
        .stereo_separation = 63,
        .stereo_convergence = 0,
        .stereo_offset_x = 0,
        .stereo_offset_y = 0,
        .stereo_zoom = 1.0f,
        .stereo_flip_mode = 0,
        .enable_color_correction = true,
        .color_correction_strength = 80,
        .save_user_settings = true,
        .calibration_points = 9
    };
    
    // Stream defaults
    stream_config_ = StreamConfig{
        .protocol = "wfb",
        .interface = "wlan0",
        .port = 5600,
        .buffer_size = 32768,
        .enable_fec = true,
        .fec_redundancy = 2,
        .packet_size = 1024,
        .enable_adaptive_bitrate = true
    };
    
    // Detection defaults
    detection_config_ = DetectionConfig{
        .enable_motion_detection = false,
        .motion_sensitivity = 50,
        .motion_threshold = 1000,
        .enable_object_detection = false,
        .object_model_path = "",
        .detection_confidence = 70,
        .enable_lens_correction = false,
        .lens_distortion_k1 = 0.0f,
        .lens_distortion_k2 = 0.0f,
        .lens_distortion_k3 = 0.0f,
        .lens_fov = 90.0f
    };
    
    // Web defaults
    web_config_ = WebConfig{
        .port = 8080,
        .web_root = "/var/www/fpv-streamer",
        .enable_api = true,
        .enable_cors = true,
        .enable_authentication = false,
        .auth_username = "admin",
        .auth_password = "admin"
    };
    
    // Recording defaults
    recording_config_ = RecordingConfig{
        .enable_recording = false,
        .output_directory = "/var/recordings",
        .max_file_size_mb = 500,
        .max_file_duration_sec = 300,
        .format = "mp4",
        .recording_quality = 80,
        .auto_delete_old = true,
        .max_days_to_keep = 7
    };
}

void ConfigManager::parse_arguments(int argc, char* argv[]) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        
        if (arg == "-h" || arg == "--help") {
            std::cout << "Usage: " << argv[0] << " [options]\n";
            std::cout << "Options:\n";
            std::cout << "  -h, --help              Show this help\n";
            std::cout << "  -c, --config FILE       Config file path\n";
            std::cout << "  -d, --device DEVICE     Video device path\n";
            std::cout << "  -w, --width WIDTH       Video width\n";
            std::cout << "  -H, --height HEIGHT     Video height\n";
            std::cout << "  -f, --fps FPS           Video framerate\n";
            std::cout << "  -p, --port PORT         Web interface port\n";
            std::cout << "  -v, --verbose           Verbose logging\n";
            exit(0);
        } else if (arg == "-c" || arg == "--config") {
            if (i + 1 < argc) config_file_ = argv[++i];
        } else if (arg == "-d" || arg == "--device") {
            if (i + 1 < argc) video_config_.device_path = argv[++i];
        } else if (arg == "-w" || arg == "--width") {
            if (i + 1 < argc) video_config_.width = std::stoi(argv[++i]);
        } else if (arg == "-H" || arg == "--height") {
            if (i + 1 < argc) video_config_.height = std::stoi(argv[++i]);
        } else if (arg == "-f" || arg == "--fps") {
            if (i + 1 < argc) video_config_.fps = std::stoi(argv[++i]);
        } else if (arg == "-p" || arg == "--port") {
            if (i + 1 < argc) web_config_.port = std::stoi(argv[++i]);
        } else if (arg == "-v" || arg == "--verbose") {
            Logger::set_verbose(true);
        }
    }
}

void ConfigManager::validate_config() {
    // Ensure video settings are reasonable
    if (video_config_.width <= 0 || video_config_.height <= 0) {
        Logger::warn("Invalid video dimensions, using defaults");
        video_config_.width = 1920;
        video_config_.height = 1080;
    }
    
    if (video_config_.fps <= 0 || video_config_.fps > 120) {
        Logger::warn("Invalid framerate, using default (60)");
        video_config_.fps = 60;
    }
    
    if (video_config_.bitrate < 100000) {
        Logger::warn("Bitrate too low, using minimum 100kbps");
        video_config_.bitrate = 100000;
    }
    
    // Check hardware encoder availability
    if (video_config_.use_hardware_encoder && !hardware_caps_.has_hardware_encoder) {
        Logger::warn("Hardware encoder not available, falling back to software");
        video_config_.use_hardware_encoder = false;
    }
}

void ConfigManager::detect_hardware_capabilities() {
    struct utsname unameData;
    if (uname(&unameData) == 0) {
        hardware_caps_.platform_type = unameData.machine;
        hardware_caps_.cpu_info = std::string(unameData.machine) + " " + unameData.release;
    }
    
    // Check for VCHIQ (Raspberry Pi)
    if (access("/dev/vchiq", F_OK) == 0) {
        hardware_caps_.has_vchiq = true;
        hardware_caps_.has_hardware_encoder = true;
    }
    
    // Check for MMAL
    if (access("/opt/vc/include/interface/mmal/mmal.h", F_OK) == 0) {
        hardware_caps_.has_mmal = true;
    }
    
    // Check for specific encoders
    hardware_caps_.available_encoders = {"h264", "mjpeg"};
    
    Logger::info("Hardware detection complete");
    Logger::info("Platform: " + hardware_caps_.platform_type);
}

void ConfigManager::update_video_config(const VideoConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    video_config_ = config;
    Logger::info("Video config updated");
}

void ConfigManager::update_stream_config(const StreamConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    stream_config_ = config;
    Logger::info("Stream config updated");
}

void ConfigManager::update_detection_config(const DetectionConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    detection_config_ = config;
    Logger::info("Detection config updated");
}

void ConfigManager::update_web_config(const WebConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    web_config_ = config;
    Logger::info("Web config updated");
}

void ConfigManager::update_recording_config(const RecordingConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    recording_config_ = config;
    Logger::info("Recording config updated");
}

void ConfigManager::update_stereo_config(const StereoConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    stereo_config_ = config;
    Logger::info("Stereo config updated");
}

void ConfigManager::update_bitrate(int new_bitrate) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    video_config_.bitrate = std::max(100000, std::min(10000000, new_bitrate));
    Logger::info("Bitrate updated to: " + std::to_string(video_config_.bitrate));
}

void ConfigManager::update_quality(int new_quality) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    video_config_.quality = std::max(1, std::min(100, new_quality));
    Logger::info("Quality updated to: " + std::to_string(video_config_.quality));
}

void ConfigManager::toggle_motion_detection(bool enable) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    detection_config_.enable_motion_detection = enable;
    Logger::info("Motion detection " + std::string(enable ? "enabled" : "disabled"));
}

void ConfigManager::toggle_object_detection(bool enable) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    detection_config_.enable_object_detection = enable;
    Logger::info("Object detection " + std::string(enable ? "enabled" : "disabled"));
}

void ConfigManager::update_object_model(const std::string& model_path) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    detection_config_.object_model_path = model_path;
    Logger::info("Object model updated: " + model_path);
}

} // namespace fpv_streamer