#include "utils/utils.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <fstream>
#include <unistd.h>
#include <sys/utsname.h>
#include <algorithm>
#include <cstdlib>

namespace fpv_streamer {

// Logger implementation
std::atomic<LogLevel> Logger::current_level_(LogLevel::WARN);
std::atomic<bool> Logger::verbose_(false);
std::atomic<bool> Logger::file_output_enabled_(false);
std::atomic<bool> Logger::console_output_enabled_(true);

std::string Logger::log_file_path_;
std::ofstream Logger::log_file_;
std::mutex Logger::file_mutex_;
std::mutex Logger::console_mutex_;

std::atomic<bool> Logger::rate_limiting_enabled_(true);
std::atomic<int> Logger::default_rate_limit_(60);
std::map<std::string, int> Logger::rate_limits_;
std::map<std::string, std::vector<std::chrono::system_clock::time_point>> Logger::rate_limit_timestamps_;
std::mutex Logger::rate_limit_mutex_;
bool Logger::environment_configured_(false);

void Logger::init(const std::string& log_file, bool console_output) {
    if (!environment_configured_) {
        configure_from_environment();
        environment_configured_ = true;
    }
    
    if (!log_file.empty()) {
        log_file_path_ = log_file;
        log_file_.open(log_file, std::ios::out | std::ios::app);
        if (log_file_.is_open()) {
            file_output_enabled_.store(true);
        }
    }
    
    console_output_enabled_.store(console_output);
    
    // Use INFO level for init messages regardless of current log level
    if (console_output_enabled_.load()) {
        std::string formatted = format_message(LogLevel::INFO, "Logger initialized");
        std::cout << formatted << std::endl;
    }
}

void Logger::shutdown() {
    info("Logger shutting down");
    
    if (log_file_.is_open()) {
        log_file_.close();
    }
}

void Logger::trace(const std::string& message) {
    log(LogLevel::TRACE, message);
}

void Logger::debug(const std::string& message) {
    log(LogLevel::DEBUG, message);
}

void Logger::info(const std::string& message) {
    log(LogLevel::INFO, message);
}

void Logger::warn(const std::string& message) {
    log(LogLevel::WARN, message);
}

void Logger::error(const std::string& message) {
    log(LogLevel::ERROR, message);
}

void Logger::fatal(const std::string& message) {
    log(LogLevel::FATAL, message);
}

void Logger::set_level(LogLevel level) {
    current_level_.store(level);
}

void Logger::set_verbose(bool verbose) {
    verbose_.store(verbose);
}

void Logger::set_file_output(bool enabled) {
    file_output_enabled_.store(enabled);
}

void Logger::set_console_output(bool enabled) {
    console_output_enabled_.store(enabled);
}

void Logger::log(LogLevel level, const std::string& message) {
    if (level < current_level_.load()) {
        return;
    }
    
    // Check rate limiting
    if (rate_limiting_enabled_.load() && !should_rate_limit(message)) {
        return;
    }
    
    if (verbose_.load() || level >= LogLevel::WARN) {
        std::string formatted = format_message(level, message);
        
        // Console output
        if (console_output_enabled_.load()) {
            std::lock_guard<std::mutex> lock(console_mutex_);
            
            if (level == LogLevel::ERROR || level == LogLevel::FATAL) {
                std::cerr << formatted << std::endl;
            } else {
                std::cout << formatted << std::endl;
            }
        }
        
        // File output
        if (file_output_enabled_.load() && log_file_.is_open()) {
            std::lock_guard<std::mutex> lock(file_mutex_);
            log_file_ << formatted << std::endl;
            log_file_.flush();
        }
        
        // Record for rate limiting
        if (rate_limiting_enabled_.load()) {
            record_message(message);
        }
    }
}

std::string Logger::format_message(LogLevel level, const std::string& message) {
    std::ostringstream ss;
    ss << "[" << get_timestamp() << "] ";
    ss << "[" << get_level_string(level) << "] ";
    ss << message;
    return ss.str();
}

std::string Logger::get_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()) % 1000;
    
    std::ostringstream ss;
    ss << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S");
    ss << "." << std::setfill('0') << std::setw(3) << ms.count();
    return ss.str();
}

std::string Logger::get_level_string(LogLevel level) {
    switch (level) {
        case LogLevel::TRACE: return "TRACE";
        case LogLevel::DEBUG: return "DEBUG";
        case LogLevel::INFO:  return "INFO ";
        case LogLevel::WARN:  return "WARN ";
        case LogLevel::ERROR: return "ERROR";
        case LogLevel::FATAL: return "FATAL";
        default: return "UNKWN";
    }
}

// Timer implementation
// Timer class methods are already defined in the header

