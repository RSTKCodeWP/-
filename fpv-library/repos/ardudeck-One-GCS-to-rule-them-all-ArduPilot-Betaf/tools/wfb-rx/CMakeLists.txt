# ardudeck-wfb-rx - headless wfb-ng receiver sidecar for ArduDeck.
#
# Vendors the radio stack from OpenIPC Aviateur (src/wifi, 3rd/devourer) and
# replaces its GUI singleton with a terminal shim (src/gui_interface.h).
# Mirrors Aviateur's build flags for those sources; no GUI, no player, no
# video decode - output is RTP over UDP for ArduDeck's media engine.
#
# Build:
#   cmake -B build -DCMAKE_BUILD_TYPE=Release
#   cmake --build build -j8
# Deps (macOS): brew install cmake libusb libsodium
# Deps (Linux): libusb-1.0-0-dev libsodium-dev libpcap-dev
# Windows: vcpkg libusb + libsodium (mirrors Aviateur's setup).

cmake_minimum_required(VERSION 3.18)

if (WIN32)
    set(CMAKE_TOOLCHAIN_FILE "$ENV{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake")
endif ()

project(ardudeck-wfb-rx
        VERSION 0.1.0
        LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_INCLUDE_CURRENT_DIR ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

find_package(PkgConfig REQUIRED)

if (WIN32)
    pkg_check_modules(LIBUSB REQUIRED IMPORTED_TARGET libusb-1.0)
    find_package(unofficial-sodium CONFIG REQUIRED)
else ()
    pkg_check_modules(LIBSODIUM REQUIRED IMPORTED_TARGET libsodium)
endif ()

add_executable(${PROJECT_NAME}
        src/main.cpp
        src/gui_interface.h
)

# The vendored wifi CMakeLists attaches its sources to ${PROJECT_NAME}.
add_subdirectory(src/wifi)

# SIMD FEC flags, mirrored from Aviateur.
target_compile_definitions(${PROJECT_NAME} PRIVATE
        ZFEX_UNROLL_ADDMUL_SIMD=8
        ZFEX_USE_INTEL_SSSE3
        ZFEX_USE_ARM_NEON
        ZFEX_INLINE_ADDMUL
        ZFEX_INLINE_ADDMUL_SIMD
)

add_subdirectory(3rd/devourer)
target_include_directories(${PROJECT_NAME} PRIVATE
        "src"
        "3rd/devourer/src"
        "3rd/devourer/hal"
        "src/wifi/wfb-ng/include"
)

if (WIN32)
    string(APPEND CMAKE_CXX_FLAGS " /utf-8")
    target_link_libraries(${PROJECT_NAME} PRIVATE
            PkgConfig::LIBUSB
            unofficial-sodium::sodium
            WiFiDriver
    )
else ()
    target_link_libraries(${PROJECT_NAME} PRIVATE
            PkgConfig::LIBSODIUM
            WiFiDriver
            pcap
    )
endif ()
