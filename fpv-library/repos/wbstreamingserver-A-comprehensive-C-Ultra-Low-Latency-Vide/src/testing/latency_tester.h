#pragma once

#include <chrono>
#include <atomic>
#include <vector>
#include <memory>
#include <thread>
#include <mutex>
#include "video/stereo_compositor.h"
#include "video/capture.h"
#include "config/config_manager.h"
#include "utils/utils.h"

namespace fpv_streamer {

// Latency testing configuration
struct LatencyTestConfig {
    int test_duration_seconds = 30;
    int target_latency_ms = 40;
    int sample_rate_hz = 100; // Samples per second
    bool enable_detailed_logging = false;
    std::string output_report_path = "./latency_report.txt";
};

// Latency measurement results
struct LatencyMeasurement {
    double capture_latency_ms = 0.0;
    double processing_latency_ms = 0.0;
    double total_latency_ms = 0.0;
    std::chrono::steady_clock::time_point timestamp;
    int frame_sequence = 0;
};

// Comprehensive test results
struct TestResults {
    bool dual_camera_success = false;
    bool stereo_compositing_success = false;
    bool latency_requirement_met = false;
    double avg_total_latency_ms = 0.0;
    double min_latency_ms = 1000.0;
    double max_latency_ms = 0.0;
    double p95_latency_ms = 0.0;
    double p99_latency_ms = 0.0;
    int total_frames_tested = 0;
    int frames_below_40ms = 0;
    std::vector<double> all_latencies;
    std::string error_message;
};

// Latency testing class
class LatencyTester {
public:
    LatencyTester();
    ~LatencyTester();
    
    bool initialize(const LatencyTestConfig& config);
    void shutdown();
    
    // Testing methods
    TestResults run_comprehensive_test();
    bool test_dual_camera_setup();
    bool test_stereo_compositing();
    TestResults test_latency_performance();
    
    // Real-time monitoring
    void start_realtime_monitoring();
    void stop_realtime_monitoring();
    bool is_monitoring_active() const { return monitoring_active_.load(); }
    
    // Results access
    const TestResults& get_last_results() const { return last_results_; }
    
private:
    // Testing utilities
    bool check_camera_devices();
    bool initialize_test_cameras();
    void cleanup_test_resources();
    
    // Measurement methods
    void measure_capture_latency(std::vector<double>& latencies);
    void measure_processing_latency(std::vector<double>& latencies);
    void measure_composite_latency(std::vector<double>& latencies);
    
    // Analysis methods
    void analyze_latency_results(const std::vector<double>& latencies, TestResults& results);
    double calculate_percentile(const std::vector<double>& data, double percentile);
    
    // Configuration and state
    LatencyTestConfig config_;
    TestResults last_results_;
    std::atomic<bool> monitoring_active_{false};
    std::atomic<bool> test_running_{false};
    
    // Test resources
    std::unique_ptr<DualCameraManager> test_camera_manager_;
    std::unique_ptr<StereoCompositor> test_compositor_;
    
    // Statistics
    std::mutex stats_mutex_;
    std::vector<LatencyMeasurement> measurements_;
    std::chrono::steady_clock::time_point test_start_time_;
    
    // Performance monitoring
    std::thread monitoring_thread_;
    std::atomic<int> frames_processed_{0};
    std::atomic<int> frames_dropped_{0};
    std::atomic<double> current_latency_ms_{0};
};

// Stereo performance testing class
class StereoPerformanceTester {
public:
    StereoPerformanceTester();
    ~StereoPerformanceTester();
    
    bool initialize();
    void shutdown();
    
    // Test methods
    bool test_frame_synchronization();
    bool test_color_correction();
    bool test_alignment_accuracy();
    bool test_stereo_modes();
    
    // Performance benchmarks
    double benchmark_compositing_speed();
    int measure_max_fps();
    double measure_memory_usage();
    
    // Quality assessment
    bool assess_stereo_quality();
    bool validate_3d_effectiveness();
    
private:
    void generate_test_frames();
    void cleanup_test_frames();
    
    std::unique_ptr<StereoCompositor> compositor_;
    std::vector<cv::Mat> test_left_frames_;
    std::vector<cv::Mat> test_right_frames_;
    cv::Mat calibration_pattern_;
    
    bool is_initialized_ = false;
};

// Comprehensive test runner
class ComprehensiveTester {
public:
    ComprehensiveTester();
    ~ComprehensiveTester();
    
    bool initialize(const ConfigManager& config_manager);
    void shutdown();
    
    // Main test execution
    TestResults run_all_tests();
    TestResults run_quick_test(); // 10-second test
    TestResults run_extended_test(); // 2-minute test
    
    // Individual test methods
    bool test_hardware_availability();
    bool test_configuration_validity();
    bool test_streaming_capability();
    
    // Reporting
    void generate_report(const TestResults& results, const std::string& output_path);
    void print_summary(const TestResults& results);
    
private:
    bool initialize_test_environment();
    void cleanup_test_environment();
    
    std::unique_ptr<LatencyTester> latency_tester_;
    std::unique_ptr<StereoPerformanceTester> stereo_tester_;
    
    bool is_initialized_ = false;
    
    // Test statistics
    std::chrono::steady_clock::time_point overall_start_time_;
    int total_tests_run_ = 0;
    int total_tests_passed_ = 0;
};

} // namespace fpv_streamer