// PerformanceMonitor implementation
PerformanceMonitor::PerformanceMonitor() 
    : monitor_thread_()
    , monitoring_(false)
    , running_(false)
    , cpu_cores_(0)
    , total_memory_mb_(0) {
    
    // Get system information
    struct utsname unameData;
    if (uname(&unameData) == 0) {
        Logger::debug("System: " + std::string(unameData.sysname) + " " + 
                     std::string(unameData.machine));
    }
    
    // Get CPU cores
    cpu_cores_ = sysconf(_SC_NPROCESSORS_ONLN);
    Logger::debug("CPU cores: " + std::to_string(cpu_cores_));
    
    // Get total memory
    long pages = sysconf(_SC_PHYS_PAGES);
    long page_size = sysconf(_SC_PAGE_SIZE);
    total_memory_mb_ = (pages * page_size) / (1024 * 1024);
    Logger::debug("Total memory: " + std::to_string(total_memory_mb_) + " MB");
    
    previous_.last_update = std::chrono::high_resolution_clock::now();
}

PerformanceMonitor::~PerformanceMonitor() {
    stop_monitoring();
}

void PerformanceMonitor::start_monitoring() {
    if (monitoring_.load()) {
        return;
    }
    
    Logger::debug("Starting performance monitoring");
    running_.store(true);
    monitoring_.store(true);
    monitor_thread_ = std::thread(&PerformanceMonitor::monitoring_thread, this);
}

void PerformanceMonitor::stop_monitoring() {
    if (!monitoring_.load()) {
        return;
    }
    
    Logger::debug("Stopping performance monitoring");
    running_.store(false);
    monitoring_.store(false);
    
    if (monitor_thread_.joinable()) {
        monitor_thread_.join();
    }
}

double PerformanceMonitor::get_cpu_usage() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_.cpu_usage;
}

double PerformanceMonitor::get_memory_usage_mb() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_.memory_usage_mb;
}

double PerformanceMonitor::get_system_load() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_.system_load;
}

uint64_t PerformanceMonitor::get_network_bytes_sent() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_.network_bytes_sent;
}

uint64_t PerformanceMonitor::get_network_bytes_received() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_.network_bytes_received;
}

double PerformanceMonitor::get_camera_fps() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_.camera_fps;
}

double PerformanceMonitor::get_encode_time_ms() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_.encode_time_ms;
}

double PerformanceMonitor::get_network_latency_ms() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return metrics_.network_latency_ms;
}

std::string PerformanceMonitor::get_system_info() const {
    std::ostringstream ss;
    ss << "CPU: " << cpu_cores_ << " cores\n";
    ss << "Memory: " << total_memory_mb_ << " MB\n";
    ss << "CPU Usage: " << std::fixed << std::setprecision(1) 
       << get_cpu_usage() << "%\n";
    ss << "Memory Usage: " << std::fixed << std::setprecision(1) 
       << get_memory_usage_mb() << " MB\n";
    ss << "Camera FPS: " << std::fixed << std::setprecision(1) 
       << get_camera_fps();
    return ss.str();
}

int PerformanceMonitor::get_cpu_cores() const {
    return cpu_cores_;
}

size_t PerformanceMonitor::get_total_memory_mb() const {
    return total_memory_mb_;
}

void PerformanceMonitor::monitoring_thread() {
    Logger::debug("Performance monitoring thread started");
    
    int log_counter = 0;
    while (running_.load()) {
        try {
            update_cpu_usage();
            update_memory_usage();
            update_network_stats();
            
            // Update network latency (ping to localhost)
            auto ping_start = std::chrono::high_resolution_clock::now();
            // This would involve actual network operations
            auto ping_end = std::chrono::high_resolution_clock::now();
            auto ping_duration = std::chrono::duration_cast<std::chrono::microseconds>(ping_end - ping_start);
            
            {
                std::lock_guard<std::mutex> lock(metrics_mutex_);
                metrics_.network_latency_ms = ping_duration.count() / 1000.0;
            }
            
            // Only log errors and important info, not every iteration
            log_counter++;
            if (log_counter % 300 == 0) { // Log every 5 minutes at 1-second intervals
                Logger::debug("Performance monitoring active");
            }
            
            // Sleep for 1 second
            std::this_thread::sleep_for(std::chrono::seconds(1));
            
        } catch (const std::exception& e) {
            Logger::warn("Exception in performance monitoring: " + std::string(e.what()));
        }
    }
    
    Logger::debug("Performance monitoring thread stopped");
}

