#pragma once

#include <memory>
#include <vector>
#include <string>
#include <atomic>
#include <mutex>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/imgutils.h>
#include <libavutil/avutil.h>
#include <libavutil/opt.h>
#include <libswscale/swscale.h>
}
#include "config/config_manager.h"
#include "video/capture.h"

namespace fpv_streamer {

// Encoded frame structure
struct EncodedFrame {
    std::vector<uint8_t> data;
    int codec_type; // AVMEDIA_TYPE_VIDEO
    uint64_t timestamp;
    uint32_t sequence;
    bool is_keyframe;
    int quality;
    size_t original_size;
    
    EncodedFrame() 
        : codec_type(AVMEDIA_TYPE_VIDEO), timestamp(0), sequence(0), 
          is_keyframe(false), quality(80), original_size(0) {}
    
    EncodedFrame(int codec, uint64_t ts, uint32_t seq, bool keyframe) 
        : codec_type(codec), timestamp(ts), sequence(seq), 
          is_keyframe(keyframe), quality(80), original_size(0) {}
};

// V4L2 encoder context structure
struct V4L2EncoderContext {
    int width;
    int height;
    int bitrate;
    int fps;
    std::vector<std::vector<uint8_t>> output_buffers;
    
    V4L2EncoderContext() 
        : width(0), height(0), bitrate(0), fps(0) {}
};

// Abstract encoder interface
class IEncoder {
public:
    virtual ~IEncoder() = default;
    virtual bool initialize() = 0;
    virtual std::unique_ptr<EncodedFrame> encode_frame(const VideoFrame& frame) = 0;
    virtual void set_bitrate(int bitrate) = 0;
    virtual void set_quality(int quality) = 0;
    virtual bool is_healthy() const = 0;
    virtual std::string get_name() const = 0;
};

// Hardware encoder wrapper
class HardwareEncoder : public IEncoder {
public:
    HardwareEncoder(const VideoConfig& config);
    ~HardwareEncoder() override;
    
    bool initialize() override;
    std::unique_ptr<EncodedFrame> encode_frame(const VideoFrame& frame) override;
    void set_bitrate(int bitrate) override;
    void set_quality(int quality) override;
    bool is_healthy() const override;
    std::string get_name() const override { 
        if (use_rockchip_mpp_) return "rockchip_mpp_" + encoder_type_;
        if (use_rga_) return "rga_" + encoder_type_;
        if (use_v4l2_) return "v4l2_" + encoder_type_;
        if (use_mmal_) return "mmal_" + encoder_type_;
        return "hardware_" + encoder_type_; 
    }
    
private:
    // Detection methods
    bool detect_hardware_encoder();
    void detect_v4l2_devices();
    void detect_rockchip_mpp();
    void detect_rga();
    
    // Initialization methods
    bool initialize_mmal_encoder();
    bool initialize_v4l2_encoder();
    bool initialize_v4l2_context();
    bool initialize_rockchip_mpp();
    bool initialize_rga();
    
    // Encoding methods
    std::unique_ptr<EncodedFrame> mmal_encode(const VideoFrame& frame);
    std::unique_ptr<EncodedFrame> v4l2_encode(const VideoFrame& frame);
    std::unique_ptr<EncodedFrame> rockchip_mpp_encode(const VideoFrame& frame);
    std::unique_ptr<EncodedFrame> rga_encode(const VideoFrame& frame);
    
    // Cleanup methods
    void cleanup_v4l2_context();
    
    VideoConfig config_;
    std::string encoder_type_;
    bool use_mmal_;
    bool use_v4l2_;
    bool use_rockchip_mpp_;
    bool use_rga_;
    
    // MMAL specific
    void* mmal_pool_;
    void* mmal_connection_;
    
    // V4L2 specific
    int v4l2_fd_;
    V4L2EncoderContext* encoder_context_;
    
    // Rockchip MPP specific
    int rockchip_mpp_fd_;
    
