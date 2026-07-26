#!/bin/bash

# FPV Streamer Build Script
# Builds the complete video streaming server for ARM SBCs
# Supports native builds and Buildroot cross-compilation

set -e

echo "Building FPV Streamer..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if we're in the right directory
check_project_directory() {
    if [[ ! -f "CMakeLists.txt" ]]; then
        echo -e "${RED}Error: CMakeLists.txt not found in current directory: $(pwd)${NC}"
        echo -e "${YELLOW}Please run this script from the project root directory${NC}"
        echo -e "${YELLOW}The script expects to find CMakeLists.txt in the current directory${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Found CMakeLists.txt in $(pwd)${NC}"
}

# Function to clean cmake cache manually
clean_cmake_cache() {
    if [[ -d "build" && -f "build/CMakeCache.txt" ]]; then
        echo -e "${YELLOW}Cleaning CMake cache...${NC}"
        cd build
        rm -rf *
        cd ..
        echo -e "${GREEN}✓ CMake cache cleaned${NC}"
    else
        echo -e "${YELLOW}No build directory or cache found to clean${NC}"
    fi
}

# Check if user wants manual cache cleaning
if [[ "$1" == "--clean-cmake" ]]; then
    echo "Manual CMake cache cleaning requested..."
    check_project_directory
    clean_cmake_cache
    exit 0
fi

# Verify we're in the correct directory
check_project_directory

# Parse command line arguments
BUILD_TYPE="native"
CLEAN_BUILD=false
ENABLE_DEBUG=false
ENABLE_HW_ENCODER=true
ENABLE_OBJECT_DETECTION=true
ENABLE_WEB_INTERFACE=true
BUILDROOT_TC_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --buildroot)
            BUILD_TYPE="buildroot"
            shift
            ;;
        --buildroot-tc-dir)
            BUILDROOT_TC_DIR="$2"
            shift 2
            ;;
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --debug)
            ENABLE_DEBUG=true
            shift
            ;;
        --no-hw-encoder)
            ENABLE_HW_ENCODER=false
            shift
            ;;
        --enable-object-detection)
            ENABLE_OBJECT_DETECTION=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --buildroot              Use Buildroot cross-compilation"
            echo "  --buildroot-tc-dir DIR   Specify Buildroot toolchain directory"
            echo "  --clean                  Clean build before building"
            echo "  --clean-cmake           Clean only CMake cache (no rebuild)"
            echo "  --debug                  Enable debug mode"
            echo "  --no-hw-encoder          Disable hardware encoding"
            echo "  --enable-object-detection Enable object detection"
            echo "  --help, -h               Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if we're on ARM architecture
if [[ "$BUILD_TYPE" == "native" ]]; then
    ARCH=$(uname -m)
    echo -e "${BLUE}Native build for architecture: $ARCH${NC}"
else
    echo -e "${BLUE}Buildroot cross-compilation${NC}"
    if [[ -z "$BUILDROOT_TC_DIR" ]]; then
        # Try to auto-detect from environment
        if [[ -n "$BUILDROOT_TC_DIR" ]]; then
            BUILDROOT_TC_DIR="$BUILDROOT_TC_DIR"
        elif [[ -n "$CROSS_COMPILE" ]]; then
            BUILDROOT_TC_DIR=$(dirname $(dirname $CROSS_COMPILE))
        else
            echo -e "${RED}Error: --buildroot-tc-dir not specified${NC}"
            exit 1
        fi
    fi
    echo -e "${BLUE}Using Buildroot toolchain from: $BUILDROOT_TC_DIR${NC}"
fi

