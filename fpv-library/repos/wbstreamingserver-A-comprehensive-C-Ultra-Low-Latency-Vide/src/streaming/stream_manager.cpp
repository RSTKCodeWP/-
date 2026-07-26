#include "streaming/stream_manager.h"
#include "utils/utils.h"
#include <algorithm>
#include <cstring>
#include <fcntl.h>
#include <sys/time.h>
#include <errno.h>

namespace fpv_streamer {

// WFBStream implementation
WFBStream::WFBStream(const StreamConfig& config) 
    : config_(config)
    , socket_fd_(-1)
    , target_port_(config.port)
    , running_(false)
    , connected_(false) {
    
    target_address_ = "255.255.255.255"; // Broadcast by default
}

WFBStream::~WFBStream() {
    stop();
}

bool WFBStream::initialize() {
    Logger::info("Initializing WFB Stream");
    
    if (!setup_wfb_socket()) {
        Logger::error("Failed to setup WFB socket");
        return false;
    }
    
    set_socket_options();
    optimize_for_latency();
    
    // Start monitoring thread
    monitor_thread_ = std::thread(&WFBStream::monitor_connection, this);
    
    running_.store(true);
    connected_.store(true);
    
    Logger::info("WFB Stream initialized: " + target_address_ + ":" + std::to_string(target_port_));
    return true;
}

void WFBStream::stop() {
    if (!running_.load()) {
        return;
    }
    
    Logger::info("Stopping WFB Stream");
    running_.store(false);
    connected_.store(false);
    
    if (monitor_thread_.joinable()) {
        monitor_thread_.join();
    }
    
    if (socket_fd_ >= 0) {
        close(socket_fd_);
        socket_fd_ = -1;
    }
    
    Logger::info("WFB Stream stopped");
}

bool WFBStream::is_healthy() const {
    return running_.load() && socket_fd_ >= 0;
}

bool WFBStream::send_frame(const EncodedFrame& frame) {
    if (!is_healthy()) {
        return false;
    }
    
    // Send as data packet with fragmentation if needed
    if (frame.data.size() > 900) {
        // Fragment large frames
        auto packets = fragment_data(frame.data.data(), frame.data.size(), 
                                   frame.is_keyframe ? 1 : 0);
        
        // Apply FEC
        if (config_.enable_fec && packets.size() > 1) {
            apply_fec(packets);
        }
        
        // Send all fragments
        for (const auto& packet : packets) {
            send_packet_fragment(packet);
        }
    } else {
        // Send as single packet
        WFBPacket single_packet;
        single_packet.sequence_number = current_sequence_.load();
        single_packet.total_fragments = 1;
        single_packet.fragment_number = 0;
        single_packet.packet_type = frame.is_keyframe ? 1 : 0;
        single_packet.timestamp = frame.timestamp;
        single_packet.data_length = std::min(frame.data.size(), sizeof(single_packet.data));
        memcpy(single_packet.data, frame.data.data(), single_packet.data_length);
        
        send_packet(single_packet);
    }
    
    current_sequence_.fetch_add(1);
    return true;
}

bool WFBStream::send_data(const void* data, size_t size, uint8_t packet_type) {
    if (!is_healthy()) {
        return false;
    }
    
    auto packets = fragment_data(data, size, packet_type);
    
    // Apply FEC for important data
    if (packet_type == 2 && config_.enable_fec) { // Config data
        apply_fec(packets);
    }
    
    for (const auto& packet : packets) {
        send_packet_fragment(packet);
    }
    
    return true;
}

void WFBStream::update_config(const StreamConfig& config) {
    config_ = config;
    
    // Update socket options if needed
    set_socket_options();
    
    Logger::info("WFB config updated");
}

void WFBStream::set_target_address(const std::string& address, int port) {
    target_address_ = address;
    target_port_ = port;
    
    // Update target address structure
    memset(&target_addr_, 0, sizeof(target_addr_));
    target_addr_.sin_family = AF_INET;
    target_addr_.sin_port = htons(target_port_);
    
    if (address == "255.255.255.255") {
        // Broadcast address
        target_addr_.sin_addr.s_addr = htonl(INADDR_BROADCAST);
    } else {
        // Unicast address
        if (inet_pton(AF_INET, address.c_str(), &target_addr_.sin_addr) <= 0) {
            Logger::warn("Invalid target address: " + address);
        }
    }
}

bool WFBStream::setup_wfb_socket() {
    // Create UDP socket
    socket_fd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (socket_fd_ < 0) {
        Logger::error("Failed to create socket: " + std::string(strerror(errno)));
        return false;
    }
    
    // Setup local address
    memset(&local_addr_, 0, sizeof(local_addr_));
    local_addr_.sin_family = AF_INET;
    local_addr_.sin_addr.s_addr = htonl(INADDR_ANY);
    local_addr_.sin_port = htons(config_.port);
    
    // Bind socket
    if (bind(socket_fd_, (sockaddr*)&local_addr_, sizeof(local_addr_)) < 0) {
        Logger::error("Failed to bind socket: " + std::string(strerror(errno)));
        close(socket_fd_);
        socket_fd_ = -1;
        return false;
    }
    
    // Setup target address
    set_target_address(target_address_, target_port_);
    
    Logger::info("WFB socket setup complete");
    return true;
}

void WFBStream::set_socket_options() {
    // Set socket to non-blocking
    int flags = fcntl(socket_fd_, F_GETFL, 0);
    fcntl(socket_fd_, F_SETFL, flags | O_NONBLOCK);
    
    // Enable broadcast
    int broadcast = 1;
    setsockopt(socket_fd_, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast));
    
