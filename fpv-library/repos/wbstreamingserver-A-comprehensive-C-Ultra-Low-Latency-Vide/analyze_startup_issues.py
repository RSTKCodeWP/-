#!/usr/bin/env python3
"""
Simple test to understand the startup issues without needing executables
"""
import os
import shutil

def create_test_executables():
    """Create minimal test executables to simulate the issue"""
    
    # Create a minimal C++ test program that simulates the startup behavior
    test_cpp = """
#include <iostream>
#include <chrono>
#include <thread>

int main(int argc, char* argv[]) {
    std::cout << "Test executable started" << std::endl;
    
    if (argc > 1 && std::string(argv[1]) == "--help") {
        std::cout << "Test executable help" << std::endl;
        return 0;
    }
    
    // Simulate startup that tries to access /dev/video0
    std::cout << "Attempting to access /dev/video0..." << std::endl;
    
    FILE* device = fopen("/dev/video0", "rb");
    if (!device) {
        std::cout << "Cannot access /dev/video0, entering sample mode..." << std::endl;
        
        // Check if sample images exist
        if (os.path.exists("samples/camera1") && os.listdir("samples/camera1")) {
            std::cout << "Sample images found, using fallback mode" << std::endl;
        } else {
            std::cout << "No sample images found!" << std::endl;
            return 1;
        }
    } else {
        std::cout << "Successfully opened video device" << std::endl;
        fclose(device);
    }
    
    // Simulate running
    std::cout << "Running... (press Ctrl+C to stop)" << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(10));
    
    return 0;
}
"""
    
    with open("test_startup.cpp", "w") as f:
        f.write(test_cpp)
    
    print("Created test_startup.cpp")
    return True

def test_sample_image_access():
    """Test sample image accessibility"""
    print("=== Testing Sample Image Access ===")
    
    # Test the sample image loading logic
    sample_dirs = {
        "camera1": "samples/camera1",
        "camera2": "samples/camera2"
    }
    
    for camera, dir_path in sample_dirs.items():
        if os.path.exists(dir_path):
            files = [f for f in os.listdir(dir_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
            print(f"✓ {camera} ({dir_path}): {len(files)} image files")
            
            # Test reading first file
            if files:
                first_file = os.path.join(dir_path, files[0])
                try:
                    with open(first_file, 'rb') as f:
                        data = f.read(100)
                        print(f"  ✓ Can read {files[0]} ({len(data)} bytes read)")
                except Exception as e:
                    print(f"  ✗ Cannot read {files[0]}: {e}")
        else:
            print(f"✗ {camera} ({dir_path}): Directory not found")
    
    print()

def simulate_device_access():
    """Simulate the device access logic"""
    print("=== Simulating Device Access Logic ===")
    
    video_devices = ["/dev/video0", "/dev/video1", "/dev/video2", "/dev/video3"]
    
    for device in video_devices:
        if os.path.exists(device):
            print(f"✓ Device {device} exists")
            
            # Try to open it
            try:
                with open(device, 'rb') as f:
                    data = os.read(f.fileno(), 10)
                    print(f"  ✓ Can read from {device} ({len(data)} bytes)")
            except PermissionError:
                print(f"  ⚠ {device}: Permission denied")
            except Exception as e:
                print(f"  ✗ {device}: Error - {e}")
        else:
            print(f"✗ Device {device} not found")
            # This should trigger fallback to sample images
            print(f"  → Should fall back to sample images for this device")
    
    print()

def analyze_sample_fallback_logic():
    """Analyze the sample image fallback logic"""
    print("=== Analyzing Sample Fallback Logic ===")
    
    # Check if the fallback directories match the expected pattern
    fallback_dirs = {
        "/dev/video0": "samples/camera1",
        "/dev/video1": "samples/camera1", 
        "/dev/video2": "samples/camera2",
        "/dev/video3": "samples/camera2",
        "camera1": "samples/camera1",
        "camera2": "samples/camera2"
    }
    
    for device, expected_dir in fallback_dirs.items():
        if os.path.exists(expected_dir):
            files = [f for f in os.listdir(expected_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
            print(f"✓ {device} → {expected_dir}: {len(files)} files")
            
            if len(files) == 0:
                print(f"  ⚠ WARNING: No images found in {expected_dir}")
        else:
            print(f"✗ {device} → {expected_dir}: Directory not found")
    
    print()

def main():
    print("FPV Streamer Startup Issue Analysis")
    print("=" * 50)
    print()
    
    print("This tool analyzes the startup issues without needing working executables.")
    print("It focuses on the sample image fallback logic and device access patterns.")
    print()
    
    test_sample_image_access()
    simulate_device_access()
    analyze_sample_fallback_logic()
    
    print("=== Analysis Summary ===")
    print()
    print("Based on the analysis above, the main issues are likely:")
    print()
    print("1. MISSING SAMPLE IMAGES: If sample image directories are empty or inaccessible")
    print("2. DEVICE LOCKING: If processes don't properly release device handles")
    print("3. FALLBACK LOGIC: If the sample image loading logic has bugs")
    print()
    print("The key problems mentioned by the user:")
    print("- Server starting without sample images → Check sample image loading")
    print("- Test runner locking devices → Check cleanup and signal handling")

if __name__ == "__main__":
    main()