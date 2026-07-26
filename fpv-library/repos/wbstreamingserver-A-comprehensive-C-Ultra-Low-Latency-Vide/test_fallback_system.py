#!/usr/bin/env python3
"""
Test script for FPV Streamer fallback system.
Tests camera fallback functionality and dual camera support.
"""

import os
import sys
import subprocess
import time
import json
import signal
import cv2
import numpy as np
from pathlib import Path

class FPVStreamerTester:
    def __init__(self, build_dir="build"):
        self.build_dir = build_dir
        self.streamer_binary = os.path.join(build_dir, "fpv-streamer")
        self.test_results = {}
        
    def check_build(self):
        """Check if the streamer binary exists"""
        if not os.path.exists(self.streamer_binary):
            print(f"❌ Streamer binary not found at {self.streamer_binary}")
            return False
        
        print(f"✅ Found streamer binary: {self.streamer_binary}")
        
        # Check file permissions
        if not os.access(self.streamer_binary, os.X_OK):
            print(f"❌ Binary is not executable: {self.streamer_binary}")
            return False
        
        print(f"✅ Binary is executable")
        return True
    
    def test_help_command(self):
        """Test the --help command"""
        print("\n📋 Testing --help command...")
        try:
            result = subprocess.run([self.streamer_binary, "--help"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and "FPV Streamer" in result.stdout:
                print("✅ Help command works")
                return True
            else:
                print(f"❌ Help command failed:")
                print(f"Return code: {result.returncode}")
                print(f"Stdout: {result.stdout}")
                print(f"Stderr: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Exception running help command: {e}")
            return False
    
    def check_sample_images(self):
        """Check if sample images are available"""
        print("\n🖼️ Checking sample images...")
        
        sample_dirs = ["samples/camera1", "samples/camera2", "samples/calibration"]
        found_images = []
        
        for sample_dir in sample_dirs:
            if os.path.exists(sample_dir):
                images = list(Path(sample_dir).glob("*.*"))
                image_count = len([img for img in images if img.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']])
                print(f"  {sample_dir}: {image_count} images")
                found_images.extend([str(img) for img in images])
            else:
                print(f"  ❌ {sample_dir}: directory not found")
        
        if found_images:
            print(f"✅ Found {len(found_images)} sample images total")
            return True
        else:
            print("❌ No sample images found")
            return False
    
    def test_video_devices(self):
        """Test video device availability"""
        print("\n📹 Checking video device availability...")
        
        video_devices = ["/dev/video0", "/dev/video1", "/dev/video2"]
        available_devices = []
        
        for device in video_devices:
            if os.path.exists(device):
                try:
                    # Try to get device info
                    result = subprocess.run(["v4l2-ctl", "--list-devices"], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        print(f"  ✅ {device}: available")
                        available_devices.append(device)
                    else:
                        print(f"  ⚠️ {device}: exists but v4l2-ctl failed")
                        available_devices.append(device)  # Still count as available
                except:
                    print(f"  ✅ {device}: exists")
                    available_devices.append(device)
            else:
                print(f"  ❌ {device}: not found")
        
        if available_devices:
            print(f"✅ Found {len(available_devices)} video devices: {available_devices}")
        else:
            print("ℹ️ No video devices found - will rely on sample images")
        
        return available_devices
    
    def test_short_run(self):
        """Test short runtime with sample image fallback"""
        print("\n🚀 Testing short runtime with fallback...")
        
        # Test with explicit sample mode
        try:
            cmd = [self.streamer_binary, "--device", "/dev/video999", "--port", "8080"]
            print(f"Running: {' '.join(cmd)}")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, text=True)
            
            # Wait a few seconds for startup
            time.sleep(3)
            
            # Check if process is still running
            if process.poll() is None:
                print("✅ Streamer started and is running")
                
                # Try to get status
                try:
                    import requests
                    response = requests.get("http://localhost:8080/status", timeout=5)
                    if response.status_code == 200:
                        print("✅ Web interface responding")
                        status_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                        print(f"Status: {str(status_data)[:200]}...")
                    else:
                        print(f"⚠️ Web interface returned status {response.status_code}")
                except:
                    print("ℹ️ Web interface not responding (may be disabled)")
                
                # Clean shutdown
                process.terminate()
                process.wait(timeout=5)
                print("✅ Clean shutdown successful")
                
                return True
            else:
                stdout, stderr = process.communicate()
                print(f"❌ Streamer exited early")
                print(f"Stdout: {stdout}")
                print(f"Stderr: {stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Exception during runtime test: {e}")
            return False
    
    def test_dual_camera_config(self):
        """Test dual camera configuration"""
        print("\n📷 Testing dual camera configuration...")
        
        # Test with dual camera settings
        cmd = [self.streamer_binary, "--enable-dual-camera", "--camera2-device", "/dev/video2"]
        print(f"Testing dual camera config: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE, text=True)
            time.sleep(2)
            
            if process.poll() is None:
                print("✅ Dual camera config accepted")
                process.terminate()
                process.wait(timeout=5)
                return True
            else:
                stdout, stderr = process.communicate()
                print(f"❌ Dual camera config failed")
                print(f"Stderr: {stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Exception testing dual camera: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("🧪 FPV Streamer Fallback System Test")
        print("=" * 50)
        
        tests = [
            ("Build Check", self.check_build),
            ("Help Command", self.test_help_command),
            ("Sample Images", self.check_sample_images),
            ("Video Devices", self.test_video_devices),
            ("Short Runtime", self.test_short_run),
            ("Dual Camera", self.test_dual_camera_config),
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                self.test_results[test_name] = result
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
                self.test_results[test_name] = False
        
        self.print_summary()
        
    def print_summary(self):
        """Print test summary"""
        print("\n📊 Test Summary")
        print("=" * 30)
        
        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:20} {status}")
        
        print("-" * 30)
        print(f"Total: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
        elif passed >= total * 0.7:
            print("⚠️ Most tests passed, system is functional")
        else:
            print("❌ Multiple tests failed, check configuration")
        
        return passed == total

def main():
    if len(sys.argv) > 1:
        build_dir = sys.argv[1]
    else:
        build_dir = "build"
    
    tester = FPVStreamerTester(build_dir)
    tester.run_all_tests()

if __name__ == "__main__":
    main()