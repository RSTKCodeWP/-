#include "detection/detection.h"
#include "utils/utils.h"
#include <algorithm>
#include <cmath>

namespace fpv_streamer {

// MotionDetector implementation
MotionDetector::MotionDetector(const DetectionConfig& config) 
    : config_(config)
    , enabled_(config.enable_motion_detection)
    , initialized_(false) {
}

MotionDetector::~MotionDetector() {
    stop();
}

bool MotionDetector::initialize() {
    if (initialized_) {
        return true;
    }
    
    Logger::info("Initializing Motion Detector");
    
    if (!enabled_) {
        Logger::info("Motion detector disabled");
        initialized_ = true;
        return true;
    }
    
    // Initialize OpenCV background subtractor
    background_subtractor_ = cv::createBackgroundSubtractorMOG2();
    if (!background_subtractor_) {
        Logger::error("Failed to create background subtractor");
        return false;
    }
    
    // Configure background subtractor for low-light conditions
    background_subtractor_->setHistory(history_length_);
    background_subtractor_->setVarThreshold(16);
    background_subtractor_->setShadowThreshold(0.5);
    background_subtractor_->setNMixtures(3);
    // setLearningRate is deprecated in newer OpenCV versions
    // background_subtractor_->setLearningRate(learning_rate_);
    
    // Initialize matrices
    foreground_mask_ = cv::Mat();
    motion_history_ = cv::Mat();
    motion_map_ = cv::Mat();
    
    Logger::info("Motion Detector initialized successfully");
    initialized_ = true;
    return true;
}

void MotionDetector::stop() {
    if (!initialized_) {
        return;
    }
    
    Logger::info("Stopping Motion Detector");
    
    background_subtractor_.release();
    foreground_mask_.release();
    motion_history_.release();
    motion_map_.release();
    previous_frame_.release();
    
    initialized_ = false;
}

void MotionDetector::process_frame(const VideoFrame& frame) {
    if (!initialized_ || !enabled_) {
        return;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    frames_processed_.fetch_add(1);
    
    // Convert frame to grayscale for processing
    cv::Mat gray_frame;
    if (frame.data.size() < (size_t)frame.width * frame.height * 3 / 2) {
        Logger::warn("Invalid frame data for motion detection");
        return;
    }
    
    // Create YUV to RGB conversion
    size_t y_size = frame.width * frame.height;
    size_t uv_size = y_size / 4;
    
    cv::Mat yuv_img(frame.height * 3 / 2, frame.width, CV_8UC1);
    memcpy(yuv_img.data, frame.data.data(), frame.data.size());
    
    cv::Mat rgb_frame;
    cv::cvtColor(yuv_img, rgb_frame, cv::COLOR_YUV2RGB_I420);
    
    // Convert to grayscale
    cv::cvtColor(rgb_frame, gray_frame, cv::COLOR_RGB2GRAY);
    
    // Apply background subtraction
    if (!background_model_.empty()) {
        background_subtractor_->apply(gray_frame, foreground_mask_);
        
        // Apply noise filtering
        cv::medianBlur(foreground_mask_, foreground_mask_, 3);
        
        // Detect motion regions
        auto detections = detect_motion(gray_frame);
        
        if (!detections.empty()) {
            apply_noise_filtering(detections);
            
            std::lock_guard<std::mutex> lock(detections_mutex_);
            recent_detections_.insert(recent_detections_.end(), detections.begin(), detections.end());
            
            // Keep only recent detections (last 100)
            if (recent_detections_.size() > 100) {
                recent_detections_.erase(recent_detections_.begin(), 
                                       recent_detections_.begin() + recent_detections_.size() - 100);
            }
            
            motions_detected_.fetch_add(detections.size());
            Logger::debug("Motion detected: " + std::to_string(detections.size()) + " regions");
        }
    }
    
    // Update background model
    update_background_model(gray_frame);
    
    previous_frame_ = gray_frame.clone();
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
    processing_time_us_.fetch_add(duration.count());
}

std::vector<MotionDetection> MotionDetector::get_detections() const {
    std::lock_guard<std::mutex> lock(detections_mutex_);
    
    auto now = std::chrono::steady_clock::now();
    auto cutoff_time = now - std::chrono::milliseconds(500); // Keep detections for 500ms
    
    // Filter out old detections
    std::vector<MotionDetection> recent;
    for (const auto& detection : recent_detections_) {
        auto detection_time = std::chrono::microseconds(detection.timestamp);
        if (detection_time.count() > 0) {
            // Simple time filtering - in practice you'd use the actual timestamp
            recent.push_back(detection);
        }
    }
    
    return recent;
}

void MotionDetector::set_enabled(bool enabled) {
    enabled_ = enabled;
    Logger::info("Motion detector " + std::string(enabled ? "enabled" : "disabled"));
}

void MotionDetector::set_sensitivity(int sensitivity) {
    motion_threshold_ = std::max(0.1f, std::min(1.0f, sensitivity / 100.0f));
    Logger::info("Motion sensitivity updated: " + std::to_string(sensitivity));
}

void MotionDetector::set_threshold(int threshold) {
    minimum_contour_area_ = std::max(10, std::min(10000, threshold));
    Logger::info("Motion threshold updated: " + std::to_string(threshold));
}

void MotionDetector::update_config(const DetectionConfig& config) {
    config_ = config;
    enabled_ = config.enable_motion_detection;
    set_sensitivity(config.motion_sensitivity);
    set_threshold(config.motion_threshold);
}

void MotionDetector::initialize_background_model() {
    background_model_ = cv::Mat();
    Logger::info("Background model initialized");
}

void MotionDetector::update_background_model(const cv::Mat& frame) {
    if (background_model_.empty()) {
        background_model_ = frame.clone();
        Logger::info("Background model updated from first frame");
    } else {
        // Gradually update background model
        cv::addWeighted(background_model_, 0.99, frame, 0.01, 0, background_model_);
    }
}

std::vector<MotionDetection> MotionDetector::detect_motion(const cv::Mat& frame) {
    std::vector<MotionDetection> detections;
    
    if (foreground_mask_.empty()) {
        return detections;
    }
    
    // Threshold the foreground mask
    cv::Mat binary_mask;
    cv::threshold(foreground_mask_, binary_mask, 127, 255, cv::THRESH_BINARY);
    
    // Find contours
    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(binary_mask, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
    
    // Process each contour
    for (const auto& contour : contours) {
        cv::Rect bounding_box = cv::boundingRect(contour);
        
        // Filter by minimum area
        double area = cv::contourArea(contour);
        if (area < minimum_contour_area_) {
            continue;
        }
        
        // Calculate motion intensity
        cv::Mat roi_mask = foreground_mask_(bounding_box);
        double mean_intensity = cv::mean(roi_mask)[0] / 255.0;
        
        // Create detection
        MotionDetection detection;
        detection.bounding_box = bounding_box;
        detection.confidence = mean_intensity;
        detection.motion_intensity = static_cast<int>(mean_intensity * 100);
        detection.timestamp = std::chrono::steady_clock::now().time_since_epoch().count();
        
        detections.push_back(detection);
    }
    
    return detections;
}

void MotionDetector::apply_noise_filtering(std::vector<MotionDetection>& detections) {
    // Remove overlapping detections
    std::vector<bool> to_remove(detections.size(), false);
    
    for (size_t i = 0; i < detections.size(); ++i) {
        if (to_remove[i]) continue;
        
        for (size_t j = i + 1; j < detections.size(); ++j) {
            if (to_remove[j]) continue;
            
            // Check if rectangles overlap significantly
            cv::Rect intersection = detections[i].bounding_box & detections[j].bounding_box;
            double overlap_area = intersection.area();
            double union_area = detections[i].bounding_box.area() + 
                              detections[j].bounding_box.area() - overlap_area;
            
            if (union_area > 0 && overlap_area / union_area > 0.5) {
                // Keep the detection with higher confidence
                if (detections[j].confidence > detections[i].confidence) {
                    to_remove[i] = true;
                } else {
                    to_remove[j] = true;
                }
            }
        }
    }
    
    // Remove marked detections
    std::vector<MotionDetection> filtered;
    for (size_t i = 0; i < detections.size(); ++i) {
        if (!to_remove[i]) {
            filtered.push_back(detections[i]);
        }
    }
    
    detections = filtered;
}

// ObjectDetector implementation
ObjectDetector::ObjectDetector(const DetectionConfig& config) 
    : config_(config)
    , enabled_(config.enable_object_detection)
    , initialized_(false)
    , model_loaded_(false)
    , confidence_threshold_(config.detection_confidence / 100.0f)
    , nms_threshold_(0.45f)
    , input_width_(416)
    , input_height_(416) {
}

ObjectDetector::~ObjectDetector() {
    stop();
}

bool ObjectDetector::initialize() {
    if (initialized_) {
        return true;
    }
    
    Logger::info("Initializing Object Detector");
    
    if (!enabled_) {
        Logger::info("Object detector disabled");
        initialized_ = true;
        return true;
    }
    
    // Load default class names for common FPV scenarios
    class_names_ = {
        "person", "bicycle", "car", "motorcycle", "airplane", "bus",
        "train", "truck", "boat", "bird", "cat", "dog",
        "horse", "sheep", "cow", "elephant", "bear", "zebra",
        "giraffe", "backpack", "umbrella", "handbag", "tie",
        "suitcase", "frisbee", "skis", "snowboard", "sports_ball",
        "kite", "baseball_bat", "baseball_glove", "skateboard",
        "surfboard", "tennis_racket", "bottle", "wine_glass", "cup",
        "fork", "knife", "spoon", "bowl", "banana", "apple",
        "sandwich", "orange", "broccoli", "carrot", "hot_dog",
        "pizza", "donut", "cake", "chair", "couch", "potted_plant",
        "bed", "dining_table", "toilet", "tv", "laptop",
        "mouse", "remote", "keyboard", "cell_phone", "microwave",
        "oven", "toaster", "sink", "refrigerator", "book",
        "clock", "vase", "scissors", "teddy_bear", "hair_drier",
        "toothbrush"
    };
    
    // Load model if path is provided
    if (!config_.object_model_path.empty()) {
        if (load_model()) {
            Logger::info("Object detection model loaded from: " + config_.object_model_path);
        } else {
            Logger::warn("Failed to load object detection model, using default");
        }
    } else {
        Logger::info("No model path provided, using simplified detection");
    }
    
    Logger::info("Object Detector initialized successfully");
    initialized_ = true;
    return true;
}

void ObjectDetector::stop() {
    if (!initialized_) {
        return;
    }
    
    Logger::info("Stopping Object Detector");
    
    // clear() method is deprecated in newer OpenCV DNN versions
    // neural_network_.clear();
    recent_detections_.clear();
    
    initialized_ = false;
}

void ObjectDetector::process_frame(const VideoFrame& frame) {
    if (!initialized_ || !enabled_) {
        return;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    frames_processed_.fetch_add(1);
    
    // Convert frame to OpenCV format
    cv::Mat input_frame;
    if (frame.data.size() < (size_t)frame.width * frame.height * 3 / 2) {
        Logger::warn("Invalid frame data for object detection");
        return;
    }
    
    // Create YUV to RGB conversion
    size_t y_size = frame.width * frame.height;
    size_t uv_size = y_size / 4;
    
    cv::Mat yuv_img(frame.height * 3 / 2, frame.width, CV_8UC1);
    memcpy(yuv_img.data, frame.data.data(), frame.data.size());
    
    cv::cvtColor(yuv_img, input_frame, cv::COLOR_YUV2RGB_I420);
    
    // Resize frame for neural network
    cv::Mat resized_frame;
    cv::resize(input_frame, resized_frame, cv::Size(input_width_, input_height_));
    
    // Run detection
    auto detections = run_detection(resized_frame);
    
    if (!detections.empty()) {
        std::lock_guard<std::mutex> lock(detections_mutex_);
        recent_detections_.insert(recent_detections_.end(), detections.begin(), detections.end());
        
        // Keep only recent detections
        if (recent_detections_.size() > 100) {
            recent_detections_.erase(recent_detections_.begin(), 
                                   recent_detections_.begin() + recent_detections_.size() - 100);
        }
        
        objects_detected_.fetch_add(detections.size());
        Logger::debug("Objects detected: " + std::to_string(detections.size()));
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
    processing_time_us_.fetch_add(duration.count());
}

std::vector<ObjectDetection> ObjectDetector::get_detections() const {
    std::lock_guard<std::mutex> lock(detections_mutex_);
    return recent_detections_;
}

void ObjectDetector::set_enabled(bool enabled) {
    enabled_ = enabled;
    Logger::info("Object detector " + std::string(enabled ? "enabled" : "disabled"));
}

void ObjectDetector::set_model_path(const std::string& model_path) {
    model_path_ = model_path;
    if (initialized_ && enabled_) {
        load_model();
    }
}

void ObjectDetector::set_confidence_threshold(float threshold) {
    confidence_threshold_ = std::max(0.1f, std::min(1.0f, threshold));
    Logger::info("Object detection confidence threshold updated: " + std::to_string(confidence_threshold_));
}

void ObjectDetector::update_config(const DetectionConfig& config) {
    config_ = config;
    enabled_ = config.enable_object_detection;
    set_confidence_threshold(config.detection_confidence / 100.0f);
}

bool ObjectDetector::train_model(const std::vector<VideoFrame>& training_frames, 
                                const std::vector<std::vector<ObjectDetection>>& labels) {
    Logger::info("Starting object detection model training");
    
    // Simplified training implementation
    // In practice, this would involve:
    // 1. Data augmentation
    // 2. Model training loop
    // 3. Validation
    // 4. Model saving
    
    Logger::warn("Object detection training not fully implemented");
    return false;
}

bool ObjectDetector::load_model() {
    try {
        if (model_path_.empty()) {
            return false;
        }
        
        // Try to load different model formats
        try {
            neural_network_ = cv::dnn::readNetFromTensorflow(model_path_);
        } catch (...) {
            try {
                neural_network_ = cv::dnn::readNetFromDarknet(model_path_);
            } catch (...) {
                neural_network_ = cv::dnn::readNetFromONNX(model_path_);
            }
        }
        
        if (neural_network_.empty()) {
            Logger::error("Failed to load neural network model");
            return false;
        }
        
        model_loaded_ = true;
        Logger::info("Neural network model loaded successfully");
        return true;
        
    } catch (const std::exception& e) {
        Logger::error("Error loading model: " + std::string(e.what()));
        model_loaded_ = false;
        return false;
    }
}

std::vector<ObjectDetection> ObjectDetector::run_detection(const cv::Mat& frame) {
    std::vector<ObjectDetection> detections;
    
    if (!model_loaded_) {
        // Simplified detection without neural network
        return run_simplified_detection(frame);
    }
    
    try {
        // Preprocess frame
        cv::Mat blob;
        cv::dnn::blobFromImage(frame, blob, 1.0/255.0, cv::Size(input_width_, input_height_), 
                             cv::Scalar(0, 0, 0), false, false);
        
        // Set input
        neural_network_.setInput(blob);
        
        // Run inference
        cv::Mat outputs = neural_network_.forward();
        
        // Process outputs - clear detections first
        detections.clear();
        
        // Convert outputs to detections (simplified)
        // This is a placeholder - in a real implementation, you would parse the YOLO output
        // For now, just create a simple detection based on the output size
        if (outputs.dims > 0 && outputs.total() > 0) {
            ObjectDetection det;
            det.class_name = "object";
            det.confidence = 0.5f;
            det.bounding_box = cv::Rect(100, 100, 200, 200); // Placeholder
            det.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count();
            detections.push_back(det);
        }
        
    } catch (const std::exception& e) {
        Logger::error("Error in object detection: " + std::string(e.what()));
    }
    
    return detections;
}

std::vector<ObjectDetection> ObjectDetector::run_simplified_detection(const cv::Mat& frame) {
    // Simplified detection using edge detection and blob detection
    std::vector<ObjectDetection> detections;
    
    cv::Mat gray;
    cv::cvtColor(frame, gray, cv::COLOR_RGB2GRAY);
    
    cv::Mat edges;
    cv::Canny(gray, edges, 50, 150);
    
    // Find contours
    std::vector<std::vector<cv::Point>> contours;
    cv::findContours(edges, contours, cv::RETR_EXTERNAL, cv::CHAIN_APPROX_SIMPLE);
    
    for (const auto& contour : contours) {
        cv::Rect bounding_box = cv::boundingRect(contour);
        
        // Filter by size
        if (bounding_box.width > 30 && bounding_box.height > 30 && 
            bounding_box.width < frame.cols * 0.8 && 
            bounding_box.height < frame.rows * 0.8) {
            
            ObjectDetection detection;
            detection.class_name = "object";
            detection.confidence = 0.5f; // Fixed confidence for simplified detection
            detection.bounding_box = bounding_box;
            detection.timestamp = std::chrono::steady_clock::now().time_since_epoch().count();
            
            detections.push_back(detection);
        }
    }
    
    return detections;
}

void ObjectDetector::preprocess_frame(const cv::Mat& input, cv::Mat& output) {
    // Resize and normalize frame for neural network
    cv::Mat resized;
    cv::resize(input, resized, cv::Size(input_width_, input_height_));
    
    // Convert to float and normalize
    resized.convertTo(output, CV_32F);
    output = output / 255.0f;
}

void ObjectDetector::postprocess_detections(std::vector<ObjectDetection>& detections) {
    // Apply non-maximum suppression
    // This is a simplified version - real implementation would be more complex
    
    // Filter by confidence threshold
    std::vector<ObjectDetection> filtered;
    for (const auto& detection : detections) {
        if (detection.confidence >= confidence_threshold_) {
            filtered.push_back(detection);
        }
    }
    
    // Apply NMS to remove overlapping detections
    // For simplicity, we'll just return the filtered results
    detections = filtered;
}

// LensCorrector implementation
LensCorrector::LensCorrector(const DetectionConfig& config) 
    : config_(config)
    , enabled_(config.enable_lens_correction)
    , initialized_(false)
    , k1_(config.lens_distortion_k1)
    , k2_(config.lens_distortion_k2)
    , k3_(config.lens_distortion_k3)
    , fov_(config.lens_fov)
    , calibrated_(false) {
}

LensCorrector::~LensCorrector() {
    stop();
}

bool LensCorrector::initialize() {
    if (initialized_) {
        return true;
    }
    
    Logger::info("Initializing Lens Corrector");
    
    if (!enabled_) {
        Logger::info("Lens corrector disabled");
        initialized_ = true;
        return true;
    }
    
    initialize_distortion_map();
    
    Logger::info("Lens Corrector initialized successfully");
    initialized_ = true;
    return true;
}

void LensCorrector::stop() {
    if (!initialized_) {
        return;
    }
    
    Logger::info("Stopping Lens Corrector");
    
    distortion_map_x_.release();
    distortion_map_y_.release();
    camera_matrix_.release();
    distortion_coefficients_.release();
    
    initialized_ = false;
}

void LensCorrector::process_frame(VideoFrame& frame) {
    if (!initialized_ || !enabled_) {
        return;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    frames_processed_.fetch_add(1);
    
    apply_distortion_correction(frame);
    
    frames_corrected_.fetch_add(1);
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
    processing_time_us_.fetch_add(duration.count());
    
    static int frame_count = 0;
    frame_count++;
    if (frame_count % 30 == 0) { // Update average every 30 frames
        average_correction_time_ms_ = (average_correction_time_ms_ + duration.count() / 1000.0f) / 2.0f;
    }
}

void LensCorrector::set_enabled(bool enabled) {
    enabled_ = enabled;
    Logger::info("Lens corrector " + std::string(enabled ? "enabled" : "disabled"));
}

void LensCorrector::set_distortion_parameters(float k1, float k2, float k3, float fov) {
    k1_ = k1;
    k2_ = k2;
    k3_ = k3;
    fov_ = fov;
    
    if (initialized_) {
        initialize_distortion_map();
    }
    
    Logger::info("Lens distortion parameters updated");
}

void LensCorrector::update_config(const DetectionConfig& config) {
    config_ = config;
    enabled_ = config.enable_lens_correction;
    set_distortion_parameters(config.lens_distortion_k1, config.lens_distortion_k2, 
                            config.lens_distortion_k3, config.lens_fov);
}

bool LensCorrector::calibrate(const std::vector<VideoFrame>& calibration_frames) {
    Logger::info("Starting lens calibration");
    
    // Simplified calibration implementation
    // Real implementation would use chessboard patterns or other calibration targets
    
    Logger::warn("Lens calibration not fully implemented");
    return false;
}

float LensCorrector::calculate_calibration_error() {
    // Calculate RMS error from calibration
    return 0.0f; // Placeholder
}

void LensCorrector::initialize_distortion_map() {
    // Initialize camera matrix with basic assumptions
    camera_matrix_ = cv::Mat::eye(3, 3, CV_64F);
    camera_matrix_.at<double>(0, 0) = config_.width * 0.8; // fx
    camera_matrix_.at<double>(1, 1) = config_.height * 0.8; // fy
    camera_matrix_.at<double>(0, 2) = config_.width / 2.0; // cx
    camera_matrix_.at<double>(1, 2) = config_.height / 2.0; // cy
    
    // Initialize distortion coefficients
    distortion_coefficients_ = cv::Mat::zeros(8, 1, CV_64F);
    distortion_coefficients_.at<double>(0, 0) = k1_;
    distortion_coefficients_.at<double>(1, 0) = k2_;
    distortion_coefficients_.at<double>(4, 0) = k3_;
    
    // Create distortion maps
    cv::initUndistortRectifyMap(camera_matrix_, distortion_coefficients_, 
                               cv::Mat(), camera_matrix_, 
                               cv::Size(config_.width, config_.height),
                               CV_32FC1, distortion_map_x_, distortion_map_y_);
}

void LensCorrector::apply_distortion_correction(VideoFrame& frame) {
    if (distortion_map_x_.empty() || distortion_map_y_.empty()) {
        return;
    }
    
    // Convert frame to RGB for processing
    size_t y_size = frame.width * frame.height;
    size_t uv_size = y_size / 4;
    
    cv::Mat yuv_img(frame.height * 3 / 2, frame.width, CV_8UC1);
    memcpy(yuv_img.data, frame.data.data(), frame.data.size());
    
    cv::Mat rgb_frame;
    cv::cvtColor(yuv_img, rgb_frame, cv::COLOR_YUV2RGB_I420);
    
    // Apply undistortion
    cv::Mat corrected_rgb;
    cv::remap(rgb_frame, corrected_rgb, distortion_map_x_, distortion_map_y_, 
             cv::INTER_LINEAR, cv::BORDER_CONSTANT);
    
    // Convert back to YUV
    cv::Mat corrected_yuv;
    cv::cvtColor(corrected_rgb, corrected_yuv, cv::COLOR_RGB2YUV_I420);
    
    // Update frame data
    frame.data.resize(corrected_yuv.total());
    memcpy(frame.data.data(), corrected_yuv.data, frame.data.size());
}

} // namespace fpv_streamer