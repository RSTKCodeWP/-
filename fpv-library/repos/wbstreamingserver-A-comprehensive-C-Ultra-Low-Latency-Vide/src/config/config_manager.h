#pragma once

#include <string>
#include <unordered_map>
#include <memory>
#include <vector>
#include <mutex>

namespace fpv_streamer {

// Configuration structure
struct VideoConfig {
    std::string device_path = "/dev/video0";
    int width = 1920;
    int height = 1080;
    int fps = 60;
    
    // Input format from camera (USB UVC)
    std::string input_format = "auto"; // auto, mjpeg, h264, raw
    int input_pixel_format = 0; // V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_H264, V4L2_PIX_FMT_YUV420
    
    // Output encoding
    bool use_hardware_encoder = true;
    std::string output_encoder = "h264"; // h264, h265, mjpeg
    std::string encoder_type = "h264";   // Current encoder type being used
    int bitrate = 2000000;
    
    // Quality settings
    int quality = 80; // 1-100
    bool enable_region_compression = true;
    float center_quality_factor = 0.8f; // Higher quality in center
    float edge_compression_factor = 0.6f; // Lower quality at edges
    
    // MJPEG compression settings
    bool enable_mjpeg_compression = false;
    int mjpeg_quality = 80; // 1-100 for MJPEG output
    int mjpeg_optimization_level = 2; // 0-3 for compression optimization
    
    // H.265 specific settings
    bool enable_h265_profile = false; // Main, Main10, etc.
    int h265_profile = 1; // 0=Main, 1=Main10, 2=MainStillPicture
    int h265_level = 4.0f; // H.265 level (4.0, 5.0, etc.)
    
    // Legacy pixel_format for compatibility
    int pixel_format = 0; // V4L2_PIX_FMT_YUV420
    
    // Dual camera settings
    bool enable_dual_camera = false;
    int camera2_width = 1920;
    int camera2_height = 1080;
    int camera2_fps = 60;
    std::string camera2_input_format = "auto"; // auto, mjpeg, h264, raw
    bool enable_frame_sync = true; // Sync frames between cameras
    int frame_sync_timeout_ms = 100; // Timeout for frame synchronization
};

struct StreamConfig {
    std::string protocol = "wfb";
    std::string interface = "wlan0";
    int port = 5600;
    int buffer_size = 32768;
    bool enable_fec = true;
    int fec_redundancy = 2;
    int packet_size = 1024;
    bool enable_adaptive_bitrate = true;
};

struct StereoConfig {
    bool enable_stereo = false; // Enable dual camera 3D mode
    int camera2_device = 2; // /dev/video2 for second camera
    int stereo_mode = 0; // 0=side-by-side, 1=top-bottom, 2=over-under
    int stereo_separation = 63; // mm between cameras (default 63mm human eye)
    int stereo_convergence = 0; // convergence offset in pixels (-100 to 100)
    int stereo_offset_x = 0; // horizontal alignment offset (-50 to 50)
    int stereo_offset_y = 0; // vertical alignment offset (-30 to 30)
    float stereo_zoom = 1.0f; // zoom factor for alignment (0.5 to 2.0)
    int stereo_flip_mode = 0; // 0=none, 1=flip camera1, 2=flip camera2, 3=flip both
    bool enable_color_correction = true; // Match color/brightness between cameras
    int color_correction_strength = 80; // 1-100
    bool save_user_settings = true; // Save stereo adjustments
    int calibration_points = 9; // Number of calibration points (3x3, 5x5, etc.)
    bool enable_frame_sync = true; // Enable frame synchronization between cameras
};

struct DetectionConfig {
    bool enable_motion_detection = true;
    int motion_sensitivity = 50; // 1-100
    int motion_threshold = 1000;
    bool enable_object_detection = true;
    std::string object_model_path = "";
    int detection_confidence = 70; // 1-100
    bool enable_lens_correction = false;
    float lens_distortion_k1 = 0.0f;
    float lens_distortion_k2 = 0.0f;
    float lens_distortion_k3 = 0.0f;
    float lens_fov = 90.0f;
    int width = 1920; // Video width for detection
    int height = 1080; // Video height for detection
};

struct WebConfig {
    int port = 8080;
    std::string web_root = "/var/www/fpv-streamer";
    bool enable_api = true;
    bool enable_cors = true;
    bool enable_authentication = false;
    std::string auth_username = "admin";
    std::string auth_password = "admin";
};

struct RecordingConfig {
    bool enable_recording = false;
    std::string output_directory = "/var/recordings";
    int max_file_size_mb = 500;
    int max_file_duration_sec = 300;
    std::string format = "mp4";
    int recording_quality = 80;
    bool auto_delete_old = true;
    int max_days_to_keep = 7;
};

class ConfigManager {
public:
    ConfigManager();
    ~ConfigManager() = default;
    
    bool initialize(int argc, char* argv[]);
    bool load_from_file(const std::string& file_path);
    bool save_to_file(const std::string& file_path);
    
    // Getters
    const VideoConfig& get_video_config() const { return video_config_; }
    const StreamConfig& get_stream_config() const { return stream_config_; }
    const DetectionConfig& get_detection_config() const { return detection_config_; }
    const WebConfig& get_web_config() const { return web_config_; }
    const RecordingConfig& get_recording_config() const { return recording_config_; }
    const StereoConfig& get_stereo_config() const { return stereo_config_; }
    
    // Setters
    void update_video_config(const VideoConfig& config);
    void update_stream_config(const StreamConfig& config);
    void update_detection_config(const DetectionConfig& config);
    void update_web_config(const WebConfig& config);
    void update_recording_config(const RecordingConfig& config);
    void update_stereo_config(const StereoConfig& config);
    
    // Dynamic updates
    void update_bitrate(int new_bitrate);
    void update_quality(int new_quality);
    void toggle_motion_detection(bool enable);
    void toggle_object_detection(bool enable);
    void update_object_model(const std::string& model_path);
    
    // Hardware detection
    void detect_hardware_capabilities();
    bool has_hardware_encoder() const { return hardware_caps_.has_hardware_encoder; }
    bool has_mmal() const { return hardware_caps_.has_mmal; }
    std::string get_platform_type() const { return hardware_caps_.platform_type; }
    
private:
    void load_defaults();
    void parse_arguments(int argc, char* argv[]);
    void validate_config();
    
    VideoConfig video_config_;
    StreamConfig stream_config_;
    DetectionConfig detection_config_;
    WebConfig web_config_;
    RecordingConfig recording_config_;
    StereoConfig stereo_config_;
    
    struct HardwareCapabilities {
        bool has_hardware_encoder = false;
        bool has_mmal = false;
        bool has_vchiq = false;
        bool has_opencl = false;
        std::string platform_type = "unknown";
        std::string cpu_info = "";
        std::vector<std::string> available_encoders;
    } hardware_caps_;
    
    std::string config_file_;
    std::mutex config_mutex_;
};

} // namespace fpv_streamer