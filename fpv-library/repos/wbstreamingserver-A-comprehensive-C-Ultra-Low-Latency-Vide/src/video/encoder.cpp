#include "video/encoder.h"
#include "utils/utils.h"
#include <algorithm>
#include <chrono>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/videodev2.h>
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/frame.h>
#include <libavutil/mem.h>
#include <libavutil/error.h>
#include <sys/mman.h>
#include <linux/v4l2-subdev.h>
#include <linux/media.h>
#include <dirent.h>
#include <cstring>
#include <dlfcn.h>
#include <errno.h>

namespace fpv_streamer {

// Helper function for FFmpeg error handling
std::string get_ffmpeg_error_string(int error_code) {
    char errbuf[128];
    av_strerror(error_code, errbuf, sizeof(errbuf));
    return std::string(errbuf);
}

// HardwareEncoder implementation
HardwareEncoder::HardwareEncoder(const VideoConfig& config) 
    : config_(config)
    , encoder_type_(config.output_encoder)
    , use_mmal_(false)
    , use_v4l2_(false)
    , use_rockchip_mpp_(false)
    , use_rga_(false)
    , mmal_pool_(nullptr)
    , mmal_connection_(nullptr)
    , v4l2_fd_(-1)
    , rockchip_mpp_fd_(-1)
    , rga_fd_(-1)
    , encoder_context_(nullptr) {
    
    detect_hardware_encoder();
}

HardwareEncoder::~HardwareEncoder() {
    // Cleanup hardware resources
    if (mmal_pool_) {
        // mmal_port_pool_release(mmal_pool_);
    }
    if (v4l2_fd_ >= 0) {
        close(v4l2_fd_);
    }
    if (rockchip_mpp_fd_ >= 0) {
        close(rockchip_mpp_fd_);
    }
    if (rga_fd_ >= 0) {
        close(rga_fd_);
    }
    if (encoder_context_) {
        cleanup_v4l2_context();
    }
}

bool HardwareEncoder::initialize() {
    Logger::info("Initializing hardware encoder: " + encoder_type_);
    
    if (use_mmal_) {
        if (!initialize_mmal_encoder()) {
            Logger::warn("MMAL encoder initialization failed, falling back to software");
            use_mmal_ = false;
        }
    }
    
    if (use_v4l2_) {
        if (!initialize_v4l2_encoder()) {
            Logger::warn("V4L2 encoder initialization failed");
            use_v4l2_ = false;
        }
    }
    
    if (use_rockchip_mpp_) {
        if (!initialize_rockchip_mpp()) {
            Logger::warn("Rockchip MPP encoder initialization failed");
            use_rockchip_mpp_ = false;
        }
    }
    
    if (use_rga_) {
        if (!initialize_rga()) {
            Logger::warn("RGA initialization failed");
            use_rga_ = false;
        }
    }
    
    if (use_mmal_ || use_v4l2_ || use_rockchip_mpp_ || use_rga_) {
        healthy_.store(true);
        Logger::info("Hardware encoder initialized successfully");
        return true;
    }
    
    Logger::warn("No hardware encoder available");
    return false;
}

std::unique_ptr<EncodedFrame> HardwareEncoder::encode_frame(const VideoFrame& frame) {
    if (use_mmal_) {
        return mmal_encode(frame);
    } else if (use_v4l2_) {
        return v4l2_encode(frame);
    } else if (use_rockchip_mpp_) {
        return rockchip_mpp_encode(frame);
    } else if (use_rga_) {
        return rga_encode(frame);
    }
    
    return nullptr;
}

void HardwareEncoder::set_bitrate(int bitrate) {
    Logger::info("Setting hardware encoder bitrate: " + std::to_string(bitrate));
    // Implementation depends on hardware type
}

void HardwareEncoder::set_quality(int quality) {
    Logger::info("Setting hardware encoder quality: " + std::to_string(quality));
    // Implementation depends on hardware type
}

bool HardwareEncoder::is_healthy() const {
    return healthy_.load();
}

bool HardwareEncoder::detect_hardware_encoder() {
    Logger::info("Detecting hardware encoder capabilities...");
    
    // Check for MMAL (Raspberry Pi)
    if (access("/opt/vc/include/interface/mmal/mmal.h", F_OK) == 0) {
        use_mmal_ = true;
        Logger::info("Detected MMAL hardware encoder support");
    }
    
    // Check for V4L2 encoder devices (including Rockchip devices)
    detect_v4l2_devices();
    
    // Check for Rockchip MPP library
    detect_rockchip_mpp();
    
    // Check for RGA (Rockchip GPU)
    detect_rga();
    
    Logger::info(std::string("Hardware detection complete: ") + 
                (use_mmal_ ? "MMAL " : "") +
                (use_v4l2_ ? "V4L2 " : "") +
                (use_rockchip_mpp_ ? "ROCKCHIP_MPP " : "") +
                (use_rga_ ? "RGA" : ""));
    
    return use_mmal_ || use_v4l2_ || use_rockchip_mpp_ || use_rga_;
}

bool HardwareEncoder::initialize_mmal_encoder() {
    Logger::info("Initializing MMAL encoder");
    // MMAL initialization would go here
    // For now, simplified implementation
    return encoder_type_ == "h264";
}

void HardwareEncoder::detect_v4l2_devices() {
    Logger::info("Scanning for V4L2 encoder devices...");
    
    DIR* dir = opendir("/dev");
    if (!dir) {
        Logger::warn("Could not open /dev directory");
        return;
    }
    
    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        if (strncmp(entry->d_name, "video", 5) == 0) {
            std::string device_path = std::string("/dev/") + entry->d_name;
            
            // Extract video device number
            int video_num = -1;
            try {
                video_num = std::stoi(std::string(entry->d_name).substr(5));
            } catch (const std::exception& e) {
                continue;
            }
            
            // Check for standard V4L2 encoder devices
            if (video_num >= 10 && video_num <= 19) {
                int fd = open(device_path.c_str(), O_RDWR | O_NONBLOCK);
                if (fd >= 0) {
                    // Query device capabilities
                    struct v4l2_capability cap;
                    if (ioctl(fd, VIDIOC_QUERYCAP, &cap) == 0) {
                        Logger::info("Found V4L2 device: " + device_path + 
                                   " - Driver: " + (char*)cap.driver);
                        
                        // Check if it's a video capture or encode device
                        if (cap.capabilities & V4L2_CAP_VIDEO_CAPTURE ||
                            cap.capabilities & V4L2_CAP_VIDEO_OUTPUT ||
                            cap.capabilities & V4L2_CAP_VIDEO_M2M) {
                            use_v4l2_ = true;
                            Logger::info("V4L2 encoder support detected on " + device_path);
                            break;
                        }
                    }
                    close(fd);
                }
            }
        }
    }
    closedir(dir);
}

