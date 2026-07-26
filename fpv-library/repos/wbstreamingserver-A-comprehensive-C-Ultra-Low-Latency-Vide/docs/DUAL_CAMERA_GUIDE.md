# Dual Camera 3D Streaming System

## Overview

The FPV Streamer has been enhanced with dual camera support and 3D stereo compositing capabilities. This allows users to combine two camera feeds into a single stereoscopic image for 3D FPV goggles.

## Key Features

### Dual Camera Support
- **Two Camera Input**: Supports simultaneous capture from `/dev/video0` and `/dev/video2` (configurable)
- **Sample Image Fallback**: Automatic fallback to stereo sample images when cameras unavailable
- **Frame Synchronization**: Optional frame sync to ensure temporal alignment
- **Format Flexibility**: Each camera can use different input formats (MJPEG, H.264, RAW)
- **Robust Configuration**: Enhanced error handling and graceful degradation

### Stereo 3D Compositing
- **Multiple Stereo Modes**:
  - Side-by-Side (horizontal)
  - Top-Bottom (vertical) 
  - Over-Under (optimized for FPV)
- **Alignment Controls**:
  - Horizontal/Vertical offset adjustment
  - Zoom factor control
  - Convergence adjustment for 3D depth
  - Camera separation configuration (40-80mm)
- **Color Correction**: Automatic brightness/contrast matching between cameras
- **Flip Options**: Individual camera flipping for hardware mounting variations

### Performance Optimization
- **Low Latency**: Target <40ms end-to-end latency
- **Frame Rate**: Up to 30fps dual camera on most hardware, 60fps on high-end systems
- **Memory Efficient**: Optimized frame buffering and processing
- **Real-time Monitoring**: Live latency and performance tracking

### Configuration Management
- **Web Interface**: Real-time configuration through browser
- **Persistent Settings**: User adjustments saved and restored
- **Multiple Profiles**: Easy switching between different setups

## Hardware Requirements

### Supported Cameras
- **USB UVC Cameras**: Any V4L2-compatible dual-lens or two separate cameras
- **Recommended**: Dual-lens cameras with synchronized capture
- **Minimum**: 720p @ 30fps per camera
- **Optimal**: 1080p @ 60fps per camera

### System Requirements
- **ARM SBC**: Radxa Rock Pi 4b+, Cubie a5a/a7a, SigmaStar SSC338Q, mstar SSR621Q
- **RAM**: 1GB minimum, 2GB recommended
- **Storage**: 100MB for application + logs
- **Performance**: Multi-core ARM processor recommended for dual processing

### Camera Setup
1. **Camera 1**: Connect to `/dev/video0`
2. **Camera 2**: Connect to `/dev/video2` (or `/dev/video4`, `/dev/video6`)
3. **Power**: Ensure adequate USB power for dual cameras
4. **Synchronization**: Use dual-lens cameras for best sync, or enable software frame sync

## Configuration Guide

### Web Interface Configuration

Navigate to `http://[device-ip]:8080` and configure:

#### Stereo 3D Settings
1. **Enable Stereo Mode**: Set to "Enabled"
2. **Camera 2 Device**: Select appropriate `/dev/videoX` device
3. **Stereo Mode**: Choose side-by-side for FPV goggles
4. **Camera Separation**: Set to 63mm (human eye average) or match your camera spacing
5. **Alignment Controls**: Use sliders for fine-tuning:
   - **Convergence**: Adjust 3D depth perception
   - **Horizontal/Vertical Offset**: Align image boundaries
   - **Zoom**: Match camera focal lengths
6. **Color Correction**: Enable for better color matching

#### Fine-tuning for 3D Goggles
1. **Start with convergence = 0**
2. **Adjust horizontal offset** to align left/right edges
3. **Use convergence** to control 3D depth:
   - Positive values: Bring objects closer
   - Negative values: Push objects farther away
4. **Test with known 3D content** to validate setup

### Command Line Configuration

```bash
# Run with dual camera configuration
./fpv-streamer --device /dev/video0 --camera2-device /dev/video2

# Enable stereo mode
./fpv-streamer --stereo-enabled true --stereo-mode 0

# Run test suite
./fpv-test-runner --quick  # 10-second test
./fpv-test-runner --extended  # Full test suite
```

## Performance Testing

### Latency Testing

### Latency Requirements
- **Target**: <50ms end-to-end latency (typical FPV requirement)
- **Measurement**: Camera capture → Compositing → Transmission
- **Monitoring**: Real-time latency display in web interface

### Test Suite
Run comprehensive tests with:
```bash
# Quick functionality test (10 seconds)
./fpv-test-runner --quick

# Full performance test (30+ seconds)
./fpv-test-runner

# Extended test with detailed logging
./fpv-test-runner --verbose --extended

# Real-time monitoring mode
./fpv-test-runner --monitor
```

