"""
Simple Servo Control App for MaixCAM
Minimal version for quick start and testing
"""

from maix import camera, display, image, pinmap, pwm, err, app
import time as pytime

# ============================================================================
# CONFIGURATION - Edit these values
# ============================================================================

SERVO_PIN = "A18"
PWM_ID = 6
SERVO_ANGLE_OPEN = 90
SERVO_ANGLE_CLOSE = 0

# Detection mode: "color", "motion"
DETECTION_MODE = "color"

# Color threshold (LAB color space)
# Yellow: [[50, 80, 0, 30, 40, 80]]
# Red:    [[30, 80, 40, 80, 10, 80]]
# Green:  [[30, 80, -120, -10, 0, 30]]
# Blue:   [[30, 80, 30, 100, -120, -60]]
COLOR_THRESHOLD = [[50, 80, 0, 30, 40, 80]]  # Yellow

MIN_AREA = 500
CLOSE_DELAY = 10  # seconds
MOTION_SENSITIVITY = 50

# ============================================================================
# SETUP
# ============================================================================

print("=" * 60)
print("SIMPLE SERVO CONTROL APP")
print("=" * 60)

# Setup PWM
err.check_raise(pinmap.set_pin_function(SERVO_PIN, f"PWM{PWM_ID}"), "PWM setup failed")

# Initialize hardware
cam = camera.Camera(640, 480, image.Format.FMT_RGB888)
disp = display.Display()
servo_pwm = pwm.PWM(PWM_ID, freq=50, duty=2.5, enable=True)

# State
servo_opened = False
open_time = 0
prev_frame = None

print(f"[INIT] Servo: {SERVO_PIN} (PWM{PWM_ID})")
print(f"[INIT] Mode: {DETECTION_MODE}")
print(f"[INIT] Ready!")
print("=" * 60)

# ============================================================================
# SERVO CONTROL
# ============================================================================

def set_servo_angle(angle):
    """Set servo angle (0-180 degrees)"""
    duty = 2.5 + (angle / 180.0) * 10.0
    servo_pwm.duty(duty)

def open_servo():
    """Open servo"""
    global servo_opened, open_time
    set_servo_angle(SERVO_ANGLE_OPEN)
    servo_opened = True
    open_time = pytime.time()
    print(f"[SERVO] OPEN ({SERVO_ANGLE_OPEN}°)")

def close_servo():
    """Close servo"""
    global servo_opened
    set_servo_angle(SERVO_ANGLE_CLOSE)
    servo_opened = False
    print(f"[SERVO] CLOSE ({SERVO_ANGLE_CLOSE}°)")

# Initialize servo to closed position
set_servo_angle(SERVO_ANGLE_CLOSE)

# ============================================================================
# DETECTION
# ============================================================================

def detect_color(img):
    """Detect color blobs"""
    blobs = img.find_blobs(
        COLOR_THRESHOLD,
        pixels_threshold=MIN_AREA,
        area_threshold=MIN_AREA,
        merge=True
    )
    return len(blobs) > 0, blobs

def detect_motion(img):
    """Detect motion"""
    global prev_frame
    
    if prev_frame is None:
        prev_frame = img.copy()
        return False, []
    
    diff = img.difference(prev_frame)
    stats = diff.get_statistics()
    prev_frame = img.copy()
    
    detected = stats.l_mean() > MOTION_SENSITIVITY
    return detected, []

# ============================================================================
# MAIN LOOP
# ============================================================================

fps = 0
frame_count = 0
fps_time = pytime.time()

try:
    while not app.need_exit():
        img = cam.read()
        
        # FPS calculation
        frame_count += 1
        if frame_count % 30 == 0:
            fps = 30 / (pytime.time() - fps_time)
            fps_time = pytime.time()
        
        # Detection
        if DETECTION_MODE == "color":
            detected, detections = detect_color(img)
        elif DETECTION_MODE == "motion":
            detected, detections = detect_motion(img)
        else:
            detected, detections = False, []
        
        # Servo control
        current_time = pytime.time()
        
        # Auto-close after delay
        if servo_opened and (current_time - open_time >= CLOSE_DELAY):
            close_servo()
        
        # Open on detection
        if detected and not servo_opened:
            open_servo()
        
        # Draw detections
        if DETECTION_MODE == "color":
            for blob in detections:
                x, y, w, h = blob[0], blob[1], blob[2], blob[3]
                area = w * h
                color = image.Color.from_rgb(0, 255, 0)
                img.draw_rect(x, y, w, h, color=color, thickness=2)
                img.draw_string(x, y - 15, f"{area}", color=color, scale=1.5)
        
        # Draw UI
        status = "OPEN" if servo_opened else "CLOSED"
        status_color = image.Color.from_rgb(0, 255, 0) if servo_opened else image.Color.from_rgb(255, 255, 255)
        img.draw_string(10, 10, f"SERVO: {status}", color=status_color, scale=3)
        
        img.draw_string(10, 50, f"Mode: {DETECTION_MODE.upper()}", 
                       color=image.Color.from_rgb(255, 255, 255), scale=2)
        img.draw_string(10, 80, f"FPS: {fps:.0f}", 
                       color=image.Color.from_rgb(255, 255, 255), scale=2)
        
        if servo_opened:
            remaining = int(CLOSE_DELAY - (current_time - open_time))
            if remaining > 0:
                img.draw_string(10, 110, f"Close: {remaining}s", 
                               color=image.Color.from_rgb(255, 255, 0), scale=2)
        
        disp.show(img)

finally:
    # Cleanup
    close_servo()
    servo_pwm.disable()
    cam.close()
    print("[EXIT] Cleanup complete")
