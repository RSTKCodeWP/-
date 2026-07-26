#include "server/server.h"
#include "utils/utils.h"
#include <iostream>
#include <chrono>
#include <sstream>

namespace fpv_streamer {

Server::Server(ConfigManager& config) 
    : config_(config) {
    
    Logger::info("Initializing FPV Streamer Server...");
    
    // Initialize performance tracking
    processing_timer_ = std::make_unique<Timer>();
    streaming_timer_ = std::make_unique<Timer>();
    
    // Check hardware compatibility
    if (!check_hardware_compatibility()) {
        Logger::warn("Hardware compatibility issues detected, some features may be limited");
    }
}

Server::~Server() {
    stop();
}

bool Server::start() {
    if (running_.load()) {
        Logger::warn("Server already running");
        return true;
    }
    
    Logger::info("Starting FPV Streamer Server...");
    
    // Initialize all components
    if (!initialize_components()) {
        Logger::error("Failed to initialize components");
        return false;
    }
    
    // Start main processing thread
    running_.store(true);
    main_thread_ = std::thread(&Server::main_loop, this);
    
    // Start frame processing thread
    frame_processing_thread_ = std::thread(&Server::frame_processing_thread, this);
    
    Logger::info("FPV Streamer Server started successfully");
    Logger::info("Web interface available at: http://localhost:" + std::to_string(config_.get_web_config().port));
    
    return true;
}

void Server::stop() {
    if (!running_.load()) {
        return;
    }
    
    Logger::info("Stopping FPV Streamer Server...");
    running_.store(false);
    
    // Signal frame processing thread to stop
    frame_ready_condition_.notify_all();
    
    // Wait for threads to finish
    if (main_thread_.joinable()) {
        main_thread_.join();
    }
    
    if (frame_processing_thread_.joinable()) {
        frame_processing_thread_.join();
    }
    
    // Stop all components
    if (video_capture_) video_capture_->stop();
    if (stream_manager_) stream_manager_->stop();
    if (web_interface_) web_interface_->stop();
    
    Logger::info("FPV Streamer Server stopped");
}

void Server::process_events() {
    // Process web interface events
    if (web_interface_) {
        web_interface_->process_requests();
    }
    
    // Update performance statistics
    update_performance_stats();
    
    // Check component health
    if (video_capture_ && !video_capture_->is_healthy()) {
        Logger::warn("Video capture unhealthy, attempting recovery");
        video_capture_->restart();
    }
    
    if (stream_manager_ && !stream_manager_->is_healthy()) {
        Logger::warn("Stream manager unhealthy, attempting recovery");
        stream_manager_->restart();
    }
}

std::string Server::get_status() const {
    std::ostringstream status;
    status << "FPV Streamer Status\n";
    status << "==================\n";
    status << "Running: " << (running_.load() ? "Yes" : "No") << "\n";
    status << "Frames Processed: " << frames_processed_.load() << "\n";
    status << "Frames Streamed: " << frames_streamed_.load() << "\n";
    status << "Current FPS: " << get_fps() << "\n";
    status << "Video Device: " << config_.get_video_config().device_path << "\n";
    status << "Resolution: " << config_.get_video_config().width << "x" << config_.get_video_config().height << "\n";
    status << "Framerate: " << config_.get_video_config().fps << " fps\n";
    status << "Bitrate: " << (config_.get_video_config().bitrate / 1000) << " kbps\n";
    status << "Encoder: " << config_.get_video_config().encoder_type << "\n";
    status << "Hardware Encode: " << (config_.get_video_config().use_hardware_encoder ? "Yes" : "No") << "\n";
    status << "Motion Detection: " << (config_.get_detection_config().enable_motion_detection ? "Enabled" : "Disabled") << "\n";
    status << "Object Detection: " << (config_.get_detection_config().enable_object_detection ? "Enabled" : "Disabled") << "\n";
    status << "Recording: " << (config_.get_recording_config().enable_recording ? "Enabled" : "Disabled") << "\n";
    
    return status.str();
}

double Server::get_fps() const {
    return performance_stats_.current_fps;
}

bool Server::initialize_components() {
    std::lock_guard<std::mutex> lock(component_mutex_);
    
    try {
        // Initialize video capture
        video_capture_ = std::make_unique<VideoCapture>(config_.get_video_config());
        if (!video_capture_->initialize()) {
            Logger::error("Failed to initialize video capture");
            return false;
        }
        
        // Set up frame ready callback for thread synchronization
        video_capture_->set_frame_ready_callback([this]() {
            new_frame_ready_.store(true);
            frame_ready_condition_.notify_one();
        });
        
        // Initialize video encoder
        video_encoder_ = std::make_unique<VideoEncoder>(config_.get_video_config());
        if (!video_encoder_->initialize()) {
            Logger::error("Failed to initialize video encoder");
            return false;
        }
        
        // Initialize compression engine
        compression_engine_ = std::make_unique<CompressionEngine>(config_.get_video_config());
        if (!compression_engine_->initialize()) {
            Logger::error("Failed to initialize compression engine");
            return false;
        }
        
        // Initialize stream manager
        stream_manager_ = std::make_unique<StreamManager>(config_.get_stream_config());
        if (!stream_manager_->initialize()) {
            Logger::error("Failed to initialize stream manager");
            return false;
        }
        
        // Initialize detection components
        motion_detector_ = std::make_unique<MotionDetector>(config_.get_detection_config());
        if (!motion_detector_->initialize()) {
            Logger::warn("Failed to initialize motion detector");
        }
        
        object_detector_ = std::make_unique<ObjectDetector>(config_.get_detection_config());
        if (!object_detector_->initialize()) {
            Logger::warn("Failed to initialize object detector");
        }
        
        lens_corrector_ = std::make_unique<LensCorrector>(config_.get_detection_config());
        if (!lens_corrector_->initialize()) {
            Logger::warn("Failed to initialize lens corrector");
        }
        
        // Initialize web interface
        web_interface_ = std::make_unique<WebInterface>(config_);
        if (!web_interface_->initialize()) {
            Logger::error("Failed to initialize web interface");
            return false;
        }
        
        // Initialize frame buffer
        frame_buffer_ = std::make_unique<FrameBuffer>(config_.get_video_config());
        
        Logger::info("All components initialized successfully");
        return true;
        
    } catch (const std::exception& e) {
        Logger::error("Exception during component initialization: " + std::string(e.what()));
        return false;
    }
}

void Server::main_loop() {
    Logger::info("Main loop started");
    
    while (running_.load()) {
        try {
            // Process web requests
            process_events();
            
            // Check for configuration updates
            // (This would be triggered by web interface)
            
            // Update performance stats every second
            static auto last_stats_update = std::chrono::steady_clock::now();
            auto now = std::chrono::steady_clock::now();
            if (std::chrono::duration_cast<std::chrono::seconds>(now - last_stats_update).count() >= 1) {
                update_performance_stats();
                last_stats_update = now;
            }
            
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            
        } catch (const std::exception& e) {
            Logger::error("Exception in main loop: " + std::string(e.what()));
            performance_stats_.error_count++;
        }
    }
    
    Logger::info("Main loop stopped");
}

void Server::frame_processing_thread() {
    Logger::info("Frame processing thread started");
    
    while (running_.load()) {
        try {
            // Wait for new frame
            std::unique_lock<std::mutex> lock(component_mutex_);
            frame_ready_condition_.wait(lock, [this] { return new_frame_ready_.load() || !running_.load(); });
            
            if (!running_.load()) break;
            
            // Process the frame
            processing_timer_->start();
            
            // Capture frame
            auto frame = video_capture_->capture_frame();
            if (!frame) {
                Logger::warn("Failed to capture frame");
                continue;
            }
            
            frames_processed_.fetch_add(1);
            
            // Apply lens correction if enabled
            if (lens_corrector_ && config_.get_detection_config().enable_lens_correction) {
                lens_corrector_->process_frame(*frame);
            }
            
            // Apply motion detection
            if (motion_detector_ && config_.get_detection_config().enable_motion_detection) {
                motion_detector_->process_frame(*frame);
            }
            
            // Apply object detection
            if (object_detector_ && config_.get_detection_config().enable_object_detection) {
                object_detector_->process_frame(*frame);
            }
            
            // Apply region-based compression
            if (compression_engine_) {
                compression_engine_->process_frame(*frame);
            }
            
            // Encode frame
            auto encoded_frame = video_encoder_->encode_frame(*frame);
            if (!encoded_frame) {
                Logger::warn("Failed to encode frame");
                continue;
            }
            
            // Stream frame
            if (stream_manager_ && stream_manager_->is_connected()) {
                if (stream_manager_->send_frame(*encoded_frame)) {
                    frames_streamed_.fetch_add(1);
                }
            }
            
            processing_timer_->stop();
            performance_stats_.avg_processing_time_ms = processing_timer_->get_elapsed_ms();
            
            new_frame_ready_.store(false);
            
        } catch (const std::exception& e) {
            Logger::error("Exception in frame processing: " + std::string(e.what()));
            performance_stats_.error_count++;
        }
    }
    
    Logger::info("Frame processing thread stopped");
}

bool Server::check_hardware_compatibility() {
    bool compatible = true;
    
    // Check video device
    if (access(config_.get_video_config().device_path.c_str(), F_OK) != 0) {
        Logger::warn("Video device not found: " + config_.get_video_config().device_path);
        compatible = false;
    }
    
    // Check for required libraries
    if (!config_.has_hardware_encoder()) {
        Logger::info("Using software encoding");
    }
    
    return compatible;
}

void Server::handle_error(const std::string& component, const std::string& error) {
    Logger::error(component + " error: " + error);
    performance_stats_.error_count++;
    
    // Attempt recovery based on component
    if (component == "video_capture") {
        if (video_capture_) video_capture_->restart();
    } else if (component == "stream_manager") {
        if (stream_manager_) stream_manager_->restart();
    }
}

void Server::update_performance_stats() {
    auto elapsed = processing_timer_->get_elapsed_ms();
    performance_stats_.avg_processing_time_ms = elapsed;
    performance_stats_.current_fps = 1000.0 / std::max(elapsed, 1.0);
    
    if (stream_manager_) {
        performance_stats_.total_bytes_streamed = stream_manager_->get_bytes_sent();
    }
}

void Server::on_config_updated() {
    // Reconfigure components based on updated configuration
    optimize_for_latency();
    
    // Update web interface
    if (web_interface_) {
        web_interface_->refresh_config();
    }
}

void Server::optimize_for_latency() {
    Logger::info("Optimizing for ultra-low latency...");
    
    // Minimize buffering
    if (frame_buffer_) {
        frame_buffer_->set_buffer_size(1); // Single frame buffer
    }
    
    // Use fastest compression settings
    auto video_config = config_.get_video_config();
    video_config.bitrate = std::min(video_config.bitrate, 2000000); // Cap bitrate for latency
    video_config.fps = std::min(video_config.fps, 60); // Cap framerate
    
    // Disable non-essential processing
    if (!config_.get_detection_config().enable_motion_detection) {
        motion_detector_.reset();
    }
    
    Logger::info("Latency optimization complete");
}

} // namespace fpv_streamer