# FPV Streamer - Enhanced Features Documentation

## 🎯 New Features Added

### H.265/HEVC Encoding Support

**Enhanced Output Encoding:**
- **H.264**: Standard H.264 encoding (default)
- **H.265**: High Efficiency Video Coding (HEVC) for better compression
- **MJPEG**: Motion JPEG compression with optimization options

**H.265 Configuration:**
- **Profiles**: 
  - Main (0): Standard H.265 profile
  - Main 10 (1): 10-bit H.265 for high dynamic range
  - Main Still Picture (2): Still image compression
- **Levels**: 4.0, 4.1, 5.0, 5.1, 5.2 for different quality/compatibility requirements
- **Hardware Acceleration**: Platform-dependent H.265 encoder support

### USB UVC Camera Input Format Selection

**Flexible Input Handling:**
- **Auto-detect**: Automatic format detection from camera capabilities
- **MJPEG**: JPEG-compressed video streams from USB cameras
- **H.264**: Hardware-encoded H.264 streams from capable USB cameras
- **RAW**: Uncompressed YUV420 format

**Input Format Benefits:**
- **MJPEG Input**: Lower CPU usage for encoding, good for high FPS applications
- **H.264 Input**: Direct hardware stream, minimal processing overhead
- **RAW Input**: Maximum flexibility, full control over processing pipeline

### Enhanced MJPEG Compression

**Advanced MJPEG Settings:**
- **Quality Control**: 1-100 scale for compression quality
- **Optimization Levels**:
  - 0: None (fastest encoding)
  - 1: Basic optimization
  - 2: Good optimization (balanced)
  - 3: Maximum optimization (highest compression)

**MJPEG Advantages:**
- **Low Latency**: Minimal encoding delay
- **Simplicity**: No complex prediction algorithms
- **Universal Compatibility**: Works with all devices
- **Constant Quality**: Consistent frame quality regardless of scene complexity

## 🔧 Configuration Interface Updates

### Web Interface Enhancements

**New Configuration Fields:**

1. **Input Format Selection**
   - Auto-detect, MJPEG, H.264, RAW options
   - Automatic format negotiation with camera
   - Format validation and error handling

2. **Output Encoder Selection**
   - Dynamic encoder switching without restart
   - Encoder-specific settings panels
   - Hardware capability detection

3. **H.265 Specific Controls**
   - Profile selection dropdown
   - Level configuration (4.0-5.2)
   - Compatibility warnings for older hardware

4. **MJPEG Advanced Options**
   - Quality slider (1-100)
   - Optimization level selection
   - Real-time compression feedback

### Dynamic UI Behavior

**Smart Interface:**
- **Conditional Settings**: H.265 options show only when H.265 is selected
- **MJPEG Controls**: Appear when MJPEG output encoder is chosen
- **Real-time Updates**: Configuration changes apply immediately
- **Hardware Warnings**: Shows when selected encoder isn't available

## 🏗️ Technical Implementation

### Video Capture Enhancements

**Multi-Format Support:**
```cpp
// New input format handling methods
std::unique_ptr<VideoFrame> process_mjpeg_input(const void* buffer, size_t buffer_size);
std::unique_ptr<VideoFrame> process_h264_input(const void* buffer, size_t buffer_size);
std::unique_ptr<VideoFrame> process_raw_input(const void* buffer, size_t buffer_size);
```

**Format Auto-Detection:**
- V4L2 capability enumeration
- Camera format negotiation
- Fallback to compatible formats
- Performance optimization for selected format

### Encoder Pipeline Updates

**Software Encoder Improvements:**
- **FFmpeg Integration**: Native H.265/HEVC encoder support
- **Context Management**: Proper codec context setup for each encoder
- **Quality Settings**: Per-encoder quality and optimization control
- **Error Handling**: Graceful fallback to H.264 if H.265 unavailable

**Hardware Encoder Abstraction:**
- Platform-specific encoder detection
- H.265 hardware encoder support (where available)
- Automatic hardware/software fallback
- Performance monitoring and reporting

### Configuration Management

**Enhanced Config Structure:**
```cpp
struct VideoConfig {
    // Input format selection
    std::string input_format = "auto"; // auto, mjpeg, h264, raw
    int input_pixel_format = 0;        // V4L2 format codes
    
    // Output encoding options
    std::string output_encoder = "h264"; // h264, h265, mjpeg
    
    // H.265 specific settings
    int h265_profile = 1;              // 0=Main, 1=Main10, 2=MainStillPicture
    float h265_level = 4.0f;           // 4.0, 4.1, 5.0, 5.1, 5.2
    
    // MJPEG specific settings
    int mjpeg_quality = 80;            // 1-100 quality scale
    int mjpeg_optimization_level = 2;  // 0-3 optimization levels
};
```

## 🚀 Usage Examples

### Configuration Scenarios