    // RGA specific
    int rga_fd_;
    
    std::atomic<bool> healthy_{false};
};

// Software encoder using FFmpeg
class SoftwareEncoder : public IEncoder {
public:
    SoftwareEncoder(const VideoConfig& config);
    ~SoftwareEncoder() override;
    
    bool initialize() override;
    std::unique_ptr<EncodedFrame> encode_frame(const VideoFrame& frame) override;
    void set_bitrate(int bitrate) override;
    void set_quality(int quality) override;
    bool is_healthy() const override;
    std::string get_name() const override { return "software_" + encoder_type_; }
    
    // H.265 specific settings
    void set_h265_profile(int profile) { h265_profile_ = profile; }
    void set_h265_level(float level) { h265_level_ = level; }
    
    // MJPEG specific settings
    void set_mjpeg_quality(int quality) { mjpeg_quality_ = quality; }
    void set_mjpeg_optimization(int level) { mjpeg_optimization_ = level; }
    
private:
    bool setup_encoder();
    void cleanup_encoder();
    std::unique_ptr<EncodedFrame> convert_and_encode(const VideoFrame& frame);
    
    VideoConfig config_;
    std::string encoder_type_;
    
    // FFmpeg context
    AVCodecContext* codec_ctx_;
    AVFrame* frame_;
    AVPacket* packet_;
    
    // Color conversion
    SwsContext* sws_ctx_;
    
    // H.265 specific settings
    int h265_profile_;
    float h265_level_;
    
    // MJPEG specific settings
    int mjpeg_quality_;
    int mjpeg_optimization_;
    
    std::atomic<bool> healthy_{false};
};

// Main encoder class
class VideoEncoder {
public:
    explicit VideoEncoder(const VideoConfig& config);
    ~VideoEncoder();
    
    bool initialize();
    void stop();
    bool is_healthy() const;
    
    // Encoding
    std::unique_ptr<EncodedFrame> encode_frame(const VideoFrame& frame);
    
    // Configuration
    void set_bitrate(int bitrate);
    void set_quality(int quality);
    void set_resolution(int width, int height);
    void set_framerate(int fps);
    
    // H.265 specific configuration
    void set_h265_profile(int profile) { 
        config_.h265_profile = profile; 
        if (software_encoder_) software_encoder_->set_h265_profile(profile);
    }
    void set_h265_level(float level) { 
        config_.h265_level = level; 
        if (software_encoder_) software_encoder_->set_h265_level(level);
    }
    
    // MJPEG specific configuration
    void set_mjpeg_quality(int quality) { 
        config_.mjpeg_quality = quality; 
        if (software_encoder_) software_encoder_->set_mjpeg_quality(quality);
    }
    void set_mjpeg_optimization(int level) { 
        config_.mjpeg_optimization_level = level; 
        if (software_encoder_) software_encoder_->set_mjpeg_optimization(level);
    }
    
    // Statistics
    uint64_t get_frames_encoded() const { return frames_encoded_.load(); }
    uint64_t get_bytes_encoded() const { return bytes_encoded_.load(); }
    double get_encoding_time_ms() const { return encoding_time_ms_.load(); }
    
    // Hardware info
    std::string get_encoder_type() const { return active_encoder_ ? active_encoder_->get_name() : "none"; }
    bool is_using_hardware() const { return use_hardware_; }
    
private:
    VideoConfig config_;
    IEncoder* active_encoder_ = nullptr;
    std::unique_ptr<HardwareEncoder> hardware_encoder_;
    std::unique_ptr<SoftwareEncoder> software_encoder_;
    
    bool use_hardware_;
    bool initialized_;
    
    // Statistics
    std::atomic<uint64_t> frames_encoded_{0};
    std::atomic<uint64_t> bytes_encoded_{0};
    std::atomic<uint64_t> encoding_time_ms_{0};
    
    mutable std::mutex encoder_mutex_;  // Made mutable for const methods
};

} // namespace fpv_streamer