    // Set send buffer size
    setsockopt(socket_fd_, SOL_SOCKET, SO_SNDBUF, &config_.buffer_size, sizeof(config_.buffer_size));
    
    // Disable TCP_NODELAY for better performance
    int no_delay = 1;
    setsockopt(socket_fd_, IPPROTO_TCP, TCP_NODELAY, &no_delay, sizeof(no_delay));
    
    Logger::info("Socket options configured");
}

void WFBStream::optimize_for_latency() {
    Logger::info("Optimizing WFB for ultra-low latency");
    
    // Reduce buffer sizes for low latency
    int sndbuf = 8192;
    setsockopt(socket_fd_, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));
    
    // Set socket priority for real-time traffic
    int priority = 6; // High priority
    setsockopt(socket_fd_, SOL_SOCKET, SO_PRIORITY, &priority, sizeof(priority));
    
    // Disable Nagle's algorithm (already done with TCP_NODELAY)
    // Set specific QoS if available
    Logger::info("WFB latency optimization complete");
}

void WFBStream::send_packet_fragment(const WFBPacket& packet) {
    if (!is_healthy()) {
        return;
    }
    
    // Set timestamp
    struct timeval tv;
    gettimeofday(&tv, nullptr);
    const_cast<WFBPacket&>(packet).timestamp = tv.tv_sec * 1000000LL + tv.tv_usec;
    
    // Send packet
    ssize_t sent = sendto(socket_fd_, &packet, sizeof(WFBPacket), 0,
                         (sockaddr*)&target_addr_, sizeof(target_addr_));
    
    if (sent > 0) {
        {
            std::lock_guard<std::mutex> lock(stats_mutex_);
            stats_.packets_sent++;
            stats_.fragments_sent++;
            stats_.bytes_sent += sent;
        }
        
        packets_sent_.fetch_add(1);
        total_bytes_sent_.fetch_add(sent);
        last_packet_time_ = std::chrono::high_resolution_clock::now();
    } else if (errno != EAGAIN && errno != EWOULDBLOCK) {
        Logger::warn("Send failed: " + std::string(strerror(errno)));
    }
}

