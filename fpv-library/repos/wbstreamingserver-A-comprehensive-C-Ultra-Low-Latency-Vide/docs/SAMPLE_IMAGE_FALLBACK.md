# FPV Streamer - Sample Image Fallback System

The FPV Streamer now includes a comprehensive sample image fallback system that allows the server to start and function even when camera hardware is not available. This feature is particularly useful for:

- **Development and Testing**: Run the server without physical cameras
- **GUI Testing**: Test alignment processes and other dependent functionality
- **Demo and Presentation**: Show the system's capabilities when cameras are not accessible
- **Graceful Degradation**: Continue operation even when cameras fail

## Sample Image Organization

The system uses a structured directory layout for sample images:

```
samples/
├── camera1/          # Primary camera fallback images
│   ├── fpv_scene_primary.jpg
│   ├── checkerboard.jpg
│   ├── radial_gradient.jpg
│   ├── real_aerial_view.jpg
│   └── fpv_aerial_view.jpg
├── camera2/          # Secondary camera fallback images  
│   ├── fpv_scene_stereo.jpg
│   ├── checkerboard_fine.jpg
│   ├── diagonal_gradient.jpg
│   ├── real_side_view.jpg
│   └── fpv_side_view.jpg
└── calibration/      # Calibration and test patterns
    ├── grid_pattern_100px.jpg
    ├── grid_pattern_50px.jpg
    ├── color_bars.jpg
    └── test_pattern.jpeg
```

## Automatic Fallback Behavior

When cameras are not available, the system:

1. **Detects Missing Cameras**: Checks for device availability at startup
2. **Loads Sample Images**: Automatically loads appropriate sample images
3. **Continues Operation**: Maintains full functionality using sample data
4. **Provides Status Information**: Reports fallback mode in logs and status

## Usage Examples

### Running with Sample Images

```bash
# Single camera mode with sample images
./fpv-streamer --device /dev/video999 --port 8080

# Dual camera mode (will use samples if cameras unavailable)
./fpv-streamer --enable-dual-camera --camera2-device /dev/video2

# Custom sample image directory
./fpv-streamer --device /dev/video999 --sample-dir ./my_samples
```

### Fallback Status Indicators

The system provides clear indicators when using sample images:

- **Log Messages**: "Using sample images fallback" appears in console logs
- **Status Output**: Status endpoint shows camera availability
- **Frame Generation**: Continuous frame generation using sample images

## Sample Image Types

### Camera 1 Samples
- **FPV Scene**: Realistic FPV aerial view for primary camera testing
- **Test Patterns**: Checkerboards and gradients for calibration
- **Real Images**: High-quality FPV footage for realistic testing

### Camera 2 Samples  
- **Stereo Scene**: Images with stereo calibration markers
- **Fine Patterns**: High-resolution patterns for dual camera testing
- **Depth Indicators**: Visual markers for stereo alignment

### Calibration Samples
- **Grid Patterns**: Various grid spacings for lens correction
- **Color Bars**: SMPTE color bars for color calibration
- **Test Patterns**: Standard camera calibration patterns

## Synthetic Image Generation

If sample images are not found, the system automatically generates synthetic test patterns:

```cpp
// Example of automatically generated test pattern
cv::Mat test_pattern(height, width, CV_8UC3, cv::Scalar(100, 150, 200));

// Adds timestamp and test elements for dynamic content
auto now = std::chrono::system_clock::now();
// Pattern includes time-based elements for dynamic testing
```

## Configuration Options

### Enable Sample Image Fallback

The fallback system can be configured through:

```cpp
// In VideoCapture class
camera->set_use_sample_images(true);

// Automatic detection (default)
camera->set_use_sample_images(false); // Auto-detect
```

### Sample Image Selection

The system cycles through available sample images automatically:

```cpp
// Cycles through images for dynamic content
std::string image_path = sample_image_paths_[current_sample_index_ % sample_image_paths_.size()];
current_sample_index_++;
```

## Technical Implementation

### Detection Logic

```cpp
bool VideoCapture::initialize() {
    device_path_ = config_.device_path;
    
    // Try to open the device first
    if (!open_device()) {
        Logger::warn("Cannot open video device, trying fallback to sample images");
        
        // Try to load sample images as fallback
        if (load_sample_images()) {
            use_sample_images_.store(true);
            Logger::info("Using sample images fallback - device: " + device_path_);
            return true;
        }
    }
    // ... normal camera initialization
}
```

### Frame Generation

```cpp
std::unique_ptr<VideoFrame> VideoCapture::create_sample_frame() {
    // Load and process sample images
    cv::Mat image = cv::imread(image_path, cv::IMREAD_COLOR);
    cv::resize(image, resized, cv::Size(actual_width_, actual_height_));
    
    // Convert to VideoFrame format (YUV420)
    // ... conversion logic
    
    return frame;
}
```

## Benefits

1. **Reliability**: Server continues operation without cameras
2. **Testing**: Comprehensive testing without hardware dependencies  
3. **Development**: Easy development and debugging environment
4. **User Experience**: Graceful degradation when cameras fail
5. **Demos**: Professional demonstrations without complex setup

## Integration Notes

- **No Configuration Required**: Fallback activates automatically
- **Seamless Transition**: Switches between real and sample images transparently
- **Performance**: Minimal overhead when using sample images
- **Compatibility**: Works with all existing features and configurations

The sample image fallback system ensures that FPV Streamer remains fully functional and testable in any environment, making it ideal for development, testing, and demonstration purposes.