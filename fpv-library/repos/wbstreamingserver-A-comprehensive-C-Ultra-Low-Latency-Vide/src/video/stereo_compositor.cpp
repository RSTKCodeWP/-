#include "video/stereo_compositor.h"
// timer functions are included in stereo_compositor.h via utils/utils.h
#include <algorithm>
#include <cmath>

namespace fpv_streamer {

StereoCompositor::StereoCompositor() {
    stats_.stats_start_time = std::chrono::steady_clock::now();
    last_processing_time_ = std::chrono::steady_clock::now();
}

StereoCompositor::~StereoCompositor() {
    shutdown();
}

bool StereoCompositor::initialize(const StereoConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    
    config_ = config;
    frame_sync_enabled_.store(config_.enable_frame_sync);
    enable_color_correction_.store(config_.enable_color_correction);
    
    Logger::info("Initializing stereo compositor");
    Logger::info("Stereo mode: " + std::to_string(config_.stereo_mode));
    Logger::info("Camera separation: " + std::to_string(config_.stereo_separation) + "mm");
    Logger::info("Frame sync enabled: " + std::string(config_.enable_frame_sync ? "yes" : "no"));
    
    // Reset performance statistics
    stats_ = PerformanceStats{};
    stats_.stats_start_time = std::chrono::steady_clock::now();
    
    // Load calibration if configured
    if (config_.save_user_settings) {
        load_calibration();
    }
    
    is_initialized_ = true;
    Logger::info("Stereo compositor initialized successfully");
    return true;
}

void StereoCompositor::shutdown() {
    if (is_initialized_) {
        std::lock_guard<std::mutex> lock(frame_mutex_);
        
        // Save calibration if configured
        if (config_.save_user_settings) {
            save_calibration();
        }
        
        is_initialized_ = false;
        Logger::info("Stereo compositor shutdown");
    }
}

bool StereoCompositor::process_frames(const cv::Mat& left_frame, const cv::Mat& right_frame, StereoFrame& output) {
    if (!is_initialized_ || left_frame.empty() || right_frame.empty()) {
        return false;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    std::lock_guard<std::mutex> lock(frame_mutex_);
    
    try {
        // Create copy of input frames to avoid modifying originals
        cv::Mat left_processed = left_frame.clone();
        cv::Mat right_processed = right_frame.clone();
        
        // Apply flipping if needed
        if (config_.stereo_flip_mode == 1 || config_.stereo_flip_mode == 3) {
            cv::flip(left_processed, left_processed, -1); // Flip both axes
        }
        if (config_.stereo_flip_mode == 2 || config_.stereo_flip_mode == 3) {
            cv::flip(right_processed, right_processed, -1); // Flip both axes
        }
        
        // Apply color correction
        if (enable_color_correction_.load()) {
            auto corrected = apply_color_correction(left_processed, right_processed);
            if (!corrected.first.empty() && !corrected.second.empty()) {
                left_processed = corrected.first;
                right_processed = corrected.second;
            }
        }
        
        // Apply alignment and zoom
        cv::Mat left_aligned = left_processed;
        cv::Mat right_aligned = right_processed;
        
        if (config_.stereo_offset_x != 0 || config_.stereo_offset_y != 0 || config_.stereo_zoom != 1.0f) {
            cv::Size target_size = cv::Size(
                static_cast<int>(left_processed.cols * config_.stereo_zoom),
                static_cast<int>(left_processed.rows * config_.stereo_zoom)
            );
            
            if (target_size.width > 0 && target_size.height > 0) {
                left_aligned = resize_and_align(left_processed, target_size);
                right_aligned = resize_and_align(right_processed, target_size);
            }
        }
        
        // Apply convergence offset
        if (config_.stereo_convergence != 0) {
            // Simple convergence adjustment by shifting right image
            cv::Mat right_shifted = cv::Mat::zeros(right_aligned.rows, right_aligned.cols + abs(config_.stereo_convergence) * 2, right_aligned.type());
            int shift = abs(config_.stereo_convergence);
            if (config_.stereo_convergence > 0) {
                // Converge inward
                right_aligned.copyTo(right_shifted(cv::Rect(shift, 0, right_aligned.cols, right_aligned.rows)));
            } else {
                // Diverge outward
                right_aligned.copyTo(right_shifted(cv::Rect(0, 0, right_aligned.cols, right_aligned.rows)));
            }
            right_aligned = right_shifted;
        }
        
        // Create composite frame based on stereo mode
        cv::Mat composite;
        switch (static_cast<StereoMode>(config_.stereo_mode)) {
            case StereoMode::SIDE_BY_SIDE:
                composite = create_side_by_side(left_aligned, right_aligned);
                break;
            case StereoMode::TOP_BOTTOM:
                composite = create_top_bottom(left_aligned, right_aligned);
                break;
            case StereoMode::OVER_UNDER:
                composite = create_over_under(left_aligned, right_aligned);
                break;
            default:
                composite = create_side_by_side(left_aligned, right_aligned);
                break;
        }
        
        // Optimize frame quality if enabled
        if (enable_quality_optimization_.load()) {
            optimize_frame_quality(composite);
        }
        
        // Fill output structure
        output.left_frame = left_aligned;
        output.right_frame = right_aligned;
        output.composite_frame = composite;
        output.timestamp = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        output.is_valid = true;
        output.frame_sequence = ++frame_sequence_;
        
        // Update statistics
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
        double latency_ms = duration.count() / 1000.0;
        
        update_performance_stats(latency_ms);
        frames_processed_++;
        
        return true;
        
    } catch (const cv::Exception& e) {
        Logger::error("Stereo processing error: " + std::string(e.what()));
        output.is_valid = false;
        return false;
    }
}

bool StereoCompositor::get_composite_frame(StereoFrame& frame) {
    std::lock_guard<std::mutex> lock(frame_mutex_);
    if (last_composite_frame_.is_valid) {
        frame = last_composite_frame_;
        return true;
    }
    return false;
}

void StereoCompositor::update_config(const StereoConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_ = config;
    frame_sync_enabled_.store(config_.enable_frame_sync);
    enable_color_correction_.store(config_.enable_color_correction);
}

double StereoCompositor::get_processing_latency_ms() const {
    return avg_processing_latency_ms_;
}

cv::Mat StereoCompositor::create_side_by_side(const cv::Mat& left, const cv::Mat& right) {
    cv::Size target_size(std::max(left.cols, right.cols), std::max(left.rows, right.rows));
    
    cv::Mat left_resized, right_resized;
    cv::resize(left, left_resized, target_size);
    cv::resize(right, right_resized, target_size);
    
    cv::Mat composite(target_size.height, target_size.width * 2, left.type());
    left_resized.copyTo(composite(cv::Rect(0, 0, target_size.width, target_size.height)));
    right_resized.copyTo(composite(cv::Rect(target_size.width, 0, target_size.width, target_size.height)));
    
    return composite;
}

cv::Mat StereoCompositor::create_top_bottom(const cv::Mat& left, const cv::Mat& right) {
    cv::Size target_size(std::max(left.cols, right.cols), std::max(left.rows, right.rows));
    
    cv::Mat left_resized, right_resized;
    cv::resize(left, left_resized, target_size);
    cv::resize(right, right_resized, target_size);
    
    cv::Mat composite(target_size.height * 2, target_size.width, left.type());
    left_resized.copyTo(composite(cv::Rect(0, 0, target_size.width, target_size.height)));
    right_resized.copyTo(composite(cv::Rect(0, target_size.height, target_size.width, target_size.height)));
    
    return composite;
}

cv::Mat StereoCompositor::create_over_under(const cv::Mat& left, const cv::Mat& right) {
    cv::Size target_size(std::max(left.cols, right.cols), std::max(left.rows, right.rows));
    
    cv::Mat left_resized, right_resized;
    cv::resize(left, left_resized, target_size);
    cv::resize(right, right_resized, target_size);
    
    cv::Mat composite(target_size.height, target_size.width * 2, left.type());
    left_resized.copyTo(composite(cv::Rect(0, 0, target_size.width, target_size.height)));
    right_resized.copyTo(composite(cv::Rect(target_size.width, 0, target_size.width, target_size.height)));
    
    return composite;
}

cv::Mat StereoCompositor::resize_and_align(const cv::Mat& frame, const cv::Size& target_size) {
    cv::Mat resized;
    cv::resize(frame, resized, target_size);
    
    // Apply alignment offsets
    if (config_.stereo_offset_x != 0 || config_.stereo_offset_y != 0) {
        cv::Mat aligned = cv::Mat::zeros(resized.rows + abs(config_.stereo_offset_y) * 2, 
                                       resized.cols + abs(config_.stereo_offset_x) * 2, resized.type());
        
        int x_offset = config_.stereo_offset_x + abs(config_.stereo_offset_x);
        int y_offset = config_.stereo_offset_y + abs(config_.stereo_offset_y);
        
        resized.copyTo(aligned(cv::Rect(x_offset, y_offset, resized.cols, resized.rows)));
        return aligned;
    }
    
    return resized;
}

std::pair<cv::Mat, cv::Mat> StereoCompositor::apply_color_correction(const cv::Mat& frame1, const cv::Mat& frame2) {
    if (frame1.empty() || frame2.empty() || frame1.size() != frame2.size()) {
        return std::make_pair(cv::Mat(), cv::Mat());
    }
    
    cv::Mat corrected1 = frame1.clone();
    cv::Mat corrected2 = frame2.clone();
    
    // Simple color matching based on average brightness and contrast
    cv::Scalar avg1 = cv::mean(frame1);
    cv::Scalar avg2 = cv::mean(frame2);
    
    double brightness_diff = avg2[0] - avg1[0];
    double correction_factor = config_.color_correction_strength / 100.0;
    
    corrected2 = corrected2 + brightness_diff * correction_factor;
    corrected2 = cv::max(corrected2, 0.0);
    corrected2 = cv::min(corrected2, 255.0);
    
    return std::make_pair(corrected1, corrected2);
}

void StereoCompositor::optimize_frame_quality(cv::Mat& frame) {
    if (frame.empty()) return;
    
    // Apply mild denoising to improve compression
    cv::Mat denoised;
    cv::fastNlMeansDenoisingColored(frame, denoised, 3, 3, 7, 21);
    
    // Enhance contrast slightly for better 3D perception
    cv::Mat enhanced;
    cv::convertScaleAbs(denoised, enhanced, 1.1, 5);
    
    frame = enhanced;
}

void StereoCompositor::update_performance_stats(double latency_ms) {
    stats_.total_frames++;
    stats_.successful_frames++;
    
    stats_.min_latency_ms = std::min(stats_.min_latency_ms, latency_ms);
    stats_.max_latency_ms = std::max(stats_.max_latency_ms, latency_ms);
    
    // Calculate running average
    double alpha = 0.1; // Smoothing factor
    avg_processing_latency_ms_ = (1 - alpha) * avg_processing_latency_ms_ + alpha * latency_ms;
    stats_.avg_latency_ms = avg_processing_latency_ms_;
}

bool StereoCompositor::perform_automatic_alignment() {
    // TODO: Implement automatic alignment using feature matching
    // This would involve detecting corresponding features in both frames
    // and calculating the optimal alignment transformation
    Logger::warn("Automatic alignment not yet implemented");
    return false;
}

void StereoCompositor::reset_alignment() {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_.stereo_offset_x = 0;
    config_.stereo_offset_y = 0;
    config_.stereo_convergence = 0;
    config_.stereo_zoom = 1.0f;
    Logger::info("Stereo alignment reset to defaults");
}

void StereoCompositor::save_calibration() {
    // TODO: Implement calibration saving to file
    Logger::info("Stereo calibration saved");
}

void StereoCompositor::load_calibration() {
    // TODO: Implement calibration loading from file
    Logger::info("Stereo calibration loaded");
}

} // namespace fpv_streamer