void HardwareEncoder::detect_rockchip_mpp() {
    Logger::info("Checking for Rockchip MPP library...");
    
    // Check for Rockchip MPP library headers and symbols
    if (access("/usr/include/mpp/mpp_frame.h", F_OK) == 0 ||
        access("/usr/include/rk_mpi/mpp_frame.h", F_OK) == 0) {
        
        // Check for rockchip-mpp library
        void* mpp_lib = dlopen("librk_mpi.so", RTLD_LAZY);
        if (!mpp_lib) {
            mpp_lib = dlopen("librockchip-mpp.so", RTLD_LAZY);
        }
        
        if (mpp_lib) {
            use_rockchip_mpp_ = true;
            Logger::info("Detected Rockchip MPP library");
            dlclose(mpp_lib);
        }
    }
}

void HardwareEncoder::detect_rga() {
    Logger::info("Checking for RGA (Rockchip GPU)...");
    
    // Check for RGA device
    if (access("/dev/rga", F_OK) == 0) {
        rga_fd_ = open("/dev/rga", O_RDWR | O_NONBLOCK);
        if (rga_fd_ >= 0) {
            use_rga_ = true;
            Logger::info("Detected RGA device: /dev/rga");
        }
    }
    
    // Also check for RGA2 device
    if (access("/dev/rga2", F_OK) == 0) {
        int rga2_fd = open("/dev/rga2", O_RDWR | O_NONBLOCK);
        if (rga2_fd >= 0) {
            if (!use_rga_) {
                use_rga_ = true;
                rga_fd_ = rga2_fd;
                Logger::info("Detected RGA2 device: /dev/rga2");
            } else {
                close(rga2_fd);
            }
        }
    }
}

