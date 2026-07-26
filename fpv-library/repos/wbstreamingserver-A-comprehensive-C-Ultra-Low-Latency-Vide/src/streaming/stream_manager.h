#pragma once

#include <memory>
#include <vector>
#include <string>
#include <atomic>
#include <thread>
#include <chrono>
#include <mutex>
#include <map>
#include <cstring>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <netinet/tcp.h>
#include "config/config_manager.h"
#include "video/encoder.h"

namespace fpv_streamer {

// WFB (WiFi Broadcast) packet structure
struct WFBPacket {
    uint16_t sequence_number;
    uint16_t fragment_number;
    uint16_t total_fragments;
    uint8_t packet_type; // 0=data, 1=keyframe, 2=config
    uint64_t timestamp;
    uint32_t data_length;
    uint8_t data[1024]; // Max packet size
    
    WFBPacket() 
        : sequence_number(0), fragment_number(0), total_fragments(1)
        , packet_type(0), timestamp(0), data_length(0) {
        ::memset(data, 0, sizeof(data));
    }
};

// Stream statistics
struct StreamStats {
    uint64_t packets_sent = 0;
    uint64_t packets_lost = 0;
    uint64_t fragments_sent = 0;
    uint64_t bytes_sent = 0;
    double packet_loss_rate = 0.0;
    double throughput_mbps = 0.0;
    uint32_t current_sequence = 0;
    uint16_t fec_redundancy = 2;
    int signal_strength = -50;
    bool connected = false;
};

// WFB Stream Manager
class WFBStream {
public:
    WFBStream(const StreamConfig& config);
    ~WFBStream();
    
    bool initialize();
    void stop();
    bool is_healthy() const;
    bool is_connected() const { return connected_.load(); }
    
    // Streaming operations
    bool send_frame(const EncodedFrame& frame);
    bool send_data(const void* data, size_t size, uint8_t packet_type = 0);
    
    // Configuration
    void update_config(const StreamConfig& config);
    void set_target_address(const std::string& address, int port);
    
    // Statistics
    const StreamStats& get_stats() const { return stats_; }
    uint64_t get_bytes_sent() const { return stats_.bytes_sent; }
    
    // Connection management
    bool start_listening();
    void stop_listening();
    
private:
    // WFB protocol implementation
    bool setup_wfb_socket();
    void send_packet_fragment(const WFBPacket& packet);
    void process_acknowledge();
    
    // Fragmentation and reassembly
    std::vector<WFBPacket> fragment_data(const void* data, size_t size, uint8_t packet_type);
    bool reassemble_packets();
    
    // FEC (Forward Error Correction)
    bool apply_fec(std::vector<WFBPacket>& packets);
    bool apply_reed_solomon(std::vector<uint8_t>& data);
    
    // Network operations
    bool send_packet(const WFBPacket& packet);
    bool receive_packet(WFBPacket& packet, sockaddr_in& sender);
    
    // Statistics and monitoring
    void update_statistics();
    void monitor_connection();
    
    // Latency optimization
    void optimize_for_latency();
    void set_socket_options();
    
    StreamConfig config_;
    int socket_fd_;
    std::string target_address_;
    int target_port_;
    
    // Socket addresses
    sockaddr_in local_addr_;
    sockaddr_in target_addr_;
    sockaddr_in receive_addr_;
    
    // Threading
    std::thread receive_thread_;
    std::thread monitor_thread_;
    std::atomic<bool> running_{false};
    std::atomic<bool> connected_{false};
    
    // Buffer management
    std::vector<uint8_t> send_buffer_;
    std::vector<uint8_t> receive_buffer_;
    std::mutex buffer_mutex_;
    
    // Sequence management
    std::atomic<uint16_t> current_sequence_{0};
    std::map<uint16_t, std::vector<WFBPacket>> pending_fragments_;
    
    // Statistics
    mutable std::mutex stats_mutex_;
    StreamStats stats_;
    
    // Performance tracking
    std::chrono::high_resolution_clock::time_point last_packet_time_;
    std::atomic<uint64_t> total_bytes_sent_{0};
    std::atomic<uint64_t> packets_sent_{0};
    std::atomic<uint64_t> packets_lost_{0};
};

// Main stream manager
class StreamManager {
public:
    explicit StreamManager(const StreamConfig& config);
    ~StreamManager();
    
    bool initialize();
    void stop();
    void restart();
    bool is_healthy() const { return healthy_.load(); }
    bool is_connected() const { return stream_ && stream_->is_connected(); }
    
    // Streaming
    bool send_frame(const EncodedFrame& frame);
    bool send_config(const void* config_data, size_t size);
    
    // Statistics
    uint64_t get_bytes_sent() const;
    const StreamStats& get_stats() const;
    
    // Connection management
    void set_target(const std::string& address, int port);
    void disconnect();
    void reconnect();
    
private:
    StreamConfig config_;
    std::unique_ptr<WFBStream> stream_;
    
    // Threading
    std::thread stats_thread_;
    std::atomic<bool> healthy_{false};
    
    // Performance optimization
    void optimize_performance();
    void update_config_from_stats();
    
    // Latency monitoring
    std::atomic<uint64_t> total_latency_us_{0};
    std::atomic<uint32_t> latency_samples_{0};
};

} // namespace fpv_streamer