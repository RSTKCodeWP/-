# FPV Streamer Standalone Makefile
# For quick builds from any directory
# Usage: make -f Makefile SOURCE_DIR=/path/to/source

# Configuration
SOURCE_DIR ?= .
BUILD_DIR ?= build
CMAKE ?= cmake
MAKE ?= make

# Check if source directory exists
ifeq ($(wildcard $(SOURCE_DIR)/CMakeLists.txt),)
    $(error CMakeLists.txt not found in $(SOURCE_DIR). Please set SOURCE_DIR correctly.)
endif

# Default target
.PHONY: all
all: build

# Create build directory and configure
.PHONY: configure
configure:
	@echo "Configuring FPV Streamer from $(SOURCE_DIR)..."
	@mkdir -p $(BUILD_DIR)
	@cd $(BUILD_DIR) && $(CMAKE) $(SOURCE_DIR)

# Build project
.PHONY: build
build: configure
	@echo "Building FPV Streamer..."
	@cd $(BUILD_DIR) && $(MAKE) -j$(shell nproc)

# Clean build
.PHONY: clean
clean:
	@echo "Cleaning build directory..."
	@rm -rf $(BUILD_DIR)

# Clean only CMake cache
.PHONY: clean-cache
clean-cache:
	@echo "Cleaning CMake cache..."
	@if [ -d "$(BUILD_DIR)" ]; then \
		cd $(BUILD_DIR) && rm -rf *; \
		echo "CMake cache cleaned"; \
	else \
		echo "No build directory found"; \
	fi

# Rebuild from clean
.PHONY: rebuild
rebuild: clean build

# Run tests
.PHONY: test
test: build
	@echo "Running tests..."
	@cd $(BUILD_DIR) && ./fpv-test-runner --quick

# Install
.PHONY: install
install: build
	@echo "Installing FPV Streamer..."
	@cd $(BUILD_DIR) && $(MAKE) install

# Show help
.PHONY: help
help:
	@echo "FPV Streamer Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make [target] [SOURCE_DIR=/path/to/source] [BUILD_DIR=/path/to/build]"
	@echo ""
	@echo "Targets:"
	@echo "  all         - Configure and build (default)"
	@echo "  configure   - Only configure CMake"
	@echo "  build       - Build the project"
	@echo "  clean       - Clean build directory"
	@echo "  clean-cache - Clean only CMake cache"
	@echo "  rebuild     - Clean and rebuild"
	@echo "  test        - Build and run tests"
	@echo "  install     - Install binaries"
	@echo "  help        - Show this help"
	@echo ""
	@echo "Examples:"
	@echo "  # Build from current directory"
	@echo "  make"
	@echo ""
	@echo "  # Build from different source directory"
	@echo "  make SOURCE_DIR=/media/data_emmc/src/wbStreamingServer_v0.3.4"
	@echo ""
	@echo "  # Clean cache and rebuild"
	@echo "  make clean-cache && make"
	@echo ""
	@echo "  # Quick test build"
	@echo "  make SOURCE_DIR=/path/to/source BUILD_DIR=/tmp/build test"

# Declare phony targets
.PHONY: all configure build clean clean-cache rebuild test install help