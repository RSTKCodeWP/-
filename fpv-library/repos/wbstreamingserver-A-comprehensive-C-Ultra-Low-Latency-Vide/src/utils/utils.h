#pragma once

#include <string>
#include <vector>
#include <chrono>
#include <memory>
#include <fstream>
#include <mutex>
#include <atomic>
#include <thread>
#include <unordered_map>
#include <map>

namespace fpv_streamer {

// Log levels
enum class LogLevel {
    TRACE = 0,
    DEBUG = 1,
    INFO = 2,
    WARN = 3,
    ERROR = 4,
    FATAL = 5
};

// Logger class for centralized logging
class Logger {
public:
    static void init(const std::string& log_file = "", bool console_output = true);
    static void shutdown();
    
    // Logging methods
    static void trace(const std::string& message);
    static void debug(const std::string& message);
    static void info(const std::string& message);
    static void warn(const std::string& message);
    static void error(const std::string& message);
    static void fatal(const std::string& message);
    
    // Configuration
    static void set_level(LogLevel level);
    static void set_verbose(bool verbose);
    static void set_file_output(bool enabled);
    static void set_console_output(bool enabled);
    
    // Environment-based configuration
    static void configure_from_environment();
    static void set_environment_log_level(const std::string& level);
    
    // Rate limiting
    static void enable_rate_limiting(bool enabled);
    static void set_rate_limit(const std::string& message_pattern, int max_per_minute);
    static void set_default_rate_limit(int max_per_minute);
    
    // Utility
    static std::string get_level_string(LogLevel level);
    static LogLevel get_level() { return current_level_.load(); }
    static bool is_verbose() { return verbose_.load(); }
    static bool is_rate_limiting_enabled() { return rate_limiting_enabled_.load(); }
    
private:
    static void log(LogLevel level, const std::string& message);
    static bool should_rate_limit(const std::string& message);
    static void record_message(const std::string& pattern);
    static std::string format_message(LogLevel level, const std::string& message);
    static std::string get_timestamp();
    static std::string extract_pattern(const std::string& message);
    
    // Configuration
    static std::atomic<LogLevel> current_level_;
    static std::atomic<bool> verbose_;
    static std::atomic<bool> file_output_enabled_;
    static std::atomic<bool> console_output_enabled_;
    
    // Rate limiting
    static std::atomic<bool> rate_limiting_enabled_;
    static std::atomic<int> default_rate_limit_;
    static std::map<std::string, int> rate_limits_;
    static std::map<std::string, std::vector<std::chrono::system_clock::time_point>> rate_limit_timestamps_;
    static std::mutex rate_limit_mutex_;
    
    // Environment configuration
    static bool environment_configured_;
    
    // File output
    static std::string log_file_path_;
    static std::ofstream log_file_;
    static std::mutex file_mutex_;
    
    // Thread safety
    static std::mutex console_mutex_;
};

// High-precision timer
class Timer {
public:
    Timer() : running_(false) {
        start_time_ = std::chrono::high_resolution_clock::now();
        end_time_ = start_time_;
    }
    
    void start() {
        start_time_ = std::chrono::high_resolution_clock::now();
        running_.store(true);
    }
    
    void stop() {
        if (running_.load()) {
            end_time_ = std::chrono::high_resolution_clock::now();
            running_.store(false);
        }
    }
    
    void reset() {
        start_time_ = std::chrono::high_resolution_clock::now();
        end_time_ = start_time_;
        running_.store(false);
    }
    
    // Get elapsed time in various units
    double get_elapsed_ms() const {
        auto now = std::chrono::high_resolution_clock::now();
        if (running_.load()) {
            return std::chrono::duration<double, std::milli>(now - start_time_).count();
        } else {
            return std::chrono::duration<double, std::milli>(end_time_ - start_time_).count();
        }
    }
    
    double get_elapsed_us() const {
        auto now = std::chrono::high_resolution_clock::now();
        if (running_.load()) {
            return std::chrono::duration<double, std::micro>(now - start_time_).count();
        } else {
            return std::chrono::duration<double, std::micro>(end_time_ - start_time_).count();
        }
    }
    
    double get_elapsed_s() const {
        return get_elapsed_ms() / 1000.0;
    }
    
