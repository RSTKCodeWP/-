cmake_minimum_required(VERSION 3.16)
project(FPVStreamer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Buildroot compatibility
if(BUILDROOT_TC_DIR)
    message(STATUS "Building for Buildroot cross-compilation")
    set(CMAKE_SYSTEM_NAME Linux)
    set(CMAKE_SYSTEM_PROCESSOR arm)
    set(CMAKE_C_COMPILER ${BUILDROOT_TC_DIR}/usr/bin/arm-linux-gnueabihf-gcc)
    set(CMAKE_CXX_COMPILER ${BUILDROOT_TC_DIR}/usr/bin/arm-linux-gnueabihf-g++)
    set(CMAKE_FIND_ROOT_PATH ${BUILDROOT_TC_DIR}/usr)
    set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
    set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
    set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
endif()

# Platform detection
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    set(TARGET_ARCH "arm64")
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "arm")
    set(TARGET_ARCH "arm")
else()
    set(TARGET_ARCH "x86_64")
endif()

message(STATUS "Target architecture: ${TARGET_ARCH}")
message(STATUS "Compiler: ${CMAKE_C_COMPILER}")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")

# Pass system information to C++ code
add_definitions(-DCMAKE_SYSTEM_PROCESSOR="${CMAKE_SYSTEM_PROCESSOR}")

# Compiler optimization for embedded targets
if(CMAKE_SYSTEM_PROCESSOR MATCHES "arm")
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -Os -ffunction-sections -fdata-sections -fmerge-constants")
    set(CMAKE_EXE_LINKER_FLAGS_RELEASE "${CMAKE_EXE_LINKER_FLAGS_RELEASE} -Wl,--gc-sections -Wl,--strip-all")
endif()

# Find required packages
find_package(Threads REQUIRED)
find_package(PkgConfig REQUIRED)

# Core dependencies - Buildroot compatible
pkg_check_modules(V4L2 libv4l2)
if(NOT V4L2_FOUND)
    pkg_check_modules(V4L2 REQUIRED v4l2)
endif()

pkg_check_modules(FFMPEG libavcodec libavformat libavutil)
if(NOT FFMPEG_FOUND)
    pkg_check_modules(FFMPEG REQUIRED ffmpeg)
endif()

pkg_check_modules(JSON json-c)
if(NOT JSON_FOUND)
    pkg_check_modules(JSON REQUIRED json-c)
endif()

# Dependencies for hardware acceleration and stereo processing
find_library(VCHIQ_LIBRARY vchiq)
find_library(MMAL_LIBRARY mmal)

# Rockchip MPP library detection
find_library(ROCKCHIP_MPP_LIBRARY rk_mpi)
if(NOT ROCKCHIP_MPP_LIBRARY)
    find_library(ROCKCHIP_MPP_LIBRARY rockchip-mpi)
endif()
if(NOT ROCKCHIP_MPP_LIBRARY)
    find_library(ROCKCHIP_MPP_LIBRARY rockchip-mpp)
endif()

# RGA library detection (Rockchip GPU)
find_library(RGA_LIBRARY rga)

# OpenCV is required for stereo compositing
find_package(OpenCV REQUIRED)

# Validate OpenCV installation
if(NOT OpenCV_FOUND)
    message(FATAL_ERROR "OpenCV is required for stereo compositing functionality")
endif()

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${V4L2_INCLUDE_DIRS}
    ${FFMPEG_INCLUDE_DIRS}
    ${JSON_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
)

# Main executable
add_executable(fpv-streamer
    src/main.cpp
    src/server/server.cpp
    src/streaming/stream_manager.cpp
    src/video/capture.cpp
    src/video/encoder.cpp
    src/video/compression.cpp
    src/video/stereo_compositor.cpp
    src/detection/detection.cpp
    src/web/web_interface.cpp
    src/config/config_manager.cpp
    src/utils/logger.cpp
    src/utils/timer.cpp
)

target_link_libraries(fpv-streamer
    ${V4L2_LIBRARIES}
    ${FFMPEG_LIBRARIES}
    swscale  # Add libswscale explicitly
    ${JSON_LIBRARIES}
    ${OpenCV_LIBS}
    Threads::Threads
    m
    pthread
    dl
)

# Hardware-specific libraries
if(VCHIQ_LIBRARY)
    target_link_libraries(fpv-streamer ${VCHIQ_LIBRARY})
    target_compile_definitions(fpv-streamer HAVE_VCHIQ)
endif()

if(MMAL_LIBRARY)
    target_link_libraries(fpv-streamer ${MMAL_LIBRARY})
    target_compile_definitions(fpv-streamer HAVE_MMAL)
endif()

if(ROCKCHIP_MPP_LIBRARY)
    target_link_libraries(fpv-streamer ${ROCKCHIP_MPP_LIBRARY})
    target_compile_definitions(fpv-streamer HAVE_ROCKCHIP_MPP)
    message(STATUS "Found Rockchip MPP library: ${ROCKCHIP_MPP_LIBRARY}")
else()
    message(STATUS "Rockchip MPP library not found - will use software fallback")
endif()

if(RGA_LIBRARY)
    target_link_libraries(fpv-streamer ${RGA_LIBRARY})
    target_compile_definitions(fpv-streamer HAVE_RGA)
    message(STATUS "Found RGA library: ${RGA_LIBRARY}")
else()
    message(STATUS "RGA library not found - will use software fallback")
endif()

# Test runner executable
add_executable(fpv-test-runner
    src/testing/test_runner.cpp
    src/testing/latency_tester.cpp
    src/video/stereo_compositor.cpp
    src/video/capture.cpp
    src/video/encoder.cpp
    src/web/web_interface.cpp
    src/config/config_manager.cpp
    src/utils/logger.cpp
    src/utils/timer.cpp
)

target_link_libraries(fpv-test-runner
    ${V4L2_LIBRARIES}
    ${FFMPEG_LIBRARIES}
    swscale  # Add libswscale explicitly
    ${JSON_LIBRARIES}
    ${OpenCV_LIBS}
    Threads::Threads
    m
    pthread
    dl
)

# Add hardware-specific libraries to test runner
if(ROCKCHIP_MPP_LIBRARY)
    target_link_libraries(fpv-test-runner ${ROCKCHIP_MPP_LIBRARY})
endif()

if(RGA_LIBRARY)
    target_link_libraries(fpv-test-runner ${RGA_LIBRARY})
endif()

if(VCHIQ_LIBRARY)
    target_link_libraries(fpv-test-runner ${VCHIQ_LIBRARY})
endif()

if(MMAL_LIBRARY)
    target_link_libraries(fpv-test-runner ${MMAL_LIBRARY})
endif()

# Platform-specific optimizations
if(TARGET_ARCH STREQUAL "arm64")
    target_compile_options(fpv-streamer PRIVATE -march=native -mtune=native)
elseif(TARGET_ARCH STREQUAL "arm")
    target_compile_options(fpv-streamer PRIVATE -march=armv7-a -mfpu=neon -mfloat-abi=hard)
endif()

# Binary size optimization
set_target_properties(fpv-streamer PROPERTIES
    CMAKE_INTERPROCEDURAL_OPTIMIZATION ON
    COMPILE_FLAGS "-flto"
    LINK_FLAGS "-flto -Wl,--gc-sections"
)

install(TARGETS fpv-streamer fpv-test-runner DESTINATION bin)