# Create build directory
mkdir -p build
if [[ "$CLEAN_BUILD" == true ]]; then
    echo -e "${YELLOW}Cleaning build directory...${NC}"
    rm -rf build/* build/.*
fi

# Auto-detect source directory changes and clean if necessary
cd build
if [[ -f "CMakeCache.txt" ]]; then
    # Extract the cached source directory
    CACHED_SOURCE_DIR=$(grep -E "^CMAKE_SOURCE_DIRECTORY" CMakeCache.txt | cut -d '=' -f2 | tr -d '"' | sed 's|\\||g')
    CURRENT_SOURCE_DIR=$(cd .. && pwd)
    
    # Compare source directories
    if [[ "$CACHED_SOURCE_DIR" != "$CURRENT_SOURCE_DIR" ]]; then
        echo -e "${YELLOW}Source directory changed from '$CACHED_SOURCE_DIR' to '$CURRENT_SOURCE_DIR'${NC}"
        echo -e "${YELLOW}Cleaning build cache to prevent conflicts...${NC}"
        rm -rf *
        echo -e "${GREEN}Build cache cleaned successfully${NC}"
    fi
fi

if [[ "$BUILD_TYPE" == "native" ]]; then
    # Install system dependencies
    echo -e "${YELLOW}Installing system dependencies...${NC}"
    sudo apt update
    sudo apt install -y \
        build-essential \
        cmake \
        pkg-config \
        libv4l-dev \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libjson-c-dev

    # Configure with CMake for native build
    echo -e "${YELLOW}Configuring with CMake for native build...${NC}"
    
    # Determine the source directory (use relative path from build directory)
    SOURCE_DIR=".."
    if [[ ! -f "../CMakeLists.txt" ]]; then
        echo -e "${RED}Error: CMakeLists.txt not found in parent directory${NC}"
        echo -e "${YELLOW}Please ensure you're running this script from the project root directory${NC}"
        exit 1
    fi
    
    CMAKE_OPTS="-DCMAKE_BUILD_TYPE=Release"
    
    if [[ "$ENABLE_DEBUG" == true ]]; then
        CMAKE_OPTS="$CMAKE_OPTS -DCMAKE_BUILD_TYPE=Debug"
    fi
    
    if [[ "$ENABLE_HW_ENCODER" == true ]]; then
        CMAKE_OPTS="$CMAKE_OPTS -DENABLE_HARDWARE_ENCODER=ON"
    fi
    
    if [[ "$ENABLE_OBJECT_DETECTION" == true ]]; then
        CMAKE_OPTS="$CMAKE_OPTS -DENABLE_OBJECT_DETECTION=ON"
    fi
    
    if [[ "$ENABLE_WEB_INTERFACE" == true ]]; then
        CMAKE_OPTS="$CMAKE_OPTS -DENABLE_WEB_INTERFACE=ON"
    fi
    
    echo -e "${BLUE}Source directory: $(cd .. && pwd)${NC}"
    echo -e "${BLUE}Build directory: $(pwd)${NC}"
    
    cmake "$SOURCE_DIR" $CMAKE_OPTS
    
else
    # Buildroot cross-compilation
    echo -e "${YELLOW}Configuring for Buildroot cross-compilation...${NC}"
    
    # Determine the source directory
    SOURCE_DIR=".."
    if [[ ! -f "../CMakeLists.txt" ]]; then
        echo -e "${RED}Error: CMakeLists.txt not found in parent directory${NC}"
        echo -e "${YELLOW}Please ensure you're running this script from the project root directory${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}Source directory: $(cd .. && pwd)${NC}"
    echo -e "${BLUE}Build directory: $(pwd)${NC}"
    
    # Create CMake cache file for cross-compilation
    cat > cmake-buildroot.cmake << EOF
set(BUILDROOT_TC_DIR "$BUILDROOT_TC_DIR")
include(\${CMAKE_CURRENT_SOURCE_DIR}/../cmake/arm-toolchain.cmake)

# Additional options
set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
EOF
    
    # Run CMake with cross-compilation settings
    cmake "$SOURCE_DIR" \
        -DCMAKE_TOOLCHAIN_FILE=cmake-buildroot.cmake \
        -DBUILDROOT_TC_DIR="$BUILDROOT_TC_DIR" \
        -DCMAKE_BUILD_TYPE=Release \
        -DENABLE_HARDWARE_ENCODER=$([[ "$ENABLE_HW_ENCODER" == true ]] && echo "ON" || echo "OFF") \
        -DENABLE_OBJECT_DETECTION=$([[ "$ENABLE_OBJECT_DETECTION" == true ]] && echo "ON" || echo "OFF") \
        -DENABLE_WEB_INTERFACE=$([[ "$ENABLE_WEB_INTERFACE" == true ]] && echo "ON" || echo "OFF") \
        -DBUILD_TESTING=OFF
fi

# Build
echo -e "${YELLOW}Building FPV Streamer...${NC}"
make -j$(nproc)

# Check binary size
if [[ -f "fpv-streamer" ]]; then
    BINARY_SIZE=$(stat -f%z fpv-streamer 2>/dev/null || stat -c%s fpv-streamer 2>/dev/null || echo "0")
    BINARY_SIZE_KB=$((BINARY_SIZE / 1024))
    BINARY_SIZE_MB=$(echo "scale=2; $BINARY_SIZE / 1024 / 1024" | bc -l 2>/dev/null || echo "N/A")
    
    echo -e "${GREEN}Build complete!${NC}"
    echo "Binary size: ${BINARY_SIZE_KB} KB (${BINARY_SIZE_MB} MB)"
    echo "Binary location: $(pwd)/fpv-streamer"
    
    # Check if binary is under 1MB target
    if [[ $BINARY_SIZE -lt 1048576 ]]; then
        echo -e "${GREEN}✓ Binary size target achieved (< 1MB)${NC}"
    else
        echo -e "${YELLOW}⚠ Binary size exceeds 1MB target${NC}"
    fi
else
    echo -e "${RED}Build failed - fpv-streamer binary not found!${NC}"
    exit 1
fi

# Test the build (only for native builds)
if [[ "$BUILD_TYPE" == "native" ]]; then
    echo -e "${YELLOW}Testing build...${NC}"
    if ./fpv-streamer --help | grep -q "FPV Streamer"; then
        echo -e "${GREEN}Build test passed!${NC}"
    else
        echo -e "${RED}Build test failed!${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Skipping test for cross-compiled binary${NC}"
fi

cd ..

echo -e "${GREEN}FPV Streamer build completed successfully!${NC}"
echo ""
if [[ "$BUILD_TYPE" == "native" ]]; then
    echo "To run the streamer:"
    echo "  ./build/fpv-streamer --device /dev/video0 --port 8080"
    echo ""
    echo "Web interface will be available at: http://localhost:8080"
else
    echo "Cross-compiled binary created for ARM architecture"
    echo "Deploy the binary to your ARM SBC and run:"
    echo "  ./fpv-streamer --device /dev/video0 --port 8080"
    echo ""
    echo "Web interface will be available at: http://<SBC_IP>:8080"
fi