bool HardwareEncoder::initialize_v4l2_encoder() {
    Logger::info("Initializing V4L2 encoder");
    
    // Try to open hardware encoder device
    const char* encoder_devices[] = {"/dev/video10", "/dev/video11", "/dev/video12", "/dev/video13", "/dev/video14", "/dev/video15"};
    
    for (const char* device : encoder_devices) {
        v4l2_fd_ = open(device, O_RDWR | O_NONBLOCK);
        if (v4l2_fd_ >= 0) {
            Logger::info("Opened V4L2 encoder: " + std::string(device));
            break;
        }
    }
    
    if (v4l2_fd_ < 0) {
        Logger::warn("Could not open V4L2 encoder device");
        return false;
    }
    
    // Initialize V4L2 encoder context
    return initialize_v4l2_context();
}

std::unique_ptr<EncodedFrame> HardwareEncoder::mmal_encode(const VideoFrame& frame) {
    // MMAL encoding implementation
    auto encoded_frame = std::make_unique<EncodedFrame>();
    
    // Simplified MMAL encoding - real implementation would be more complex
    encoded_frame->data = frame.data; // Copy data for now
    encoded_frame->timestamp = frame.timestamp;
    encoded_frame->sequence = frame.sequence;
    encoded_frame->is_keyframe = (frame.sequence % 30 == 0); // Keyframe every 30 frames
    encoded_frame->original_size = frame.data.size();
    
    return encoded_frame;
}

bool HardwareEncoder::initialize_v4l2_context() {
    Logger::info("Initializing V4L2 encoder context...");
    
    encoder_context_ = new V4L2EncoderContext();
    if (!encoder_context_) {
        Logger::error("Failed to allocate V4L2 encoder context");
        return false;
    }
    
    struct v4l2_capability cap;
    if (ioctl(v4l2_fd_, VIDIOC_QUERYCAP, &cap) < 0) {
        Logger::error("Failed to query V4L2 device capabilities");
        delete encoder_context_;
        encoder_context_ = nullptr;
        return false;
    }
    
    Logger::info("V4L2 device: " + std::string((char*)cap.card));
    
    // Try to set encoder parameters
    struct v4l2_control ctrl;
    memset(&ctrl, 0, sizeof(ctrl));
    
    if (encoder_type_ == "h264") {
        ctrl.id = V4L2_CID_MPEG_VIDEO_H264_PROFILE;
        ctrl.value = V4L2_MPEG_VIDEO_H264_PROFILE_BASELINE;
        ioctl(v4l2_fd_, VIDIOC_S_CTRL, &ctrl);
    }
    
    encoder_context_->width = config_.width;
    encoder_context_->height = config_.height;
    encoder_context_->bitrate = config_.bitrate;
    encoder_context_->fps = config_.fps;
    
    Logger::info("V4L2 encoder context initialized successfully");
    return true;
}

void HardwareEncoder::cleanup_v4l2_context() {
    if (encoder_context_) {
        delete encoder_context_;
        encoder_context_ = nullptr;
    }
}

