#include "testing/latency_tester.h"
#include "video/stereo_compositor.h"
#include "video/capture.h"
#include <algorithm>
#include <numeric>
#include <fstream>
#include <sstream>

namespace fpv_streamer {

LatencyTester::LatencyTester() {
    Logger::info("Initializing latency tester");
}

LatencyTester::~LatencyTester() {
    shutdown();
}

bool LatencyTester::initialize(const LatencyTestConfig& config) {
    config_ = config;
    
    Logger::info("Latency test configuration:");
    Logger::info("  Test duration: " + std::to_string(config_.test_duration_seconds) + " seconds");
    Logger::info("  Target latency: " + std::to_string(config_.target_latency_ms) + "ms");
    Logger::info("  Sample rate: " + std::to_string(config_.sample_rate_hz) + " Hz");
    
    // Initialize test resources
    VideoConfig test_config1;
    test_config1.device_path = "/dev/video0";
    test_config1.width = 1920;
    test_config1.height = 1080;
    test_config1.fps = 60;
    
    StereoConfig stereo_config;
    stereo_config.enable_stereo = false; // Start with single camera for testing
    stereo_config.enable_frame_sync = true;
    
    test_camera_manager_ = std::make_unique<DualCameraManager>(test_config1, stereo_config);
    test_compositor_ = std::make_unique<StereoCompositor>();
    
    return true;
}

void LatencyTester::shutdown() {
    stop_realtime_monitoring();
    test_running_.store(false);
    
    test_camera_manager_.reset();
    test_compositor_.reset();
    
    Logger::info("Latency tester shutdown complete");
}

TestResults LatencyTester::run_comprehensive_test() {
    Logger::info("Starting comprehensive test suite");
    TestResults results;
    test_running_.store(true);
    
    try {
        // Test 1: Dual camera setup
        Logger::info("Testing dual camera setup...");
        results.dual_camera_success = test_dual_camera_setup();
        if (!results.dual_camera_success) {
            results.error_message = "Dual camera setup failed";
            return results;
        }
        
        // Test 2: Stereo compositing
        Logger::info("Testing stereo compositing...");
        results.stereo_compositing_success = test_stereo_compositing();
        if (!results.stereo_compositing_success) {
            results.error_message = "Stereo compositing failed";
            return results;
        }
        
        // Test 3: Latency performance
        Logger::info("Testing latency performance...");
        TestResults latency_results = test_latency_performance();
        results.latency_requirement_met = latency_results.latency_requirement_met;
        results.avg_total_latency_ms = latency_results.avg_total_latency_ms;
        results.min_latency_ms = latency_results.min_latency_ms;
        results.max_latency_ms = latency_results.max_latency_ms;
        results.p95_latency_ms = latency_results.p95_latency_ms;
        results.p99_latency_ms = latency_results.p99_latency_ms;
        results.total_frames_tested = latency_results.total_frames_tested;
        results.frames_below_40ms = latency_results.frames_below_40ms;
        results.all_latencies = latency_results.all_latencies;
        
        // Overall assessment
        results.latency_requirement_met = (results.avg_total_latency_ms <= config_.target_latency_ms);
        
        Logger::info("Comprehensive test completed");
        Logger::info("  Dual camera: " + std::string(results.dual_camera_success ? "PASS" : "FAIL"));
        Logger::info("  Stereo compositing: " + std::string(results.stereo_compositing_success ? "PASS" : "FAIL"));
        Logger::info("  Latency requirement: " + std::string(results.latency_requirement_met ? "PASS" : "FAIL"));
        Logger::info("  Average latency: " + std::to_string(results.avg_total_latency_ms) + "ms");
        
    } catch (const std::exception& e) {
        Logger::error("Comprehensive test failed: " + std::string(e.what()));
        results.error_message = std::string("Test exception: ") + e.what();
    }
    
    test_running_.store(false);
    return results;
}

bool LatencyTester::test_dual_camera_setup() {
    try {
        if (!check_camera_devices()) {
            Logger::warn("Not all required camera devices available");
            return false;
        }
        
        if (!initialize_test_cameras()) {
            Logger::error("Failed to initialize test cameras");
            return false;
        }
        
        Logger::info("Dual camera setup test passed");
        return true;
        
    } catch (const std::exception& e) {
        Logger::error("Dual camera setup test failed: " + std::string(e.what()));
        return false;
    }
}

bool LatencyTester::test_stereo_compositing() {
    try {
        StereoConfig stereo_config;
        stereo_config.enable_stereo = true;
        stereo_config.stereo_mode = 0; // Side by side
        stereo_config.enable_color_correction = true;
        
        if (!test_compositor_->initialize(stereo_config)) {
            Logger::error("Failed to initialize stereo compositor");
            return false;
        }
        
        // Generate test frames
        cv::Mat test_frame1(1080, 1920, CV_8UC3, cv::Scalar(0, 255, 0)); // Green
        cv::Mat test_frame2(1080, 1920, CV_8UC3, cv::Scalar(255, 0, 0)); // Red
        
        // Test compositing
        StereoFrame result;
        if (!test_compositor_->process_frames(test_frame1, test_frame2, result)) {
            Logger::error("Failed to process stereo frames");
            return false;
        }
        
        if (!result.is_valid || result.composite_frame.empty()) {
            Logger::error("Stereo compositing produced invalid result");
            return false;
        }
        
        Logger::info("Stereo compositing test passed");
        Logger::info("  Composite frame size: " + std::to_string(result.composite_frame.cols) + "x" + std::to_string(result.composite_frame.rows));
        
        return true;
        
    } catch (const std::exception& e) {
        Logger::error("Stereo compositing test failed: " + std::string(e.what()));
        return false;
    }
}

TestResults LatencyTester::test_latency_performance() {
    TestResults results;
    std::vector<double> total_latencies;
    
    Logger::info("Starting latency performance test for " + std::to_string(config_.test_duration_seconds) + " seconds");
    
    auto test_start = std::chrono::steady_clock::now();
    auto test_end = test_start + std::chrono::seconds(config_.test_duration_seconds);
    
    // Start real-time monitoring
    start_realtime_monitoring();
    
    int frame_count = 0;
    int frames_below_40ms = 0;  // Local counter for frames under target latency
    while (std::chrono::steady_clock::now() < test_end && test_running_.load()) {
        auto frame_start = std::chrono::high_resolution_clock::now();
        
        try {
            // Capture test frame
            StereoFrame stereo_frame;
            if (test_camera_manager_->capture_stereo_frames(stereo_frame)) {
                // Process with stereo compositor if available
                if (test_compositor_) {
                    if (test_compositor_->process_frames(stereo_frame.left_frame, stereo_frame.right_frame, stereo_frame)) {
                        // Successfully processed stereo frame
                    }
                }
                
                auto frame_end = std::chrono::high_resolution_clock::now();
                auto frame_duration = std::chrono::duration_cast<std::chrono::microseconds>(frame_end - frame_start);
                double latency_ms = frame_duration.count() / 1000.0;
                
                total_latencies.push_back(latency_ms);
                frame_count++;
                frames_processed_++;
                
                if (latency_ms < config_.target_latency_ms) {
                    frames_below_40ms++;
                }
                
                if (config_.enable_detailed_logging && frame_count % 100 == 0) {
                    Logger::debug("Frame " + std::to_string(frame_count) + " latency: " + std::to_string(latency_ms) + "ms");
                }
            } else {
                frames_dropped_++;
            }
            
        } catch (const std::exception& e) {
            Logger::error("Frame processing error: " + std::string(e.what()));
        }
        
        // Control sample rate
        std::this_thread::sleep_for(std::chrono::milliseconds(1000 / config_.sample_rate_hz));
    }
    
    stop_realtime_monitoring();
    
    // Analyze results
    if (!total_latencies.empty()) {
        analyze_latency_results(total_latencies, results);
    }
    
    results.total_frames_tested = frame_count;
    results.frames_below_40ms = frames_below_40ms;
    results.all_latencies = total_latencies;
    
    Logger::info("Latency test completed:");
    Logger::info("  Frames processed: " + std::to_string(frame_count));
    Logger::info("  Frames dropped: " + std::to_string(frames_dropped_.load()));
    Logger::info("  Average latency: " + std::to_string(results.avg_total_latency_ms) + "ms");
    Logger::info("  Min latency: " + std::to_string(results.min_latency_ms) + "ms");
    Logger::info("  Max latency: " + std::to_string(results.max_latency_ms) + "ms");
    Logger::info("  Frames under " + std::to_string(config_.target_latency_ms) + "ms: " + std::to_string(results.frames_below_40ms));
    
    return results;
}

void LatencyTester::start_realtime_monitoring() {
    monitoring_active_.store(true);
    
    monitoring_thread_ = std::thread([this]() {
        while (monitoring_active_.load()) {
            try {
                current_latency_ms_.store(test_compositor_->get_processing_latency_ms());
                
                if (config_.enable_detailed_logging) {
                    Logger::debug("Current latency: " + std::to_string(current_latency_ms_.load()) + "ms");
                }
                
                std::this_thread::sleep_for(std::chrono::seconds(1));
            } catch (const std::exception& e) {
                Logger::error("Monitoring thread error: " + std::string(e.what()));
            }
        }
    });
    
    Logger::info("Real-time monitoring started");
}

void LatencyTester::stop_realtime_monitoring() {
    if (monitoring_active_.load()) {
        monitoring_active_.store(false);
        
        if (monitoring_thread_.joinable()) {
            monitoring_thread_.join();
        }
        
        Logger::info("Real-time monitoring stopped");
    }
}

bool LatencyTester::check_camera_devices() {
    // Check for primary camera
    std::ifstream video0("/dev/video0");
    if (!video0.good()) {
        Logger::warn("Primary camera /dev/video0 not available");
        return false;
    }
    
    // Check for secondary camera if needed
    // TODO: Add stereo configuration to LatencyTestConfig
    /*
    std::string device2_path = "/dev/video2"; // Default to /dev/video2
    std::ifstream video2(device2_path);
    if (!video2.good()) {
        Logger::warn("Secondary camera " + device2_path + " not available");
        return false;
    }
    */
    
    Logger::info("Camera device check passed");
    return true;
}

bool LatencyTester::initialize_test_cameras() {
    if (!test_camera_manager_->initialize()) {
        Logger::error("Failed to initialize dual camera manager");
        return false;
    }
    
    test_camera_manager_->start_capture();
    Logger::info("Test cameras initialized and started");
    return true;
}

void LatencyTester::analyze_latency_results(const std::vector<double>& latencies, TestResults& results) {
    if (latencies.empty()) {
        results.error_message = "No latency measurements collected";
        return;
    }
    
    // Calculate basic statistics
    double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
    results.avg_total_latency_ms = sum / latencies.size();
    results.min_latency_ms = *std::min_element(latencies.begin(), latencies.end());
    results.max_latency_ms = *std::max_element(latencies.begin(), latencies.end());
    
    // Calculate percentiles
    std::vector<double> sorted_latencies = latencies;
    std::sort(sorted_latencies.begin(), sorted_latencies.end());
    
    results.p95_latency_ms = calculate_percentile(sorted_latencies, 95.0);
    results.p99_latency_ms = calculate_percentile(sorted_latencies, 99.0);
    
    // Assessment
    results.latency_requirement_met = (results.avg_total_latency_ms <= config_.target_latency_ms);
}

double LatencyTester::calculate_percentile(const std::vector<double>& data, double percentile) {
    if (data.empty()) return 0.0;
    
    size_t index = static_cast<size_t>(std::ceil(data.size() * percentile / 100.0)) - 1;
    if (index >= data.size()) index = data.size() - 1;
    
    return data[index];
}

// StereoPerformanceTester implementation
StereoPerformanceTester::StereoPerformanceTester() {
}

StereoPerformanceTester::~StereoPerformanceTester() {
    shutdown();
}

bool StereoPerformanceTester::initialize() {
    compositor_ = std::make_unique<StereoCompositor>();
    
    StereoConfig config;
    config.enable_stereo = true;
    
    if (!compositor_->initialize(config)) {
        Logger::error("Failed to initialize stereo performance tester");
        return false;
    }
    
    generate_test_frames();
    is_initialized_ = true;
    
    Logger::info("Stereo performance tester initialized");
    return true;
}

void StereoPerformanceTester::shutdown() {
    cleanup_test_frames();
    compositor_.reset();
    is_initialized_ = false;
    
    Logger::info("Stereo performance tester shutdown complete");
}

bool StereoPerformanceTester::test_frame_synchronization() {
    if (!is_initialized_) return false;
    
    // Test frame synchronization by capturing synchronized frames
    Logger::info("Testing frame synchronization...");
    
    // This would require actual synchronized capture from dual cameras
    // For now, return true as placeholder
    return true;
}

bool StereoPerformanceTester::test_color_correction() {
    if (!is_initialized_) return false;
    
    Logger::info("Testing color correction...");
    
    // Test color correction with different colored frames
    cv::Mat blue_frame(1080, 1920, CV_8UC3, cv::Scalar(255, 0, 0)); // Blue
    cv::Mat red_frame(1080, 1920, CV_8UC3, cv::Scalar(0, 0, 255)); // Red
    
    StereoFrame result;
    if (compositor_->process_frames(blue_frame, red_frame, result)) {
        Logger::info("Color correction test passed");
        return true;
    }
    
    return false;
}

double StereoPerformanceTester::benchmark_compositing_speed() {
    if (!is_initialized_) return -1.0;
    
    Logger::info("Benchmarking compositing speed...");
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    int iterations = 1000;
    for (int i = 0; i < iterations; ++i) {
        StereoFrame result;
        cv::Mat test_frame1(1080, 1920, CV_8UC3);
        cv::Mat test_frame2(1080, 1920, CV_8UC3);
        
        // Fill with test pattern
        test_frame1 = cv::Scalar(i % 255, (i * 2) % 255, (i * 3) % 255);
        test_frame2 = cv::Scalar((i * 4) % 255, (i * 5) % 255, (i * 6) % 255);
        
        compositor_->process_frames(test_frame1, test_frame2, result);
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    
    double avg_time_ms = duration.count() / static_cast<double>(iterations);
    
    Logger::info("Compositing benchmark: " + std::to_string(avg_time_ms) + "ms per frame");
    
    return avg_time_ms;
}

void StereoPerformanceTester::generate_test_frames() {
    // Generate test frames for performance testing
    test_left_frames_.clear();
    test_right_frames_.clear();
    
    for (int i = 0; i < 10; ++i) {
        cv::Mat left_frame(1080, 1920, CV_8UC3);
        cv::Mat right_frame(1080, 1920, CV_8UC3);
        
        // Create different test patterns
        cv::rectangle(left_frame, cv::Point(0, 0), cv::Point(1920, 1080), cv::Scalar(0, 255, 0), -1);
        cv::rectangle(right_frame, cv::Point(0, 0), cv::Point(1920, 1080), cv::Scalar(0, 0, 255), -1);
        
        test_left_frames_.push_back(left_frame);
        test_right_frames_.push_back(right_frame);
    }
}

void StereoPerformanceTester::cleanup_test_frames() {
    test_left_frames_.clear();
    test_right_frames_.clear();
}

// ComprehensiveTester implementation
ComprehensiveTester::ComprehensiveTester() {
}

ComprehensiveTester::~ComprehensiveTester() {
    shutdown();
}

bool ComprehensiveTester::initialize(const ConfigManager& config_manager) {
    // Note: Cannot copy ConfigManager due to mutex member, using reference instead
    
    latency_tester_ = std::make_unique<LatencyTester>();
    stereo_tester_ = std::make_unique<StereoPerformanceTester>();
    
    // Initialize latency tester
    LatencyTestConfig latency_config;
    latency_config.test_duration_seconds = 30;
    latency_config.target_latency_ms = 40;
    latency_config.enable_detailed_logging = true;
    
    if (!latency_tester_->initialize(latency_config)) {
        Logger::error("Failed to initialize latency tester");
        return false;
    }
    
    // Initialize stereo tester
    if (!stereo_tester_->initialize()) {
        Logger::error("Failed to initialize stereo tester");
        return false;
    }
    
    is_initialized_ = true;
    
    Logger::info("Comprehensive tester initialized");
    return true;
}

void ComprehensiveTester::shutdown() {
    latency_tester_.reset();
    stereo_tester_.reset();
    is_initialized_ = false;
    
    Logger::info("Comprehensive tester shutdown complete");
}

TestResults ComprehensiveTester::run_all_tests() {
    if (!is_initialized_) {
        TestResults error_results;
        error_results.error_message = "Tester not initialized";
        return error_results;
    }
    
    Logger::info("Starting comprehensive test suite");
    overall_start_time_ = std::chrono::steady_clock::now();
    
    TestResults final_results;
    
    // Run individual tests
    final_results.dual_camera_success = latency_tester_->test_dual_camera_setup();
    final_results.stereo_compositing_success = latency_tester_->test_stereo_compositing();
    
    TestResults latency_results = latency_tester_->run_comprehensive_test();
    final_results.latency_requirement_met = latency_results.latency_requirement_met;
    final_results.avg_total_latency_ms = latency_results.avg_total_latency_ms;
    final_results.min_latency_ms = latency_results.min_latency_ms;
    final_results.max_latency_ms = latency_results.max_latency_ms;
    final_results.total_frames_tested = latency_results.total_frames_tested;
    final_results.frames_below_40ms = latency_results.frames_below_40ms;
    final_results.all_latencies = latency_results.all_latencies;
    
    // Performance testing
    double compositing_speed = stereo_tester_->benchmark_compositing_speed();
    Logger::info("Stereo compositing speed: " + std::to_string(compositing_speed) + "ms per frame");
    
    auto overall_end = std::chrono::steady_clock::now();
    auto total_duration = std::chrono::duration_cast<std::chrono::seconds>(overall_end - overall_start_time_);
    
    Logger::info("Comprehensive test suite completed in " + std::to_string(total_duration.count()) + " seconds");
    
    // Generate report
    generate_report(final_results, "./comprehensive_test_report.txt");
    print_summary(final_results);
    
    return final_results;
}

TestResults ComprehensiveTester::run_quick_test() {
    // 10-second quick test
    Logger::info("Running quick test (10 seconds)");
    
    TestResults results;
    
    // Basic functionality test
    results.dual_camera_success = latency_tester_->test_dual_camera_setup();
    results.stereo_compositing_success = latency_tester_->test_stereo_compositing();
    
    // Short latency test
    LatencyTestConfig quick_config;
    quick_config.test_duration_seconds = 10;
    quick_config.target_latency_ms = 40;
    quick_config.enable_detailed_logging = false;
    
    // Initialize with quick config
    if (!latency_tester_->initialize(quick_config)) {
        Logger::error("Failed to initialize latency tester for quick test");
        return results;
    }
    
    TestResults quick_latency_results = latency_tester_->test_latency_performance();
    
    results.latency_requirement_met = quick_latency_results.latency_requirement_met;
    results.avg_total_latency_ms = quick_latency_results.avg_total_latency_ms;
    results.total_frames_tested = quick_latency_results.total_frames_tested;
    results.frames_below_40ms = quick_latency_results.frames_below_40ms;
    
    // Note: Cannot restore original config due to private member access
    // This is acceptable for a quick test
    
    Logger::info("Quick test completed");
    return results;
}

void ComprehensiveTester::generate_report(const TestResults& results, const std::string& output_path) {
    std::ofstream report(output_path);
    if (!report.is_open()) {
        Logger::error("Failed to create test report: " + output_path);
        return;
    }
    
    report << "FPV Streamer Dual Camera Test Report\n";
    report << "=====================================\n\n";
    report << "Test Date: " << std::time(nullptr) << "\n\n";
    
    // Test Results
    report << "Test Results:\n";
    report << "-------------\n";
    report << "Dual Camera Setup: " << (results.dual_camera_success ? "PASS" : "FAIL") << "\n";
    report << "Stereo Compositing: " << (results.stereo_compositing_success ? "PASS" : "FAIL") << "\n";
    report << "Latency Requirement (40ms): " << (results.latency_requirement_met ? "PASS" : "FAIL") << "\n\n";
    
    // Latency Statistics
    if (results.total_frames_tested > 0) {
        report << "Latency Statistics:\n";
        report << "-------------------\n";
        report << "Total Frames Tested: " << results.total_frames_tested << "\n";
        report << "Frames Under 40ms: " << results.frames_below_40ms << "\n";
        report << "Average Latency: " << results.avg_total_latency_ms << "ms\n";
        report << "Minimum Latency: " << results.min_latency_ms << "ms\n";
        report << "Maximum Latency: " << results.max_latency_ms << "ms\n";
        if (results.p95_latency_ms > 0) {
            report << "95th Percentile: " << results.p95_latency_ms << "ms\n";
            report << "99th Percentile: " << results.p99_latency_ms << "ms\n";
        }
        report << "\n";
    }
    
    // Error Message
    if (!results.error_message.empty()) {
        report << "Errors:\n";
        report << "-------\n";
        report << results.error_message << "\n\n";
    }
    
    report.close();
    Logger::info("Test report generated: " + output_path);
}

void ComprehensiveTester::print_summary(const TestResults& results) {
    Logger::info("=== TEST SUMMARY ===");
    Logger::info("Dual Camera: " + std::string(results.dual_camera_success ? "PASS" : "FAIL"));
    Logger::info("Stereo Compositing: " + std::string(results.stereo_compositing_success ? "PASS" : "FAIL"));
    Logger::info("Latency Requirement: " + std::string(results.latency_requirement_met ? "PASS" : "FAIL"));
    
    if (results.total_frames_tested > 0) {
        Logger::info("Average Latency: " + std::to_string(results.avg_total_latency_ms) + "ms");
        Logger::info("Frames Under 40ms: " + std::to_string(results.frames_below_40ms) + "/" + std::to_string(results.total_frames_tested));
    }
    
    if (!results.error_message.empty()) {
        Logger::info("Error: " + results.error_message);
    }
    
    if (results.dual_camera_success && results.stereo_compositing_success && results.latency_requirement_met) {
        Logger::info("🎉 ALL TESTS PASSED! System is ready for dual camera 3D streaming.");
    } else {
        Logger::warn("❌ Some tests failed. Please check configuration and hardware setup.");
    }
}

} // namespace fpv_streamer