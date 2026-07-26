# Buildroot Integration Guide for FPV Streamer

This guide explains how to integrate FPV Streamer into your Buildroot project using the provided configuration files.

## Directory Structure

```
fpv-streamer/
├── buildroot/
│   ├── Config.in          # Buildroot package configuration
│   └── Makefile          # Package build script
├── cmake/
│   └── arm-toolchain.cmake # Cross-compilation toolchain
├── build.sh              # Enhanced build script with Buildroot support
└── src/                  # Source code
```

## Integration Steps

### 1. Copy Package Files to Buildroot

Copy the `buildroot/` directory to your Buildroot project:

```bash
# Copy to your Buildroot directory
cp -r fpv-streamer/buildroot /path/to/buildroot/package/fpv-streamer
```

### 2. Add Package to Buildroot Configuration

Add the following to your Buildroot `Config.in` file:

```makefile
source "package/fpv-streamer/Config.in"
```

### 3. Configure Buildroot

Run `make menuconfig` and select FPV Streamer:

```
Target packages  --->
    Multimedia  --->
        [*] fpv-streamer  --->
            [*]   Enable debug mode
            [*]   Enable hardware encoding support
            [ ]   Enable object detection
            [*]   Enable web interface
```

### 4. Add Dependencies

Ensure these packages are enabled in your Buildroot configuration:

```
- ffmpeg
- json-c
- libv4l2
- cmake (for native builds)
```

### 5. Build the System

```bash
# Build the entire system
make fpv-streamer-dirclean
make fpv-streamer

# Or build everything
make all
```

## Cross-Compilation with Custom Toolchain

### Using the Enhanced build.sh Script

```bash
# Build with Buildroot toolchain
./build.sh --buildroot --buildroot-tc-dir /path/to/buildroot/output/host/arm-buildroot-linux-gnueabihf

# With custom options
./build.sh --buildroot --buildroot-tc-dir /path/to/buildroot/output \
    --enable-object-detection --debug
```

### Manual CMake Configuration

```bash
# Create build directory
mkdir -p build
cd build

# Configure with Buildroot toolchain
cmake .. \
    -DCMAKE_TOOLCHAIN_FILE=../cmake/arm-toolchain.cmake \
    -DBUILDROOT_TC_DIR=/path/to/buildroot/output/host/arm-buildroot-linux-gnueabihf \
    -DCMAKE_BUILD_TYPE=Release \
    -DENABLE_HARDWARE_ENCODER=ON \
    -DENABLE_OBJECT_DETECTION=OFF \
    -DENABLE_WEB_INTERFACE=ON

# Build
make -j$(nproc)
```

## Platform-Specific Notes

### Radxa Rock Pi 4b+
- Enable Rockchip MPP encoder support
- Requires `librockchip-mpp` package in Buildroot

### Radxa Cubie a5a/a7a
- Uses Allwinner hardware encoder
- Enable `sunxi-tools` package in Buildroot

### SigmaStar SSC338Q
- Specialized vision processing unit
- May require custom VPE encoder integration

### mstar SSR621Q
- Embedded multimedia processor
- Check for platform-specific encoder libraries

## Hardware Encoder Support

To enable hardware encoding, ensure the following packages are available:

```makefile
# For Raspberry Pi (if using compatible hardware)
BR2_PACKAGE_RASPBERRYPI_USERLAND = y
BR2_PACKAGE_MMAL_UTIL = y

# For Rockchip platforms
BR2_PACKAGE_LIBROCKCHIP_MPP = y

# For Allwinner platforms
BR2_PACKAGE_SUNXI_TOOLS = y
```

## Configuration Files

### Buildroot Config.in Options

```makefile
config BR2_PACKAGE_FPV_STREAMER_DEBUG
    bool "Enable debug mode"
    default n
    help
      Enable debug logging and symbols.
      This increases binary size but provides
      better debugging capabilities.

config BR2_PACKAGE_FPV_STREAMER_HARDWARE_ENCODER
    bool "Enable hardware encoding support"
    default y
    help
      Enable hardware video encoding acceleration
      for supported ARM platforms.

config BR2_PACKAGE_FPV_STREAMER_OBJECT_DETECTION
    bool "Enable object detection"
    default n
    help
      Enable motion and object detection using OpenCV.
      Requires significant additional CPU resources.

config BR2_PACKAGE_FPV_STREAMER_WEB_INTERFACE
    bool "Enable web interface"
    default y
    help
      Enable HTTP web interface for configuration
      and monitoring.
```

## Binary Size Optimization

Buildroot provides several size optimization options:

### Compiler Optimization Flags

```makefile
# Enable in package Makefile
FPV_STREAMER_CONF_OPTS += CFLAGS="-Os -ffunction-sections -fdata-sections"
FPV_STREAMER_CONF_OPTS += LDFLAGS="-Wl,--gc-sections -Wl,--strip-all"
```

### Build Type

```bash
# Use Release build for smaller binaries
-DCMAKE_BUILD_TYPE=Release

# For development, use Debug
-DCMAKE_BUILD_TYPE=Debug
```

## Troubleshooting

### Build Errors

1. **Missing dependencies**: Ensure all required packages are enabled
2. **Toolchain issues**: Verify Buildroot toolchain path is correct
3. **Library not found**: Check pkg-config files are installed

### Runtime Errors

1. **Permission denied**: Ensure `/dev/video0` is accessible
2. **Hardware encoder not found**: Check if required libraries are present
3. **Web interface not accessible**: Verify port 8080 is not blocked

### Performance Issues

1. **High CPU usage**: Disable object detection if not needed
2. **Video stuttering**: Check hardware encoder support
3. **Web interface slow**: Reduce update frequency or disable statistics

## Development Workflow

### Local Development

```bash
# Build locally for testing
./build.sh

# Test on target hardware
scp build/fpv-streamer user@target:/tmp/
ssh user@target "/tmp/fpv-streamer --device /dev/video0 --port 8080"
```

### Buildroot Development

```bash
# Clean and rebuild
make fpv-streamer-dirclean
make fpv-streamer

# Rebuild only the package
make fpv-streamer-rebuild
```

## Advanced Configuration

### Custom Buildroot Overlay

Create a `fpv-streamer-overlay` directory with:

```
fpv-streamer-overlay/
├── etc/
│   └── init.d/
│       └── S99fpv-streamer  # Startup script
└── usr/
    └── bin/
        └── fpv-streamer     # Symlink to binary
```

### Systemd Integration

For systemd-based Buildroot systems:

```ini
# /etc/systemd/system/fpv-streamer.service
[Unit]
Description=FPV Streamer Video Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/fpv-streamer --device /dev/video0 --port 8080
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
```

## Support and Contributing

For issues and contributions:

1. Check Buildroot logs for compilation errors
2. Verify hardware platform compatibility
3. Test with minimal configuration first
4. Report issues with full build configuration

## License

FPV Streamer is released under the MIT License. See LICENSE file for details.