std::unique_ptr<EncodedFrame> HardwareEncoder::v4l2_encode(const VideoFrame& frame) {
    if (v4l2_fd_ < 0 || !encoder_context_) {
        Logger::warn("V4L2 encoder not initialized");
        return nullptr;
    }
    
    auto encoded_frame = std::make_unique<EncodedFrame>();
    
    try {
        // Prepare frame buffer for V4L2
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = V4L2_BUF_TYPE_VIDEO_OUTPUT;
        buf.memory = V4L2_MEMORY_USERPTR;
        buf.index = 0;
        buf.m.userptr = reinterpret_cast<unsigned long>(frame.data.data());
        buf.length = frame.data.size();
        buf.timestamp.tv_sec = frame.timestamp / 1000000;
        buf.timestamp.tv_usec = frame.timestamp % 1000000;
        
        // Queue the input frame
        if (ioctl(v4l2_fd_, VIDIOC_QBUF, &buf) < 0) {
            Logger::warn("Failed to queue V4L2 buffer: " + std::string(strerror(errno)));
            return nullptr;
        }
        
        // Try to dequeue encoded output
        struct v4l2_buffer out_buf;
        memset(&out_buf, 0, sizeof(out_buf));
        out_buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        out_buf.memory = V4L2_MEMORY_MMAP;
        
        int ret = ioctl(v4l2_fd_, VIDIOC_DQBUF, &out_buf);
        if (ret >= 0 && out_buf.bytesused > 0) {
            // Copy encoded data
            encoded_frame->data.resize(out_buf.bytesused);
            memcpy(encoded_frame->data.data(), 
                   encoder_context_->output_buffers[out_buf.index].data(), 
                   out_buf.bytesused);
            
            encoded_frame->timestamp = frame.timestamp;
            encoded_frame->sequence = frame.sequence;
            encoded_frame->is_keyframe = (out_buf.flags & V4L2_BUF_FLAG_KEYFRAME) != 0;
            encoded_frame->original_size = frame.data.size();
            
            // Re-queue the buffer
            ioctl(v4l2_fd_, VIDIOC_QBUF, &out_buf);
            
            return encoded_frame;
        }
        
        Logger::debug("No encoded data available from V4L2 encoder");
        
    } catch (const std::exception& e) {
        Logger::error("V4L2 encoding error: " + std::string(e.what()));
    }
    
    return nullptr;
}

bool HardwareEncoder::initialize_rockchip_mpp() {
    Logger::info("Initializing Rockchip MPP encoder");
    
    // Rockchip MPP initialization would go here
    // This is a placeholder for the full MPP implementation
    Logger::info("Rockchip MPP encoder initialized (placeholder)");
    return true;
}

std::unique_ptr<EncodedFrame> HardwareEncoder::rockchip_mpp_encode(const VideoFrame& frame) {
    Logger::debug("Rockchip MPP encoding (placeholder)");
    
    // Placeholder implementation
    auto encoded_frame = std::make_unique<EncodedFrame>();
    encoded_frame->data = frame.data; // Copy data for now
    encoded_frame->timestamp = frame.timestamp;
    encoded_frame->sequence = frame.sequence;
    encoded_frame->is_keyframe = (frame.sequence % 30 == 0);
    encoded_frame->original_size = frame.data.size();
    
    return encoded_frame;
}

bool HardwareEncoder::initialize_rga() {
    Logger::info("Initializing RGA (Rockchip GPU)");
    
    if (rga_fd_ < 0) {
        rga_fd_ = open("/dev/rga", O_RDWR);
        if (rga_fd_ < 0) {
            Logger::warn("Could not open RGA device");
            return false;
        }
    }
    
    Logger::info("RGA initialized successfully");
    return true;
}