**Scenario 1: High-Quality FPV Streaming**
```
Input Format: Auto-detect
Output Encoder: H.265
H.265 Profile: Main 10
H.265 Level: 5.1
Quality: 90
```
*Result: Best compression with high dynamic range support*

**Scenario 2: Ultra-Low Latency**
```
Input Format: MJPEG
Output Encoder: H.264
Quality: 80
Hardware Encoder: Enabled
```
*Result: Minimal encoding delay, good quality*

**Scenario 3: Maximum Compatibility**
```
Input Format: RAW
Output Encoder: MJPEG
MJPEG Quality: 85
MJPEG Optimization: 3
```
*Result: Universal compatibility, highest compression*

**Scenario 4: High FPS Gaming**
```
Input Format: H.264
Output Encoder: H.264
Quality: 70
Hardware Encoder: Enabled
```
*Result: Direct hardware stream pass-through*

## 📊 Performance Characteristics

### Encoding Efficiency

**H.264 vs H.265 Comparison:**
- **Compression**: H.265 provides 25-50% better compression than H.264
- **Quality**: H.265 Main 10 supports HDR and higher color depths
- **Compatibility**: H.264 has wider device support
- **Processing**: H.265 requires more CPU/GPU resources

**Input Format Impact:**
- **MJPEG Input**: Lowest encoding overhead, good for live streaming
- **H.264 Input**: Direct stream pass-through, minimal processing
- **RAW Input**: Maximum control, highest processing requirements

### Latency Analysis

**End-to-End Latency Breakdown:**
1. **Camera Capture**: 1-2ms (format dependent)
2. **Input Processing**: 0-5ms (format conversion)
3. **Encoding**: 2-10ms (encoder dependent)
4. **Network Buffering**: 1-5ms (streaming protocol)

**Optimization Tips:**
- Use hardware encoders when available
- Match input/output formats to reduce conversion
- Adjust GOP size for your latency requirements
- Enable region-based compression for FPV focus

## 🔧 Buildroot Integration

### Package Dependencies

**New Required Packages:**
```makefile
# For H.265 encoding support
BR2_PACKAGE_FFMPEG = y
BR2_PACKAGE_LIBX265 = y  # If software H.265 needed

# Enhanced video support
BR2_PACKAGE_LIBJPEG_TURBO = y  # For MJPEG optimization
BR2_PACKAGE_LIBYUV = y         # For RAW format conversion
```

### Cross-Compilation Notes

**ARM Hardware Encoder Support:**
- **Rockchip**: H.265 via RKVENC hardware encoder
- **Allwinner**: H.265 via CedarX encoder (platform dependent)
- **Generic ARM**: Software H.265 encoding with NEON optimization

**Build Configuration:**
```bash
# Enable H.265 support in Buildroot
make menuconfig
# Target packages -> Multimedia -> [*] libx265

# Cross-compile with H.265 support
./build.sh --buildroot --buildroot-tc-dir /path/to/buildroot \
    --enable-h265 --enable-mjpeg-optimization
```

## 🛠️ Troubleshooting

### Common Issues

**Issue: H.265 encoder not found**
- **Cause**: FFmpeg compiled without H.265 support
- **Solution**: Ensure libx265 is included in Buildroot configuration

**Issue: USB camera only shows MJPEG**
- **Cause**: Camera hardware limitation
- **Solution**: Use MJPEG input format, let system handle encoding

**Issue: High latency with H.265**
- **Cause**: Software encoding on ARM without hardware acceleration
- **Solution**: Fall back to H.264 or enable hardware encoder

**Issue: MJPEG quality too low**
- **Cause**: Default optimization level too aggressive
- **Solution**: Increase MJPEG quality setting or reduce optimization level

### Debug Information

**Enable Debug Logging:**
```cpp
// Add to configuration
config.debug_level = 2;  // Enable detailed logging

// Check encoder status
curl http://localhost:8080/api/status
// Look for "encoder_type", "input_format", "output_encoder"
```

## 🎯 Future Enhancements

### Planned Features

1. **AV1 Encoding**: Next-generation codec support
2. **Multi-Stream Output**: Simultaneous H.264 and H.265 streams
3. **AI-Enhanced Compression**: ML-based quality optimization
4. **HDR Support**: PQ and HLG tone mapping for H.265 Main 10
5. **Adaptive Streaming**: Dynamic format switching based on network conditions

### Contributing

The enhanced FPV Streamer is now more flexible and powerful than ever. The modular architecture makes it easy to add new encoders, input formats, and optimization features.

**Key Development Areas:**
- Hardware encoder integration for new platforms
- Advanced compression algorithms
- AI-powered quality optimization
- Multi-format streaming capabilities

---

*Enhanced by MiniMax Agent - Pushing the boundaries of AI-powered embedded video streaming solutions* 🚁✨