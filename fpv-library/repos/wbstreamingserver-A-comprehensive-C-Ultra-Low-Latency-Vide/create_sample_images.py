#!/usr/bin/env python3
"""
Generate synthetic test images for FPV Streamer fallback testing.
Creates various test patterns and realistic FPV-style images.
"""

import cv2
import numpy as np
import os

def create_gradient_image(width=1920, height=1080, gradient_type='diagonal'):
    """Create a gradient test image"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    
    if gradient_type == 'horizontal':
        for x in range(width):
            img[:, x] = [int(255 * x / width)] * 3
    elif gradient_type == 'vertical':
        for y in range(height):
            img[y, :] = [int(255 * y / height)] * 3
    elif gradient_type == 'diagonal':
        for y in range(height):
            for x in range(width):
                intensity = int(255 * (x + y) / (width + height))
                img[y, x] = [intensity] * 3
    elif gradient_type == 'radial':
        center_x, center_y = width // 2, height // 2
        for y in range(height):
            for x in range(width):
                distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                max_distance = np.sqrt(center_x**2 + center_y**2)
                intensity = int(255 * (1 - distance / max_distance))
                img[y, x] = [intensity] * 3
    
    return img

def create_grid_pattern(width=1920, height=1080, cell_size=100):
    """Create a grid pattern for calibration"""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    
    # Vertical lines
    for x in range(0, width, cell_size):
        cv2.line(img, (x, 0), (x, height), (0, 0, 0), 2)
    
    # Horizontal lines
    for y in range(0, height, cell_size):
        cv2.line(img, (0, y), (width, y), (0, 0, 0), 2)
    
    # Add corner markers
    marker_size = 50
    cv2.rectangle(img, (10, 10), (10 + marker_size, 10 + marker_size), (0, 0, 255), -1)
    cv2.rectangle(img, (width - marker_size - 10, 10), (width - 10, 10 + marker_size), (0, 0, 255), -1)
    cv2.rectangle(img, (10, height - marker_size - 10), (10 + marker_size, height - 10), (0, 0, 255), -1)
    cv2.rectangle(img, (width - marker_size - 10, height - marker_size - 10), (width - 10, height - 10), (0, 0, 255), -1)
    
    return img

def create_color_bars(width=1920, height=1080):
    """Create SMPTE color bars"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    
    bar_width = width // 7
    colors = [
        (192, 192, 192),  # White
        (192, 192, 0),    # Yellow
        (0, 192, 192),    # Cyan
        (0, 192, 0),      # Green
        (192, 0, 192),    # Magenta
        (192, 0, 0),      # Red
        (0, 0, 192),      # Blue
    ]
    
    for i, color in enumerate(colors):
        start_x = i * bar_width
        end_x = start_x + bar_width
        img[:, start_x:end_x] = color
    
    # Add black section at bottom
    img[height//2:, :] = 0
    
    return img

def create_checkerboard(width=1920, height=1080, square_size=50):
    """Create a checkerboard pattern"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    
    for y in range(0, height, square_size):
        for x in range(0, width, square_size):
            if ((x // square_size) + (y // square_size)) % 2 == 0:
                img[y:y+square_size, x:x+square_size] = 255
    
    return img

def create_fpv_test_scene(width=1920, height=1080):
    """Create a synthetic FPV test scene"""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Sky gradient (blue to white)
    sky_height = height // 2
    for y in range(sky_height):
        intensity = int(255 * (sky_height - y) / sky_height)
        img[y, :] = [int(intensity * 0.7), int(intensity * 0.9), intensity]
    
    # Ground (green gradient)
    for y in range(sky_height, height):
        intensity = int(255 * (height - y) / (height - sky_height))
        img[y, :] = [0, int(intensity * 0.6), int(intensity * 0.3)]
    
    # Add some white clouds
    for _ in range(5):
        cloud_x = np.random.randint(100, width - 100)
        cloud_y = np.random.randint(50, sky_height - 50)
        cloud_size = np.random.randint(50, 150)
        cv2.circle(img, (cloud_x, cloud_y), cloud_size, (255, 255, 255), -1)
    
    # Add some ground objects
    for _ in range(10):
        obj_x = np.random.randint(50, width - 50)
        obj_y = np.random.randint(sky_height, height - 30)
        obj_size = np.random.randint(10, 30)
        color = (np.random.randint(50, 200), np.random.randint(50, 200), np.random.randint(50, 200))
        cv2.circle(img, (obj_x, obj_y), obj_size, color, -1)
    
    return img

def create_dual_camera_scene(width=1920, height=1080):
    """Create a scene specifically for dual camera testing"""
    img = create_fpv_test_scene(width, height)
    
    # Add stereo calibration markers
    marker_size = 20
    cv2.circle(img, (width//4, height//2), marker_size, (255, 255, 0), 2)  # Left camera target
    cv2.circle(img, (3*width//4, height//2), marker_size, (255, 255, 0), 2)  # Right camera target
    
    # Add depth indicators
    cv2.line(img, (width//4, height//2), (width//4, height//2 + 100), (255, 0, 0), 3)
    cv2.line(img, (3*width//4, height//2), (3*width//4, height//2 + 100), (255, 0, 0), 3)
    
    return img

def main():
    """Generate all test images"""
    print("Creating sample images for FPV Streamer fallback testing...")
    
    # Ensure directories exist
    os.makedirs("samples/camera1", exist_ok=True)
    os.makedirs("samples/camera2", exist_ok=True)
    os.makedirs("samples/calibration", exist_ok=True)
    
    # Camera 1 samples (primary FPV view)
    print("Creating camera 1 samples...")
    img = create_fpv_test_scene(1920, 1080)
    cv2.imwrite("samples/camera1/fpv_scene_primary.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    img = create_gradient_image(1920, 1080, 'radial')
    cv2.imwrite("samples/camera1/radial_gradient.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    img = create_checkerboard(1920, 1080)
    cv2.imwrite("samples/camera1/checkerboard.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    # Camera 2 samples (secondary view for dual camera)
    print("Creating camera 2 samples...")
    img = create_dual_camera_scene(1920, 1080)
    cv2.imwrite("samples/camera2/fpv_scene_stereo.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    img = create_gradient_image(1920, 1080, 'diagonal')
    cv2.imwrite("samples/camera2/diagonal_gradient.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    img = create_checkerboard(1920, 1080, 40)  # Different square size
    cv2.imwrite("samples/camera2/checkerboard_fine.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    # Calibration samples
    print("Creating calibration samples...")
    img = create_grid_pattern(1920, 1080, 100)
    cv2.imwrite("samples/calibration/grid_pattern_100px.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    img = create_grid_pattern(1920, 1080, 50)
    cv2.imwrite("samples/calibration/grid_pattern_50px.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    img = create_color_bars(1920, 1080)
    cv2.imwrite("samples/calibration/color_bars.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    # Copy real sample images if they exist
    import shutil
    if os.path.exists("imgs/fpv_main_view_9.jpg"):
        shutil.copy2("imgs/fpv_main_view_9.jpg", "samples/camera1/real_aerial_view.jpg")
    if os.path.exists("imgs/fpv_side_view_4.jpg"):
        shutil.copy2("imgs/fpv_side_view_4.jpg", "samples/camera2/real_side_view.jpg")
    
    print("Sample images created successfully!")
    print("\nGenerated files:")
    print("Camera 1 samples:")
    for file in os.listdir("samples/camera1"):
        print(f"  - samples/camera1/{file}")
    print("Camera 2 samples:")
    for file in os.listdir("samples/camera2"):
        print(f"  - samples/camera2/{file}")
    print("Calibration samples:")
    for file in os.listdir("samples/calibration"):
        print(f"  - samples/calibration/{file}")

if __name__ == "__main__":
    main()