bool WFBStream::send_packet(const WFBPacket& packet) {
    if (!is_healthy()) {
        return false;
    }
    
    // Set timestamp
    struct timeval tv;
    gettimeofday(&tv, nullptr);
    const_cast<WFBPacket&>(packet).timestamp = tv.tv_sec * 1000000LL + tv.tv_usec;
    
    // Send packet
    ssize_t sent = sendto(socket_fd_, &packet, sizeof(WFBPacket), 0,
                         (sockaddr*)&target_addr_, sizeof(target_addr_));
    
    if (sent > 0) {
        Logger::debug("Sent packet: " + std::to_string(sent) + " bytes");
        stats_.packets_sent++;
        stats_.bytes_sent += sent;
        
        packets_sent_.fetch_add(1);
        total_bytes_sent_.fetch_add(sent);
        last_packet_time_ = std::chrono::high_resolution_clock::now();
        return true;
    } else if (errno != EAGAIN && errno != EWOULDBLOCK) {
        Logger::warn("Send failed: " + std::string(strerror(errno)));
        return false;
    }
    return false;
}

std::vector<WFBPacket> WFBStream::fragment_data(const void* data, size_t size, uint8_t packet_type) {
    std::vector<WFBPacket> packets;
    
    const uint8_t* bytes = static_cast<const uint8_t*>(data);
    size_t remaining = size;
    size_t offset = 0;
    
    uint16_t total_fragments = (remaining + sizeof(WFBPacket::data) - 1) / sizeof(WFBPacket::data);
    
    while (remaining > 0) {
        WFBPacket packet;
        packet.sequence_number = current_sequence_.load();
        packet.total_fragments = total_fragments;
        packet.fragment_number = packets.size();
        packet.packet_type = packet_type;
        
        size_t fragment_size = std::min(remaining, sizeof(packet.data));
        packet.data_length = fragment_size;
        memcpy(packet.data, bytes + offset, fragment_size);
        
        packets.push_back(packet);
        
        offset += fragment_size;
        remaining -= fragment_size;
    }
    
    return packets;
}

bool WFBStream::apply_fec(std::vector<WFBPacket>& packets) {
    if (packets.size() <= 1) {
        return false;
    }
    
    // Simple FEC implementation - in practice, this would use Reed-Solomon
    int redundancy = std::min(config_.fec_redundancy, (int)packets.size() / 2);
    
    // Create redundant packets
    for (int i = 0; i < redundancy; i++) {
        WFBPacket fec_packet;
        fec_packet.sequence_number = current_sequence_.load();
        fec_packet.total_fragments = packets.size() + redundancy;
        fec_packet.fragment_number = packets.size() + i;
        fec_packet.packet_type = 255; // FEC packet type
        
        // Simple XOR-based FEC
        memset(fec_packet.data, 0, sizeof(fec_packet.data));
        for (const auto& packet : packets) {
            for (size_t j = 0; j < packet.data_length && j < sizeof(fec_packet.data); j++) {
                fec_packet.data[j] ^= packet.data[j];
            }
        }
        fec_packet.data_length = sizeof(fec_packet.data);
        
        packets.push_back(fec_packet);
    }
    
    Logger::debug("Applied FEC with " + std::to_string(redundancy) + " redundant packets");
    return true;
}

void WFBStream::monitor_connection() {
    Logger::info("WFB connection monitoring started");
    
    while (running_.load()) {
        try {
            // Update statistics
            update_statistics();
            
            // Check connection health
            auto now = std::chrono::high_resolution_clock::now();
            auto time_since_last = std::chrono::duration_cast<std::chrono::seconds>(now - last_packet_time_);
            
            if (time_since_last.count() > 30) { // No packets for 30 seconds
                Logger::warn("No packets sent for 30 seconds");
                connected_.store(false);
            } else {
                connected_.store(true);
            }
            
            std::this_thread::sleep_for(std::chrono::seconds(1));
            
        } catch (const std::exception& e) {
            Logger::error("Exception in WFB monitor: " + std::string(e.what()));
        }
    }
    
    Logger::info("WFB connection monitoring stopped");
}

void WFBStream::update_statistics() {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    
    auto now = std::chrono::high_resolution_clock::now();
    static auto last_update = now;
    
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_update);
    if (elapsed.count() >= 1000) { // Update every second
        uint64_t packets = packets_sent_.load();
        uint64_t bytes = total_bytes_sent_.load();
        
        stats_.packets_sent = packets;
        stats_.bytes_sent = bytes;
        stats_.throughput_mbps = (bytes * 8.0) / 1000000.0;
        stats_.current_sequence = current_sequence_.load();
        stats_.fec_redundancy = config_.fec_redundancy;
        
        last_update = now;
    }
}