void PerformanceMonitor::update_cpu_usage() {
    // Read /proc/stat for CPU usage
    std::ifstream stat_file("/proc/stat");
    if (!stat_file.is_open()) {
        return;
    }
    
    std::string line;
    std::getline(stat_file, line);
    std::istringstream iss(line);
    
    std::string cpu;
    unsigned long user, nice, system, idle, iowait, irq, softirq;
    
    iss >> cpu >> user >> nice >> system >> idle >> iowait >> irq >> softirq;
    
    static unsigned long prev_user = 0, prev_nice = 0, prev_system = 0, prev_idle = 0;
    static unsigned long prev_iowait = 0, prev_irq = 0, prev_softirq = 0;
    
    unsigned long total = user + nice + system + idle + iowait + irq + softirq;
    unsigned long prev_total = prev_user + prev_nice + prev_system + prev_idle + prev_iowait + prev_irq + prev_softirq;
    
    unsigned long idle_time = idle + iowait;
    unsigned long prev_idle_time = prev_idle + prev_iowait;
    
    if (total > prev_total && total - prev_total > 0) {
        double cpu_usage = 100.0 * (total - prev_total - (idle_time - prev_idle_time)) / (total - prev_total);
        
        std::lock_guard<std::mutex> lock(metrics_mutex_);
        metrics_.cpu_usage = cpu_usage;
    }
    
    // Update previous values
    prev_user = user;
    prev_nice = nice;
    prev_system = system;
    prev_idle = idle;
    prev_iowait = iowait;
    prev_irq = irq;
    prev_softirq = softirq;
}

void PerformanceMonitor::update_memory_usage() {
    // Read /proc/meminfo for memory usage
    std::ifstream meminfo_file("/proc/meminfo");
    if (!meminfo_file.is_open()) {
        return;
    }
    
    unsigned long mem_total = 0, mem_available = 0;
    std::string line;
    
    while (std::getline(meminfo_file, line)) {
        if (line.find("MemTotal:") == 0) {
            std::istringstream iss(line.substr(9));
            iss >> mem_total;
        } else if (line.find("MemAvailable:") == 0) {
            std::istringstream iss(line.substr(13));
            iss >> mem_available;
        }
    }
    
    if (mem_total > 0 && mem_available >= 0) {
        double memory_usage_mb = (mem_total - mem_available) / 1024.0;
        
        std::lock_guard<std::mutex> lock(metrics_mutex_);
        metrics_.memory_usage_mb = memory_usage_mb;
    }
}

void PerformanceMonitor::update_network_stats() {
    // Read /proc/net/dev for network statistics
    std::ifstream netdev_file("/proc/net/dev");
    if (!netdev_file.is_open()) {
        return;
    }
    
    std::string line;
    std::getline(netdev_file, line); // Skip header
    std::getline(netdev_file, line); // Skip header
    
    uint64_t bytes_sent = 0, bytes_received = 0;
    
    while (std::getline(netdev_file, line)) {
        std::istringstream iss(line);
        std::string interface;
        iss >> interface;
        
        // Skip loopback
        if (interface == "lo:") {
            continue;
        }
        
        uint64_t rx_bytes, tx_bytes;
        iss >> rx_bytes >> std::ws; // rx_bytes
        iss >> tx_bytes; // tx_bytes
        
        bytes_received += rx_bytes;
        bytes_sent += tx_bytes;
    }
    
    auto now = std::chrono::high_resolution_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - previous_.last_update);
    
    if (elapsed.count() > 1000 && previous_.network_bytes_sent > 0) {
        double rate = (bytes_sent - previous_.network_bytes_sent) * 8.0 / (elapsed.count() / 1000.0); // bits per second
        
        std::lock_guard<std::mutex> lock(metrics_mutex_);
        metrics_.network_bytes_sent = bytes_sent;
        metrics_.network_bytes_received = bytes_received;
    }
    
    previous_.network_bytes_sent = bytes_sent;
    previous_.network_bytes_received = bytes_received;
    previous_.last_update = now;
}

void Logger::configure_from_environment() {
    // Configure log level from environment
    set_environment_log_level("");
    
    // Configure rate limiting from environment
    const char* rate_limit_env = std::getenv("FPV_RATE_LIMIT_ENABLED");
    if (rate_limit_env) {
        std::string value(rate_limit_env);
        rate_limiting_enabled_.store(value == "1" || value == "true" || value == "yes");
    }
    
    const char* default_rate_env = std::getenv("FPV_DEFAULT_RATE_LIMIT");
    if (default_rate_env) {
        try {
            int value = std::stoi(default_rate_env);
            if (value > 0) {
                default_rate_limit_.store(value);
            }
        } catch (const std::exception& e) {
            // Ignore invalid values
        }
    }
    
    // Configure verbose mode from environment
    const char* verbose_env = std::getenv("FPV_LOG_VERBOSE");
    if (verbose_env) {
        std::string value(verbose_env);
        verbose_.store(value == "1" || value == "true" || value == "yes");
    }
}

