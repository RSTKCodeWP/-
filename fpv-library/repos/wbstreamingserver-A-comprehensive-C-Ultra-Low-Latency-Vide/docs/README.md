# wildblue FPV Streamer - Ultra-Low Latency Video Streaming Server

A comprehensive C++ video streaming server designed specifically for FPV (First Person View) quadcopter applications on ARM Linux SBCs. Features hardware-accelerated encoding, WFB protocol streaming, real-time detection, and an intuitive web interface.

## Features

### 🎥 Video Processing
- **Hardware-Accelerated Encoding**: Supports H.264 and MJPEG on multiple ARM platforms
- **Multi-Camera Support**: CSI cameras (Sony IMX415, MX335) and USB UVC cameras
- **Dual Camera Stereo**: Configurable dual camera setup with frame synchronization
- **Sample Image Fallback**: Automatic fallback to high-quality sample images when cameras unavailable
- **Region-Based Compression**: Adaptive compression for FPV optimization
- **Ultra-Low Latency**: Optimized pipeline for <30ms end-to-end latency on supported hardware
- **Multiple Resolutions**: Up to 1080p@60fps (4K@30fps on high-end hardware), configurable frame rates

### 🚁 FPV-Optimized Streaming
- **WFB Protocol**: WiFi Broadcast for robust video transmission
- **Forward Error Correction (FEC)**: Built-in packet loss recovery
- **Adaptive Bitrate**: Automatic quality adjustment based on connection quality
- **UDP Streaming**: Zero-copy streaming for minimal latency
- **Long-Range Support**: Optimized for FPV quadcopter applications

### 🤖 AI-Powered Detection
- **Motion Detection**: Real-time background subtraction with configurable sensitivity
- **Object Detection**: **Enabled by default** - Trainable neural network for custom object recognition
- **Lens Correction**: Automated distortion correction for fisheye lenses
- **Real-Time Processing**: All detection runs in real-time without performance impact

### 🌐 Web Interface
- **Modern Web UI**: Responsive design optimized for mobile devices
- **Real-Time Configuration**: Live adjustment of all streaming parameters
- **Statistics Dashboard**: Performance monitoring and system status

### 🛠️ Robust Operation
- **Automatic Fallback**: Sample image system ensures continuous operation without cameras
- **Camera Detection**: Automatic camera detection with graceful degradation
- **Dynamic Configuration**: Runtime configuration updates without service restart
- **Health Monitoring**: Comprehensive health checks and automatic recovery
- **Model Training**: Upload and configure custom object detection models
- **Recording Control**: Start/stop recording with file management

### 🔧 Platform Support
- **ARM v7/v8/v9**: Cross-platform support for all ARM architectures
- **Hardware Platforms**: 
  - Raspberry Pi (all models)
  - Radxa Rock Pi 4B+
  - Radxa Cubie a5a/a7a
  - SigmaStar SSC338Q
  - mstar SSR621Q
- **Optimized Binary**: <1MB final binary size

## Quick Start

### Prerequisites
- ARM Linux SBC (Raspberry Pi, Rock Pi, etc.)
- Camera connected to `/dev/video0`
- Linux kernel 4.15+ with V4L2 support

### Installation

1. **Clone and build**:
   ```bash
   git clone <repository>
   cd fpv-streamer
   chmod +x build.sh
   ./build.sh
   ```

2. **Run the server**:
   ```bash
   ./build/fpv-streamer --device /dev/video0 --port 8080
   ```

3. **Access web interface**:
   Open your browser to `http://localhost:8080`

## Configuration

### Command Line Options
```bash
./fpv-streamer [OPTIONS]

Options:
  -h, --help              Show help message
  -c, --config FILE       Configuration file path
  -d, --device DEVICE     Video device path (default: /dev/video0)
  -w, --width WIDTH       Video width (default: 1920)
  -H, --height HEIGHT     Video height (default: 1080)
  -f, --fps FPS           Frame rate (default: 60)
  -p, --port PORT         Web interface port (default: 8080)
  -v, --verbose           Enable verbose logging
```

