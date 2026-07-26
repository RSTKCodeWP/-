# 📚 Examples & Use Cases

## Real-World Applications

### 1. Automatic Pet Feeder

Открывает кормушку когда видит кошку или собаку.

**Configuration:**
```json
{
  "detection_mode": "object",
  "object_preset": "cat",
  "confidence_threshold": 0.6,
  "close_delay": 15,
  "rearm_mode": true,
  "rearm_delay": 60,
  "servo_angle_open": 90,
  "servo_angle_close": 0
}
```

**Hardware Setup:**
- Servo attached to feeder door
- Camera positioned to see feeding area
- External 5V 2A power supply

**Tips:**
- Set `rearm_delay` to 60+ seconds to prevent overfeeding
- Use `confidence_threshold` 0.6-0.7 to avoid false triggers
- Position camera 1-2 meters from feeding area

---

### 2. Color-Based Sorting System

Сортирует объекты по цвету, открывая заслонку для определенного цвета.

**Configuration:**
```json
{
  "detection_mode": "color",
  "color_preset": "Red",
  "min_area": 800,
  "close_delay": 3,
  "rearm_mode": true,
  "rearm_delay": 1,
  "camera_width": 640,
  "camera_height": 480
}
```

**Workflow:**
1. Calibrate for target color using touchscreen
2. Position camera above conveyor/chute
3. Servo opens gate when color detected
4. Quick rearm (1s) for continuous operation

**Multiple Colors:**
```python
# Modify code to cycle through colors
color_sequence = ["Red", "Green", "Blue"]
current_color_idx = 0

# On detection, switch to next color
if detected:
    current_color_idx = (current_color_idx + 1) % len(color_sequence)
    state.config["color_preset"] = color_sequence[current_color_idx]
```

---

### 3. Motion-Activated Security System

Срабатывает при обнаружении движения, может управлять сигнализацией или камерой.

**Configuration:**
```json
{
  "detection_mode": "motion",
  "motion_sensitivity": 45,
  "close_delay": 5,
  "rearm_mode": true,
  "rearm_delay": 2,
  "repeat_trigger": false
}
```

**Enhanced Version with Logging:**
```python
import time

motion_log = []

def log_motion_event():
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    motion_log.append(timestamp)
    
    # Save to file
    with open("/root/motion_log.txt", "a") as f:
        f.write(f"{timestamp} - Motion detected\n")
    
    # Keep only last 100 events in memory
    if len(motion_log) > 100:
        motion_log.pop(0)

# In main loop, after detection:
if detected and not state.servo_opened:
    log_motion_event()
    servo.open()
```

---

### 4. People Counter

Считает количество людей, проходящих через дверь.

**Configuration:**
```json
{
  "detection_mode": "object",
  "object_preset": "person",
  "confidence_threshold": 0.65,
  "close_delay": 2,
  "rearm_mode": true,
  "rearm_delay": 3,
  "camera_width": 640,
  "camera_height": 480
}
```

**Counter Implementation:**
```python
people_count = 0
last_count_time = 0

def count_person():
    global people_count, last_count_time
    current_time = time.time()
    
    # Debounce: only count if 3+ seconds since last count
    if current_time - last_count_time >= 3:
        people_count += 1
        last_count_time = current_time
        
        # Save count
        with open("/root/people_count.txt", "w") as f:
            f.write(str(people_count))
        
        print(f"Total people: {people_count}")

# In main loop:
if detected and not state.servo_opened and state.armed:
    count_person()
    servo.open()
```

**Display Counter on Screen:**
```python
# In UI drawing:
img.draw_string(10, 200, f"Count: {people_count}", 
               color=image.Color.from_rgb(0, 255, 255), scale=3)
```

---

### 5. Automatic Door Opener

Открывает дверь при обнаружении человека.

**Configuration:**
```json
{
  "detection_mode": "object",
  "object_preset": "person",
  "confidence_threshold": 0.6,
  "close_delay": 10,
  "rearm_mode": true,
  "rearm_delay": 5,
  "servo_angle_open": 180,
  "servo_angle_close": 0
}
```

**Safety Features:**
```python
# Add safety timeout - keep door open if person still present
def safe_door_control(detected):
    if detected:
        # Person detected, keep door open
        if not state.servo_opened:
            servo.open()
        # Reset close timer
        state.open_time = time.time()
    else:
        # No person, allow normal close after delay
        if state.servo_opened:
            elapsed = time.time() - state.open_time
            if elapsed >= state.config["close_delay"]:
                servo.close()
```

---

### 6. Gesture-Controlled System

Использует детекцию объектов для распознавания жестов (например, поднятая рука).

**Configuration:**
```json
{
  "detection_mode": "object",
  "object_preset": "person",
  "confidence_threshold": 0.5,
  "close_delay": 5,
  "rearm_mode": true,
  "rearm_delay": 2
}
```