// StreamManager implementation
StreamManager::StreamManager(const StreamConfig& config) 
    : config_(config)
    , healthy_(false) {
}

StreamManager::~StreamManager() {
    stop();
}

bool StreamManager::initialize() {
    Logger::info("Initializing Stream Manager");
    
    stream_ = std::make_unique<WFBStream>(config_);
    if (!stream_->initialize()) {
        Logger::error("Failed to initialize WFB stream");
        return false;
    }
    
    // Start statistics thread
    stats_thread_ = std::thread(&StreamManager::optimize_performance, this);
    
    healthy_.store(true);
    Logger::info("Stream Manager initialized successfully");
    return true;
}

void StreamManager::stop() {
    if (!healthy_.load()) {
        return;
    }
    
    Logger::info("Stopping Stream Manager");
    healthy_.store(false);
    
    if (stats_thread_.joinable()) {
        stats_thread_.join();
    }
    
    if (stream_) {
        stream_->stop();
        stream_.reset();
    }
    
    Logger::info("Stream Manager stopped");
}

void StreamManager::restart() {
    Logger::info("Restarting Stream Manager");
    stop();
    
    std::this_thread::sleep_for(std::chrono::seconds(1));
    
    if (initialize()) {
        Logger::info("Stream Manager restarted successfully");
    } else {
        Logger::error("Failed to restart Stream Manager");
    }
}

bool StreamManager::send_frame(const EncodedFrame& frame) {
    if (!healthy_.load() || !stream_) {
        return false;
    }
    
    return stream_->send_frame(frame);
}

bool StreamManager::send_config(const void* config_data, size_t size) {
    if (!healthy_.load() || !stream_) {
        return false;
    }
    
    return stream_->send_data(config_data, size, 2); // 2 = config packet type
}

uint64_t StreamManager::get_bytes_sent() const {
    if (stream_) {
        return stream_->get_bytes_sent();
    }
    return 0;
}

const StreamStats& StreamManager::get_stats() const {
    static StreamStats empty_stats;
    if (stream_) {
        return stream_->get_stats();
    }
    return empty_stats;
}

void StreamManager::set_target(const std::string& address, int port) {
    if (stream_) {
        stream_->set_target_address(address, port);
    }
    Logger::info("Stream target updated: " + address + ":" + std::to_string(port));
}

void StreamManager::disconnect() {
    if (stream_) {
        stream_->stop();
    }
    Logger::info("Stream disconnected");
}

void StreamManager::reconnect() {
    if (stream_) {
        stream_->initialize();
    }
    Logger::info("Stream reconnected");
}

void StreamManager::optimize_performance() {
    Logger::info("Stream performance optimization started");
    
    while (healthy_.load()) {
        try {
            // Update configuration based on statistics
            if (stream_) {
                update_config_from_stats();
            }
            
            std::this_thread::sleep_for(std::chrono::seconds(2));
            
        } catch (const std::exception& e) {
            Logger::error("Exception in performance optimization: " + std::string(e.what()));
        }
    }
    
    Logger::info("Stream performance optimization stopped");
}

void StreamManager::update_config_from_stats() {
    // Adjust FEC based on packet loss
    // Adjust bitrate based on throughput
    // This would implement adaptive streaming logic
    
    // For now, just log statistics
    auto stats = get_stats();
    
    static auto last_log = std::chrono::steady_clock::now();
    auto now = std::chrono::steady_clock::now();
    
    if (std::chrono::duration_cast<std::chrono::seconds>(now - last_log).count() >= 5) {
        Logger::info("Stream stats - Packets: " + std::to_string(stats.packets_sent) + 
                    ", Throughput: " + std::to_string(stats.throughput_mbps) + " Mbps");
        last_log = now;
    }
}

} // namespace fpv_streamer