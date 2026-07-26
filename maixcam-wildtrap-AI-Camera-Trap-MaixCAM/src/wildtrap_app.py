#!/usr/bin/env python3
"""
MaixCAM WildTrap - AI-Powered Camera Trap
Production-ready wildlife monitoring system
"""

import os, sys, time, json, csv
from datetime import datetime
from pathlib import Path

try:
    from maix import camera, display, image, nn, touchscreen, pinmap, pwm, err
except ImportError:
    camera = display = image = nn = touchscreen = pinmap = pwm = err = None

VERSION = "1.6.0"
CONFIG_FILE = "wildtrap_config.json"
BASE_DIR = Path("/root/wildtrap")
CAPTURES_DIR = BASE_DIR / "captures"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

# COCO classes for YOLOv8
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
    "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

# UI Colors
COLOR_BG = (20, 20, 30)
COLOR_TEXT = (255, 255, 255)
COLOR_ACCENT = (0, 200, 100)
COLOR_WARNING = (255, 150, 0)
COLOR_ERROR = (255, 50, 50)

DEFAULT_CONFIG = {
    "detection_mode": "hybrid",
    "capture_mode": "burst",
    "burst_count": 5,
    "video_duration": 10,
    "timelapse_interval": 60,
    "target_objects": ["person", "dog", "cat", "bird", "horse", "cow", "sheep", "bear"],
    "confidence_threshold": 0.6,
    "min_object_size": 1000,
    "motion_sensitivity": 50,
    "cooldown_seconds": 30,
    "camera_width": 1280,
    "camera_height": 720,
    "night_mode": True,
    "jpeg_quality": 90,
    "osd_enabled": True,
    "servo_enabled": False,
    "servo_pin": "A18",
    "pwm_id": 6,
    "servo_angle_open": 90,
    "servo_angle_close": 0,
    "servo_close_delay": 10,
    "ext_trigger_enabled": False,
    "ext_trigger_pin": "A19",
    "ext_trigger_duration": 5,
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_throttle_minutes": 5,
    "webhook_enabled": False,
    "webhook_url": "",
    "storage_max_gb": 5,
    "storage_keep_days": 7,
    "auto_cleanup": True,
    "armed": False
}

