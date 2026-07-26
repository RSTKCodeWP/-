#!/usr/bin/env python3
"""
Debug script to test FPV Streamer startup issues
"""
import os
import subprocess
import time
import signal
import sys

def test_sample_images():
    """Test if sample images are accessible"""
    print("=== Testing Sample Images ===")
    
    sample_dirs = ["samples/camera1", "samples/camera2", "samples/calibration"]
    
    for dir_path in sample_dirs:
        if os.path.exists(dir_path):
            files = os.listdir(dir_path)
            print(f"✓ {dir_path}: {len(files)} files")
            for f in files[:3]:  # Show first 3 files
                print(f"  - {f}")
        else:
            print(f"✗ {dir_path}: Directory not found")
    
    print()

def test_video_devices():
    """Test video device availability"""
    print("=== Testing Video Devices ===")
    
    video_devices = ["/dev/video0", "/dev/video1", "/dev/video2", "/dev/video3"]
    
    for device in video_devices:
        if os.path.exists(device):
            try:
                with open(device, 'rb') as f:
                    # Try to read a few bytes to check accessibility
                    data = os.read(f.fileno(), 10)
                    print(f"✓ {device}: Accessible (read {len(data)} bytes)")
            except PermissionError:
                print(f"⚠ {device}: Permission denied")
            except Exception as e:
                print(f"✗ {device}: Error - {e}")
        else:
            print(f"✗ {device}: Not found")
    
    print()

def test_executable_startup():
    """Test executable startup behavior"""
    print("=== Testing Executable Startup ===")
    
    executable = "./build/fpv-streamer"
    
    if not os.path.exists(executable):
        print(f"✗ Executable not found: {executable}")
        return
    
    print(f"Testing {executable} startup...")
    
    try:
        # Try to start the executable
        process = subprocess.Popen(
            [executable, "--help"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit for startup
        try:
            stdout, stderr = process.communicate(timeout=5)
            print(f"Exit code: {process.returncode}")
            if stdout:
                print("STDOUT:")
                print(stdout[:500] + "..." if len(stdout) > 500 else stdout)
            if stderr:
                print("STDERR:")
                print(stderr[:500] + "..." if len(stderr) > 500 else stderr)
        except subprocess.TimeoutExpired:
            print("Process timed out")
            process.kill()
            stdout, stderr = process.communicate()
            if stdout:
                print("STDOUT:")
                print(stdout[:500] + "..." if len(stdout) > 500 else stdout)
            if stderr:
                print("STDERR:")
                print(stderr[:500] + "..." if len(stderr) > 500 else stderr)
            
    except Exception as e:
        print(f"✗ Failed to start executable: {e}")
    
    print()

def test_fpv_test_runner():
    """Test fpv-test-runner startup and cancellation"""
    print("=== Testing fpv-test-runner ===")
    
    executable = "./build/fpv-test-runner"
    
    if not os.path.exists(executable):
        print(f"✗ Test runner not found: {executable}")
        return
    
    print(f"Testing {executable} startup and cancellation...")
    
    try:
        # Start the test runner
        process = subprocess.Popen(
            [executable, "--quick"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("Started test runner, waiting 3 seconds before sending SIGINT...")
        time.sleep(3)
        
        # Send SIGINT (Ctrl+C)
        print("Sending SIGINT...")
        process.send_signal(signal.SIGINT)
        
        # Wait for graceful shutdown
        try:
            stdout, stderr = process.communicate(timeout=5)
            print(f"Exit code: {process.returncode}")
            if stdout:
                print("STDOUT:")
                print(stdout[:500] + "..." if len(stdout) > 500 else stdout)
            if stderr:
                print("STDERR:")
                print(stderr[:500] + "..." if len(stderr) > 500 else stderr)
                
            # Check if process shut down gracefully
            if process.returncode == 0:
                print("✓ Test runner shut down gracefully")
            else:
                print(f"⚠ Test runner exited with code {process.returncode}")
                
        except subprocess.TimeoutExpired:
            print("✗ Test runner did not respond to SIGINT within 5 seconds")
            process.kill()
            print("Process killed (not graceful)")
            
    except Exception as e:
        print(f"✗ Failed to test runner: {e}")
    
    print()

def main():
    print("FPV Streamer Startup Debug Tool")
    print("=" * 50)
    
    test_sample_images()
    test_video_devices()
    test_executable_startup()
    test_fpv_test_runner()
    
    print("=== Summary ===")
    print("This debug tool tested:")
    print("1. Sample image availability")
    print("2. Video device accessibility")
    print("3. Executable startup behavior")
    print("4. Test runner cancellation handling")
    print()
    print("Check the output above for specific issues.")

if __name__ == "__main__":
    main()