std::unique_ptr<EncodedFrame> HardwareEncoder::rga_encode(const VideoFrame& frame) {
    Logger::debug("RGA processing (placeholder)");
    
    // Placeholder implementation using RGA for hardware acceleration
    auto encoded_frame = std::make_unique<EncodedFrame>();
    encoded_frame->data = frame.data; // Copy data for now
    encoded_frame->timestamp = frame.timestamp;
    encoded_frame->sequence = frame.sequence;
    encoded_frame->is_keyframe = (frame.sequence % 30 == 0);
    encoded_frame->original_size = frame.data.size();
    
    return encoded_frame;
}

// SoftwareEncoder implementation
SoftwareEncoder::SoftwareEncoder(const VideoConfig& config) 
    : config_(config)
    , encoder_type_(config.output_encoder)
    , codec_ctx_(nullptr)
    , frame_(nullptr)
    , packet_(nullptr)
    , sws_ctx_(nullptr)
    , h265_profile_(config.h265_profile)
    , h265_level_(config.h265_level)
    , mjpeg_quality_(config.mjpeg_quality)
    , mjpeg_optimization_(config.mjpeg_optimization_level)
    , healthy_(false) {
}

SoftwareEncoder::~SoftwareEncoder() {
    cleanup_encoder();
}

bool SoftwareEncoder::initialize() {
    Logger::info("Initializing software encoder: " + encoder_type_);
    
    if (!setup_encoder()) {
        Logger::error("Failed to setup software encoder");
        return false;
    }
    
    healthy_.store(true);
    Logger::info("Software encoder initialized successfully");
    return true;
}

std::unique_ptr<EncodedFrame> SoftwareEncoder::encode_frame(const VideoFrame& frame) {
    auto start_time = std::chrono::high_resolution_clock::now();
    
    auto result = convert_and_encode(frame);
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
    
    // Update statistics (this would be updated by the VideoEncoder class)
    
    return result;
}

void SoftwareEncoder::set_bitrate(int bitrate) {
    if (codec_ctx_) {
        codec_ctx_->bit_rate = bitrate;
        Logger::info("Updated software encoder bitrate: " + std::to_string(bitrate));
    }
}

void SoftwareEncoder::set_quality(int quality) {
    if (codec_ctx_) {
        // Map quality (1-100) to FFmpeg qp scale
        int qp = std::max(1, std::min(51, 51 - (quality * 50) / 100));
        codec_ctx_->global_quality = qp * FF_QP2LAMBDA;
        Logger::info("Updated software encoder quality: " + std::to_string(quality) + " (qp: " + std::to_string(qp) + ")");
    }
}

bool SoftwareEncoder::is_healthy() const {
    return healthy_.load() && codec_ctx_ && frame_ && packet_;
}