**Gesture Detection (Advanced):**
```python
def detect_gesture(detections):
    """
    Detect raised hand gesture by checking person position
    """
    for obj in detections:
        x, y, w, h = obj.x, obj.y, obj.w, obj.h
        
        # Check if detection is in upper half of frame
        # (indicates raised hand/arm)
        if y < img.height() // 3:
            return True
    
    return False

# In main loop:
detected, detections = object_detector.detect(img)
if detect_gesture(detections):
    servo.open()
```

---

### 7. Wildlife Camera Trigger

Срабатывает при обнаружении животных для фотосъемки.

**Configuration:**
```json
{
  "detection_mode": "object",
  "object_preset": "bird",
  "confidence_threshold": 0.5,
  "close_delay": 2,
  "rearm_mode": true,
  "rearm_delay": 10,
  "camera_width": 1280,
  "camera_height": 720
}
```

**Photo Capture:**
```python
import os

photo_count = 0

def capture_photo(img):
    global photo_count
    photo_count += 1
    
    filename = f"/root/wildlife_{photo_count:04d}.jpg"
    img.save(filename)
    print(f"Saved: {filename}")

# In main loop:
if detected and not state.servo_opened:
    capture_photo(img)
    servo.open()
```

**Supported Animals (COCO dataset):**
- bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe

---

### 8. Quality Control System

Проверяет наличие дефектов по цвету или форме.

**Configuration:**
```json
{
  "detection_mode": "color",
  "color_preset": "Custom",
  "min_area": 1000,
  "close_delay": 2,
  "rearm_mode": true,
  "rearm_delay": 1,
  "camera_width": 1280,
  "camera_height": 720
}
```

**Defect Detection:**
```python
good_count = 0
defect_count = 0

def check_quality(blobs):
    """
    Check if detected object meets quality criteria
    """
    if not blobs:
        return False
    
    largest = max(blobs, key=lambda b: b[2] * b[3])
    area = largest[2] * largest[3]
    
    # Check size criteria
    if area < 800 or area > 5000:
        return False  # Defect: wrong size
    
    # Check shape (aspect ratio)
    aspect_ratio = largest[2] / largest[3]
    if aspect_ratio < 0.8 or aspect_ratio > 1.2:
        return False  # Defect: wrong shape
    
    return True  # Good

# In main loop:
detected, blobs = color_detector.detect(img)
if detected:
    if check_quality(blobs):
        good_count += 1
        # Don't trigger servo (let it pass)
    else:
        defect_count += 1
        servo.open()  # Reject defect
```

---

### 9. Parking Space Monitor

Определяет занятость парковочного места.

**Configuration:**
```json
{
  "detection_mode": "object",
  "object_preset": "car",
  "confidence_threshold": 0.7,
  "close_delay": 60,
  "rearm_mode": false,
  "camera_width": 640,
  "camera_height": 480
}
```

**Status Tracking:**
```python
parking_occupied = False
occupation_time = 0

def update_parking_status(detected):
    global parking_occupied, occupation_time
    
    if detected and not parking_occupied:
        # Car arrived
        parking_occupied = True
        occupation_time = time.time()
        print("Parking: OCCUPIED")
    
    elif not detected and parking_occupied:
        # Car left
        duration = time.time() - occupation_time
        parking_occupied = False
        print(f"Parking: FREE (occupied for {duration/60:.1f} min)")

# Display status:
status = "OCCUPIED" if parking_occupied else "FREE"
color = image.Color.from_rgb(255, 0, 0) if parking_occupied else image.Color.from_rgb(0, 255, 0)
img.draw_string(10, 10, f"Parking: {status}", color=color, scale=3)
```

---

### 10. Interactive Art Installation

Реагирует на присутствие людей для интерактивного искусства.

**Configuration:**
```json
{
  "detection_mode": "motion",
  "motion_sensitivity": 50,
  "close_delay": 5,
  "rearm_mode": true,
  "rearm_delay": 2,
  "repeat_trigger": true,
  "repeat_interval": 3
}
```

**Multi-Servo Choreography:**
```python
import math

def create_wave_pattern(t):
    """
    Create wave pattern across multiple servos
    """
    servos = [servo1, servo2, servo3]  # Multiple servos
    
    for i, servo in enumerate(servos):
        # Phase shift for wave effect
        phase = i * (2 * math.pi / len(servos))
        angle = 90 + 45 * math.sin(t + phase)
        
        duty = 2.5 + (angle / 180.0) * 10.0
        servo.duty(duty)

# In main loop:
if detected:
    t = time.time()
    create_wave_pattern(t)
```

---

## Integration Examples

### 1. MQTT Integration

Отправка событий в MQTT брокер.