void Logger::set_environment_log_level(const std::string& level) {
    const char* log_level_env = std::getenv("FPV_LOG_LEVEL");
    std::string effective_level = level;
    
    if (log_level_env && effective_level.empty()) {
        effective_level = std::string(log_level_env);
    } else if (effective_level.empty()) {
        effective_level = "WARN"; // Default
    }
    
    // Convert to uppercase
    std::transform(effective_level.begin(), effective_level.end(), 
                   effective_level.begin(), ::toupper);
    
    LogLevel new_level = LogLevel::WARN;
    if (effective_level == "TRACE") {
        new_level = LogLevel::TRACE;
    } else if (effective_level == "DEBUG") {
        new_level = LogLevel::DEBUG;
    } else if (effective_level == "INFO") {
        new_level = LogLevel::INFO;
    } else if (effective_level == "WARN") {
        new_level = LogLevel::WARN;
    } else if (effective_level == "ERROR") {
        new_level = LogLevel::ERROR;
    } else if (effective_level == "FATAL") {
        new_level = LogLevel::FATAL;
    }
    
    set_level(new_level);
}

void Logger::enable_rate_limiting(bool enabled) {
    rate_limiting_enabled_.store(enabled);
}

void Logger::set_rate_limit(const std::string& message_pattern, int max_per_minute) {
    std::lock_guard<std::mutex> lock(rate_limit_mutex_);
    rate_limits_[message_pattern] = max_per_minute;
}

void Logger::set_default_rate_limit(int max_per_minute) {
    default_rate_limit_.store(max_per_minute);
}

bool Logger::should_rate_limit(const std::string& message) {
    if (!rate_limiting_enabled_.load()) {
        return true; // Don't filter
    }
    
    std::string pattern = extract_pattern(message);
    int limit = default_rate_limit_.load();
    
    {
        std::lock_guard<std::mutex> lock(rate_limit_mutex_);
        
        // Check specific pattern limit
        auto it = rate_limits_.find(pattern);
        if (it != rate_limits_.end()) {
            limit = it->second;
        }
        
        // Get timestamps for this pattern
        auto& timestamps = rate_limit_timestamps_[pattern];
        auto now = std::chrono::system_clock::now();
        
        // Remove timestamps older than 1 minute
        timestamps.erase(
            std::remove_if(timestamps.begin(), timestamps.end(),
                [now](const auto& ts) {
                    return std::chrono::duration_cast<std::chrono::minutes>(
                        now - ts).count() >= 1;
                }),
            timestamps.end()
        );
        
        // Check if we've exceeded the limit
        if (static_cast<int>(timestamps.size()) >= limit) {
            return false; // Rate limited
        }
        
        return true; // Allowed
    }
}

void Logger::record_message(const std::string& message) {
    std::string pattern = extract_pattern(message);
    
    std::lock_guard<std::mutex> lock(rate_limit_mutex_);
    rate_limit_timestamps_[pattern].push_back(std::chrono::system_clock::now());
}

std::string Logger::extract_pattern(const std::string& message) {
    // Extract meaningful patterns from messages to group similar logs
    // This is a simplified implementation - could be enhanced with regex
    
    // Hardware compatibility patterns
    if (message.find("hardware encoder") != std::string::npos) {
        return "HARDWARE_ENCODER";
    }
    
    if (message.find("Failed to") != std::string::npos) {
        return "FAILURE_PATTERNS";
    }
    
    if (message.find("Cannot open") != std::string::npos) {
        return "DEVICE_OPEN_FAILURES";
    }
    
    if (message.find("frame capture") != std::string::npos || 
        message.find("VIDIOC_DQBUF") != std::string::npos) {
        return "FRAME_CAPTURE_ERRORS";
    }
    
    if (message.find("hardware compatibility") != std::string::npos) {
        return "HARDWARE_COMPATIBILITY";
    }
    
    if (message.find("device not available") != std::string::npos) {
        return "DEVICE_NOT_AVAILABLE";
    }
    
    // For performance monitoring related messages
    if (message.find("Performance monitoring") != std::string::npos) {
        return "PERFORMANCE_MONITORING";
    }
    
    // Default: use first few words as pattern
    size_t space_pos = message.find(' ');
    if (space_pos != std::string::npos) {
        return message.substr(0, std::min(space_pos + 20, message.length()));
    }
    
    return message.substr(0, std::min(static_cast<size_t>(20), message.length()));
}

} // namespace fpv_streamer