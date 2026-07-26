#pragma once

#include <memory>
#include <vector>
#include <string>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include <thread>
#include <chrono>
#include <linux/videodev2.h>
#include <opencv2/opencv.hpp>
#include <dirent.h>
#include <sys/stat.h>
#include "config/config_manager.h"

namespace fpv_streamer {

// Frame structure
struct VideoFrame {
    std::vector<uint8_t> data;
    int width;
    int height;
    int pixel_format;
    uint64_t timestamp;
    uint32_t sequence;
    bool is_keyframe;
    
    VideoFrame() 
        : width(0), height(0), pixel_format(0), timestamp(0), sequence(0), is_keyframe(false) {}
    
    VideoFrame(int w, int h, int fmt, uint64_t ts, uint32_t seq) 
        : width(w), height(h), pixel_format(fmt), timestamp(ts), sequence(seq), is_keyframe(false) {}
};

// Stereo frame structure for dual camera
struct StereoFrame {
    cv::Mat left_frame;
    cv::Mat right_frame;
    cv::Mat composite_frame;  // Combined stereo frame
    uint64_t timestamp;
    uint32_t sequence;
    uint32_t frame_sequence;   // Frame sequence number
    bool is_keyframe;
    bool is_valid;             // Frame validity flag
    
    StereoFrame() 
        : timestamp(0), sequence(0), frame_sequence(0), is_keyframe(false), is_valid(false) {}
    
    StereoFrame(const cv::Mat& left, const cv::Mat& right, uint64_t ts, uint32_t seq, uint32_t frame_seq = 0)
        : left_frame(left), right_frame(right), timestamp(ts), sequence(seq), frame_sequence(frame_seq), is_keyframe(false), is_valid(true) {}
};

// Frame buffer management
class FrameBuffer {
public:
    FrameBuffer();
    explicit FrameBuffer(const VideoConfig& config);
    ~FrameBuffer();
    
    bool initialize();
    void set_buffer_size(int size);
    bool push_frame(const VideoFrame& frame);
    std::unique_ptr<VideoFrame> pop_frame();
    bool is_empty() const;
    size_t size() const;
    void clear();
    
private:
    std::vector<std::unique_ptr<VideoFrame>> buffer_;
    mutable std::mutex buffer_mutex_;  // Made mutable for const methods
    std::condition_variable buffer_condition_;
    size_t max_buffer_size_;
    VideoConfig config_;
};

class VideoCapture {
public:
    explicit VideoCapture(const VideoConfig& config);
    ~VideoCapture();
    
    bool initialize();
    void stop();
    bool is_healthy() const;
    void restart();
    
    // Frame capture
    std::unique_ptr<VideoFrame> capture_frame();
    bool start_capture();
    void stop_capture();
    
    // Device information
    std::string get_device_name() const;
    int get_actual_width() const { return actual_width_; }
    int get_actual_height() const { return actual_height_; }
    int get_actual_fps() const { return actual_fps_; }
    
    // Sample image fallback support
    bool is_using_sample_images() const { return use_sample_images_.load(); }
    void set_use_sample_images(bool use) { use_sample_images_.store(use); }
    std::vector<std::string> get_available_sample_images() const;
    
    // Statistics
    uint64_t get_frames_captured() const { return frames_captured_.load(); }
    uint64_t get_frames_dropped() const { return frames_dropped_.load(); }
    
    // Frame ready notification for single camera mode
    void set_frame_ready_callback(std::function<void()> callback) {
        frame_ready_callback_ = callback;
    }
    
private:
    bool open_device();
    bool close_device();
    bool set_format();
    bool request_buffers();
    bool start_streaming();
    void stop_streaming();
    
    // V4L2 operations
    bool query_capabilities();
    bool enumerate_formats();
    bool set_control(uint32_t id, int32_t value);
    
    // Frame processing
    std::unique_ptr<VideoFrame> convert_frame(const void* buffer, size_t buffer_size);
    bool apply_cscorrection(VideoFrame& frame);
    
    // Input format handling
    bool set_input_format();
    std::unique_ptr<VideoFrame> process_mjpeg_input(const void* buffer, size_t buffer_size);
    std::unique_ptr<VideoFrame> process_h264_input(const void* buffer, size_t buffer_size);
    std::unique_ptr<VideoFrame> process_raw_input(const void* buffer, size_t buffer_size);
    bool is_input_format_supported(const std::string& format);
    