```python
import socket
import json

def send_mqtt_event(event_type, data):
    """
    Simple MQTT publish (requires paho-mqtt or similar)
    """
    try:
        # Simplified - use proper MQTT library in production
        message = json.dumps({
            "event": event_type,
            "timestamp": time.time(),
            "data": data
        })
        
        # Send to MQTT broker
        # mqtt_client.publish("maixcam/servo", message)
        print(f"MQTT: {message}")
    except Exception as e:
        print(f"MQTT error: {e}")

# In main loop:
if detected and not state.servo_opened:
    send_mqtt_event("detection", {
        "mode": state.config["detection_mode"],
        "target": state.config.get("color_preset") or state.config.get("object_preset")
    })
    servo.open()
```

### 2. HTTP API Integration

Отправка данных на веб-сервер.

```python
import urequests  # MicroPython HTTP library

def send_http_event(event_data):
    """
    Send event to HTTP endpoint
    """
    try:
        url = "http://your-server.com/api/events"
        headers = {"Content-Type": "application/json"}
        
        response = urequests.post(url, json=event_data, headers=headers)
        print(f"HTTP: {response.status_code}")
        response.close()
    except Exception as e:
        print(f"HTTP error: {e}")

# Usage:
if detected:
    send_http_event({
        "device": "maixcam-01",
        "event": "detection",
        "timestamp": time.time()
    })
```

### 3. Database Logging

Сохранение событий в локальную базу данных.

```python
import sqlite3

# Initialize database
conn = sqlite3.connect("/root/events.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        event_type TEXT,
        detection_mode TEXT,
        target TEXT
    )
""")
conn.commit()

def log_event(event_type, detection_mode, target):
    """
    Log event to database
    """
    cursor.execute("""
        INSERT INTO events (timestamp, event_type, detection_mode, target)
        VALUES (?, ?, ?, ?)
    """, (time.time(), event_type, detection_mode, target))
    conn.commit()

# Usage:
if detected:
    log_event("detection", 
              state.config["detection_mode"],
              state.config.get("color_preset") or state.config.get("object_preset"))
```

---

## Performance Optimization Examples

### 1. Frame Skipping for Higher FPS

```python
frame_skip = 2  # Process every 2nd frame
frame_counter = 0

while not app.need_exit():
    img = cam.read()
    frame_counter += 1
    
    # Only process every Nth frame
    if frame_counter % frame_skip == 0:
        detected, detections = detector.detect(img)
        servo.update(detected)
    
    # Always display
    ui.draw_osd(img, detected, detections)
    disp.show(img)
```

### 2. Region of Interest (ROI) Processing

```python
# Only process center region for faster detection
roi_x = img.width() // 4
roi_y = img.height() // 4
roi_w = img.width() // 2
roi_h = img.height() // 2

# Crop to ROI
roi_img = img.crop(roi_x, roi_y, roi_w, roi_h)

# Detect in ROI only
detected, detections = detector.detect(roi_img)

# Adjust detection coordinates back to full frame
for det in detections:
    det.x += roi_x
    det.y += roi_y
```

### 3. Adaptive Resolution

```python
# Lower resolution when no detection, higher when detected
def adaptive_resolution(detected):
    if detected:
        # High resolution for accurate tracking
        return 640, 480
    else:
        # Low resolution for fast scanning
        return 320, 240

# Reinitialize camera with new resolution
current_res = (640, 480)
new_res = adaptive_resolution(detected)

if new_res != current_res:
    cam.close()
    cam = camera.Camera(new_res[0], new_res[1], image.Format.FMT_RGB888)
    current_res = new_res
```

---

## Tips & Best Practices

### 1. Lighting Optimization
- Use consistent lighting for color detection
- Avoid backlighting (light behind object)
- Add LED ring light around camera for best results

### 2. Camera Positioning
- Position camera perpendicular to detection area
- Maintain consistent distance (1-3 meters optimal)
- Avoid reflective surfaces in view

### 3. Power Management
- Use external 5V 2A+ power supply for reliability
- Add 470µF capacitor across servo power for stability
- Consider battery backup for critical applications

### 4. Error Handling
```python
try:
    detected, detections = detector.detect(img)
except Exception as e:
    print(f"Detection error: {e}")
    detected = False
    detections = []
```

### 5. Configuration Backup
```python
import shutil

def backup_config():
    shutil.copy(CONFIG_FILE, CONFIG_FILE + ".backup")

# Backup before saving new config
backup_config()
state.save_config()
```

---

## Community Contributions

Have a cool use case? Share it!

1. Fork the repository
2. Add your example to this file
3. Submit a pull request

**Template:**
```markdown
### Your Use Case Name

Brief description.

**Configuration:**
```json
{
  // Your config
}
```

**Implementation:**
```python
# Your code
```

**Tips:**
- Tip 1
- Tip 2
```

---

**More examples coming soon!** Check the [GitHub repository](https://github.com/bobberdolle1/maixcam-servo-control) for updates.