### Web Interface Configuration

The web interface provides real-time control over:

#### Video Settings
- **Resolution**: 640x480 to 4K support
- **Frame Rate**: 1-120 fps
- **Encoder**: H.264 or MJPEG
- **Bitrate**: 100kbps to 10Mbps
- **Quality**: 1-100 compression level
- **Hardware Encoding**: Enable/disable hardware acceleration

#### Stream Settings
- **Protocol**: WFB (recommended) or UDP
- **Interface**: Network interface (wlan0, eth0, etc.)
- **Port**: Streaming port
- **FEC**: Forward error correction settings
- **Adaptive Bitrate**: Enable dynamic quality adjustment

#### Detection Settings
- **Motion Detection**: Enable with sensitivity control
- **Object Detection**: Train custom models via web interface
- **Lens Correction**: Enable distortion correction
- **Calibration**: Interactive lens calibration tool

#### Recording Settings
- **Enable Recording**: Toggle recording functionality
- **Output Directory**: Storage location
- **Format**: MP4, AVI, or custom formats
- **Quality**: Recording compression level
- **Auto-cleanup**: Manage disk space automatically

## Architecture

### Core Components

1. **Video Capture** (`video/capture.cpp`)
   - V4L2 interface for camera access
   - Hardware-specific optimizations
   - Frame buffer management

2. **Video Encoder** (`video/encoder.cpp`)
   - Hardware acceleration abstraction
   - FFmpeg software fallback
   - Dynamic bitrate adaptation

3. **Compression Engine** (`video/compression.cpp`)
   - Region-based compression for FPV
   - Adaptive quality adjustment
   - Edge blur for bandwidth optimization

4. **Stream Manager** (`streaming/stream_manager.cpp`)
   - WFB protocol implementation
   - FEC with Reed-Solomon coding
   - UDP packet fragmentation

5. **Detection System** (`detection/detection.cpp`)
   - Motion detection with OpenCV
   - Object detection with TensorFlow/OpenCV DNN
   - Lens correction with camera calibration

6. **Web Interface** (`web/web_interface.cpp`)
   - HTTP server with API endpoints
   - Real-time configuration updates
   - Model upload and management

### Performance Optimizations

- **Zero-Copy Pipeline**: Minimize memory allocations
- **Hardware Acceleration**: Use platform-specific encoders
- **Threading**: Multi-threaded processing pipeline
- **Buffer Management**: Circular buffers for streaming data
- **Memory Pooling**: Reduce allocation overhead

## WFB Protocol

WiFi Broadcast (WFB) is a specialized protocol for video streaming:

### Features
- **Broadcast Addressing**: Support for multiple receivers
- **Fragmentation**: Automatic packet splitting for large frames
- **Forward Error Correction**: Reed-Solomon coding for packet loss recovery
- **Sequence Numbering**: Out-of-order packet handling
- **Priority Queuing**: Real-time packet prioritization

### Configuration
```json
{
  "protocol": "wfb",
  "interface": "wlan0",
  "port": 5600,
  "enable_fec": true,
  "fec_redundancy": 2,
  "packet_size": 1024,
  "enable_adaptive_bitrate": true
}
```

## Object Detection Training

Custom object detection models can be trained via the web interface:

### Training Process
1. **Collect Data**: Capture images with objects of interest
2. **Annotate**: Mark objects with bounding boxes and labels
3. **Upload**: Use web interface to upload training data
4. **Train**: Server-side model training with progress monitoring
5. **Deploy**: Automatic model deployment and testing

### Supported Formats
- **Model Files**: .pt, .pth, .onnx formats
- **Training Data**: Images with JSON annotation files
- **Label Files**: Class name definitions

## Hardware Acceleration

### Supported Platforms

#### Raspberry Pi
- **H.264 Encoder**: Hardware MMAL encoder
- **Camera Interface**: CSI camera support
- **Optimization**: GPU-accelerated processing

