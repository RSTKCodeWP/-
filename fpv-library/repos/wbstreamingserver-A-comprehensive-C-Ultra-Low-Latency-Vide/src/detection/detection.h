#pragma once

#include <memory>
#include <vector>
#include <atomic>
#include <opencv2/opencv.hpp>
#include "config/config_manager.h"
#include "video/capture.h"
#include "utils/utils.h"

namespace fpv_streamer {

// Motion detection result
struct MotionDetection {
    cv::Rect bounding_box;
    float confidence; // 0.0 - 1.0
    uint64_t timestamp;
    int motion_intensity;
};

// Object detection result
struct ObjectDetection {
    std::string class_name;
    float confidence; // 0.0 - 1.0
    cv::Rect bounding_box;
    uint64_t timestamp;
};

// Motion Detector
class MotionDetector {
public:
    explicit MotionDetector(const DetectionConfig& config);
    ~MotionDetector();
    
    bool initialize();
    void stop();
    bool is_enabled() const { return enabled_; }
    bool is_healthy() const { return initialized_; }
    
    // Processing
    void process_frame(const VideoFrame& frame);
    std::vector<MotionDetection> get_detections() const;
    
    // Configuration
    void set_enabled(bool enabled);
    void set_sensitivity(int sensitivity);
    void set_threshold(int threshold);
    void update_config(const DetectionConfig& config);
    
    // Statistics
    uint64_t get_frames_processed() const { return frames_processed_.load(); }
    uint64_t get_motions_detected() const { return motions_detected_.load(); }
    
private:
    void initialize_background_model();
    void update_background_model(const cv::Mat& frame);
    std::vector<MotionDetection> detect_motion(const cv::Mat& frame);
    void apply_noise_filtering(std::vector<MotionDetection>& detections);
    
    // Background subtraction
    cv::Ptr<cv::BackgroundSubtractorMOG2> background_subtractor_;
    cv::Mat background_model_;
    cv::Mat foreground_mask_;
    
    // Motion analysis
    cv::Mat previous_frame_;
    cv::Mat motion_history_;
    cv::Mat motion_map_;
    
    DetectionConfig config_;
    bool enabled_;
    bool initialized_;
    
    // Processing parameters
    int history_length_ = 30;
    int learning_rate_ = 0.005;
    float motion_threshold_ = 0.3f;
    int minimum_contour_area_ = 100;
    
    // Detection results
    mutable std::mutex detections_mutex_;
    std::vector<MotionDetection> recent_detections_;
    
    // Statistics
    std::atomic<uint64_t> frames_processed_{0};
    std::atomic<uint64_t> motions_detected_{0};
    std::atomic<uint64_t> processing_time_us_{0};
};

// Object Detector (simplified implementation)
class ObjectDetector {
public:
    explicit ObjectDetector(const DetectionConfig& config);
    ~ObjectDetector();
    
    bool initialize();
    void stop();
    bool is_enabled() const { return enabled_; }
    bool is_healthy() const { return initialized_; }
    
    // Processing
    void process_frame(const VideoFrame& frame);
    std::vector<ObjectDetection> get_detections() const;
    
    // Configuration
    void set_enabled(bool enabled);
    void set_model_path(const std::string& model_path);
    void set_confidence_threshold(float threshold);
    void update_config(const DetectionConfig& config);
    
    // Model training (simplified)
    bool train_model(const std::vector<VideoFrame>& training_frames, 
                     const std::vector<std::vector<ObjectDetection>>& labels);
    
    // Statistics
    uint64_t get_frames_processed() const { return frames_processed_.load(); }
    uint64_t get_objects_detected() const { return objects_detected_.load(); }
    
private:
    bool load_model();
    std::vector<ObjectDetection> run_detection(const cv::Mat& frame);
    std::vector<ObjectDetection> run_simplified_detection(const cv::Mat& frame);
    void preprocess_frame(const cv::Mat& input, cv::Mat& output);
    void postprocess_detections(std::vector<ObjectDetection>& detections);
    
    // Model management
    std::string model_path_;
    cv::dnn::Net neural_network_;
    std::vector<std::string> class_names_;
    bool model_loaded_;
    
    // Detection configuration
    float confidence_threshold_;
    float nms_threshold_;
    int input_width_;
    int input_height_;
    
    DetectionConfig config_;
    bool enabled_;
    bool initialized_;
    
    // Detection results
    mutable std::mutex detections_mutex_;
    std::vector<ObjectDetection> recent_detections_;
    
    // Statistics
    std::atomic<uint64_t> frames_processed_{0};
    std::atomic<uint64_t> objects_detected_{0};
    std::atomic<uint64_t> processing_time_us_{0};
};

// Lens Corrector
class LensCorrector {
public:
    explicit LensCorrector(const DetectionConfig& config);
    ~LensCorrector();
    
    bool initialize();
    void stop();
    bool is_enabled() const { return enabled_; }
    bool is_healthy() const { return initialized_; }
    
    // Processing
    void process_frame(VideoFrame& frame);
    
    // Configuration
    void set_enabled(bool enabled);
    void set_distortion_parameters(float k1, float k2, float k3, float fov);
    void update_config(const DetectionConfig& config);
    
    // Calibration
    bool calibrate(const std::vector<VideoFrame>& calibration_frames);
    float calculate_calibration_error();
    
    // Statistics
    uint64_t get_frames_processed() const { return frames_processed_.load(); }
    uint64_t get_frames_corrected() const { return frames_corrected_.load(); }
    
private:
    void initialize_distortion_map();
    void apply_distortion_correction(VideoFrame& frame);
    
    // Distortion parameters
    float k1_, k2_, k3_; // Radial distortion coefficients
    float fov_; // Field of view
    cv::Mat distortion_map_x_;
    cv::Mat distortion_map_y_;
    
    // Calibration data
    std::vector<std::vector<cv::Point2f>> calibration_points_;
    std::vector<cv::Point2f> detected_corners_;
    cv::Mat camera_matrix_;
    cv::Mat distortion_coefficients_;
    bool calibrated_;
    
    DetectionConfig config_;
    bool enabled_;
    bool initialized_;
    
    // Statistics
    std::atomic<uint64_t> frames_processed_{0};
    std::atomic<uint64_t> frames_corrected_{0};
    std::atomic<uint64_t> processing_time_us_{0};
    float average_correction_time_ms_{0.0f};
};

} // namespace fpv_streamer

// OpenCV DataType specialization for ObjectDetection
namespace cv {
template<>
struct DataType<fpv_streamer::ObjectDetection> {
    using value_type = fpv_streamer::ObjectDetection;
    using work_type = value_type;
    using channel_type = value_type;
    using accum_type = float;
    using scale_type = float;
    
    enum {
        type = CV_8UC1,
        channels = 1,
        depth = CV_8U
    };
};
} // namespace cv