bool SoftwareEncoder::setup_encoder() {
    const AVCodec* codec = nullptr;
    
    // Find encoder based on type
    if (encoder_type_ == "h264") {
        codec = avcodec_find_encoder(AV_CODEC_ID_H264);
    } else if (encoder_type_ == "h265") {
        codec = avcodec_find_encoder(AV_CODEC_ID_HEVC);
        if (codec) {
            Logger::info("Using H.265/HEVC encoder");
        } else {
            Logger::warn("H.265/HEVC encoder not available, falling back to H.264");
            encoder_type_ = "h264";
            codec = avcodec_find_encoder(AV_CODEC_ID_H264);
        }
    } else if (encoder_type_ == "mjpeg") {
        codec = avcodec_find_encoder(AV_CODEC_ID_MJPEG);
    } else {
        Logger::error("Unsupported encoder type: " + encoder_type_ + ", falling back to H.264");
        encoder_type_ = "h264";
        codec = avcodec_find_encoder(AV_CODEC_ID_H264);
    }
    
    if (!codec) {
        Logger::error("Encoder not found: " + encoder_type_);
        return false;
    }
    
    // Allocate codec context
    codec_ctx_ = avcodec_alloc_context3(codec);
    if (!codec_ctx_) {
        Logger::error("Failed to allocate codec context");
        return false;
    }
    
    // Configure codec for low latency
    codec_ctx_->width = config_.width;
    codec_ctx_->height = config_.height;
    codec_ctx_->pix_fmt = AV_PIX_FMT_YUV420P;
    codec_ctx_->time_base = {1, config_.fps};
    codec_ctx_->framerate = {config_.fps, 1};
    
    // Low latency settings
    codec_ctx_->thread_count = 1; // Single thread for minimal latency
    codec_ctx_->gop_size = 10; // Small GOP for low latency
    codec_ctx_->max_b_frames = 0; // No B-frames for low latency
    codec_ctx_->has_b_frames = 0;
    
    // Bitrate and quality
    codec_ctx_->bit_rate = config_.bitrate;
    codec_ctx_->rc_max_rate = config_.bitrate;
    codec_ctx_->rc_buffer_size = config_.bitrate / 2;
    
    // H.264 specific settings
    if (encoder_type_ == "h264") {
        codec_ctx_->profile = FF_PROFILE_H264_HIGH;
        codec_ctx_->level = 40; // Level 4.0 for compatibility
        
        // Low latency presets
        av_opt_set(codec_ctx_->priv_data, "preset", "ultrafast", 0);
        av_opt_set(codec_ctx_->priv_data, "tune", "zerolatency", 0);
        av_opt_set(codec_ctx_->priv_data, "x264-params", "keyint=10:min-keyint=5:scenecut=0", 0);
    }
    
    // H.265 specific settings
    else if (encoder_type_ == "h265") {
        codec_ctx_->profile = h265_profile_; // 0=Main, 1=Main10, 2=MainStillPicture
        
        // Set H.265 level
        if (h265_level_ >= 1.0f && h265_level_ <= 6.2f) {
            codec_ctx_->level = static_cast<int>(h265_level_ * 10);
        } else {
            codec_ctx_->level = 40; // Default to Level 4.0
        }
        
        // Low latency presets for H.265
        av_opt_set(codec_ctx_->priv_data, "preset", "ultrafast", 0);
        av_opt_set(codec_ctx_->priv_data, "tune", "zerolatency", 0);
        av_opt_set(codec_ctx_->priv_data, "x265-params", "keyint=10:min-keyint=5:scenecut=0:bframes=0", 0);
        
        Logger::info("H.265 configured - Profile: " + std::to_string(h265_profile_) + 
                    ", Level: " + std::to_string(h265_level_));
    }
    
    // MJPEG specific settings
    else if (encoder_type_ == "mjpeg") {
        // MJPEG doesn't use profile/level, but we can set quality
        av_opt_set(codec_ctx_->priv_data, "qscale", std::to_string(mjpeg_quality_).c_str(), 0);
        
        // Enable MJPEG optimization
        av_opt_set(codec_ctx_->priv_data, "optimize", std::to_string(mjpeg_optimization_).c_str(), 0);
        
        Logger::info("MJPEG configured - Quality: " + std::to_string(mjpeg_quality_) + 
                    ", Optimization: " + std::to_string(mjpeg_optimization_));
    }
    
    // Open codec
    int ret = avcodec_open2(codec_ctx_, codec, nullptr);
    if (ret < 0) {
        Logger::error("Failed to open codec: " + get_ffmpeg_error_string(ret));
        cleanup_encoder();
        return false;
    }
    
    // Allocate frame and packet
    frame_ = av_frame_alloc();
    packet_ = av_packet_alloc();
    
    if (!frame_ || !packet_) {
        Logger::error("Failed to allocate frame or packet");
        cleanup_encoder();
        return false;
    }
    
    // Setup frame
    frame_->width = config_.width;
    frame_->height = config_.height;
    frame_->format = AV_PIX_FMT_YUV420P;
    frame_->pts = 0;
    frame_->pkt_dts = 0;
    
    int ret2 = av_frame_get_buffer(frame_, 32);
    if (ret2 < 0) {
        Logger::error("Failed to allocate frame buffer: " + get_ffmpeg_error_string(ret2));
        cleanup_encoder();
        return false;
    }
    
    Logger::info("Software encoder setup complete");
    return true;
}