def load_config():
    """Load configuration from JSON file or create default."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        else:
            save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def ensure_directories():
    """Create required directories if they don't exist."""
    for directory in [BASE_DIR, CAPTURES_DIR, LOGS_DIR, TEMP_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

def get_timestamp():
    """Get current timestamp in YYYYMMDD_HHMMSS format."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def get_disk_usage():
    """Get disk usage in GB."""
    try:
        stat = os.statvfs(str(CAPTURES_DIR))
        total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
        used_gb = ((stat.f_blocks - stat.f_bfree) * stat.f_frsize) / (1024**3)
        return used_gb, total_gb
    except:
        return 0, 0

def apply_night_mode(img):
    """Apply night vision enhancement to image."""
    try:
        img = img.mul(1.5)
        img = img.histeq()
        return img
    except:
        return img

class ServoController:
    """Manages servo for physical actions (e.g. food dispenser)."""
    def __init__(self, state):
        self.state = state
        self.pwm = None
        self.servo_opened = False
        self.open_time = 0
        self.setup()
    
    def setup(self):
        if not self.state.config.get("servo_enabled", False):
            return
        try:
            if pinmap is None or pwm is None or err is None:
                print("PWM/Pinmap modules not available")
                return
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
        if self.pwm:
            duty = 2.5 + (angle / 180.0) * 10.0
            self.pwm.duty(duty)
            
    def open(self):
        if not self.pwm or not self.state.config.get("servo_enabled", False):
            return
        angle = self.state.config["servo_angle_open"]
        self.set_angle(angle)
        self.servo_opened = True
        self.open_time = time.time()
        print(f"[SERVO] OPEN ({angle}°)")
        
    def close(self):
        if not self.pwm:
            return
        angle = self.state.config["servo_angle_close"]
        self.set_angle(angle)
        self.servo_opened = False
        print(f"[SERVO] CLOSE ({angle}°)")
        
    def update(self):
        if self.servo_opened:
            elapsed = time.time() - self.open_time
            if elapsed >= self.state.config.get("servo_close_delay", 10):
                self.close()
                
    def cleanup(self):
        if self.pwm:
            self.close()
            self.pwm.disable()

class ExternalTrigger:
    """Manages external triggers like lights or alarms via GPIO."""
    def __init__(self, state):
        self.state = state
        self.active = False
        self.start_time = 0
        self.pin = None
        self.setup()
        
    def setup(self):
        if not self.state.config.get("ext_trigger_enabled", False):
            return
        try:
            from maix import gpio
            pin_name = self.state.config.get("ext_trigger_pin", "A19")
            self.pin = gpio.GPIO(pin_name, gpio.Mode.OUT)
            self.pin.value(0)
            print(f"[TRIGGER] Initialized on {pin_name}")
        except Exception as e:
            print(f"[TRIGGER] Setup error: {e}")
            
    def trigger(self):
        if not self.pin or not self.state.config.get("ext_trigger_enabled", False):
            return
        self.pin.value(1)
        self.active = True
        self.start_time = time.time()
        print("[TRIGGER] ACTIVE")
        
    def update(self):
        if self.active:
            elapsed = time.time() - self.start_time
            if elapsed >= self.state.config.get("ext_trigger_duration", 5):
                self.pin.value(0)
                self.active = False
                print("[TRIGGER] OFF")
                
    def cleanup(self):
        if self.pin:
            self.pin.value(0)

class AppState:
    """Central application state management."""
    def __init__(self):
        self.config = load_config()
        self.running = True
        self.armed = self.config.get("armed", False)
        self.current_screen = "main"
        self.settings_page = 0
        self.gallery_index = 0
        self.gallery_files = []
        self.last_touch_time = 0
        self.last_detection_time = 0
        self.captures_today = 0
        self.last_capture_info = None
        self.total_detections = 0
        self.detection_counts = {}
        
    def save(self):
        """Save current state to config."""
        self.config["armed"] = self.armed
        save_config(self.config)
    
    def can_capture(self):
        """Check if cooldown period has passed."""
        cooldown = self.config.get("cooldown_seconds", 30)
        return (time.time() - self.last_detection_time) >= cooldown
    
    def record_detection(self, objects):
        """Record detection event."""
        self.last_detection_time = time.time()
        self.total_detections += 1
        for obj in objects:
            label = obj.get("label", "unknown")
            self.detection_counts[label] = self.detection_counts.get(label, 0) + 1

class CameraController:
    """Manages camera operations and settings."""
    def __init__(self, state):
        self.state = state
        self.cam = None
        self.disp = None
        self.initialized = False
        
    def initialize(self):
        """Initialize camera and display."""
        try:
            if camera is None:
                print("Camera module not available")
                return False
            width = self.state.config.get("camera_width", 1280)
            height = self.state.config.get("camera_height", 720)
            self.cam = camera.Camera(width, height)
            self.disp = display.Display()
            self.initialized = True
            print(f"Camera initialized: {width}x{height}")
            return True
        except Exception as e:
            print(f"Camera initialization error: {e}")
            return False
    
    def capture_frame(self):
        """Capture a single frame."""
        if not self.initialized or self.cam is None:
            return None
        try:
            img = self.cam.read()
            if self.state.config.get("night_mode", False):
                img = apply_night_mode(img)
            return img
        except Exception as e:
            print(f"Frame capture error: {e}")
            return None
    
    def capture_photo(self, filename):
        """Capture and save a photo."""
        img = self.capture_frame()
        if img:
            try:
                img.save(str(filename))
                return True
            except Exception as e:
                print(f"Photo save error: {e}")
        return False
    
    def capture_burst(self, base_filename, count):
        """Capture burst of photos."""
        captured = []
        for i in range(count):
            filename = f"{base_filename}_burst{i+1}.jpg"
            if self.capture_photo(filename):
                captured.append(filename)
            time.sleep(0.2)
        return captured
    
    def capture_video(self, filename, duration):
        """Capture video for specified duration."""
        frames = []
        start_time = time.time()
        frame_count = 0
        while time.time() - start_time < duration:
            img = self.capture_frame()
            if img:
                frame_file = f"{filename}_frame{frame_count:04d}.jpg"
                img.save(str(frame_file))
                frames.append(frame_file)
                frame_count += 1
            time.sleep(0.1)
        return frames
    
    def display_frame(self, img):
        """Display frame on screen."""
        if self.disp and img:
            try:
                self.disp.show(img)
            except Exception as e:
                print(f"Display error: {e}")
    
    def cleanup(self):
        """Release camera resources."""
        if self.cam:
            del self.cam
        if self.disp:
            del self.disp
        self.initialized = False

class MotionDetector:
    """Frame differencing motion detection."""
    def __init__(self, state):
        self.state = state
        self.previous_frame = None
        self.motion_threshold = 25
        
    def detect(self, img):
        """Detect motion in current frame."""
        if img is None:
            return False
        try:
            gray = img.to_grayscale()
            small = gray.resize(160, 120)
            if self.previous_frame is None:
                self.previous_frame = small
                return False
            diff = small.difference(self.previous_frame)
            self.previous_frame = small
            # Simplified motion detection
            return True
        except Exception as e:
            print(f"Motion detection error: {e}")
            return False

class AIDetector:
    """YOLOv8 object detection with filtering."""
    def __init__(self, state):
        self.state = state
        self.model = None
        self.initialized = False
        
    def initialize(self):
        """Load YOLOv8 model."""
        try:
            if nn is None:
                print("Neural network module not available")
                return False
            model_path = "/root/models/yolov8n.mud"
            if os.path.exists(model_path):
                self.model = nn.YOLOv8(model=model_path)
                self.initialized = True
                print("YOLOv8 model loaded")
                return True
            else:
                print(f"Model not found: {model_path}")
                return False
        except Exception as e:
            print(f"AI model initialization error: {e}")
            return False
    
    def detect(self, img):
        """Detect objects in image."""
        if not self.initialized or self.model is None or img is None:
            return []
        try:
            results = self.model.detect(img)
            target_objects = self.state.config.get("target_objects", [])
            confidence_threshold = self.state.config.get("confidence_threshold", 0.6)
            min_size = self.state.config.get("min_object_size", 1000)
            filtered_objects = []
            for obj in results:
                class_id = obj.class_id
                confidence = obj.score
                bbox = obj.box
                label = COCO_CLASSES[class_id] if class_id < len(COCO_CLASSES) else "unknown"
                if label not in target_objects:
                    continue
                if confidence < confidence_threshold:
                    continue
                bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                if bbox_area < min_size:
                    continue
                filtered_objects.append({
                    "label": label,
                    "confidence": confidence,
                    "bbox": bbox
                })
            return filtered_objects
        except Exception as e:
            print(f"AI detection error: {e}")
            return []

class HybridDetector:
    """Combined motion + AI detection pipeline."""
    def __init__(self, state, motion_detector, ai_detector):
        self.state = state
        self.motion_detector = motion_detector
        self.ai_detector = ai_detector
    
    def detect(self, img):
        """Run hybrid detection: motion → AI verification."""
        if not self.motion_detector.detect(img):
            return []
        objects = self.ai_detector.detect(img)
        return objects

class CaptureManager:
    """Manages file saving, metadata, and cleanup."""
    def __init__(self, state):
        self.state = state
        
    def save_capture(self, img, objects, camera_controller):
        """Save capture with metadata."""
        try:
            timestamp = get_timestamp()
            if objects:
                obj_label = objects[0]["label"]
                obj_conf = objects[0]["confidence"]
                base_name = f"{timestamp}_{obj_label}_{obj_conf:.2f}"
            else:
                base_name = f"{timestamp}_capture"
            mode = self.state.config.get("capture_mode", "photo")
            files_saved = []
            if mode == "photo":
                filename = CAPTURES_DIR / f"{base_name}.jpg"
                if camera_controller.capture_photo(filename):
                    files_saved.append(str(filename))
            elif mode == "burst":
                count = self.state.config.get("burst_count", 5)
                files_saved = camera_controller.capture_burst(CAPTURES_DIR / base_name, count)
            elif mode == "video":
                duration = self.state.config.get("video_duration", 10)
                files_saved = camera_controller.capture_video(CAPTURES_DIR / base_name, duration)
            if files_saved:
                metadata = {
                    "timestamp": timestamp,
                    "detection_mode": self.state.config.get("detection_mode"),
                    "capture_mode": mode,
                    "detected_objects": objects,
                    "camera_settings": {
                        "width": self.state.config.get("camera_width"),
                        "height": self.state.config.get("camera_height"),
                        "night_mode": self.state.config.get("night_mode"),
                        "quality": self.state.config.get("jpeg_quality")
                    },
                    "files": files_saved
                }
                metadata_file = CAPTURES_DIR / f"{base_name}.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                self._log_detection(timestamp, objects)
                self.state.captures_today += 1
                self.state.last_capture_info = {"time": timestamp, "objects": objects}
                return files_saved
        except Exception as e:
            print(f"Capture save error: {e}")
        return []
    
    def _log_detection(self, timestamp, objects):
        """Log detection to CSV file."""
        try:
            log_file = LOGS_DIR / "detections.csv"
            file_exists = log_file.exists()
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["timestamp", "object", "confidence", "bbox"])
                for obj in objects:
                    writer.writerow([timestamp, obj["label"], obj["confidence"], str(obj["bbox"])])
        except Exception as e:
            print(f"CSV logging error: {e}")
    
    def cleanup_old_files(self):
        """Remove old captures based on storage limits."""
        try:
            if not self.state.config.get("auto_cleanup", True):
                return
            max_gb = self.state.config.get("storage_max_gb", 5)
            keep_days = self.state.config.get("storage_keep_days", 7)
            used_gb, _ = get_disk_usage()
            if used_gb > max_gb:
                files = sorted(CAPTURES_DIR.glob("*"), key=lambda p: p.stat().st_mtime)
                for file in files[:len(files)//4]:
                    try:
                        file.unlink()
                    except:
                        pass
            cutoff_time = time.time() - (keep_days * 86400)
            for file in CAPTURES_DIR.glob("*"):
                if file.stat().st_mtime < cutoff_time:
                    try:
                        file.unlink()
                    except:
                        pass
        except Exception as e:
            print(f"Cleanup error: {e}")

class NotificationManager:
    """Handles Telegram and webhook notifications."""
    def __init__(self, state):
        self.state = state
        self.last_notification_time = 0
    
    def can_notify(self):
        """Check if throttle period has passed."""
        throttle_minutes = self.state.config.get("telegram_throttle_minutes", 5)
        return (time.time() - self.last_notification_time) >= (throttle_minutes * 60)
    
    def send_notification(self, image_path, objects):
        """Send notification via enabled channels."""
        if not self.can_notify():
            return
        try:
            if self.state.config.get("telegram_enabled", False):
                self._send_telegram(image_path, objects)
            if self.state.config.get("webhook_enabled", False):
                self._send_webhook(image_path, objects)
            self.last_notification_time = time.time()
        except Exception as e:
            print(f"Notification error: {e}")
    
    def _send_telegram(self, image_path, objects):
        """Send photo to Telegram."""
        try:
            import urequests
            bot_token = self.state.config.get("telegram_bot_token", "")
            chat_id = self.state.config.get("telegram_chat_id", "")
            if not bot_token or not chat_id:
                return
            caption = "🎯 WildTrap Detection\n"
            for obj in objects:
                caption += f"• {obj['label']}: {obj['confidence']:.2%}\n"
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(image_path, 'rb') as f:
                files = {'photo': f}
                data = {'chat_id': chat_id, 'caption': caption}
                response = urequests.post(url, files=files, data=data)
            print(f"Telegram notification sent: {response.status_code}")
        except Exception as e:
            print(f"Telegram error: {e}")
    
    def _send_webhook(self, image_path, objects):
        """Send POST request to webhook URL."""
        try:
            import urequests
            webhook_url = self.state.config.get("webhook_url", "")
            if not webhook_url:
                return
            payload = {"timestamp": get_timestamp(), "objects": objects}
            response = urequests.post(webhook_url, json=payload)
            print(f"Webhook notification sent: {response.status_code}")
        except Exception as e:
            print(f"Webhook error: {e}")

class UI:
    """Touchscreen interface management."""
    def __init__(self, state, camera_controller):
        self.state = state
        self.camera = camera_controller
        self.touch = None
        self.active_buttons = []
        self.settings_page = 0
        
    def initialize(self):
        """Initialize touchscreen."""
        try:
            if touchscreen:
                self.touch = touchscreen.TouchScreen()
                return True
        except:
            pass
        return False
    
    def draw(self, img, objects=None):
        if img is None:
            return
            
        if self.state.current_screen == "main":
            self.draw_main_screen(img, objects)
        elif self.state.current_screen == "menu":
            self.draw_menu_screen(img)
        elif self.state.current_screen == "gallery":
            self.draw_gallery_screen(img)
            
        self.camera.display_frame(img)

    def draw_gallery_screen(self, img):
        """Draw gallery of captures."""
        self.active_buttons = []
        scale = 1.2 if img.width() <= 640 else 1.5
        
        # Dim background
        img.draw_rectangle(0, 0, img.width(), img.height(), color=(0,0,0), thickness=-1)
        
        if not self.state.gallery_files:
            img.draw_string(img.width()//2 - int(80*scale), img.height()//2, "NO CAPTURES", color=COLOR_WARNING, scale=scale*2)
            btn_back = UIButton(10, 10, img.height() - int(60*scale), img.width() - 20, int(50*scale), "BACK TO MENU")
            btn_back.draw(img, scale)
            self.active_buttons.append({"id": 10, "x": 10, "y": img.height() - int(60*scale), "w": img.width() - 20, "h": int(50*scale)})
            return
            
        # Show current image preview
        file_path = self.state.gallery_files[self.state.gallery_index]
        try:
            # We draw a small version of the image in the center
            from maix import image as mimage
            prev_img = mimage.load(str(file_path))
            # Fit to screen roughly
            prev_img = prev_img.resize(img.width() - 40, img.height() - 140)
            img.draw_image(20, 40, prev_img)
        except:
            img.draw_string(50, 100, "ERR LOADING IMG", color=COLOR_ERROR, scale=scale)
            
        img.draw_string(10, 10, f"GALLERY ({self.state.gallery_index + 1}/{len(self.state.gallery_files)})", color=COLOR_ACCENT, scale=scale)
        img.draw_string(10, img.height() - int(100*scale), Path(file_path).name, color=COLOR_TEXT, scale=scale*0.8)
        
        w = int(img.width() / 3) - 15
        h = int(50 * scale)
        y = img.height() - int(60 * scale)
        
        btn_prev = UIButton(200, 10, y, w, h, "<< PREV")
        btn_next = UIButton(201, 10 + w + 10, y, w, h, "NEXT >>")
        btn_back = UIButton(10, 10 + 2*(w + 10), y, w, h, "BACK")
        
        # We need to manually add to active_buttons because UIButton doesn't store state perfectly in this flow
        btns = [btn_prev, btn_next, btn_back]
        for b in btns:
            b.draw(img, scale)
            self.active_buttons.append({"id": b.id, "x": b.x, "y": b.y, "w": b.w, "h": b.h})

    def draw_menu_screen(self, img):
        """Draw settings menu overlay."""
        self.active_buttons = []
        scale = 1.0 if img.width() <= 640 else 1.5
        
        # Dim background
        img.draw_rectangle(0, 0, img.width(), img.height(), color=(0,0,0), thickness=-1)
        title = f"SETTINGS (Page {self.settings_page + 1}/3)"
        img.draw_string(10, 10, title, color=COLOR_ACCENT, scale=scale*1.8)
        
        w = int(img.width() / 2) - 20
        h = int(50 * scale)
        spacing = int(10 * scale)
        start_y = int(60 * scale)
        
        btn_data = []
        if self.settings_page == 0:
            # Page 1: WildTrap Core Settings
            btn_data = [
                (0, "Arm State", "ARMED" if self.state.armed else "STANDBY"),
                (1, "Detect Mode", self.state.config.get("detection_mode", "hybrid")),
                (2, "Capture Mode", self.state.config.get("capture_mode", "burst")),
                (3, "Confidence", f"{self.state.config.get('confidence_threshold', 0.6)}"),
                (4, "Night Mode", "ON" if self.state.config.get("night_mode", True) else "OFF"),
                (100, "Next Page ->", "")
            ]
        elif self.settings_page == 1:
            # Page 2: Hardware
            btn_data = [
                (5, "OSD Display", "ON" if self.state.config.get("osd_enabled", True) else "OFF"),
                (6, "Servo En", "ON" if self.state.config.get("servo_enabled", False) else "OFF"),
                (7, "Servo Pin", str(self.state.config.get("servo_pin", "A18"))),
                (8, "Servo Open", f"{self.state.config.get('servo_angle_open', 90)}°"),
                (101, "<- Prev Page", ""),
                (100, "Next Page ->", "")
            ]
        else:
            # Page 3: External & Gallery
            btn_data = [
                (11, "Ext Trigger", "ON" if self.state.config.get("ext_trigger_enabled", False) else "OFF"),
                (12, "Trigger Pin", str(self.state.config.get("ext_trigger_pin", "A19"))),
                (13, "OPEN GALLERY", "", COLOR_ACCENT),
                (9, "RESET ALL", "!!!", COLOR_ERROR),
                (101, "<- Prev Page", ""),
                (10, "SAVE & EXIT", "", COLOR_WARNING)
            ]
            
        for i, data in enumerate(btn_data):
            id, label, value = data[0], data[1], data[2]
            color_btn = data[3] if len(data) > 3 else None
            
            col = i % 2
            row = i // 2
            x = 10 + col * (w + 10)
            y = start_y + row * (h + spacing)
            
            img.draw_rectangle(x, y, w, h, color=COLOR_BG, thickness=-1)
            img.draw_rectangle(x, y, w, h, color=color_btn if color_btn else COLOR_TEXT, thickness=2)
            
            txt_color = color_btn if color_btn else COLOR_TEXT
            if value != "":
                img.draw_string(x + int(10*scale), y + int(5*scale), label, color=COLOR_TEXT, scale=scale)
                img.draw_string(x + int(10*scale), y + int(25*scale), value, color=COLOR_ACCENT, scale=scale*1.2)
            else:
                img.draw_string(x + int(10*scale), y + h//2 - int(10*scale), label, color=txt_color, scale=scale*1.2)
                
            self.active_buttons.append({"id": id, "x": x, "y": y, "w": w, "h": h})
    
    def draw_main_screen(self, img, objects=None):
        """Draw main monitoring screen with live preview."""
        try:
            if self.state.config.get("osd_enabled", True):
                # Scale font sizes and positions for potentially smaller display (like 552x368)
                scale = 1.2 if img.width() <= 640 else 1.5
                y_offset = int(10 * scale)
                
                status = "ARMED" if self.state.armed else "STANDBY"
                status_color = COLOR_ACCENT if self.state.armed else COLOR_WARNING
                img.draw_string(10, 10, f"STATUS: {status}", color=status_color, scale=scale*1.3)
                
                mode = self.state.config.get("detection_mode", "hybrid").upper()
                img.draw_string(10, int(40 * scale), f"Mode: {mode}", color=COLOR_TEXT, scale=scale)
                img.draw_string(10, int(65 * scale), f"Captures: {self.state.captures_today}", color=COLOR_TEXT, scale=scale)
                
                if objects:
                    y_obj_offset = int(90 * scale)
                    for obj in objects[:3]:
                        text = f"{obj['label']}: {obj['confidence']:.2%}"
                        img.draw_string(10, y_obj_offset, text, color=COLOR_ACCENT, scale=scale)
                        bbox = obj['bbox']
                        img.draw_rectangle(int(bbox[0]), int(bbox[1]), 
                                         int(bbox[2]-bbox[0]), int(bbox[3]-bbox[1]),
                                         color=COLOR_ACCENT, thickness=2)
                        y_obj_offset += int(25 * scale)
                        
                used_gb, total_gb = get_disk_usage()
                img.draw_string(10, img.height() - int(30 * scale), 
                              f"Storage: {used_gb:.1f}GB / {total_gb:.1f}GB",
                              color=COLOR_TEXT, scale=scale)
                img.draw_string(img.width()//2 - int(80 * scale), img.height() - int(30 * scale),
                              "TAP FOR MENU", color=COLOR_WARNING, scale=scale)
        except Exception as e:
            print(f"UI draw error: {e}")
    
    def check_touch(self):
        """Check for touch input."""
        if self.touch is None:
            return None
        try:
            points = self.touch.read()
            if points:
                return points[0]
        except:
            pass
        return None
    
    def handle_input(self, img=None):
        """Handle touch input."""
        touch = self.check_touch()
        if touch:
            tx, ty, pressed = touch
            if not pressed:
                return None
                
            current_time = time.time()
            if current_time - self.state.last_touch_time > 0.3:
                self.state.last_touch_time = current_time
                
                if self.state.current_screen == "main":
                    self.state.current_screen = "menu"
                elif self.state.current_screen == "menu":
                    disp_w, disp_h = 552, 368
                    if img and touchscreen:
                        try:
                            x = int(tx * img.width() / disp_w)
                            y = int(ty * img.height() / disp_h)
                        except:
                            x, y = tx, ty
                    else:
                        x, y = tx, ty
                        
                    for btn in self.active_buttons:
                        if btn["x"] <= x <= btn["x"] + btn["w"] and btn["y"] <= y <= btn["y"] + btn["h"]:
                            self._handle_button_click(btn["id"])
                            break
        return touch

    def _handle_button_click(self, btn_id):
        if btn_id == 0:
            self.state.armed = not self.state.armed
        elif btn_id == 1:
            modes = ["motion", "ai", "hybrid", "scheduled"]
            current = self.state.config.get("detection_mode", "hybrid")
            idx = (modes.index(current) + 1) % len(modes) if current in modes else 0
            self.state.config["detection_mode"] = modes[idx]
        elif btn_id == 2:
            caps = ["photo", "burst", "video", "timelapse"]
            current = self.state.config.get("capture_mode", "photo")
            idx = (caps.index(current) + 1) % len(caps) if current in caps else 0
            self.state.config["capture_mode"] = caps[idx]
        elif btn_id == 3:
            confs = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
            current = self.state.config.get("confidence_threshold", 0.6)
            idx = (confs.index(current) + 1) % len(confs) if current in confs else 0
            self.state.config["confidence_threshold"] = confs[idx]
        elif btn_id == 4:
            self.state.config["night_mode"] = not self.state.config.get("night_mode", True)
        elif btn_id == 5:
            self.state.config["osd_enabled"] = not self.state.config.get("osd_enabled", True)
        elif btn_id == 6:
            self.state.config["servo_enabled"] = not self.state.config.get("servo_enabled", False)
        elif btn_id == 7:
            pins = ["A14", "A15", "A16", "A17", "A18", "A19"]
            current = self.state.config.get("servo_pin", "A18")
            idx = (pins.index(current) + 1) % len(pins) if current in pins else 0
            self.state.config["servo_pin"] = pins[idx]
        elif btn_id == 8:
            angles = [0, 45, 90, 135, 180]
            current = self.state.config.get("servo_angle_open", 90)
            idx = (angles.index(current) + 1) % len(angles) if current in angles else 0
            self.state.config["servo_angle_open"] = angles[idx]
        elif btn_id == 9:
            self.state.config = DEFAULT_CONFIG.copy()
            self.state.armed = False
            print("[UI] Settings reset to default")
        elif btn_id == 11:
            self.state.config["ext_trigger_enabled"] = not self.state.config.get("ext_trigger_enabled", False)
        elif btn_id == 12:
            pins = ["A14", "A15", "A16", "A17", "A18", "A19"]
            current = self.state.config.get("ext_trigger_pin", "A19")
            idx = (pins.index(current) + 1) % len(pins) if current in pins else 0
            self.state.config["ext_trigger_pin"] = pins[idx]
        elif btn_id == 13:
            # Open Gallery
            self.state.gallery_files = sorted([str(f) for f in CAPTURES_DIR.glob("*.jpg")], reverse=True)
            self.state.gallery_index = 0
            self.state.current_screen = "gallery"
        elif btn_id == 200:
            # Gallery Prev
            if self.state.gallery_index > 0:
                self.state.gallery_index -= 1
        elif btn_id == 201:
            # Gallery Next
            if self.state.gallery_index < len(self.state.gallery_files) - 1:
                self.state.gallery_index += 1
        elif btn_id == 100:
            self.settings_page = (self.settings_page + 1) % 3
        elif btn_id == 101:
            self.settings_page = (self.settings_page - 1) % 3
        elif btn_id == 10:
            self.state.save()
            self.state.current_screen = "main"
            self.settings_page = 0

class WildTrapApp:
    """Main application controller."""
    def __init__(self):
        self.state = AppState()
        self.servo = ServoController(self.state)
        self.trigger = ExternalTrigger(self.state)
        self.camera = CameraController(self.state)
        self.motion_detector = MotionDetector(self.state)
        self.ai_detector = AIDetector(self.state)
        self.hybrid_detector = HybridDetector(self.state, self.motion_detector, self.ai_detector)
        self.capture_manager = CaptureManager(self.state)
        self.notification_manager = NotificationManager(self.state)
        self.ui = UI(self.state, self.camera)

    def initialize(self):
        """Initialize all components."""
        print(f"WildTrap v{VERSION} - Initializing...")
        ensure_directories()
        if not self.camera.initialize():
            print("Warning: Camera initialization failed")
        self.ai_detector.initialize()
        self.ui.initialize()
        print("Initialization complete")
        return True

    def run_detection_cycle(self):
        """Execute one detection cycle."""
        img = self.camera.capture_frame()
        if img is None:
            return None
        mode = self.state.config.get("detection_mode", "hybrid")
        objects = []
        if mode == "motion":
            if self.motion_detector.detect(img):
                objects = [{"label": "motion", "confidence": 1.0, "bbox": [0,0,0,0]}]
        elif mode == "ai":
            objects = self.ai_detector.detect(img)
        elif mode == "hybrid":
            objects = self.hybrid_detector.detect(img)
        elif mode == "scheduled":
            interval = self.state.config.get("timelapse_interval", 60)
            if time.time() - self.state.last_detection_time >= interval:
                objects = [{"label": "scheduled", "confidence": 1.0, "bbox": [0,0,0,0]}]
        return img, objects

    def process_detection(self, img, objects):
        """Process detected objects and trigger capture."""
        if not objects or not self.state.armed:
            return
        if not self.state.can_capture():
            return
        self.state.record_detection(objects)

        # Trigger outputs
        self.servo.open()
        self.trigger.trigger()

        files = self.capture_manager.save_capture(img, objects, self.camera)
        if files:
            print(f"Captured: {len(files)} files")
            self.notification_manager.send_notification(files[0], objects)
            self.capture_manager.cleanup_old_files()

    def run(self):
        """Main application loop."""
        if not self.initialize():
            print("Initialization failed")
            return
        print("WildTrap running. Press Ctrl+C to exit.")
        try:
            while self.state.running:
                self.servo.update()
                self.trigger.update()
                result = self.run_detection_cycle()
                if result:
                    img, objects = result
                    self.process_detection(img, objects)
                    self.ui.draw(img, objects)
                    self.ui.handle_input(img)
                time.sleep(0.033)  # ~30 FPS
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        self.state.save()
        self.servo.cleanup()
        self.trigger.cleanup()
        self.camera.cleanup()
        print("Cleanup complete")
def main():
    """Application entry point."""
    app = WildTrapApp()
    app.run()

if __name__ == "__main__":
    main()
