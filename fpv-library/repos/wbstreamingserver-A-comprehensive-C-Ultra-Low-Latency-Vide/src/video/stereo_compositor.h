#pragma once

#include <opencv2/opencv.hpp>
#include <memory>
#include <thread>
#include <mutex>
#include <atomic>
#include <chrono>
#include "config/config_manager.h"
#include "utils/utils.h"
#include "video/capture.h"  // Include to get StereoFrame definition

namespace fpv_streamer {

// Stereo compositor class for combining dual camera feeds
class StereoCompositor {
public:
    StereoCompositor();
    ~StereoCompositor();
    
    bool initialize(const StereoConfig& config);
    void shutdown();
    
    // Frame processing
    bool process_frames(const cv::Mat& left_frame, const cv::Mat& right_frame, StereoFrame& output);
    bool get_composite_frame(StereoFrame& frame);
    
    // Configuration updates
    void update_config(const StereoConfig& config);
    const StereoConfig& get_config() const { return config_; }
    
    // Performance monitoring
    double get_processing_latency_ms() const;
    int get_frames_processed() const { return frames_processed_; }
    bool is_healthy() const { return is_initialized_; }
    
    // Calibration and alignment
    bool perform_automatic_alignment();
    void reset_alignment();
    void save_calibration();
    void load_calibration();
    
private:
    enum class StereoMode {
        SIDE_BY_SIDE = 0,
        TOP_BOTTOM = 1,
        OVER_UNDER = 2
    };
    
    // Processing methods
    cv::Mat create_side_by_side(const cv::Mat& left, const cv::Mat& right);
    cv::Mat create_top_bottom(const cv::Mat& left, const cv::Mat& right);
    cv::Mat create_over_under(const cv::Mat& left, const cv::Mat& right);
    
    // Alignment methods
    cv::Mat apply_alignment(const cv::Mat& frame, const cv::Mat& reference);
    std::pair<cv::Mat, cv::Mat> apply_color_correction(const cv::Mat& frame1, const cv::Mat& frame2);
    cv::Mat apply_flipping(const cv::Mat& frame, int flip_mode);
    
    // Utility methods
    cv::Mat resize_and_align(const cv::Mat& frame, const cv::Size& target_size);
    void optimize_frame_quality(cv::Mat& frame);
    
    // Thread safety
    mutable std::mutex frame_mutex_;
    mutable std::mutex config_mutex_;
    
    // Configuration
    StereoConfig config_;
    bool is_initialized_ = false;
    
    // Frame buffers
    StereoFrame last_composite_frame_;
    std::atomic<int> frames_processed_{0};
    std::atomic<long long> total_processing_time_us_{0};
    
    // Frame synchronization
    std::atomic<bool> frame_sync_enabled_{true};
    int frame_sequence_ = 0;
    
    // Processing timing
    mutable std::chrono::steady_clock::time_point last_processing_time_;
    double avg_processing_latency_ms_ = 0.0;
    
    // Calibration data
    cv::Mat alignment_matrix_left_;
    cv::Mat alignment_matrix_right_;
    cv::Mat color_correction_matrix_;
    bool calibration_loaded_ = false;
    
    // Processing flags
    std::atomic<bool> enable_color_correction_{true};
    std::atomic<bool> enable_quality_optimization_{true};
    
    // Performance statistics
    struct PerformanceStats {
        int total_frames = 0;
        int successful_frames = 0;
        int failed_frames = 0;
        double min_latency_ms = 1000.0;
        double max_latency_ms = 0.0;
        double avg_latency_ms = 0.0;
        std::chrono::steady_clock::time_point stats_start_time;
    } stats_;
    
    void update_performance_stats(double latency_ms);
};

} // namespace fpv_streamer