#pragma once

#include <memory>
#include <thread>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include "config/config_manager.h"
#include "video/capture.h"
#include "video/encoder.h"
#include "video/compression.h"
#include "streaming/stream_manager.h"
#include "detection/detection.h"
#include "web/web_interface.h"
#include "utils/utils.h"

namespace fpv_streamer {

class Server {
public:
    Server(ConfigManager& config);
    ~Server();
    
    bool start();
    void stop();
    void process_events();
    
    // Status methods
    bool is_running() const { return running_.load(); }
    std::string get_status() const;
    uint64_t get_frames_processed() const { return frames_processed_.load(); }
    uint64_t get_frames_streamed() const { return frames_streamed_.load(); }
    double get_fps() const;
    
    // Encoder type getter for compatibility
    std::string get_encoder_type() const { return "h264"; } // Default encoder type
    
private:
    bool initialize_components();
    void main_loop();
    void frame_processing_thread();
    
    ConfigManager& config_;
    std::atomic<bool> running_{false};
    std::thread main_thread_;
    std::thread frame_processing_thread_;
    std::atomic<uint64_t> frames_processed_{0};
    std::atomic<uint64_t> frames_streamed_{0};
    
    // Core components
    std::unique_ptr<VideoCapture> video_capture_;
    std::unique_ptr<VideoEncoder> video_encoder_;
    std::unique_ptr<CompressionEngine> compression_engine_;
    std::unique_ptr<StreamManager> stream_manager_;
    
    // Detection components
    std::unique_ptr<MotionDetector> motion_detector_;
    std::unique_ptr<ObjectDetector> object_detector_;
    std::unique_ptr<LensCorrector> lens_corrector_;
    
    // Web interface
    std::unique_ptr<WebInterface> web_interface_;
    
    // Frame buffer
    std::unique_ptr<FrameBuffer> frame_buffer_;
    
    // Performance tracking
    std::unique_ptr<Timer> processing_timer_;
    std::unique_ptr<Timer> streaming_timer_;
    
    // Thread synchronization
    std::mutex component_mutex_;
    std::condition_variable frame_ready_condition_;
    std::atomic<bool> new_frame_ready_{false};
    
    // Configuration callbacks
    void on_config_updated();
    
    // Error handling
    void handle_error(const std::string& component, const std::string& error);
    
    // Performance optimization
    void optimize_for_latency();
    void update_performance_stats();
    
    struct PerformanceStats {
        double avg_processing_time_ms = 0.0;
        double avg_encoding_time_ms = 0.0;
        double avg_streaming_time_ms = 0.0;
        double current_fps = 0.0;
        uint64_t total_bytes_streamed = 0;
        uint64_t dropped_frames = 0;
        uint64_t error_count = 0;
    } performance_stats_;
    
    // Utility methods
    bool check_hardware_compatibility();
    void setup_signal_handlers();
};

} // namespace fpv_streamer