    bool is_running() const {
        return running_.load();
    }
    
private:
    std::chrono::high_resolution_clock::time_point start_time_;
    std::chrono::high_resolution_clock::time_point end_time_;
    std::atomic<bool> running_;
};

// Performance monitor for tracking system performance
class PerformanceMonitor {
public:
    PerformanceMonitor();
    ~PerformanceMonitor();
    
    void start_monitoring();
    void stop_monitoring();
    bool is_monitoring() const { return monitoring_.load(); }
    
    // CPU and memory monitoring
    double get_cpu_usage() const;
    double get_memory_usage_mb() const;
    double get_system_load() const;
    
    // Network monitoring
    uint64_t get_network_bytes_sent() const;
    uint64_t get_network_bytes_received() const;
    
    // Camera monitoring
    double get_camera_fps() const;
    double get_encode_time_ms() const;
    double get_network_latency_ms() const;
    
    // System information
    std::string get_system_info() const;
    int get_cpu_cores() const;
    size_t get_total_memory_mb() const;
    
private:
    void monitoring_thread();
    void update_cpu_usage();
    void update_memory_usage();
    void update_network_stats();
    
    std::thread monitor_thread_;
    std::atomic<bool> monitoring_{false};
    std::atomic<bool> running_{false};
    
    // Performance metrics
    mutable std::mutex metrics_mutex_;
    struct Metrics {
        double cpu_usage = 0.0;
        double memory_usage_mb = 0.0;
        uint64_t network_bytes_sent = 0;
        uint64_t network_bytes_received = 0;
        double camera_fps = 0.0;
        double encode_time_ms = 0.0;
        double network_latency_ms = 0.0;
        double system_load = 0.0;
    } metrics_;
    
    // Previous measurements for calculations
    struct PreviousMetrics {
        uint64_t network_bytes_sent = 0;
        uint64_t network_bytes_received = 0;
        uint64_t camera_frames = 0;
        std::chrono::high_resolution_clock::time_point last_update;
    } previous_;
    
    // System information
    int cpu_cores_;
    size_t total_memory_mb_;
};

// Memory pool for efficient memory allocation
template<typename T>
class MemoryPool {
public:
    MemoryPool(size_t pool_size = 1000) : pool_size_(pool_size) {
        objects_.reserve(pool_size_);
        
        // Pre-allocate objects
        for (size_t i = 0; i < pool_size_; ++i) {
            objects_.push_back(std::make_unique<T>());
            free_objects_.push_back(objects_[i].get());
        }
    }
    
    ~MemoryPool() = default;
    
    T* acquire() {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (!free_objects_.empty()) {
            T* obj = free_objects_.back();
            free_objects_.pop_back();
            return obj;
        }
        
        // If pool is exhausted, create new object
        return new T();
    }
    
    void release(T* obj) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (free_objects_.size() < pool_size_) {
            free_objects_.push_back(obj);
        } else {
            delete obj; // Delete if pool is full
        }
    }
    
    size_t get_free_count() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return free_objects_.size();
    }
    
    size_t get_total_count() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return objects_.size();
    }
    
private:
    size_t pool_size_;
    std::vector<std::unique_ptr<T>> objects_;
    std::vector<T*> free_objects_;
    mutable std::mutex mutex_;
};

// Circular buffer for streaming data
template<typename T, size_t Size>
class CircularBuffer {
public:
    CircularBuffer() : head_(0), tail_(0), count_(0) {}
    
    bool push(const T& item) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (count_ == Size) {
            return false; // Buffer full
        }
        
        buffer_[head_] = item;
        head_ = (head_ + 1) % Size;
        count_++;
        
        return true;
    }
    
    bool pop(T& item) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (count_ == 0) {
            return false; // Buffer empty
        }
        
        item = buffer_[tail_];
        tail_ = (tail_ + 1) % Size;
        count_--;
        
        return true;
    }
    
    bool is_empty() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_ == 0;
    }
    
    bool is_full() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_ == Size;
    }
    
    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_;
    }
    
    void clear() {
        std::lock_guard<std::mutex> lock(mutex_);
        head_ = 0;
        tail_ = 0;
        count_ = 0;
    }
    
private:
    T buffer_[Size];
    size_t head_;
    size_t tail_;
    size_t count_;
    mutable std::mutex mutex_;
};

} // namespace fpv_streamer