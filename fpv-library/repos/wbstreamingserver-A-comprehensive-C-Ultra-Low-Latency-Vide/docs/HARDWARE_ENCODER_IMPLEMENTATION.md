# Hardware Encoder Implementation for Rock Pi 4b+

## Overview
This implementation adds hardware encoder support for Rock Pi 4b+ with Rockchip RGA, V4L2 encoder detection, and Rockchip MPP library integration.

## Key Features Implemented

### 1. Enhanced Hardware Detection
- **Rockchip Device Detection**: Scans `/dev/video10-19` for potential encoder devices
- **RGA (Rockchip GPU) Detection**: Detects `/dev/rga` and `/dev/rga2` devices
- **Rockchip MPP Library**: Detects `librk_mpi.so` and `librockchip-mpp.so`
- **Capability Querying**: Uses V4L2 ioctl calls to query device capabilities
- **Multiple Fallback Support**: Tries multiple hardware acceleration methods in priority order

### 2. V4L2 Encoder Implementation
- **Proper V4L2 Buffer Management**: Implements VIDIOC_QBUF and VIDIOC_DQBUF for frame queuing
- **Hardware Capability Detection**: Queries V4L2 devices for encoding capabilities
- **Error Handling**: Robust error handling with proper logging
- **Context Management**: V4L2EncoderContext structure for maintaining encoder state

### 3. RGA Hardware Acceleration
- **RGA Device Detection**: Automatic detection of RGA and RGA2 devices
- **Hardware Acceleration**: Placeholder for RGA-based hardware acceleration
- **Integration Ready**: Structure ready for full RGA implementation

### 4. Rockchip MPP Integration
- **Library Detection**: Dynamic library loading for Rockchip MPP
- **Header Detection**: Checks for MPP headers in multiple locations
- **Placeholder Implementation**: Framework for full MPP encoder integration

### 5. Enhanced CMake Build System
- **Rockchip MPP Detection**: Automatic detection and linking of rockchip-mpp library
- **RGA Library Detection**: Automatic detection and linking of rga library
- **Conditional Compilation**: Proper compile definitions for available hardware
- **Multiple Target Support**: Both fpv-streamer and fpv-test-runner targets updated

## File Changes

### Modified Files
1. **`src/video/encoder.cpp`**
   - Added comprehensive hardware detection methods
   - Implemented proper V4L2 encoder with buffer management
   - Added Rockchip MPP and RGA detection and initialization
   - Enhanced error handling and logging

2. **`src/video/encoder.h`**
   - Added V4L2EncoderContext structure
   - Added new methods for hardware detection and initialization
   - Updated class interface for new hardware types
   - Enhanced encoder naming to reflect hardware type

3. **`CMakeLists.txt`**
   - Added rockchip-mpp library detection
   - Added rga library detection
   - Updated library linking for hardware-specific libraries
   - Added compile-time definitions for available hardware

### New Files
1. **`test_hardware_encoder.cpp`**
   - Standalone test program for hardware detection
   - Comprehensive testing of all hardware detection methods
   - System information reporting
   - Useful for debugging and hardware validation

## Hardware Detection Priority

The implementation checks for hardware in the following order:

1. **MMAL** (Raspberry Pi)
2. **V4L2** (Generic video devices)
3. **Rockchip MPP** (Specialized hardware encoding)
4. **RGA** (Rockchip GPU acceleration)

## Usage

### Automatic Detection
The hardware encoder is automatically detected during `HardwareEncoder` initialization:

```cpp
HardwareEncoder encoder(config);
bool success = encoder.initialize(); // Automatically detects and initializes hardware
```

### Manual Hardware Testing
Run the hardware detection test program:

```bash
g++ -o test_hardware_encoder test_hardware_encoder.cpp -std=c++17
./test_hardware_encoder
```

### Build Integration
The build system automatically detects and links available hardware libraries:

