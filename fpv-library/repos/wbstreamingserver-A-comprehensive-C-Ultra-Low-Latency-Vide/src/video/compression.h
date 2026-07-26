#pragma once

#include <memory>
#include <vector>
#include <atomic>
#include <opencv2/opencv.hpp>
#include "config/config_manager.h"
#include "video/capture.h"

namespace fpv_streamer {

// Compression region definitions
struct CompressionRegion {
    cv::Rect region;
    float quality_factor; // 0.0 - 1.0 (1.0 = best quality)
    int priority; // Higher number = higher priority
};

class CompressionEngine {
public:
    explicit CompressionEngine(const VideoConfig& config);
    ~CompressionEngine();
    
    bool initialize();
    void stop();
    bool is_enabled() const { return enabled_; }
    
    // Frame processing
    void process_frame(VideoFrame& frame);
    
    // Configuration
    void set_enabled(bool enabled);
    void set_center_quality(float factor);
    void set_edge_quality(float factor);
    void set_regions(const std::vector<CompressionRegion>& regions);
    void update_from_config(const VideoConfig& config);
    
    // Statistics
    uint64_t get_frames_processed() const { return frames_processed_.load(); }
    uint64_t get_regions_compressed() const { return regions_compressed_.load(); }
    
private:
    void setup_default_regions();
    void calculate_regions();
    void apply_region_compression(VideoFrame& frame);
    void apply_adaptive_compression(VideoFrame& frame);
    
    // Region analysis
    void analyze_frame_regions(const VideoFrame& frame);
    std::vector<cv::Rect> detect_areas_of_interest(const cv::Mat& gray);
    
    // Quality adjustment
    float calculate_quality_for_region(const cv::Rect& region, const VideoFrame& frame);
    void apply_quality_adjustment(VideoFrame& frame, const cv::Rect& region, float quality);
    
    VideoConfig config_;
    bool enabled_;
    bool initialized_;
    
    // Compression regions
    std::vector<CompressionRegion> compression_regions_;
    cv::Mat frame_buffer_;
    
    // Adaptive compression
    bool use_adaptive_;
    float center_quality_factor_;
    float edge_quality_factor_;
    
    // Frame analysis
    cv::Mat previous_frame_;
    cv::Mat motion_map_;
    cv::Mat saliency_map_;
    
    // Performance tracking
    std::atomic<uint64_t> frames_processed_{0};
    std::atomic<uint64_t> regions_compressed_{0};
    std::atomic<uint64_t> processing_time_us_{0};
    
    // Parameters for FPV optimization
    struct FPVParameters {
        float center_radius_factor = 0.3f; // 30% of frame as high-quality center
        float edge_compression_multiplier = 0.7f; // 30% more compression at edges
        int edge_blur_strength = 3;
        bool preserve_center_detail = true;
        bool enhance_center_brightness = true;
    } fpv_params_;
};

} // namespace fpv_streamer