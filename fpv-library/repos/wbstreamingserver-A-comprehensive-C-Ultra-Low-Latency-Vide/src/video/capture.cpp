#include "video/capture.h"
#include "config/config_manager.h"
#include "utils/utils.h"
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <errno.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <iomanip>
#include <sstream>

namespace fpv_streamer {

// FrameBuffer implementation
FrameBuffer::FrameBuffer() : max_buffer_size_(5) {
}

FrameBuffer::FrameBuffer(const VideoConfig& config) : max_buffer_size_(5), config_(config) {
    if (config.fps >= 60) {
        max_buffer_size_ = 3; // Reduce buffer for high FPS
    } else if (config.fps >= 30) {
        max_buffer_size_ = 5;
    } else {
        max_buffer_size_ = 10;
    }
}

FrameBuffer::~FrameBuffer() = default;

bool FrameBuffer::initialize() {
    buffer_.clear();
    return true;
}

void FrameBuffer::set_buffer_size(int size) {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    max_buffer_size_ = std::max(1, std::min(30, size));
    
    // Trim buffer if it's too large
    while (buffer_.size() > max_buffer_size_) {
        buffer_.erase(buffer_.begin());
    }
}

bool FrameBuffer::push_frame(const VideoFrame& frame) {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    
    // Don't add if buffer is full
    if (buffer_.size() >= max_buffer_size_) {
        return false;
    }
    
    buffer_.push_back(std::make_unique<VideoFrame>(frame));
    buffer_condition_.notify_one();
    
    return true;
}

std::unique_ptr<VideoFrame> FrameBuffer::pop_frame() {
    std::unique_lock<std::mutex> lock(buffer_mutex_);
    
    if (buffer_.empty()) {
        return nullptr;
    }
    
    auto frame = std::move(buffer_.front());
    buffer_.erase(buffer_.begin());
    
    return frame;
}

bool FrameBuffer::is_empty() const {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    return buffer_.empty();
}

size_t FrameBuffer::size() const {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    return buffer_.size();
}

void FrameBuffer::clear() {
    std::lock_guard<std::mutex> lock(buffer_mutex_);
    buffer_.clear();
}

// VideoCapture implementation
VideoCapture::VideoCapture(const VideoConfig& config) 
    : config_(config)
    , device_fd_(-1)
    , actual_width_(0)
    , actual_height_(0)
    , actual_fps_(0)
    , actual_pixel_format_(0)
    , num_buffers_(0)
    , current_buffer_index_(0)
    , brightness_(0.0f)
    , contrast_(1.0f)
    , saturation_(1.0f)
    , hue_(0.0f)
    , frame_ready_callback_(nullptr) {
}

VideoCapture::~VideoCapture() {
    stop();
}

bool VideoCapture::initialize() {
    device_path_ = config_.device_path;
    
    // Try to open the device first
    if (!open_device()) {
        Logger::warn("Cannot open video device " + device_path_ + ", trying fallback to sample images");
        
        // Try to load sample images as fallback
        if (load_sample_images()) {
            use_sample_images_.store(true);
            Logger::info("Using sample images fallback - device: " + device_path_);
            
            // Set default format values for sample images
            actual_width_ = config_.width;
            actual_height_ = config_.height;
            actual_fps_ = config_.fps;
            actual_pixel_format_ = V4L2_PIX_FMT_BGR24;
            
            healthy_.store(true);
            return true;
        } else {
            Logger::error("Failed to load sample images as fallback");
            return false;
        }
    }
    
    if (!query_capabilities()) {
        close_device();
        return false;
    }
    
    if (!set_format()) {
        close_device();
        return false;
    }
    
    if (!request_buffers()) {
        close_device();
        return false;
    }
    
    if (!start_streaming()) {
        close_device();
        return false;
    }
    
    healthy_.store(true);
    Logger::info("Video capture initialized: " + std::to_string(actual_width_) + "x" + 
                std::to_string(actual_height_) + "@" + std::to_string(actual_fps_) + "fps");
    
    return true;
}

void VideoCapture::stop() {
    stop_streaming();
    
    if (device_fd_ >= 0) {
        close_device();
    }
    
    healthy_.store(false);
}

bool VideoCapture::is_healthy() const {
    return healthy_.load() && device_fd_ >= 0;
}

void VideoCapture::restart() {
    Logger::debug("Restarting video capture...");
    stop();
    
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    if (initialize()) {
        Logger::debug("Video capture restarted successfully");
    } else {
        Logger::warn("Failed to restart video capture");
    }
}

std::unique_ptr<VideoFrame> VideoCapture::capture_frame() {
    // If using sample images, generate synthetic frames
    if (use_sample_images_.load()) {
        return create_sample_frame();
    }
    
    if (!streaming_active_.load() || device_fd_ < 0) {
        return nullptr;
    }
    
    // Dequeue buffer
    struct v4l2_buffer buf;
    memset(&buf, 0, sizeof(buf));
    buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    
    if (ioctl(device_fd_, VIDIOC_DQBUF, &buf) < 0) {
        if (errno == EAGAIN) {
            return nullptr;
        }
        Logger::error("VIDIOC_DQBUF failed: " + std::string(strerror(errno)));
        return nullptr;
    }
    
    // Create frame
    auto frame = convert_frame(buffer_ptrs_[buf.index], buf.bytesused);
    if (!frame) {
        // Requeue buffer
        ioctl(device_fd_, VIDIOC_QBUF, &buf);
        frames_dropped_.fetch_add(1);
        return nullptr;
    }
    
    frame->timestamp = buf.timestamp.tv_sec * 1000000LL + buf.timestamp.tv_usec;
    frame->sequence = buf.sequence;
    frame->is_keyframe = (buf.flags & V4L2_BUF_FLAG_KEYFRAME) != 0;
    
    // Requeue buffer
    ioctl(device_fd_, VIDIOC_QBUF, &buf);
    
    frames_captured_.fetch_add(1);
    total_bytes_captured_.fetch_add(buf.bytesused);
    
    // Signal frame ready for thread synchronization
    if (frame_ready_callback_) {
        frame_ready_callback_();
    }
    
    return frame;
}

bool VideoCapture::start_capture() {
    // Capture is automatic in streaming mode
    return streaming_active_.load();
}

void VideoCapture::stop_capture() {
    streaming_active_.store(false);
}

std::string VideoCapture::get_device_name() const {
    return device_path_;
}

bool VideoCapture::open_device() {
    device_fd_ = open(device_path_.c_str(), O_RDWR | O_NONBLOCK);
    if (device_fd_ < 0) {
        Logger::warn("Cannot open video device " + device_path_ + ": " + strerror(errno));
        return false;
    }
    
    Logger::debug("Opened video device: " + device_path_);
    return true;
}

bool VideoCapture::close_device() {
    if (device_fd_ >= 0) {
        close(device_fd_);
        device_fd_ = -1;
    }
    return true;
}

bool VideoCapture::set_format() {
    // Set input format first
    if (!set_input_format()) {
        Logger::warn("Failed to set input format, using auto-detection");
    }
    
    struct v4l2_format fmt;
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    
    // Set format based on input configuration
    fmt.fmt.pix.width = config_.width;
    fmt.fmt.pix.height = config_.height;
    
    // Determine pixel format based on input_format setting
    if (config_.input_format == "mjpeg") {
        fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
        Logger::info("Setting MJPEG input format");
    } else if (config_.input_format == "h264") {
        fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_H264;
        Logger::info("Setting H.264 input format");
    } else if (config_.input_format == "raw") {
        fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUV420;
        Logger::info("Setting RAW YUV420 input format");
    } else {
        // Auto-detection
        fmt.fmt.pix.pixelformat = config_.input_pixel_format;
        Logger::info("Using auto-detected input format: " + std::to_string(fmt.fmt.pix.pixelformat));
    }
    
    fmt.fmt.pix.field = V4L2_FIELD_ANY;
    
    if (ioctl(device_fd_, VIDIOC_S_FMT, &fmt) < 0) {
        Logger::error("Failed to set format: " + std::string(strerror(errno)));
        return false;
    }
    
    actual_width_ = fmt.fmt.pix.width;
    actual_height_ = fmt.fmt.pix.height;
    actual_pixel_format_ = fmt.fmt.pix.pixelformat;
    
    // Set framerate
    struct v4l2_streamparm parm;
    memset(&parm, 0, sizeof(parm));
    parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    parm.parm.capture.timeperframe.numerator = 1;
    parm.parm.capture.timeperframe.denominator = config_.fps;
    
    if (ioctl(device_fd_, VIDIOC_S_PARM, &parm) == 0) {
        if (parm.parm.capture.timeperframe.denominator > 0) {
            actual_fps_ = parm.parm.capture.timeperframe.denominator / parm.parm.capture.timeperframe.numerator;
        }
    }
    
    Logger::info("Format set: " + std::to_string(actual_width_) + "x" + 
                std::to_string(actual_height_) + "@" + std::to_string(actual_fps_) + "fps " +
                "Input: " + config_.input_format + " Output: " + config_.output_encoder);
    
    return true;
}

bool VideoCapture::request_buffers() {
    struct v4l2_requestbuffers req;
    memset(&req, 0, sizeof(req));
    req.count = 4;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    
    if (ioctl(device_fd_, VIDIOC_REQBUFS, &req) < 0) {
        Logger::error("Failed to request buffers: " + std::string(strerror(errno)));
        return false;
    }
    
    if (req.count < 2) {
        Logger::error("Insufficient buffer memory");
        return false;
    }
    
    num_buffers_ = req.count;
    
    // Map buffers
    for (int i = 0; i < num_buffers_; i++) {
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index = i;
        
        if (ioctl(device_fd_, VIDIOC_QUERYBUF, &buf) < 0) {
            Logger::error("Failed to query buffer " + std::to_string(i));
            return false;
        }
        
        v4l2_buffers_[i] = buf;
        buffer_ptrs_[i] = mmap(nullptr, buf.length, PROT_READ | PROT_WRITE, 
                              MAP_SHARED, device_fd_, buf.m.offset);
        
        if (buffer_ptrs_[i] == MAP_FAILED) {
            Logger::error("Failed to map buffer " + std::to_string(i));
            return false;
        }
        
        // Queue buffer
        ioctl(device_fd_, VIDIOC_QBUF, &buf);
    }
    
    Logger::info("Request buffers: " + std::to_string(num_buffers_) + " buffers");
    return true;
}

bool VideoCapture::start_streaming() {
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    
    if (ioctl(device_fd_, VIDIOC_STREAMON, &type) < 0) {
        Logger::error("Failed to start streaming: " + std::string(strerror(errno)));
        return false;
    }
    
    streaming_active_.store(true);
    Logger::info("Streaming started");
    return true;
}

void VideoCapture::stop_streaming() {
    if (streaming_active_.load()) {
        enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        ioctl(device_fd_, VIDIOC_STREAMOFF, &type);
        streaming_active_.store(false);
    }
    
    // Unmap buffers
    for (int i = 0; i < num_buffers_; i++) {
        if (buffer_ptrs_[i] != MAP_FAILED && buffer_ptrs_[i] != nullptr) {
            munmap(buffer_ptrs_[i], v4l2_buffers_[i].length);
            buffer_ptrs_[i] = nullptr;
        }
    }
    
    Logger::info("Streaming stopped");
}

bool VideoCapture::query_capabilities() {
    struct v4l2_capability cap;
    memset(&cap, 0, sizeof(cap));
    
    if (ioctl(device_fd_, VIDIOC_QUERYCAP, &cap) < 0) {
        Logger::error("Failed to query capabilities: " + std::string(strerror(errno)));
        return false;
    }
    
    if (!(cap.capabilities & V4L2_CAP_VIDEO_CAPTURE)) {
        Logger::error("Device does not support video capture");
        return false;
    }
    
    if (!(cap.capabilities & V4L2_CAP_STREAMING)) {
        Logger::error("Device does not support streaming");
        return false;
    }
    
    Logger::info("Device capabilities: " + std::string((char*)cap.card));
    return true;
}

std::unique_ptr<VideoFrame> VideoCapture::convert_frame(const void* buffer, size_t buffer_size) {
    if (!buffer || buffer_size == 0) {
        return nullptr;
    }
    
    // Create YUV420 frame
    size_t y_size = actual_width_ * actual_height_;
    size_t uv_size = y_size / 4;
    size_t total_size = y_size + uv_size + uv_size;
    
    if (buffer_size < total_size) {
        Logger::warn("Frame buffer too small");
        return nullptr;
    }
    
    auto frame = std::make_unique<VideoFrame>(actual_width_, actual_height_, 
                                            actual_pixel_format_, 0, frame_sequence_++);
    frame->data.resize(total_size);
    
    // Copy data
    memcpy(frame->data.data(), buffer, total_size);
    
    return frame;
}

bool VideoCapture::apply_cscorrection(VideoFrame& frame) {
    // Basic color correction - could be enhanced
    if (brightness_ != 0.0f || contrast_ != 1.0f || saturation_ != 1.0f) {
        // Apply brightness/contrast/saturation adjustments
        // This is a simplified implementation
        Logger::debug("Applying color correction");
    }
    
    return true;
}

bool VideoCapture::set_input_format() {
    // Check if the requested input format is supported
    if (!is_input_format_supported(config_.input_format)) {
        Logger::warn("Input format " + config_.input_format + " not supported, using auto-detection");
        return false;
    }
    
    // For USB UVC cameras, the format is typically set by the camera itself
    // We just configure our V4L2 capture to expect the right format
    Logger::info("Input format configured: " + config_.input_format);
    return true;
}

bool VideoCapture::is_input_format_supported(const std::string& format) {
    if (format == "auto" || format == "mjpeg" || format == "h264" || format == "raw") {
        return true;
    }
    return false;
}

std::unique_ptr<VideoFrame> VideoCapture::process_mjpeg_input(const void* buffer, size_t buffer_size) {
    Logger::debug("Processing MJPEG input frame, size: " + std::to_string(buffer_size));
    
    auto frame = std::make_unique<VideoFrame>(actual_width_, actual_height_, 
                                            V4L2_PIX_FMT_MJPEG, 0, frame_sequence_++);
    frame->data.resize(buffer_size);
    memcpy(frame->data.data(), buffer, buffer_size);
    
    return frame;
}

std::unique_ptr<VideoFrame> VideoCapture::process_h264_input(const void* buffer, size_t buffer_size) {
    Logger::debug("Processing H.264 input frame, size: " + std::to_string(buffer_size));
    
    auto frame = std::make_unique<VideoFrame>(actual_width_, actual_height_, 
                                            V4L2_PIX_FMT_H264, 0, frame_sequence_++);
    frame->data.resize(buffer_size);
    memcpy(frame->data.data(), buffer, buffer_size);
    
    // Check for keyframe (nal_unit_type == 5 for I-frame)
    const uint8_t* data = static_cast<const uint8_t*>(buffer);
    if (buffer_size >= 4 && (data[4] & 0x1F) == 5) {
        frame->is_keyframe = true;
        Logger::debug("H.264 keyframe detected");
    }
    
    return frame;
}

std::unique_ptr<VideoFrame> VideoCapture::process_raw_input(const void* buffer, size_t buffer_size) {
    Logger::debug("Processing RAW YUV input frame, size: " + std::to_string(buffer_size));
    
    // For RAW input, we expect YUV420 format
    size_t y_size = actual_width_ * actual_height_;
    size_t uv_size = y_size / 4;
    size_t total_size = y_size + uv_size + uv_size;
    
    if (buffer_size < total_size) {
        Logger::warn("RAW frame buffer too small, expected: " + std::to_string(total_size) + 
                    ", got: " + std::to_string(buffer_size));
        return nullptr;
    }
    
    auto frame = std::make_unique<VideoFrame>(actual_width_, actual_height_, 
                                            V4L2_PIX_FMT_YUV420, 0, frame_sequence_++);
    frame->data.resize(total_size);
    memcpy(frame->data.data(), buffer, total_size);
    
    return frame;
}

// DualCameraManager implementation
DualCameraManager::DualCameraManager(const VideoConfig& config1, const StereoConfig& stereo_config)
    : config1_(config1), stereo_config_(stereo_config) {
    
    // Configure second camera settings
    config2_ = config1;
    config2_.device_path = "/dev/video" + std::to_string(stereo_config_.camera2_device);
    config2_.width = config1.camera2_width;
    config2_.height = config1.camera2_height;
    config2_.fps = config1.camera2_fps;
    config2_.input_format = config1.camera2_input_format;
    
    device1_path_ = config1_.device_path;
    device2_path_ = config2_.device_path;
    
    Logger::info("Initializing dual camera manager");
    Logger::info("Camera 1: " + device1_path_);
    Logger::info("Camera 2: " + device2_path_);
    Logger::info("Stereo sync: " + std::string(stereo_config_.enable_frame_sync ? "enabled" : "disabled"));
}

DualCameraManager::~DualCameraManager() {
    shutdown();
}

bool DualCameraManager::initialize() {
    if (stereo_config_.enable_stereo) {
        Logger::info("Initializing dual camera stereo setup");
        
        // Initialize both cameras
        camera1_ = std::make_unique<VideoCapture>(config1_);
        camera2_ = std::make_unique<VideoCapture>(config2_);
        
        bool cam1_success = camera1_->initialize();
        bool cam2_success = camera2_->initialize();
        
        if (!cam1_success && !cam2_success) {
            Logger::error("Failed to initialize both cameras");
            return false;
        }
        
        if (!cam1_success) {
            Logger::warn("Camera 1 not available, using sample images");
            camera1_->set_use_sample_images(true);
            camera1_->initialize();
        }
        
        if (!cam2_success) {
            Logger::warn("Camera 2 not available, using sample images");
            camera2_->set_use_sample_images(true);
            camera2_->initialize();
        }
        
        Logger::info("Dual camera setup initialized (camera1: " + 
                    std::string(camera1_->is_using_sample_images() ? "sample" : "real") + 
                    ", camera2: " + 
                    std::string(camera2_->is_using_sample_images() ? "sample" : "real") + ")");
        healthy_ = true;
        return true;
    } else {
        Logger::info("Stereo mode disabled, using single camera");
        camera1_ = std::make_unique<VideoCapture>(config1_);
        bool success = camera1_->initialize();
        
        if (!success) {
            Logger::warn("Primary camera not available, using sample images");
            camera1_->set_use_sample_images(true);
            success = camera1_->initialize();
        }
        
        return success;
    }
}

void DualCameraManager::shutdown() {
    if (running_.load()) {
        stop_capture();
    }
    
    if (camera1_) {
        camera1_->stop();
    }
    if (camera2_) {
        camera2_->stop();
    }
    
    camera1_.reset();
    camera2_.reset();
    
    healthy_ = false;
    Logger::info("Dual camera manager shutdown");
}

bool DualCameraManager::is_healthy() const {
    if (stereo_config_.enable_stereo) {
        return healthy_.load() && camera1_ && camera2_ && 
               camera1_->is_healthy() && camera2_->is_healthy();
    } else {
        return camera1_ && camera1_->is_healthy();
    }
}

bool DualCameraManager::capture_stereo_frames(StereoFrame& stereo_frame) {
    if (!is_healthy()) {
        return false;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    if (stereo_config_.enable_stereo) {
        // Capture from both cameras with synchronization
        auto frame1 = camera1_->capture_frame();
        auto frame2 = camera2_->capture_frame();
        
        if (!frame1 || !frame2) {
            frames_dropped_++;
            return false;
        }
        
        // Convert VideoFrame to cv::Mat
        cv::Mat mat1, mat2;
        
        if (frame1->pixel_format == V4L2_PIX_FMT_MJPEG) {
            mat1 = cv::imdecode(cv::Mat(frame1->data), cv::IMREAD_COLOR);
        } else if (frame1->pixel_format == V4L2_PIX_FMT_YUV420) {
            cv::cvtColor(cv::Mat(frame1->height, frame1->width, CV_8UC3, frame1->data.data()), 
                        mat1, cv::COLOR_YUV2BGR);
        } else {
            mat1 = cv::Mat(frame1->height, frame1->width, CV_8UC3, frame1->data.data());
        }
        
        if (frame2->pixel_format == V4L2_PIX_FMT_MJPEG) {
            mat2 = cv::imdecode(cv::Mat(frame2->data), cv::IMREAD_COLOR);
        } else if (frame2->pixel_format == V4L2_PIX_FMT_YUV420) {
            cv::cvtColor(cv::Mat(frame2->height, frame2->width, CV_8UC3, frame2->data.data()), 
                        mat2, cv::COLOR_YUV2BGR);
        } else {
            mat2 = cv::Mat(frame2->height, frame2->width, CV_8UC3, frame2->data.data());
        }
        
        // Fill stereo frame structure
        stereo_frame.left_frame = mat1;
        stereo_frame.right_frame = mat2;
        stereo_frame.timestamp = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        stereo_frame.is_valid = !mat1.empty() && !mat2.empty();
        stereo_frame.frame_sequence = frames_captured_.load() + 1;
        
        // Update statistics
        frames_captured_++;
        
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
        sync_latency_ms_.store(duration.count() / 1000.0);
        
        return stereo_frame.is_valid;
    } else {
        // Single camera mode
        auto frame = camera1_->capture_frame();
        if (!frame) {
            frames_dropped_++;
            return false;
        }
        
        cv::Mat mat;
        if (frame->pixel_format == V4L2_PIX_FMT_MJPEG) {
            mat = cv::imdecode(cv::Mat(frame->data), cv::IMREAD_COLOR);
        } else if (frame->pixel_format == V4L2_PIX_FMT_YUV420) {
            cv::cvtColor(cv::Mat(frame->height, frame->width, CV_8UC3, frame->data.data()), 
                        mat, cv::COLOR_YUV2BGR);
        } else {
            mat = cv::Mat(frame->height, frame->width, CV_8UC3, frame->data.data());
        }
        
        stereo_frame.left_frame = mat;
        stereo_frame.right_frame = cv::Mat();
        stereo_frame.timestamp = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        stereo_frame.is_valid = !mat.empty();
        stereo_frame.frame_sequence = frames_captured_.load() + 1;
        
        frames_captured_++;
        
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
        sync_latency_ms_.store(duration.count() / 1000.0);
        
        return stereo_frame.is_valid;
    }
}

void DualCameraManager::start_capture() {
    if (!healthy_.load()) {
        Logger::warn("Cannot start capture - dual camera manager not healthy");
        return;
    }
    
    if (running_.load()) {
        Logger::warn("Capture already running");
        return;
    }
    
    running_ = true;
    
    if (camera1_) {
        camera1_->start_capture();
    }
    if (camera2_ && stereo_config_.enable_stereo) {
        camera2_->start_capture();
    }
    
    // Start frame synchronization thread if enabled
    if (stereo_config_.enable_frame_sync && stereo_config_.enable_stereo) {
        sync_thread_ = std::thread(&DualCameraManager::frame_sync_worker, this);
    }
    
    Logger::info("Dual camera capture started");
}

void DualCameraManager::stop_capture() {
    if (!running_.load()) {
        return;
    }
    
    running_ = false;
    
    // Stop frame sync thread
    if (sync_thread_.joinable()) {
        sync_thread_.join();
    }
    
    if (camera1_) {
        camera1_->stop_capture();
    }
    if (camera2_) {
        camera2_->stop_capture();
    }
    
    Logger::info("Dual camera capture stopped");
}

void DualCameraManager::update_stereo_config(const StereoConfig& config) {
    std::lock_guard<std::mutex> lock(frame_mutex_);
    stereo_config_ = config;
    
    if (camera2_) {
        config2_.device_path = "/dev/video" + std::to_string(config.camera2_device);
        // Note: camera2 settings should come from VideoConfig, not StereoConfig
        // Using default values for now
        if (!config2_.width) config2_.width = 1920;
        if (!config2_.height) config2_.height = 1080;
        if (!config2_.fps) config2_.fps = 60;
    }
    
    Logger::info("Stereo configuration updated");
}

void DualCameraManager::frame_sync_worker() {
    Logger::info("Frame synchronization worker started");
    
    while (running_.load()) {
        auto frame1 = camera1_->capture_frame();
        auto frame2 = camera2_->capture_frame();
        
        if (frame1 && frame2) {
            std::lock_guard<std::mutex> lock(frame_mutex_);
            frame1_buffer_ = *frame1;
            frame2_buffer_ = *frame2;
            frame1_ready_.store(true);
            frame2_ready_.store(true);
            frame_condition_.notify_one();
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    
    Logger::info("Frame synchronization worker stopped");
}

} // namespace fpv_streamer

// Sample image fallback implementation
namespace fpv_streamer {

bool VideoCapture::load_sample_images() {
    std::lock_guard<std::mutex> lock(sample_mutex_);
    
    // Clear any existing sample paths
    sample_image_paths_.clear();
    current_sample_index_ = 0;
    
    // Determine sample directory based on device path
    std::string sample_dir;
    if (device_path_.find("video0") != std::string::npos || device_path_.find("camera1") != std::string::npos) {
        sample_dir = "samples/camera1";
    } else if (device_path_.find("video1") != std::string::npos || device_path_.find("video2") != std::string::npos || 
               device_path_.find("camera2") != std::string::npos) {
        sample_dir = "samples/camera2";
    } else {
        sample_dir = "samples/camera1";  // Default fallback
    }
    
    Logger::info("Loading sample images for device " + device_path_ + " from directory: " + sample_dir);
    
    // Check if directory exists
    struct stat st;
    if (stat(sample_dir.c_str(), &st) != 0) {
        Logger::warn("Sample directory does not exist: " + sample_dir);
        return create_synthetic_samples();
    }
    
    // Scan directory for image files
    if (scan_directory_for_images(sample_dir)) {
        if (sample_image_paths_.empty()) {
            Logger::warn("Scan reported success but no images were found");
            return create_synthetic_samples();
        }
        Logger::info("Successfully loaded " + std::to_string(sample_image_paths_.size()) + " sample images");
        return true;
    }
    
    Logger::warn("No sample images found in " + sample_dir + ", creating synthetic test patterns");
    return create_synthetic_samples();
}

bool VideoCapture::scan_sample_directory() {
    return scan_directory_for_images(get_sample_directory_for_device());
}

std::vector<std::string> VideoCapture::get_available_sample_images() const {
    std::lock_guard<std::mutex> lock(sample_mutex_);
    return sample_image_paths_;
}

std::string VideoCapture::get_sample_directory_for_device() const {
    if (device_path_.find("video0") != std::string::npos || device_path_.find("camera1") != std::string::npos) {
        return "samples/camera1";
    } else if (device_path_.find("video1") != std::string::npos || device_path_.find("video2") != std::string::npos || 
               device_path_.find("camera2") != std::string::npos) {
        return "samples/camera2";
    }
    return "samples/camera1";
}

bool VideoCapture::scan_directory_for_images(const std::string& dir_path) {
    // Clear any existing sample paths before scanning
    sample_image_paths_.clear();
    
    DIR* dir = opendir(dir_path.c_str());
    if (!dir) {
        Logger::warn("Cannot open sample directory: " + dir_path);
        return false;
    }
    
    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        std::string filename = entry->d_name;
        
        // Skip . and .. entries
        if (filename == "." || filename == "..") {
            continue;
        }
        
        // Check for image file extensions
        if (filename.length() > 4) {
            std::string ext = filename.substr(filename.length() - 4);
            std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
            
            if (ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".bmp") {
                std::string full_path = dir_path + "/" + filename;
                sample_image_paths_.push_back(full_path);
                Logger::debug("Found sample image: " + full_path);
            }
        }
    }
    
    closedir(dir);
    Logger::info("Scanned directory " + dir_path + ": found " + std::to_string(sample_image_paths_.size()) + " images");
    return !sample_image_paths_.empty();
}

bool VideoCapture::create_synthetic_samples() {
    // Create a simple synthetic test pattern
    Logger::info("Creating synthetic test pattern");
    
    try {
        cv::Mat test_pattern(config_.height, config_.width, CV_8UC3, cv::Scalar(100, 150, 200));
        
        // Add some basic pattern elements
        cv::rectangle(test_pattern, cv::Point(100, 100), cv::Point(400, 300), cv::Scalar(255, 0, 0), 2);
        cv::circle(test_pattern, cv::Point(config_.width/2, config_.height/2), 100, cv::Scalar(0, 255, 0), 3);
        
        // Add timestamp text
        auto now = std::chrono::system_clock::now();
        auto now_c = std::chrono::system_clock::to_time_t(now);
        std::stringstream ss;
        ss << "SAMPLE MODE - " << std::put_time(std::localtime(&now_c), "%H:%M:%S");
        cv::putText(test_pattern, ss.str(), cv::Point(50, config_.height - 50), 
                   cv::FONT_HERSHEY_SIMPLEX, 2, cv::Scalar(255, 255, 255), 3);
        
        // Create a temporary file path
        std::string temp_path = "/tmp/fpv_sample_" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + ".jpg";
        
        if (cv::imwrite(temp_path, test_pattern)) {
            sample_image_paths_.push_back(temp_path);
            Logger::info("Created synthetic test pattern: " + temp_path);
            return true;
        }
        
    } catch (const std::exception& e) {
        Logger::error("Failed to create synthetic samples: " + std::string(e.what()));
    }
    
    return false;
}

std::unique_ptr<VideoFrame> VideoCapture::create_sample_frame() {
    if (sample_image_paths_.empty()) {
        Logger::warn("No sample images available");
        return nullptr;
    }
    
    std::lock_guard<std::mutex> lock(sample_mutex_);
    
    // Cycle through available sample images
    std::string image_path = sample_image_paths_[current_sample_index_ % sample_image_paths_.size()];
    current_sample_index_++;
    
    try {
        // Load the image
        cv::Mat image = cv::imread(image_path, cv::IMREAD_COLOR);
        if (image.empty()) {
            Logger::warn("Failed to load sample image: " + image_path);
            return nullptr;
        }
        
        // Resize to target resolution
        cv::Mat resized;
        cv::resize(image, resized, cv::Size(actual_width_, actual_height_));
        
        // Convert to VideoFrame format
        size_t y_size = actual_width_ * actual_height_;
        size_t uv_size = y_size / 4;
        size_t total_size = y_size + uv_size + uv_size; // YUV420 format
        
        auto frame = std::make_unique<VideoFrame>(actual_width_, actual_height_, 
                                                V4L2_PIX_FMT_YUV420, 
                                                std::chrono::duration_cast<std::chrono::microseconds>(
                                                    std::chrono::steady_clock::now().time_since_epoch()).count(),
                                                frame_sequence_++);
        frame->data.resize(total_size);
        
        // Convert BGR to YUV420 (simplified conversion)
        cv::Mat yuv;
        cv::cvtColor(resized, yuv, cv::COLOR_BGR2YUV);
        
        // Extract Y, U, V channels
        std::vector<cv::Mat> channels(3);
        cv::split(yuv, channels);
        
        // Copy Y channel
        memcpy(frame->data.data(), channels[0].data, y_size);
        
        // Copy U and V channels (downsampled)
        size_t uv_channel_size = uv_size;
        uchar* u_data = frame->data.data() + y_size;
        uchar* v_data = frame->data.data() + y_size + uv_channel_size;
        
        // Downsample U and V channels
        cv::Mat downsampled_u, downsampled_v;
        cv::resize(channels[1], downsampled_u, cv::Size(actual_width_/2, actual_height_/2));
        cv::resize(channels[2], downsampled_v, cv::Size(actual_width_/2, actual_height_/2));
        
        memcpy(u_data, downsampled_u.data, uv_channel_size);
        memcpy(v_data, downsampled_v.data, uv_channel_size);
        
        // Signal frame ready for thread synchronization
        if (frame_ready_callback_) {
            frame_ready_callback_();
        }
        
        return frame;
        
    } catch (const std::exception& e) {
        Logger::error("Exception creating sample frame: " + std::string(e.what()));
        return nullptr;
    }
}

} // namespace fpv_streamer