### Test Results Interpretation
```
=== TEST SUMMARY ===
Dual Camera: PASS
Stereo Compositing: PASS  
Latency Requirement: PASS
Average Latency: 32.8ms
Frames Under 50ms: 2876/2880
🎉 ALL TESTS PASSED! System is ready for dual camera 3D streaming.
```

## Troubleshooting

### Common Issues

#### Cameras Not Detected
- **Check device paths**: Verify `/dev/video0` and `/dev/video2` exist
- **Permissions**: Ensure user has access to video devices
- **USB Power**: Verify adequate power for dual cameras

#### Poor 3D Effect
- **Alignment**: Adjust horizontal/vertical offsets
- **Convergence**: Fine-tune depth perception
- **Color Correction**: Enable for color matching
- **Flip Mode**: Try different flipping options

#### High Latency
- **Resolution**: Lower resolution if needed
- **Frame Rate**: Reduce FPS targets
- **Format**: Try different input formats
- **Hardware**: Check CPU usage and thermal throttling

#### Frame Synchronization Issues
- **Enable Frame Sync**: Turn on software frame sync
- **Timeout**: Increase sync timeout if needed
- **Hardware**: Consider dual-lens cameras for better sync

### Performance Optimization

#### For Low-Latency FPV
1. **Minimize Resolution**: Use 720p instead of 1080p
2. **Optimize Encoder**: Use hardware H.264 if available
3. **Disable Features**: Turn off unnecessary processing
4. **USB Configuration**: Ensure USB 3.0 if available

#### For High Quality
1. **Full Resolution**: Use maximum supported resolution
2. **Higher FPS**: Target 60fps if hardware permits
3. **Quality Settings**: Increase encoder quality
4. **Color Correction**: Enable for professional look

## Technical Details

### Stereo Compositing Pipeline
```
Camera 1 (Left)  →  Frame Processing  →  ┐
                                      →  →  Stereo Composer  →  Output Stream
Camera 2 (Right) →  Frame Processing  →  ┘
```

### Frame Synchronization
- **Timestamp-based**: Synchronize frames by capture timestamp
- **Timeout handling**: Configurable sync timeout (default 100ms)
- **Fallback**: Continue with best-effort sync if perfect sync unavailable

### Memory Management
- **Double Buffering**: Separate buffers for each camera
- **Zero-Copy**: Minimize data copying between stages
- **Garbage Collection**: Automatic cleanup of frame buffers

## File Structure

```
src/
├── video/
│   ├── capture.h/cpp          # Dual camera capture
│   ├── stereo_compositor.h/cpp # 3D image compositing
│   └── encoder.h/cpp          # Video encoding
├── testing/
│   ├── latency_tester.h/cpp   # Performance testing
│   └── test_runner.cpp        # Test harness
├── web/
│   └── web_interface.cpp      # Web UI with stereo controls
└── config/
    └── config_manager.h/cpp   # Configuration management
```

## Build Instructions

### Standard Build
```bash
mkdir build && cd build
cmake ..
make
```

### Cross-Compilation (Buildroot)
```bash
cmake .. -DBUILDROOT_TC_DIR=/path/to/buildroot/toolchain
make
```

### Dependencies Required
- **V4L2**: Video4Linux2 for camera access
- **FFmpeg**: Video encoding/decoding
- **OpenCV**: Image processing for stereo compositing
- **JSON-C**: Configuration file parsing

## API Reference

### Stereo Configuration JSON
```json
{
  "stereoEnabled": true,
  "stereoCamera2Device": 2,
  "stereoMode": 0,
  "stereoSeparation": 63,
  "stereoConvergence": 0,
  "stereoOffsetX": 0,
  "stereoOffsetY": 0,
  "stereoZoom": 1.0,
  "stereoFlipMode": 0,
  "stereoColorCorrection": true,
  "stereoColorStrength": 80
}
```

### Real-time Metrics
The system provides real-time metrics via the web interface:
- **Capture Latency**: Camera to frame buffer time
- **Processing Latency**: Stereo compositing time  
- **Total Latency**: End-to-end processing time
- **Frame Rate**: Actual FPS being achieved
- **Dropped Frames**: Lost frames count

## Support and Development

### Getting Help
1. **Check Logs**: Review system logs for error messages
2. **Run Tests**: Execute test suite to identify issues
3. **Monitor Performance**: Use built-in performance monitoring
4. **Configuration**: Verify all settings are appropriate for hardware

### Contributing
- **Code Style**: Follow existing C++17 standards
- **Documentation**: Update this guide for new features
- **Testing**: Add comprehensive tests for new functionality
- **Performance**: Maintain <50ms latency target

---

*This dual camera 3D system is designed for low-latency FPV applications. For best results, use synchronized dual-lens cameras and ensure adequate hardware performance.*