void SoftwareEncoder::cleanup_encoder() {
    if (frame_) {
        av_frame_free(&frame_);
        frame_ = nullptr;
    }
    
    if (packet_) {
        av_packet_free(&packet_);
        packet_ = nullptr;
    }
    
    if (codec_ctx_) {
        avcodec_free_context(&codec_ctx_);
        codec_ctx_ = nullptr;
    }
    
    if (sws_ctx_) {
        sws_freeContext(sws_ctx_);
        sws_ctx_ = nullptr;
    }
}

std::unique_ptr<EncodedFrame> SoftwareEncoder::convert_and_encode(const VideoFrame& frame) {
    if (!healthy_.load()) {
        return nullptr;
    }
    
    // Fill frame with YUV420 data
    size_t y_size = frame.width * frame.height;
    size_t uv_size = y_size / 4;
    
    if (frame.data.size() < y_size + uv_size + uv_size) {
        Logger::warn("Invalid frame data size");
        return nullptr;
    }
    
    // Setup color conversion if needed
    if (!sws_ctx_) {
        sws_ctx_ = sws_getContext(frame.width, frame.height, AV_PIX_FMT_YUV420P,
                                 frame.width, frame.height, AV_PIX_FMT_YUV420P,
                                 SWS_FAST_BILINEAR, nullptr, nullptr, nullptr);
    }
    
    // Prepare frame data
    uint8_t* src_data[4] = {
        const_cast<uint8_t*>(frame.data.data()),
        const_cast<uint8_t*>(frame.data.data() + y_size),
        const_cast<uint8_t*>(frame.data.data() + y_size + uv_size),
        nullptr
    };
    int src_linesize[4] = {
        frame.width,
        frame.width / 2,
        frame.width / 2,
        0
    };
    
    // Convert frame (if needed)
    if (sws_ctx_) {
        sws_scale(sws_ctx_, src_data, src_linesize, 0, frame.height,
                 frame_->data, frame_->linesize);
    } else {
        // Direct copy if no conversion needed
        memcpy(frame_->data[0], src_data[0], y_size + uv_size + uv_size);
    }
    
    // Set frame properties
    frame_->pts = frame.sequence;
    frame_->pkt_dts = frame.sequence;
    
    // Encode frame
    int ret = avcodec_send_frame(codec_ctx_, frame_);
    if (ret < 0) {
        Logger::error("Failed to send frame to encoder: " + get_ffmpeg_error_string(ret));
        return nullptr;
    }
    
    auto encoded_frame = std::make_unique<EncodedFrame>();
    bool got_frame = false;
    
    while (ret >= 0) {
        ret = avcodec_receive_packet(codec_ctx_, packet_);
        if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF) {
            break;
        } else if (ret < 0) {
            Logger::error("Error encoding frame: " + get_ffmpeg_error_string(ret));
            return nullptr;
        }
        
        // Copy encoded data
        encoded_frame->data.resize(packet_->size);
        memcpy(encoded_frame->data.data(), packet_->data, packet_->size);
        encoded_frame->timestamp = packet_->pts != AV_NOPTS_VALUE ? packet_->pts : frame.timestamp;
        encoded_frame->sequence = frame.sequence;
        encoded_frame->is_keyframe = (packet_->flags & AV_PKT_FLAG_KEY) != 0;
        encoded_frame->original_size = frame.data.size();
        
        got_frame = true;
        
        av_packet_unref(packet_);
    }
    
    if (!got_frame) {
        Logger::warn("No encoded frame produced");
        return nullptr;
    }
    
    return encoded_frame;
}

