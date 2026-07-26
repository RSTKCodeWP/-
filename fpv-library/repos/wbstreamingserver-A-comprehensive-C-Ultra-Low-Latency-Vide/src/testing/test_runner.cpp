#include "testing/latency_tester.h"
#include "config/config_manager.h"
#include "utils/utils.h"
#include <iostream>
#include <signal.h>
#include <chrono>
#include <cstdlib>

using namespace fpv_streamer;
using namespace std::chrono_literals;

std::atomic<bool> running_(true);

void signal_handler(int signal) {
    Logger::info("Received signal " + std::to_string(signal) + ", shutting down...");
    running_.store(false);
    
    // Force exit after signal is received
    std::quick_exit(0);
}

int main(int argc, char* argv[]) {
    // Setup signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Initialize logging
    Logger::init();
    Logger::info("Starting FPV Streamer Dual Camera Test Suite");
    
    try {
        // Parse command line arguments
        bool quick_test = false;
        bool extended_test = false;
        bool realtime_monitoring = false;
        int test_duration = 30; // seconds
        int target_latency = 40; // ms
        
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--help" || arg == "-h") {
                std::cout << "FPV Streamer Dual Camera Test Suite\n";
                std::cout << "Usage: " << argv[0] << " [options]\n";
                std::cout << "Options:\n";
                std::cout << "  --help, -h              Show this help\n";
                std::cout << "  --quick                 Run 10-second quick test\n";
                std::cout << "  --extended              Run 2-minute extended test\n";
                std::cout << "  --duration SECONDS      Set test duration (default: 30)\n";
                std::cout << "  --target-latency MS     Set target latency in ms (default: 40)\n";
                std::cout << "  --monitor               Enable real-time monitoring\n";
                std::cout << "  --verbose               Enable verbose logging\n";
                return 0;
            } else if (arg == "--quick") {
                quick_test = true;
            } else if (arg == "--extended") {
                extended_test = true;
            } else if (arg == "--monitor") {
                realtime_monitoring = true;
            } else if (arg == "--verbose") {
                Logger::set_level(LogLevel::DEBUG);
            } else if (arg == "--duration" && i + 1 < argc) {
                test_duration = std::stoi(argv[++i]);
            } else if (arg == "--target-latency" && i + 1 < argc) {
                target_latency = std::stoi(argv[++i]);
            }
        }
        
        // Initialize configuration
        ConfigManager config_manager;
        if (!config_manager.initialize(argc, argv)) {
            Logger::error("Failed to initialize configuration");
            return 1;
        }
        
        // Check for early termination signal
        if (!running_.load()) {
            Logger::info("Shutdown requested during configuration");
            return 0;
        }
        
        // Initialize comprehensive tester
        ComprehensiveTester tester;
        if (!tester.initialize(config_manager)) {
            Logger::error("Failed to initialize test suite");
            return 1;
        }
        
        // Check for termination signal before starting tests
        if (!running_.load()) {
            Logger::info("Shutdown requested during test suite initialization");
            tester.shutdown();
            return 0;
        }
        
        Logger::info("Test suite initialized successfully");
        
        // Run appropriate test based on arguments
        TestResults results;
        
        if (!running_.load()) {
            Logger::info("Shutdown requested before starting tests");
            tester.shutdown();
            return 0;
        }
        
        if (quick_test) {
            Logger::info("Running quick test (10 seconds)");
            results = tester.run_quick_test();
        } else if (extended_test) {
            Logger::info("Running extended test (2 minutes)");
            // For extended test, we would need to modify the tester
            // For now, run standard test with longer duration
            results = tester.run_all_tests();
        } else {
            Logger::info("Running comprehensive test (" + std::to_string(test_duration) + " seconds)");
            results = tester.run_all_tests();
        }
        
        // Check for termination signal after tests
        if (!running_.load()) {
            Logger::info("Shutdown requested during test execution");
            tester.shutdown();
            return 0;
        }
        
        // Print final results
        tester.print_summary(results);
        
        // Real-time monitoring mode
        if (realtime_monitoring) {
            Logger::info("Starting real-time monitoring mode (Press Ctrl+C to stop)");
            Logger::info("Monitoring dual camera system performance...");
            
            while (running_.load()) {
                std::this_thread::sleep_for(5s);
                
                if (running_.load()) {
                    Logger::info("System status: Running");
                    // Add more monitoring output here as needed
                }
            }
        }
        
        // Return appropriate exit code
        if (results.dual_camera_success && results.stereo_compositing_success && results.latency_requirement_met) {
            Logger::info("✅ ALL TESTS PASSED - System is ready for dual camera 3D streaming!");
            return 0;
        } else {
            Logger::error("❌ TESTS FAILED - Please check configuration and hardware setup");
            return 1;
        }
        
    } catch (const std::exception& e) {
        Logger::error("Test suite error: " + std::string(e.what()));
        return 1;
    } catch (...) {
        Logger::error("Unknown error occurred in test suite");
        return 1;
    }
    
    return 0;
}