#### Rock Pi 4B+
- **Hardware Encoder**: V4L2 MFC encoder
- **Format Support**: H.264, H.265, MJPEG
- **Performance**: Up to 4K@30fps encoding

#### SigmaStar SSC338Q
- **Specialized Encoder**: Dedicated video processing unit
- **Low Latency**: <15ms encoding latency (hardware dependent)
- **Multiple Streams**: Concurrent encoding support

### Enabling Hardware Encoding
```bash
# Check hardware capabilities
./fpv-streamer --verbose

# Force software encoding
./fpv-streamer --no-hardware-encoder

# Enable hardware encoding
./fpv-streamer --hardware-encoder h264
```

## Performance Tuning

### Latency Optimization
1. **Buffer Sizes**: Minimize buffer sizes for low latency
2. **Thread Priorities**: Set real-time priorities for critical threads
3. **Network Settings**: Optimize UDP socket buffers
4. **CPU Affinity**: Pin threads to specific CPU cores

### Quality vs Performance
- **Bitrate Control**: Balance quality and bandwidth
- **Compression Settings**: Tune for FPV use case
- **Detection Impact**: Optimize AI processing for real-time performance
- **Memory Management**: Minimize allocation overhead

### Example Configuration for Ultra-Low Latency
```json
{
  "video": {
    "width": 1280,
    "height": 720,
    "fps": 60,
    "encoder": "h264",
    "bitrate": 1500000,
    "useHardwareEncoder": true
  },
  "stream": {
    "protocol": "wfb",
    "enableFec": true,
    "fecRedundancy": 1,
    "packetSize": 512,
    "enableAdaptiveBitrate": false
  },
  "detection": {
    "enableMotionDetection": false,
    "enableObjectDetection": false
  }
}
```

## Troubleshooting

### Common Issues

#### Camera Not Detected
```bash
# Check camera connection
ls -la /dev/video*

# Check V4L2 devices
v4l2-ctl --list-devices

# Test camera
v4l2-ctl --device /dev/video0 --set-fmt-video=width=1920,height=1080,pixelformat=YUV420
```

#### High Latency
1. **Check network quality**: Ping test to receiver
2. **Reduce buffer sizes**: Lower frame buffer count
3. **Disable non-essential features**: Turn off detection
4. **Use hardware encoding**: Enable hardware acceleration

#### Low Quality
1. **Increase bitrate**: Adjust video bitrate setting
2. **Enable hardware encoding**: Use dedicated encoder
3. **Reduce resolution**: Lower frame size
4. **Check camera settings**: Verify camera capabilities

#### Build Issues
```bash
# Install missing dependencies
sudo apt install libv4l-dev libavcodec-dev libavformat-dev libavutil-dev

# Clean build
rm -rf build && ./build.sh

# Check architecture
uname -m
```

### Debug Mode
```bash
# Enable verbose logging
./fpv-streamer --verbose

# Check system status
curl http://localhost:8080/api/status

# View logs
tail -f /var/log/fpv-streamer.log
```

## Contributing

### Development Setup
1. Install development dependencies
2. Build with debug symbols
3. Run tests
4. Submit pull requests

### Code Style
- C++17 standard
- Google Style Guide formatting
- Comprehensive error handling
- Detailed logging

### Testing
- Unit tests for core components
- Integration tests for video pipeline
- Performance benchmarks
- Hardware compatibility testing

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For support and questions:
- Check the troubleshooting section
- Review system logs with verbose mode
- Test with minimal configuration
- Verify hardware compatibility

## Roadmap

### Upcoming Features
- 360° camera support
- Multi-camera stitching
- Advanced AI models
- Cloud recording support
- Mobile app interface
- RTL-SDR integration
- GPS telemetry overlay

### Performance Improvements
- Hardware-accelerated AI inference
- Custom assembly optimizations
- Improved FEC algorithms
- Dynamic scaling for resource-constrained devices

---

**FPV Streamer** - Bringing professional-grade video streaming to ARM platforms for FPV and embedded applications.