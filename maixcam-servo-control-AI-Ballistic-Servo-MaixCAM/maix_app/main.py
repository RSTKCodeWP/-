"""
Advanced Servo Control App for MaixCAM
Supports: Color Detection, Object Detection (YOLO), Motion Detection
Features: Presets, Full Settings, ARM Mode, OSD/UI
Optimized for speed and accuracy
"""

from maix import camera, display, image, touchscreen, pinmap, pwm, err, app, nn
import time as pytime
import json
import os
import math

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG_FILE = "/root/advanced_servo_config.json"

# Default settings
DEFAULT_CONFIG = {
    "servo_pin": "A18",
    "pwm_id": 6,
    "servo_angle_open": 90,
    "servo_angle_close": 0,
    "close_delay": 10,
    "rearm_mode": True,  # Auto rearm after object disappears
    "rearm_delay": 2,    # Seconds to wait before rearming
    "repeat_trigger": False,  # Repeat trigger every N seconds while detected
    "repeat_interval": 10,
    
    # Detection settings
    "detection_mode": "color",  # color, object, motion
    "color_preset": "Yellow",
    "object_preset": "person",
    "confidence_threshold": 0.5,
    "min_area": 500,
    "motion_sensitivity": 50,
    
    # Camera settings
    "camera_width": 640,
    "camera_height": 480,
    "fps_target": 30,
    # Ballistics & Recording
    "ballistics_mode": False,
    "altitude": 30,      # meters
    "auto_altitude": True, # Estimate altitude via AI bounding box size
    "speed": 15,         # m/s
    "auto_speed": True,  # Calculate speed automatically
    "video_recording": False,

    # Custom color threshold (LAB)
    "custom_threshold": [[50, 80, 0, 30, 40, 80]]
}

# Color presets (LAB color space)
COLOR_PRESETS = {
    "Yellow": [[50, 80, 0, 30, 40, 80]],
    "Red": [[30, 80, 20, 80, 10, 70]],
    "Green": [[20, 80, -60, -20, -10, 40]],
    "Blue": [[20, 80, -10, 30, -60, -20]],
    "Orange": [[40, 80, 20, 60, 30, 70]],
    "Purple": [[20, 70, 20, 80, -80, -20]],
    "White": [[80, 100, -20, 20, -20, 20]],
    "Black": [[0, 30, -20, 20, -20, 20]],
    "Custom": [[50, 80, 0, 30, 40, 80]]
}

# Estimated real-world heights (meters) for auto-altitude
REAL_WORLD_HEIGHTS = {
    "person": 1.7,
    "car": 1.5,
    "dog": 0.5,
    "cat": 0.3,
    "bird": 0.2,
    "bottle": 0.25,
    "cup": 0.1,
    "cell phone": 0.15,
    "chair": 1.0,
    "tv": 0.6,
    "laptop": 0.3,
    "book": 0.25,
    "clock": 0.3,
    "custom": 1.0,  # Generic assumption
    "color": 1.0    # Generic assumed canvas size
}

