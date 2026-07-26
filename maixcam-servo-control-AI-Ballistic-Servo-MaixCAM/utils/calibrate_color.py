"""
Color Calibration Tool for MaixCAM
Interactive color calibration with live preview
"""

from maix import camera, display, image, touchscreen, app
import json
import os

CONFIG_FILE = "/root/advanced_servo_config.json"

print("=" * 60)
print("COLOR CALIBRATION TOOL")
print("=" * 60)

# Initialize hardware
cam = camera.Camera(640, 480, image.Format.FMT_RGB888)
disp = display.Display()
ts = touchscreen.TouchScreen()

# State
calibrated_threshold = None
calibration_point = None

print("\n[INIT] Camera and display ready")
print("[INIT] Touch the screen on the target color to calibrate")
print("[INIT] Touch again to save and exit")
print("=" * 60)

def get_lab_at_point(img, x, y, radius=30):
    """Get average LAB values around a point"""
    stats = img.get_statistics(roi=(x-radius, y-radius, radius*2, radius*2))
    return stats.l_mean(), stats.a_mean(), stats.b_mean()

def create_threshold(l, a, b, tolerance_l=25, tolerance_ab=30):
    """Create LAB threshold with tolerance"""
    l_min = max(0, int(l - tolerance_l))
    l_max = min(100, int(l + tolerance_l))
    a_min = max(-128, int(a - tolerance_ab))
    a_max = min(127, int(a + tolerance_ab))
    b_min = max(-128, int(b - tolerance_ab))
    b_max = min(127, int(b + tolerance_ab))
    
    return [[l_min, l_max, a_min, a_max, b_min, b_max]]

def save_calibration(threshold):
    """Save calibration to config file"""
    try:
        # Load existing config
        config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        
        # Update threshold
        config["custom_threshold"] = threshold
        config["color_preset"] = "Custom"
        
        # Save
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\n[SAVE] Calibration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed to save: {e}")
        return False

try:
    while not app.need_exit():
        img = cam.read()
        
        # Handle touch
        touch_data = ts.read()
        if touch_data:
            tx, ty, pressed = touch_data
            
            if pressed:
                # Scale touch coordinates to image coordinates
                img_w, img_h = img.width(), img.height()
                disp_w, disp_h = 552, 368  # MaixCAM display size
                x = int(tx * img_w / disp_w)
                y = int(ty * img_h / disp_h)
                
                if calibrated_threshold is None:
                    # First touch - calibrate
                    l, a, b = get_lab_at_point(img, x, y)
                    calibrated_threshold = create_threshold(l, a, b)
                    calibration_point = (x, y)
                    
                    print("\n" + "=" * 60)
                    print("CALIBRATION RESULT")
                    print("=" * 60)
                    print(f"LAB values: L={l:.1f}, A={a:.1f}, B={b:.1f}")
                    print(f"Threshold: {calibrated_threshold[0]}")
                    print("\nTouch screen again to save and exit")
                    print("=" * 60)
                else:
                    # Second touch - save and exit
                    if save_calibration(calibrated_threshold):
                        print("\n✓ Calibration complete!")
                        break
        
        # Show live preview with calibrated threshold
        if calibrated_threshold:
            # Find blobs with calibrated threshold
            blobs = img.find_blobs(
                calibrated_threshold,
                pixels_threshold=300,
                area_threshold=300,
                merge=True
            )
            
            # Draw blobs
            for blob in blobs:
                x, y, w, h = blob[0], blob[1], blob[2], blob[3]
                area = w * h
                color = image.Color.from_rgb(0, 255, 0)
                img.draw_rect(x, y, w, h, color=color, thickness=3)
                img.draw_string(x, y - 20, f"Area: {area}", color=color, scale=2)
            
            # Draw calibration point
            if calibration_point:
                cx, cy = calibration_point
                img.draw_circle(cx, cy, 40, color=image.Color.from_rgb(255, 0, 255), thickness=4)
                img.draw_circle(cx, cy, 5, color=image.Color.from_rgb(255, 0, 255), thickness=-1)
            
            # Status
            img.draw_string(10, 10, "CALIBRATED", 
                           color=image.Color.from_rgb(0, 255, 0), scale=3)
            img.draw_string(10, 50, f"Blobs: {len(blobs)}", 
                           color=image.Color.from_rgb(255, 255, 255), scale=2)
            img.draw_string(10, img.height() - 40, "TAP TO SAVE & EXIT", 
                           color=image.Color.from_rgb(255, 255, 0), scale=2)
        else:
            # Waiting for calibration
            img.draw_string(10, 10, "CALIBRATION MODE", 
                           color=image.Color.from_rgb(255, 255, 0), scale=3)
            img.draw_string(10, img.height() // 2, "TAP TARGET COLOR", 
                           color=image.Color.from_rgb(255, 0, 255), scale=3)
            
            # Draw crosshair in center
            cx, cy = img.width() // 2, img.height() // 2
            img.draw_line(cx - 30, cy, cx + 30, cy, 
                         color=image.Color.from_rgb(255, 255, 255), thickness=2)
            img.draw_line(cx, cy - 30, cx, cy + 30, 
                         color=image.Color.from_rgb(255, 255, 255), thickness=2)
        
        disp.show(img)

finally:
    cam.close()
    print("\n[EXIT] Calibration tool closed")