    VideoConfig config_;
    int device_fd_;
    std::string device_path_;
    
    // Current format
    int actual_width_;
    int actual_height_;
    int actual_fps_;
    int actual_pixel_format_;
    
    // V4L2 buffers
    struct v4l2_buffer v4l2_buffers_[4];
    void* buffer_ptrs_[4];
    int num_buffers_;
    int current_buffer_index_;
    
    // Streaming state
    std::atomic<bool> streaming_active_{false};
    std::atomic<bool> healthy_{false};
    std::thread capture_thread_;
    
    // Statistics
    std::atomic<uint64_t> frames_captured_{0};
    std::atomic<uint64_t> frames_dropped_{0};
    std::atomic<uint64_t> total_bytes_captured_{0};
    
    // Color correction parameters
    float brightness_;
    float contrast_;
    float saturation_;
    float hue_;
    
    // Frame timing
    std::chrono::high_resolution_clock::time_point last_frame_time_;
    uint32_t frame_sequence_;
    
    // Sample image fallback support
    std::atomic<bool> use_sample_images_{false};
    std::vector<std::string> sample_image_paths_;
    mutable std::mutex sample_mutex_;
    size_t current_sample_index_;
    
    // Sample image methods
    bool load_sample_images();
    std::unique_ptr<VideoFrame> create_sample_frame();
    bool scan_sample_directory();
    bool scan_directory_for_images(const std::string& dir_path);
    bool create_synthetic_samples();
    std::string get_sample_directory_for_device() const;
    
private:
    std::function<void()> frame_ready_callback_;
};

// Dual camera manager for stereo capture
class DualCameraManager {
public:
    DualCameraManager(const VideoConfig& config1, const StereoConfig& stereo_config);
    ~DualCameraManager();
    
    bool initialize();
    void shutdown();
    bool is_healthy() const;
    
    // Dual frame capture
    bool capture_stereo_frames(StereoFrame& stereo_frame);
    void start_capture();
    void stop_capture();
    
    // Individual camera access
    VideoCapture* get_camera1() { return camera1_.get(); }
    VideoCapture* get_camera2() { return camera2_.get(); }
    
    // Configuration
    void update_stereo_config(const StereoConfig& config);
    const StereoConfig& get_stereo_config() const { return stereo_config_; }
    
    // Statistics
    uint64_t get_frames_captured() const { return frames_captured_.load(); }
    uint64_t get_frames_dropped() const { return frames_dropped_.load(); }
    double get_sync_latency_ms() const { return sync_latency_ms_.load(); }
    
    // Frame synchronization
    bool enable_frame_sync() const { return stereo_config_.enable_frame_sync; }
    void set_sync_timeout(int timeout_ms) { sync_timeout_ms_ = timeout_ms; }
    
private:
    bool open_devices();
    bool configure_devices();
    void frame_sync_worker();
    
    // Camera instances
    std::unique_ptr<VideoCapture> camera1_;
    std::unique_ptr<VideoCapture> camera2_;
    
    // Configuration
    VideoConfig config1_;
    VideoConfig config2_;
    StereoConfig stereo_config_;
    
    // Device management
    std::string device1_path_;
    std::string device2_path_;
    
    // Threading
    std::thread sync_thread_;
    std::atomic<bool> running_{false};
    std::atomic<bool> healthy_{false};
    
    // Frame synchronization
    std::mutex frame_mutex_;
    std::condition_variable frame_condition_;
    std::atomic<int> sync_timeout_ms_{100};
    
    // Frame buffers
    VideoFrame frame1_buffer_;
    VideoFrame frame2_buffer_;
    std::atomic<bool> frame1_ready_{false};
    std::atomic<bool> frame2_ready_{false};
    
    // Statistics
    std::atomic<uint64_t> frames_captured_{0};
    std::atomic<uint64_t> frames_dropped_{0};
    std::atomic<double> sync_latency_ms_{0};
    
    // Performance monitoring
    std::chrono::steady_clock::time_point last_sync_time_;
};

} // namespace fpv_streamer