# Object detection labels (COCO dataset)
OBJECT_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class AppState:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.ui_mode = "run"  # run, menu, settings, calibrate
        self.menu_page = 0
        self.settings_page = 0
        
        # Servo state
        self.servo_opened = False
        self.open_time = 0
        self.last_trigger_time = 0
        self.armed = True
        self.last_detection_time = 0
        self.rearm_timer = 0
        
        # Detection state
        self.prev_frame = None
        self.detector = None
        
        # UI state
        self.fps = 0
        self.frame_count = 0
        self.fps_time = pytime.time()
        
        # UI debouncing and sub-menus
        self.prev_pressed = False
        self.select_target = None
        self.select_options = []
        self.select_labels = []
        self.select_page = 0
        
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
                print(f"[CONFIG] Loaded: {CONFIG_FILE}")
        except Exception as e:
            print(f"[CONFIG] Load error: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"[CONFIG] Saved: {CONFIG_FILE}")
        except Exception as e:
            print(f"[CONFIG] Save error: {e}")
    
    def update_fps(self):
        """Update FPS counter"""
        self.frame_count += 1
        if self.frame_count % 30 == 0:
            now = pytime.time()
            self.fps = 30 / (now - self.fps_time)
            self.fps_time = now

# ============================================================================
# SERVO CONTROL
# ============================================================================

class ServoController:
    def __init__(self, state):
        self.state = state
        self.pwm = None
        self.setup()
    
    def setup(self):
        """Initialize servo PWM"""
        try:
            pin = self.state.config["servo_pin"]
            pwm_id = self.state.config["pwm_id"]
            
            err.check_raise(
                pinmap.set_pin_function(pin, f"PWM{pwm_id}"),
                f"PWM setup failed for {pin}"
            )
            
            self.pwm = pwm.PWM(pwm_id, freq=50, duty=2.5, enable=True)
            self.set_angle(self.state.config["servo_angle_close"])
            print(f"[SERVO] Initialized: {pin} (PWM{pwm_id})")
        except Exception as e:
            print(f"[SERVO] Setup error: {e}")
    
    def set_angle(self, angle):
        """Set servo angle (0-180 degrees)"""
        if self.pwm:
            duty = 2.5 + (angle / 180.0) * 10.0
            self.pwm.duty(duty)
    
    def open(self):
        """Open servo"""
        angle = self.state.config["servo_angle_open"]
        self.set_angle(angle)
        self.state.servo_opened = True
        self.state.open_time = pytime.time()
        self.state.last_trigger_time = pytime.time()
        print(f"[SERVO] OPEN ({angle}°)")
    
    def close(self):
        """Close servo"""
        angle = self.state.config["servo_angle_close"]
        self.set_angle(angle)
        self.state.servo_opened = False
        print(f"[SERVO] CLOSE ({angle}°)")
    
    def update(self, detected):
        """Update servo based on detection and timing logic"""
        current_time = pytime.time()
        
        # Update detection time
        if detected:
            self.state.last_detection_time = current_time
        
        # Check if object disappeared and rearm mode is enabled
        if not detected and self.state.servo_opened:
            time_since_detection = current_time - self.state.last_detection_time
            if time_since_detection >= 1.0:  # Object gone for 1 second
                if self.state.config["rearm_mode"]:
                    # Start rearm timer
                    if self.state.rearm_timer == 0:
                        self.state.rearm_timer = current_time
                    
                    # Check if rearm delay passed
                    if current_time - self.state.rearm_timer >= self.state.config["rearm_delay"]:
                        self.close()
                        self.state.armed = True
                        self.state.rearm_timer = 0
                        print("[SERVO] Rearmed")
        else:
            self.state.rearm_timer = 0
        
        # Auto-close after delay
        if self.state.servo_opened:
            elapsed = current_time - self.state.open_time
            if elapsed >= self.state.config["close_delay"]:
                self.close()
                if not self.state.config["rearm_mode"]:
                    self.state.armed = False
        
        # Repeat trigger logic
        if detected and self.state.servo_opened and self.state.config["repeat_trigger"]:
            elapsed_since_trigger = current_time - self.state.last_trigger_time
            if elapsed_since_trigger >= self.state.config["repeat_interval"]:
                self.open()  # Re-trigger
        
        # Trigger on new detection
        if detected and not self.state.servo_opened and self.state.armed:
            self.open()
            if not self.state.config["rearm_mode"]:
                self.state.armed = False
    
    def cleanup(self):
        """Cleanup servo"""
        if self.pwm:
            self.close()
            self.pwm.disable()

# ============================================================================
# DETECTION ENGINES
# ============================================================================

class ColorDetector:
    def __init__(self, state):
        self.state = state
    
    def detect(self, img):
        """Detect color blobs"""
        preset = self.state.config["color_preset"]
        
        if preset == "Custom":
            threshold = self.state.config["custom_threshold"]
        else:
            threshold = COLOR_PRESETS.get(preset, COLOR_PRESETS["Yellow"])
        
        min_area = self.state.config["min_area"]
        
        blobs = img.find_blobs(
            threshold,
            pixels_threshold=min_area,
            area_threshold=min_area,
            merge=True
        )
        
        return len(blobs) > 0, blobs
    
    def calibrate(self, img, x, y, radius=30):
        """Calibrate custom color from point"""
        try:
            stats = img.get_statistics(roi=(x-radius, y-radius, radius*2, radius*2))
            l, a, b = stats.l_mean(), stats.a_mean(), stats.b_mean()
            
            # Create threshold with tolerance
            l_min = max(0, int(l - 25))
            l_max = min(100, int(l + 25))
            a_min = max(-128, int(a - 30))
            a_max = min(127, int(a + 30))
            b_min = max(-128, int(b - 30))
            b_max = min(127, int(b + 30))
            
            self.state.config["custom_threshold"] = [[l_min, l_max, a_min, a_max, b_min, b_max]]
            self.state.config["color_preset"] = "Custom"
            self.state.save_config()
            
            print(f"[COLOR] Calibrated: LAB=({l:.0f},{a:.0f},{b:.0f})")
            return True
        except Exception as e:
            print(f"[COLOR] Calibration error: {e}")
            return False

class ObjectDetector:
    def __init__(self, state):
        self.state = state
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load YOLO model"""
        try:
            # Try to load YOLOv8 model (default on MaixCAM)
            self.model = nn.YOLOv8(model="/root/models/yolov8n.mud")
            print("[OBJECT] YOLOv8 model loaded")
        except Exception as e:
            print(f"[OBJECT] Model load error: {e}")
            print("[OBJECT] Falling back to color detection")
    
    def detect(self, img):
        """Detect objects using YOLO"""
        if not self.model:
            return False, []
        
        try:
            target_label = self.state.config["object_preset"]
            confidence = self.state.config["confidence_threshold"]
            
            # Run detection
            objs = self.model.detect(img, conf_th=confidence, iou_th=0.45)
            
            # Filter by target label
            filtered = []
            for obj in objs:
                label_idx = obj.class_id
                if label_idx < len(OBJECT_LABELS):
                    label = OBJECT_LABELS[label_idx]
                    if label == target_label:
                        filtered.append(obj)
            
            return len(filtered) > 0, filtered
        except Exception as e:
            print(f"[OBJECT] Detection error: {e}")
            return False, []

class MotionDetector:
    def __init__(self, state):
        self.state = state
    
    def detect(self, img):
        """Detect motion between frames"""
        if self.state.prev_frame is None:
            self.state.prev_frame = img.copy()
            return False, []
        
        try:
            # Calculate difference
            diff = img.difference(self.state.prev_frame)
            stats = diff.get_statistics()
            
            # Update previous frame
            self.state.prev_frame = img.copy()
            
            # Check if motion exceeds threshold
            sensitivity = self.state.config["motion_sensitivity"]
            detected = stats.l_mean() > sensitivity
            
            return detected, []
        except Exception as e:
            print(f"[MOTION] Detection error: {e}")
            return False, []

# ============================================================================
# SPEED ESTIMATOR
# ============================================================================

class SpeedEstimator:
    def __init__(self, state):
        self.state = state
        self.prev_img = None
        self.last_time = pytime.time()
        self.current_speed = self.state.config.get("speed", 15)
        self.smooth_speed = self.current_speed
        
    def estimate(self, img):
        if not self.state.config.get("auto_speed", True):
            self.smooth_speed = self.state.config.get("speed", 15)
            return self.smooth_speed
            
        current_time = pytime.time()
        dt = current_time - self.last_time
        if dt <= 0:
            return self.smooth_speed
            
        # Fast, low-res grayscale crop for optical flow
        try:
            cx = img.width() // 2 - 32
            cy = img.height() // 2 - 32
            # Crop center 64x64, convert to grayscale to save memory and avoid SIGSEGV
            current_img = img.crop(cx, cy, 64, 64)
            
            if self.prev_img is not None:
                # Calculate pixel displacement
                res = current_img.find_displacement(self.prev_img)
                if res and hasattr(res, 'y_translation'):
                    dy = res.y_translation()
                    response = res.response()
                    
                    if response > 0.1: # Confidence threshold
                        # Calculate physical speed
                        # Assuming 60 deg vertical FOV, ground_h = 1.15 * Altitude
                        H = self.state.config.get("altitude", 30)
                        ground_h = 1.15 * H
                        ppm = img.height() / ground_h if ground_h > 0 else 1
                        
                        # Speed = (dy pixels / pixels_per_meter) / dt
                        # Note: dy is usually negative if the ground moves "down" relative to the camera
                        raw_speed = abs(dy / ppm) / dt
                        
                        # Clamp and smooth
                        raw_speed = max(0, min(raw_speed, 50)) # Cap at 50 m/s
                        self.smooth_speed = (self.smooth_speed * 0.8) + (raw_speed * 0.2)
                        self.state.config["speed"] = int(self.smooth_speed)
            
            self.prev_img = current_img.copy()
        except Exception as e:
            # Fallback if find_displacement crashes or lacks memory
            pass
            
        self.last_time = current_time
        return self.smooth_speed

# ============================================================================
# UI RENDERING
# ============================================================================

class UIButton:
    def __init__(self, id, x, y, w, h, label, value=""):
        self.id = id
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label = label
        self.value = value
        
    def draw(self, img):
        img.draw_rect(self.x, self.y, self.w, self.h, color=image.Color.from_rgb(40, 40, 40), thickness=-1)
        img.draw_rect(self.x, self.y, self.w, self.h, color=image.Color.from_rgb(200, 200, 200), thickness=2)
        
        if self.value != "":
            img.draw_string(self.x + 10, self.y + 5, self.label, color=image.Color.from_rgb(200, 200, 200), scale=1.5)
            img.draw_string(self.x + 10, self.y + 30, str(self.value), color=image.Color.from_rgb(0, 255, 255), scale=2.0)
        else:
            img.draw_string(self.x + 10, self.y + (self.h // 2) - 12, self.label, color=image.Color.from_rgb(255, 255, 255), scale=1.8)

    def is_clicked(self, x, y):
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h

class UI:
    def __init__(self, state):
        self.state = state
        self.active_buttons = []
    
    def draw_osd(self, img, detected, detections, ballistics_line_y=-1):
        """Draw on-screen display (OSD) in run mode"""
        # Draw OSD background box for better contrast
        img.draw_rect(5, 5, 260, 230, color=image.Color.from_rgb(0, 0, 0), thickness=-1)
        img.draw_rect(5, 5, 260, 230, color=image.Color.from_rgb(100, 100, 100), thickness=2)
        
        # Servo status - large and prominent
        status = "OPEN" if self.state.servo_opened else "CLOSED"
        status_color = image.Color.from_rgb(0, 255, 0) if self.state.servo_opened else image.Color.from_rgb(255, 255, 255)
        img.draw_string(15, 15, f"SERVO: {status}", color=status_color, scale=2.5)
        
        # ARM status
        arm_status = "ARMED" if self.state.armed else "DISARMED"
        arm_color = image.Color.from_rgb(0, 255, 0) if self.state.armed else image.Color.from_rgb(255, 0, 0)
        img.draw_string(15, 50, f"[{arm_status}]", color=arm_color, scale=2.0)
        
        # Detection mode and target
        mode = self.state.config["detection_mode"].upper()
        if mode == "COLOR":
            target = self.state.config["color_preset"]
        elif mode == "OBJECT":
            target = self.state.config["object_preset"]
        else:
            target = "MOTION"
        
        img.draw_string(15, 85, f"MODE: {mode}", color=image.Color.from_rgb(200, 200, 200), scale=1.8)
        img.draw_string(15, 115, f"TGT: {target}", color=image.Color.from_rgb(0, 255, 255), scale=1.8)
        
        # FPS
        img.draw_string(15, 145, f"FPS: {self.state.fps:.0f}", color=image.Color.from_rgb(255, 255, 255), scale=1.8)
        
        # Timer countdown
        y_timer = 175
        if self.state.servo_opened:
            current_time = pytime.time()
            remaining = int(self.state.config["close_delay"] - (current_time - self.state.open_time))
            if remaining > 0:
                img.draw_string(15, y_timer, f"CLOSE: {remaining}s", color=image.Color.from_rgb(255, 255, 0), scale=1.8)
                y_timer += 30
        
        # Rearm timer
        if self.state.rearm_timer > 0:
            current_time = pytime.time()
            rearm_remaining = int(self.state.config["rearm_delay"] - (current_time - self.state.rearm_timer))
            if rearm_remaining > 0:
                img.draw_string(15, y_timer, f"REARM: {rearm_remaining}s", color=image.Color.from_rgb(255, 165, 0), scale=1.8)
        
        # Video Recording OSD
        if self.state.config.get("video_recording"):
            rec_color = image.Color.from_rgb(255, 0, 0) if (int(pytime.time() * 2) % 2 == 0) else image.Color.from_rgb(150, 0, 0)
            img.draw_circle(img.width() - 30, 30, 15, color=rec_color, thickness=-1)
            img.draw_string(img.width() - 85, 20, "REC", color=image.Color.from_rgb(255, 255, 255), scale=2.0)
            
        # Draw Ballistics Line
        if self.state.config.get("ballistics_mode") and ballistics_line_y > 0:
            color = image.Color.from_rgb(255, 0, 255)
            # Draw dashed line
            for i in range(0, img.width(), 20):
                img.draw_line(i, ballistics_line_y, i+10, ballistics_line_y, color=color, thickness=3)
            # Crosshair center
            cx = img.width() // 2
            img.draw_line(cx, ballistics_line_y - 20, cx, ballistics_line_y + 20, color=color, thickness=3)
            img.draw_string(5, ballistics_line_y - 25, "DROP LINE", color=color, scale=1.5)
        
        # Draw detections
        self.draw_detections(img, detections)
        
        # Hint box at the bottom
        img.draw_rect(img.width()//2 - 120, img.height() - 45, 240, 40, color=image.Color.from_rgb(0, 0, 0), thickness=-1)
        img.draw_string(img.width()//2 - 100, img.height() - 35, "TAP FOR MENU", 
                       color=image.Color.from_rgb(200, 200, 200), scale=2.0)
    
    def draw_detections(self, img, detections):
        """Draw detection boxes"""
        mode = self.state.config["detection_mode"]
        
        if mode == "color":
            for blob in detections:
                x, y, w, h = blob[0], blob[1], blob[2], blob[3]
                area = w * h
                color = image.Color.from_rgb(0, 255, 0)
                img.draw_rect(x, y, w, h, color=color, thickness=2)
                img.draw_string(x, y - 15, f"{area}", color=color, scale=1.5)
        
        elif mode == "object":
            for obj in detections:
                x, y, w, h = obj.x, obj.y, obj.w, obj.h
                label_idx = obj.class_id
                conf = obj.score
                
                if label_idx < len(OBJECT_LABELS):
                    label = OBJECT_LABELS[label_idx]
                else:
                    label = f"ID{label_idx}"
                
                color = image.Color.from_rgb(0, 255, 0)
                img.draw_rect(x, y, w, h, color=color, thickness=2)
                img.draw_string(x, y - 15, f"{label} {conf:.2f}", color=color, scale=1.5)
    
    def draw_menu(self, img):
        """Draw main menu using UIButtons"""
        self.active_buttons = []
        
        # Semi-transparent background
        img.draw_rect(0, 0, img.width(), img.height(), color=image.Color.from_rgb(0, 0, 0), thickness=-1)
        
        # Title
        img.draw_string(10, 5, "MAIN MENU", color=image.Color.from_rgb(255, 255, 0), scale=2.5)
        
        y = 45
        h = 65
        w = int(img.width() / 2) - 15
        spacing = 75
        
        mode = self.state.config["detection_mode"]
        
        btn_data = [
            (0, "Mode", mode.upper()),
        ]
        
        if mode == "color":
            btn_data.append((1, "Color", self.state.config["color_preset"]))
            btn_data.append((4, "Calibrate", "Color"))
        elif mode == "object":
            btn_data.append((2, "Target", self.state.config["object_preset"]))
            
        btn_data.extend([
            (3, "Settings", ""),
            (5, "State", "ARMED" if self.state.armed else "DISARMED"),
            (6, "Save & Exit", "")
        ])
        
        for i, (id, label, value) in enumerate(btn_data):
            col = i % 2
            row = i // 2
            btn_x = 10 + col * (w + 10)
            btn_y = y + row * spacing
            btn = UIButton(id, btn_x, btn_y, w, h, label, value)
            btn.draw(img)
            self.active_buttons.append(btn)
    
    def draw_calibrate(self, img):
        """Draw calibration screen"""
        img.draw_string(img.width()//2 - 150, img.height()//2, 
                       "TAP TARGET COLOR", 
                       color=image.Color.from_rgb(255, 0, 255), scale=3)
        
        img.draw_string(img.width()//2 - 100, img.height()//2 + 50, 
                       "TAP AGAIN TO CANCEL", 
                       color=image.Color.from_rgb(150, 150, 150), scale=2)
    
    def draw_settings(self, img):
        """Draw settings menu using UIButtons in a grid"""
        self.active_buttons = []
        
        # Semi-transparent background
        img.draw_rect(0, 0, img.width(), img.height(), color=image.Color.from_rgb(0, 0, 0), thickness=-1)
        
        # Title
        img.draw_string(10, 5, f"SETTINGS P{self.state.settings_page+1}", color=image.Color.from_rgb(255, 255, 0), scale=2.5)
        
        y = 45
        h = 60
        w = int(img.width() / 2) - 15
        spacing = 65
        
        if self.state.settings_page == 0:
            btn_data = [
                (0, "Close", f"{self.state.config['close_delay']}s"),
                (1, "Rearm", "ON" if self.state.config['rearm_mode'] else "OFF"),
                (2, "Rearm Dly", f"{self.state.config['rearm_delay']}s"),
                (3, "Repeat", "ON" if self.state.config['repeat_trigger'] else "OFF"),
                (4, "Min Area", f"{self.state.config['min_area']}"),
                (5, "Conf.", f"{self.state.config['confidence_threshold']:.2f}"),
                (6, "Mot. Sens", f"{self.state.config['motion_sensitivity']}"),
                (7, "Next Page", ""),
                (8, "Back to Menu", "")
            ]
        elif self.state.settings_page == 1:
            res = f"{self.state.config['camera_width']}x{self.state.config['camera_height']}"
            btn_data = [
                (0, "Res", res),
                (1, "Servo Pin", str(self.state.config.get('servo_pin', 'A18'))),
                (2, "Angle Op", f"{self.state.config.get('servo_angle_open', 90)}°"),
                (3, "Angle Cl", f"{self.state.config.get('servo_angle_close', 0)}°"),
                (4, "Rep. Int", f"{self.state.config.get('repeat_interval', 10)}s"),
                (7, "Next Page", ""),
                (5, "Prev Page", ""),
                (6, "Back to Menu", "")
            ]
        else:
            speed_val = "AUTO" if self.state.config.get('auto_speed') else f"{self.state.config.get('speed', 15)}m/s"
            alt_val = "AUTO" if self.state.config.get('auto_altitude') else f"{self.state.config.get('altitude', 30)}m"
            btn_data = [
                (9, "Ballistics", "ON" if self.state.config.get('ballistics_mode') else "OFF"),
                (14, "Auto Alt", "ON" if self.state.config.get('auto_altitude', True) else "OFF"),
                (10, "Altitude", alt_val),
                (11, "Auto Speed", "ON" if self.state.config.get('auto_speed', True) else "OFF"),
                (12, "Speed", speed_val),
                (13, "Video Rec", "ON" if self.state.config.get('video_recording') else "OFF"),
                (15, "Reset", "CONFIG"),
                (5, "Prev Page", ""),
                (6, "Back to Menu", "")
            ]
            
        for i, (id, label, value) in enumerate(btn_data):
            col = i % 2
            row = i // 2
            btn_x = 10 + col * (w + 10)
            btn_y = y + row * spacing
            btn = UIButton(id, btn_x, btn_y, w, h, label, value)
            btn.draw(img)
            self.active_buttons.append(btn)

    def draw_select(self, img):
        """Draw selection list/grid"""
        self.active_buttons = []
        img.draw_rect(0, 0, img.width(), img.height(), color=image.Color.from_rgb(0, 0, 0), thickness=-1)
        img.draw_string(10, 5, f"SELECT (P{self.state.select_page+1})", color=image.Color.from_rgb(255, 255, 0), scale=2.5)
        
        y = 45
        h = 60
        w = int(img.width() / 2) - 15
        spacing = 65
        
        items_per_page = 8
        start_idx = self.state.select_page * items_per_page
        page_items = self.state.select_options[start_idx:start_idx + items_per_page]
        
        for i, option in enumerate(page_items):
            # Calculate grid position (2 columns)
            col = i % 2
            row = i // 2
            btn_x = 10 + col * (w + 10)
            btn_y = y + row * spacing
            
            # Highlight current value
            label = str(option)
            if option == self.state.config.get(self.state.select_target):
                label = f"[{label}]"
            
            btn = UIButton(i, btn_x, btn_y, w, h, label)
            btn.draw(img)
            self.active_buttons.append(btn)
        
        # Navigation buttons at bottom
        # Calculate Y for nav buttons
        rows = (items_per_page + 1) // 2
        nav_y = y + rows * spacing + 10
        
        btn_prev = UIButton(-1, 10, nav_y, w, h, "<- Prev Page")
        btn_prev.draw(img)
        self.active_buttons.append(btn_prev)
        
        btn_next = UIButton(-2, 10 + w + 10, nav_y, w, h, "Next Page ->")
        btn_next.draw(img)
        self.active_buttons.append(btn_next)
        
        btn_back = UIButton(-3, 10, nav_y + spacing + 10, img.width() - 20, h, "Back")
        btn_back.draw(img)
        self.active_buttons.append(btn_back)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    print("=" * 60)
    print("ADVANCED SERVO CONTROL APP")
    print("=" * 60)
    
    # Initialize state
    state = AppState()
    state.load_config()
    
    # Initialize components
    cam = camera.Camera(
        state.config["camera_width"],
        state.config["camera_height"],
        image.Format.FMT_RGB888
    )
    disp = display.Display()
    ts = touchscreen.TouchScreen()
    
    servo = ServoController(state)
    color_detector = ColorDetector(state)
    object_detector = ObjectDetector(state)
    motion_detector = MotionDetector(state)
    speed_estimator = SpeedEstimator(state)
    ui = UI(state)
    
    print(f"[INIT] Camera: {state.config['camera_width']}x{state.config['camera_height']}")
    print(f"[INIT] Mode: {state.config['detection_mode']}")
    print(f"[INIT] Ready!")
    print("=" * 60)
    
    # Main loop
    try:
        while not app.need_exit():
            img = cam.read()
            state.update_fps()
            
            # Handle touch input
            touch_data = ts.read()
            if touch_data:
                tx, ty, pressed = touch_data
                if pressed and not state.prev_pressed:
                    handle_touch(state, img, tx, ty, color_detector, ui)
                state.prev_pressed = pressed
            else:
                state.prev_pressed = False
            
            # Detection and servo control
            detected = False
            detections = []
            
            if state.ui_mode == "run":
                mode = state.config["detection_mode"]
                
                if mode == "color":
                    detected, detections = color_detector.detect(img)
                elif mode == "object":
                    detected, detections = object_detector.detect(img)
                elif mode == "motion":
                    detected, detections = motion_detector.detect(img)
                
                ballistics_line_y = -1
                if state.config.get("ballistics_mode"):
                    H = state.config.get("altitude", 30)
                    
                    # AI Rangefinder: Auto-Altitude estimation
                    if state.config.get("auto_altitude", True) and detected and len(detections) > 0:
                        # Find largest bounding box height to estimate distance
                        max_h_px = 0
                        target_real_h = 1.0 # Default fallback
                        
                        if mode == "color":
                            max_h_px = max([blob[3] for blob in detections])
                            target_real_h = REAL_WORLD_HEIGHTS.get("color", 1.0)
                        elif mode == "object":
                            largest_obj = max(detections, key=lambda obj: obj.h)
                            max_h_px = largest_obj.h
                            label_idx = largest_obj.class_id
                            if label_idx < len(OBJECT_LABELS):
                                label_name = OBJECT_LABELS[label_idx]
                                target_real_h = REAL_WORLD_HEIGHTS.get(label_name, 1.0)
                        
                        if max_h_px > 0:
                            # Distance = (Real Height * Camera Height) / (Object Height * 1.15) 
                            # (Assuming ~60 deg vertical FOV: 2 * tan(30) = 1.15)
                            estimated_H = (target_real_h * state.config["camera_height"]) / (max_h_px * 1.15)
                            # Clamp extreme values to prevent physics glitching
                            H = max(1.0, min(estimated_H, 200.0))
                            state.config["altitude"] = int(H) # Update config to show in UI
                    
                    # Update speed dynamically using optical flow if auto_speed is enabled
                    V = speed_estimator.estimate(img)
                    
                    g = 9.81
                    # Math: t = sqrt(2H/g), D = V * t
                    t_fall = math.sqrt(2 * H / g)
                    D = V * t_fall
                    
                    # Assume 60 degree Vertical FOV => ground_h = 1.15 * H
                    ground_h = 1.15 * H
                    ppm = state.config["camera_height"] / ground_h if ground_h > 0 else 1
                    pixel_offset = int(D * ppm)
                    
                    # Target approaches from top, we must drop early (above center)
                    ballistics_line_y = int(state.config["camera_height"] / 2 - pixel_offset)
                    
                    # Clamp to screen
                    ballistics_line_y = max(10, min(ballistics_line_y, state.config["camera_height"] - 10))
                    
                    # Intercept logic
                    if detected and len(detections) > 0:
                        valid_cross = False
                        if mode == "color":
                            for blob in detections:
                                cy = blob[1] + blob[3]/2
                                if cy >= ballistics_line_y:
                                    valid_cross = True
                        elif mode == "object":
                            for obj in detections:
                                cy = obj.y + obj.h/2
                                if cy >= ballistics_line_y:
                                    valid_cross = True
                        # For motion, just use raw detect (or you could calculate center)
                        detected = valid_cross

                servo.update(detected)
            
            # Render UI
            if state.ui_mode == "run":
                ui.draw_osd(img, detected, detections, ballistics_line_y)
            elif state.ui_mode == "menu":
                ui.draw_menu(img)
            elif state.ui_mode == "calibrate":
                ui.draw_calibrate(img)
            elif state.ui_mode == "settings":
                ui.draw_settings(img)
            elif state.ui_mode == "select":
                ui.draw_select(img)
            
            disp.show(img)
    
    finally:
        # Cleanup
        servo.cleanup()
        cam.close()
        print("[EXIT] Cleanup complete")

def handle_touch(state, img, tx, ty, color_detector, ui):
    """Handle touch screen input"""
    if state.ui_mode == "run":
        # Open menu
        state.ui_mode = "menu"
        return
    
    elif state.ui_mode == "calibrate":
        # Calibrate color or cancel
        if ty < img.height() // 2:
            # Scale touch coordinates to image coordinates
            img_w, img_h = img.width(), img.height()
            disp_w, disp_h = 552, 368  # MaixCAM display size
            x = int(tx * img_w / disp_w)
            y = int(ty * img_h / disp_h)
            
            color_detector.calibrate(img, x, y)
        
        state.ui_mode = "run"
        return

    # Check which button was clicked
    clicked_btn = None
    for btn in ui.active_buttons:
        if btn.is_clicked(tx, ty):
            clicked_btn = btn
            break
            
    if not clicked_btn:
        return

    setting_item = clicked_btn.id

    if state.ui_mode == "select":
        if setting_item == -1:  # Prev Page
            if state.select_page > 0: state.select_page -= 1
        elif setting_item == -2:  # Next Page
            state.select_page += 1
        elif setting_item == -3:  # Back
            state.ui_mode = "settings" if state.select_target not in ["detection_mode", "color_preset", "object_preset"] else "menu"
        else:
            # An option was selected
            items_per_page = 8
            idx = state.select_page * items_per_page + setting_item
            if idx < len(state.select_options):
                state.config[state.select_target] = state.select_options[idx]
                # Return to previous menu
                state.ui_mode = "settings" if state.select_target not in ["detection_mode", "color_preset", "object_preset"] else "menu"
        return

    if state.ui_mode == "menu":
        if setting_item == 0:  # Detection mode
            state.select_target = "detection_mode"
            state.select_options = ["color", "object", "motion"]
            state.select_page = 0
            state.ui_mode = "select"
        
        elif setting_item == 1:  # Color preset
            state.select_target = "color_preset"
            state.select_options = list(COLOR_PRESETS.keys())
            state.select_page = 0
            state.ui_mode = "select"
        
        elif setting_item == 2:  # Object target
            state.select_target = "object_preset"
            state.select_options = ["person", "car", "dog", "cat", "bird", "bottle", "cup", "cell phone", "chair", "tv", "laptop", "book", "clock", "custom"]
            state.select_page = 0
            state.ui_mode = "select"
        
        elif setting_item == 3:  # Settings
            state.ui_mode = "settings"
            state.settings_page = 0
        
        elif setting_item == 4:  # Calibrate
            state.ui_mode = "calibrate"
        
        elif setting_item == 5:  # ARM/DISARM
            state.armed = not state.armed
        
        elif setting_item == 6:  # Save & Exit
            state.save_config()
            state.ui_mode = "run"
    
    elif state.ui_mode == "settings":
        if state.settings_page == 0:
            if setting_item == 0:  # Close delay
                state.select_target = "close_delay"
                state.select_options = [3, 5, 10, 15, 20, 30, 60]
                state.select_page = 0
                state.ui_mode = "select"
            
            elif setting_item == 1:  # Rearm mode
                state.config["rearm_mode"] = not state.config["rearm_mode"]
            
            elif setting_item == 2:  # Rearm delay
                state.select_target = "rearm_delay"
                state.select_options = [1, 2, 3, 5, 10]
                state.select_page = 0
                state.ui_mode = "select"
            
            elif setting_item == 3:  # Repeat trigger
                state.config["repeat_trigger"] = not state.config["repeat_trigger"]
            
            elif setting_item == 4:  # Min area
                state.select_target = "min_area"
                state.select_options = [300, 500, 800, 1000, 1500, 2000]
                state.select_page = 0
                state.ui_mode = "select"
            
            elif setting_item == 5:  # Confidence threshold
                state.select_target = "confidence_threshold"
                state.select_options = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
                state.select_page = 0
                state.ui_mode = "select"
            
            elif setting_item == 6:  # Motion sensitivity
                state.select_target = "motion_sensitivity"
                state.select_options = [30, 40, 50, 60, 70, 80]
                state.select_page = 0
                state.ui_mode = "select"
            
            elif setting_item == 7:  # Next Page
                state.settings_page = 1
            
            elif setting_item == 8:  # Back to menu
                state.save_config()
                state.ui_mode = "menu"
                state.settings_page = 0
                
        elif state.settings_page == 1:
            if setting_item == 0:  # Resolution
                state.select_target = "resolution"
                state.select_options = ["320x240", "640x480", "800x600", "1280x720"]
                # For resolution we need a slight hack since the config stores width/height
                state.config["resolution"] = f"{state.config['camera_width']}x{state.config['camera_height']}"
                state.select_page = 0
                state.ui_mode = "select"
                
            elif setting_item == 1:  # Servo Pin
                state.select_target = "servo_pin"
                state.select_options = ["A14", "A15", "A16", "A17", "A18", "A19"]
                state.select_page = 0
                state.ui_mode = "select"
                
            elif setting_item == 2:  # Angle Open
                state.select_target = "servo_angle_open"
                state.select_options = [0, 45, 90, 135, 180]
                state.select_page = 0
                state.ui_mode = "select"
                
            elif setting_item == 3:  # Angle Close
                state.select_target = "servo_angle_close"
                state.select_options = [0, 45, 90, 135, 180]
                state.select_page = 0
                state.ui_mode = "select"
                
            elif setting_item == 4:  # Rep Interval
                state.select_target = "repeat_interval"
                state.select_options = [1, 2, 5, 10, 15, 30]
                state.select_page = 0
                state.ui_mode = "select"
                
            elif setting_item == 7:  # Next Page
                state.settings_page = 2
                
            elif setting_item == 5:  # Prev Page
                state.settings_page = 0
                
            elif setting_item == 6:  # Back to menu
                state.save_config()
                state.ui_mode = "menu"
                state.settings_page = 0
                
        else: # settings_page == 2
            if setting_item == 9:  # Ballistics
                state.config["ballistics_mode"] = not state.config.get("ballistics_mode", False)
            elif setting_item == 14:  # Auto Altitude Toggle
                state.config["auto_altitude"] = not state.config.get("auto_altitude", True)
            elif setting_item == 10:  # Altitude Manual
                state.select_target = "altitude"
                state.select_options = [10, 20, 30, 40, 50, 60, 80, 100]
                state.select_page = 0
                state.ui_mode = "select"
            elif setting_item == 11:  # Auto Speed Toggle
                state.config["auto_speed"] = not state.config.get("auto_speed", True)
            elif setting_item == 12:  # Speed Manual
                state.select_target = "speed"
                state.select_options = [5, 10, 15, 20, 25, 30]
                state.select_page = 0
                state.ui_mode = "select"
            elif setting_item == 13:  # Video Recording
                state.config["video_recording"] = not state.config.get("video_recording", False)
            elif setting_item == 15:  # Reset Config
                state.config = DEFAULT_CONFIG.copy()
                state.save_config()
                print("[SETTINGS] Configuration reset to defaults")
                state.ui_mode = "menu"
                state.settings_page = 0
            elif setting_item == 5:  # Prev Page
                state.settings_page = 1
            elif setting_item == 6:  # Back to menu
                state.save_config()
                state.ui_mode = "menu"
                state.settings_page = 0
                
    # Parse resolution if it was just selected
    if state.config.get("resolution"):
        parts = state.config["resolution"].split("x")
        state.config["camera_width"] = int(parts[0])
        state.config["camera_height"] = int(parts[1])
        del state.config["resolution"]

if __name__ == "__main__":
    main()
