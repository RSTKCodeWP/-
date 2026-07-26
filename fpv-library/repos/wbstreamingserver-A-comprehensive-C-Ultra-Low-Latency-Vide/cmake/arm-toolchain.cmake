# ARM toolchain file for Buildroot cross-compilation
# This file is used by CMake to configure cross-compilation settings

set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)

# Detect Buildroot toolchain
if(NOT BUILDROOT_TC_DIR)
    # Try to auto-detect from environment
    if(DEFINED ENV{BUILDROOT_TC_DIR})
        set(BUILDROOT_TC_DIR $ENV{BUILDROOT_TC_DIR})
    elseif(DEFINED ENV{CROSS_COMPILE})
        set(BUILDROOT_TC_DIR $(shell dirname $(shell dirname $(CROSS_COMPILE))))
    endif()
endif()

# Cross-compiler settings
set(CMAKE_C_COMPILER ${BUILDROOT_TC_DIR}/usr/bin/arm-linux-gnueabihf-gcc)
set(CMAKE_CXX_COMPILER ${BUILDROOT_TC_DIR}/usr/bin/arm-linux-gnueabihf-g++)
set(CMAKE_AR ${BUILDROOT_TC_DIR}/usr/bin/arm-linux-gnueabihf-ar)
set(CMAKE_RANLIB ${BUILDROOT_TC_DIR}/usr/bin/arm-linux-gnueabihf-ranlib)
set(CMAKE_STRIP ${BUILDROOT_TC_DIR}/usr/bin/arm-linux-gnueabihf-strip)

# Target system root for libraries and headers
set(CMAKE_FIND_ROOT_PATH ${BUILDROOT_TC_DIR}/usr)

# Search for programs and libraries in the target filesystem
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)

# Compiler flags for ARM
set(CMAKE_C_FLAGS "-mcpu=cortex-a7 -mfpu=neon -mfloat-abi=hard -O2 -pipe")
set(CMAKE_CXX_FLAGS "-mcpu=cortex-a7 -mfpu=neon -mfloat-abi=hard -O2 -pipe")

# Linker flags
set(CMAKE_EXE_LINKER_FLAGS "-mcpu=cortex-a7 -mfpu=neon -mfloat-abi=hard")

# This caches the knowledge that we are cross-compiling
set(CMAKE_CROSSCOMPILING TRUE)

message(STATUS "Cross-compilation using toolchain from: ${BUILDROOT_TC_DIR}")
message(STATUS "C compiler: ${CMAKE_C_COMPILER}")
message(STATUS "CXX compiler: ${CMAKE_CXX_COMPILER}")