```bash
# On systems with Rockchip MPP:
-- Found Rockchip MPP library: /usr/lib/librk_mpi.so
-- Compiling with: -DHAVE_ROCKCHIP_MPP

# On systems with RGA:
-- Found RGA library: /usr/lib/librga.so
-- Compiling with: -DHAVE_RGA
```

## Technical Implementation Details

### V4L2 Encoding Flow
1. **Device Detection**: Scan `/dev/video10-19` for encoder devices
2. **Capability Query**: Use `VIDIOC_QUERYCAP` to get device information
3. **Context Initialization**: Create and configure V4L2EncoderContext
4. **Frame Processing**: Queue input frames and dequeue encoded output
5. **Buffer Management**: Proper memory management for frame buffers

### Rockchip MPP Detection
1. **Header Check**: Look for `/usr/include/mpp/mpp_frame.h`
2. **Library Load**: Attempt to load `librk_mpi.so` or `librockchip-mpp.so`
3. **Symbol Verification**: Verify library symbols are available
4. **Fallback Support**: Graceful fallback if MPP is not available

### RGA Integration
1. **Device Detection**: Check for `/dev/rga` and `/dev/rga2`
2. **Device Opening**: Open device with non-blocking access
3. **Capability Reporting**: Report RGA availability in encoder name
4. **Acceleration Ready**: Framework for hardware acceleration integration

## Fallback Behavior
- If no hardware is detected, automatically falls back to software encoding
- Each hardware type has graceful degradation
- Detailed logging of detection process for troubleshooting
- Maintains compatibility with existing software encoding path

## Performance Benefits
- **Hardware Acceleration**: Leverages dedicated hardware for encoding
- **Lower CPU Usage**: Reduces CPU load for encoding operations
- **Better Power Efficiency**: Hardware encoders typically consume less power
- **Real-time Performance**: Dedicated hardware provides better real-time performance

## Compatibility
- **Backward Compatible**: Existing software encoding continues to work
- **Cross-Platform**: Works on x86_64 (fallback) and ARM (with hardware)
- **Build System**: Automatic detection works on various Linux distributions
- **Error Handling**: Robust error handling prevents crashes on missing hardware

## Testing and Validation

### Hardware Detection Test
The standalone test program validates:
- V4L2 device enumeration and capability detection
- Rockchip MPP library presence and symbols
- RGA device detection and accessibility
- System architecture and device tree compatibility

### Integration Testing
Build and test the main application:
```bash
mkdir build && cd build
cmake ..
make fpv-streamer
./fpv-streamer --help
```

## Future Enhancements
1. **Full Rockchip MPP Implementation**: Complete MPP encoder integration
2. **RGA Hardware Acceleration**: Implement RGA-based image processing
3. **Performance Optimization**: Hardware-specific optimizations
4. **Multi-stream Support**: Hardware encoding for multiple video streams
5. **Quality Control**: Hardware-specific quality and bitrate control

## Troubleshooting

### Common Issues
1. **No Hardware Detected**: Verify device permissions and driver installation
2. **Library Not Found**: Install rockchip-mpp or rga packages
3. **V4L2 Errors**: Check video device permissions and kernel support

### Debug Logging
Enable debug logging in the application:
```cpp
Logger::set_level(Logger::LEVEL_DEBUG);
```

### Hardware Validation
Use the test program to identify available hardware:
```bash
./test_hardware_encoder
```

## Implementation Status
✅ **Complete**: V4L2 encoder detection and initialization  
✅ **Complete**: Rockchip MPP library detection  
✅ **Complete**: RGA device detection  
✅ **Complete**: Enhanced CMake build system  
✅ **Complete**: Hardware detection test program  
✅ **Complete**: Documentation and examples  

## Files Modified
- `src/video/encoder.cpp` - Enhanced with hardware detection and V4L2 implementation
- `src/video/encoder.h` - Updated with new methods and structures
- `CMakeLists.txt` - Added rockchip-mpp and rga library detection
- `test_hardware_encoder.cpp` - New hardware detection test program

This implementation provides a solid foundation for hardware-accelerated encoding on Rock Pi 4b+ devices while maintaining full backward compatibility and graceful fallback behavior.