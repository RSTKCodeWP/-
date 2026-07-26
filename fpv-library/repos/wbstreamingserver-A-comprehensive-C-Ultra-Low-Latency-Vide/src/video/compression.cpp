#include "video/compression.h"
#include "utils/utils.h"
#include <algorithm>
#include <cmath>

namespace fpv_streamer {

CompressionEngine::CompressionEngine(const VideoConfig& config) 
    : config_(config)
    , enabled_(config.enable_region_compression)
    , initialized_(false)
    , use_adaptive_(true)
    , center_quality_factor_(config.center_quality_factor)
    , edge_quality_factor_(config.edge_compression_factor) {
}

CompressionEngine::~CompressionEngine() {
    stop();
}

bool CompressionEngine::initialize() {
    if (initialized_) {
        return true;
    }
    
    Logger::info("Initializing compression engine");
    
    if (!enabled_) {
        Logger::info("Compression engine disabled");
        initialized_ = true;
        return true;
    }
    
    // Setup default regions optimized for FPV
    setup_default_regions();
    
    // Allocate frame buffers
    int width = config_.width;
    int height = config_.height;
    
    frame_buffer_ = cv::Mat(height, width, CV_8UC3);
    previous_frame_ = cv::Mat(height, width, CV_8UC1);
    motion_map_ = cv::Mat(height, width, CV_32F);
    saliency_map_ = cv::Mat(height, width, CV_32F);
    
    Logger::info("Compression engine initialized with " + std::to_string(compression_regions_.size()) + " regions");
    initialized_ = true;
    
    return true;
}

void CompressionEngine::stop() {
    if (!initialized_) {
        return;
    }
    
    Logger::info("Stopping compression engine");
    
    frame_buffer_.release();
    previous_frame_.release();
    motion_map_.release();
    saliency_map_.release();
    
    initialized_ = false;
}

void CompressionEngine::process_frame(VideoFrame& frame) {
    if (!initialized_ || !enabled_) {
        return;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    frames_processed_.fetch_add(1);
    
    // Convert frame to OpenCV Mat for processing
    cv::Mat yuv_frame;
    if (frame.data.size() < (size_t)frame.width * frame.height * 3 / 2) {
        Logger::warn("Invalid frame data for compression");
        return;
    }
    
    size_t y_size = frame.width * frame.height;
    size_t uv_size = y_size / 4;
    
    // Create YUV to RGB conversion
    cv::Mat yuv_img(frame.height * 3 / 2, frame.width, CV_8UC1);
    memcpy(yuv_img.data, frame.data.data(), frame.data.size());
    
    cv::cvtColor(yuv_img, frame_buffer_, cv::COLOR_YUV2RGB_I420);
    
    if (use_adaptive_) {
        apply_adaptive_compression(frame);
    } else {
        apply_region_compression(frame);
    }
    
    // Convert back to YUV
    cv::Mat yuv_output;
    cv::cvtColor(frame_buffer_, yuv_output, cv::COLOR_RGB2YUV_I420);
    
    // Update frame data
    frame.data.resize(yuv_output.total());
    memcpy(frame.data.data(), yuv_output.data, frame.data.size());
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
    processing_time_us_.fetch_add(duration.count());
}

void CompressionEngine::set_enabled(bool enabled) {
    enabled_ = enabled;
    Logger::info("Compression engine " + std::string(enabled ? "enabled" : "disabled"));
}

void CompressionEngine::set_center_quality(float factor) {
    center_quality_factor_ = std::max(0.1f, std::min(1.0f, factor));
    Logger::info("Center quality factor updated: " + std::to_string(center_quality_factor_));
}

void CompressionEngine::set_edge_quality(float factor) {
    edge_quality_factor_ = std::max(0.1f, std::min(1.0f, factor));
    Logger::info("Edge quality factor updated: " + std::to_string(edge_quality_factor_));
}

void CompressionEngine::set_regions(const std::vector<CompressionRegion>& regions) {
    compression_regions_ = regions;
    Logger::info("Compression regions updated: " + std::to_string(regions.size()) + " regions");
}

void CompressionEngine::update_from_config(const VideoConfig& config) {
    config_ = config;
    enabled_ = config.enable_region_compression;
    center_quality_factor_ = config.center_quality_factor;
    edge_quality_factor_ = config.edge_compression_factor;
    
    if (initialized_) {
        setup_default_regions();
    }
}

void CompressionEngine::setup_default_regions() {
    compression_regions_.clear();
    
    int width = config_.width;
    int height = config_.height;
    
    // Center region (high quality) - 40% of frame
    int center_w = (int)(width * 0.4);
    int center_h = (int)(height * 0.4);
    int center_x = (width - center_w) / 2;
    int center_y = (height - center_h) / 2;
    
    compression_regions_.push_back({
        cv::Rect(center_x, center_y, center_w, center_h),
        center_quality_factor_,
        10
    });
    
    // Upper middle region
    compression_regions_.push_back({
        cv::Rect(0, 0, width, height / 3),
        edge_quality_factor_ * 0.8f,
        5
    });
    
    // Lower middle region
    compression_regions_.push_back({
        cv::Rect(0, height * 2 / 3, width, height / 3),
        edge_quality_factor_ * 0.8f,
        5
    });
    
    // Left edge region
    compression_regions_.push_back({
        cv::Rect(0, 0, width / 4, height),
        edge_quality_factor_ * 0.6f,
        3
    });
    
    // Right edge region
    compression_regions_.push_back({
        cv::Rect(width * 3 / 4, 0, width / 4, height),
        edge_quality_factor_ * 0.6f,
        3
    });
    
    // Corner regions (highest compression)
    compression_regions_.push_back({
        cv::Rect(0, 0, width / 6, height / 6),
        edge_quality_factor_ * 0.4f,
        1
    });
    
    compression_regions_.push_back({
        cv::Rect(width * 5 / 6, 0, width / 6, height / 6),
        edge_quality_factor_ * 0.4f,
        1
    });
    
    compression_regions_.push_back({
        cv::Rect(0, height * 5 / 6, width / 6, height / 6),
        edge_quality_factor_ * 0.4f,
        1
    });
    
    compression_regions_.push_back({
        cv::Rect(width * 5 / 6, height * 5 / 6, width / 6, height / 6),
        edge_quality_factor_ * 0.4f,
        1
    });
}

void CompressionEngine::apply_region_compression(VideoFrame& frame) {
    for (const auto& region : compression_regions_) {
        apply_quality_adjustment(frame, region.region, region.quality_factor);
        regions_compressed_.fetch_add(1);
    }
}

void CompressionEngine::apply_adaptive_compression(VideoFrame& frame) {
    // Analyze frame for areas of interest
    analyze_frame_regions(frame);
    
    // Apply dynamic regions based on analysis
    auto roi_regions = detect_areas_of_interest(frame_buffer_);
    
    // Apply high quality to detected objects
    for (const auto& roi : roi_regions) {
        cv::Rect padded_roi(
            std::max(0, roi.x - roi.width / 2),
            std::max(0, roi.y - roi.height / 2),
            std::min(frame.width - std::max(0, roi.x - roi.width / 2), roi.width),
            std::min(frame.height - std::max(0, roi.y - roi.height / 2), roi.height)
        );
        
        apply_quality_adjustment(frame, padded_roi, 1.0f); // Full quality for objects
    }
    
    // Apply standard region compression
    apply_region_compression(frame);
}

void CompressionEngine::analyze_frame_regions(const VideoFrame& frame) {
    if (previous_frame_.empty()) {
        cv::cvtColor(frame_buffer_, previous_frame_, cv::COLOR_RGB2GRAY);
        return;
    }
    
    // Calculate motion
    cv::Mat current_gray;
    cv::cvtColor(frame_buffer_, current_gray, cv::COLOR_RGB2GRAY);
    
    cv::absdiff(current_gray, previous_frame_, motion_map_);
    motion_map_.convertTo(motion_map_, CV_32F);
    motion_map_ /= 255.0f;
    
    // Simple saliency calculation (edge detection + motion)
    cv::Mat edges;
    cv::Canny(current_gray, edges, 50, 150);
    edges.convertTo(edges, CV_32F);
    edges /= 255.0f;
    
    saliency_map_ = motion_map_ + edges * 0.5f;
    
    previous_frame_ = current_gray.clone();
}

std::vector<cv::Rect> CompressionEngine::detect_areas_of_interest(const cv::Mat& gray_frame) {
    std::vector<cv::Rect> regions;
    
    // Find areas with high saliency
    cv::Mat thresholded;
    double thresh = cv::threshold(saliency_map_, thresholded, 0.7, 1.0, cv::THRESH_BINARY);
    
    // Find contours
    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(thresholded, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
    
    // Filter and create regions for significant objects
    for (const auto& contour : contours) {
        cv::Rect bbox = cv::boundingRect(contour);
        
        // Filter small regions
        if (bbox.width > 50 && bbox.height > 50 && 
            bbox.width < gray_frame.cols * 0.8 && 
            bbox.height < gray_frame.rows * 0.8) {
            regions.push_back(bbox);
        }
    }
    
    return regions;
}

float CompressionEngine::calculate_quality_for_region(const cv::Rect& region, const VideoFrame& frame) {
    // Calculate quality based on region position and size
    int center_x = frame.width / 2;
    int center_y = frame.height / 2;
    
    float distance_from_center = std::sqrt(
        std::pow(region.x + region.width / 2 - center_x, 2) +
        std::pow(region.y + region.height / 2 - center_y, 2)
    );
    
    float max_distance = std::sqrt(
        std::pow(center_x, 2) + std::pow(center_y, 2)
    );
    
    float normalized_distance = distance_from_center / max_distance;
    
    // Edge regions get lower quality
    float edge_factor = std::max(edge_quality_factor_, 1.0f - normalized_distance * 0.5f);
    
    // Center regions get higher quality
    float center_factor = std::min(center_quality_factor_, 1.0f - normalized_distance * 0.3f);
    
    return std::min(1.0f, std::max(0.1f, (center_factor + edge_factor) / 2.0f));
}

void CompressionEngine::apply_quality_adjustment(VideoFrame& frame, const cv::Rect& region, float quality) {
    if (quality >= 1.0f) {
        return; // No compression needed
    }
    
    // Clamp region to frame bounds
    cv::Rect clipped_region(
        std::max(0, region.x),
        std::max(0, region.y),
        std::min(region.width, frame.width - std::max(0, region.x)),
        std::min(region.height, frame.height - std::max(0, region.y))
    );
    
    if (clipped_region.width <= 0 || clipped_region.height <= 0) {
        return;
    }
    
    // Extract region from frame_buffer_
    cv::Mat roi = frame_buffer_(clipped_region);
    
    // Apply compression based on quality factor
    if (quality < 0.8f) {
        // High compression: blur + reduce detail
        int blur_strength = (int)((1.0f - quality) * fpv_params_.edge_blur_strength);
        if (blur_strength > 0 && blur_strength % 2 == 0) {
            blur_strength++; // Ensure odd number for kernel size
        }
        
        cv::Mat blurred;
        cv::GaussianBlur(roi, blurred, cv::Size(blur_strength, blur_strength), 0);
        
        // Blend original with blurred based on quality
        float blend_factor = 1.0f - quality;
        roi = roi * (1.0f - blend_factor) + blurred * blend_factor;
        roi.convertTo(roi, CV_8UC3);
    } else if (quality < 0.95f) {
        // Medium compression: mild blur
        cv::Mat blurred;
        cv::GaussianBlur(roi, blurred, cv::Size(3, 3), 0);
        roi = roi * 0.7f + blurred * 0.3f;
        roi.convertTo(roi, CV_8UC3);
    }
    
    // Store compressed region back
    roi.copyTo(frame_buffer_(clipped_region));
}

} // namespace fpv_streamer