// VideoEncoder implementation
VideoEncoder::VideoEncoder(const VideoConfig& config) 
    : config_(config)
    , use_hardware_(config.use_hardware_encoder)
    , initialized_(false) {
}

VideoEncoder::~VideoEncoder() {
    stop();
}

bool VideoEncoder::initialize() {
    std::lock_guard<std::mutex> lock(encoder_mutex_);
    
    if (initialized_) {
        return true;
    }
    
    Logger::info("Initializing video encoder...");
    
    // Try hardware encoder first if enabled
    if (use_hardware_) {
        hardware_encoder_ = std::make_unique<HardwareEncoder>(config_);
        if (hardware_encoder_->initialize()) {
            active_encoder_ = hardware_encoder_.get();
            use_hardware_ = true;
            Logger::info("Using hardware encoder: " + active_encoder_->get_name());
        } else {
            Logger::warn("Hardware encoder failed, falling back to software");
            hardware_encoder_.reset();
            use_hardware_ = false;
        }
    }
    
    // Fallback to software encoder
    if (!active_encoder_) {
        software_encoder_ = std::make_unique<SoftwareEncoder>(config_);
        if (software_encoder_->initialize()) {
            active_encoder_ = software_encoder_.get();
            Logger::info("Using software encoder: " + active_encoder_->get_name());
        } else {
            Logger::error("Failed to initialize any encoder");
            return false;
        }
    }
    
    initialized_ = true;
    Logger::info("Video encoder initialized successfully");
    return true;
}

void VideoEncoder::stop() {
    std::lock_guard<std::mutex> lock(encoder_mutex_);
    
    if (!initialized_) {
        return;
    }
    
    Logger::info("Stopping video encoder");
    
    hardware_encoder_.reset();
    software_encoder_.reset();
    active_encoder_ = nullptr; // Just nullify the pointer
    
    initialized_ = false;
}

bool VideoEncoder::is_healthy() const {
    std::lock_guard<std::mutex> lock(encoder_mutex_);
    return initialized_ && active_encoder_ && active_encoder_->is_healthy();
}

std::unique_ptr<EncodedFrame> VideoEncoder::encode_frame(const VideoFrame& frame) {
    std::lock_guard<std::mutex> lock(encoder_mutex_);
    
    if (!initialized_ || !active_encoder_) {
        return nullptr;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    auto encoded_frame = active_encoder_->encode_frame(frame);
    
    if (encoded_frame) {
        frames_encoded_.fetch_add(1);
        bytes_encoded_.fetch_add(encoded_frame->data.size());
        
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
        encoding_time_ms_.fetch_add(duration.count() / 1000);
    }
    
    return encoded_frame;
}

void VideoEncoder::set_bitrate(int bitrate) {
    std::lock_guard<std::mutex> lock(encoder_mutex_);
    
    if (active_encoder_) {
        active_encoder_->set_bitrate(bitrate);
    }
    
    config_.bitrate = bitrate;
}

void VideoEncoder::set_quality(int quality) {
    std::lock_guard<std::mutex> lock(encoder_mutex_);
    
    if (active_encoder_) {
        active_encoder_->set_quality(quality);
    }
    
    config_.quality = quality;
}

void VideoEncoder::set_resolution(int width, int height) {
    std::lock_guard<std::mutex> lock(encoder_mutex_);
    
    config_.width = width;
    config_.height = height;
    
    // Reinitialize encoder with new resolution
    if (initialized_) {
        Logger::info("Reinitializing encoder for new resolution: " + 
                    std::to_string(width) + "x" + std::to_string(height));
        stop();
        initialize();
    }
}

void VideoEncoder::set_framerate(int fps) {
    std::lock_guard<std::mutex> lock(encoder_mutex_);
    
    config_.fps = fps;
    
    if (active_encoder_) {
        // Update encoder framerate settings
        Logger::info("Updated encoder framerate: " + std::to_string(fps));
    }
}

} // namespace fpv_streamer