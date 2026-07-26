/*
 * FPV Streamer - Main Entry Point
 * Ultra-low latency video streaming server for ARM SBCs
 * Supports H.264/MJPEG encoding with WFB streaming protocol
 */

#include <signal.h>
#include <unistd.h>
#include <iostream>
#include <memory>
#include "server/server.h"
#include "config/config_manager.h"
#include "utils/utils.h"

using namespace fpv_streamer;

volatile bool g_running = true;

void signal_handler(int signum) {
    Logger::info("Received signal " + std::to_string(signum) + ", shutting down...");
    g_running = false;
}

int main(int argc, char* argv[]) {
    // Set up signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    // Configure logging system before initialization
    Logger::configure_from_environment();
    Logger::init("", true); // Initialize with default settings
    
    // Set up rate limiting for common noisy log patterns
    Logger::set_rate_limit("FRAME_CAPTURE_ERRORS", 10);      // Max 10 frame capture errors per minute
    Logger::set_rate_limit("HARDWARE_ENCODER", 5);          // Max 5 hardware encoder warnings per minute
    Logger::set_rate_limit("HARDWARE_COMPATIBILITY", 3);    // Max 3 hardware compatibility warnings per minute
    Logger::set_rate_limit("DEVICE_NOT_AVAILABLE", 8);      // Max 8 device unavailable messages per minute
    Logger::set_rate_limit("DEVICE_OPEN_FAILURES", 5);      // Max 5 device open failures per minute
    Logger::set_rate_limit("PERFORMANCE_MONITORING", 2);    // Max 2 performance monitoring logs per minute
    Logger::set_default_rate_limit(30);                     // Default 30 messages per pattern per minute
    
    Logger::info("FPV Streamer Starting...");
    Logger::debug("Architecture: " + std::string(CMAKE_SYSTEM_PROCESSOR));
    
    try {
        // Initialize configuration
        auto config = std::make_unique<ConfigManager>();
        if (!config->initialize(argc, argv)) {
            Logger::error("Failed to initialize configuration");
            return 1;
        }
        
        // Create and start server
        auto server = std::make_unique<Server>(*config);
        
        Logger::info("Starting FPV Streamer Server...");
        if (server->start()) {
            Logger::info("Server started successfully");
            
            // Main event loop
            while (g_running) {
                server->process_events();
                usleep(10000); // 10ms sleep for low CPU usage
            }
        } else {
            Logger::error("Failed to start server");
            return 1;
        }
        
        Logger::info("Shutting down gracefully...");
        server->stop();
        
    } catch (const std::exception& e) {
        Logger::error("Exception: " + std::string(e.what()));
        return 1;
    }
    
    Logger::info("FPV Streamer stopped");
    return 0;
}