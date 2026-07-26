# 🔧 Technical Documentation

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Application                         │
│                  (advanced_servo_app.py)                     │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐     ┌──────────────┐
│   Camera     │      │  Detection   │     │    Servo     │
│   Module     │──────▶   Engines    │────▶│  Controller  │
└──────────────┘      └──────────────┘     └──────────────┘
        │                     │                     │
        │              ┌──────┴──────┐              │
        │              │             │              │
        ▼              ▼             ▼              ▼
┌──────────────┐  ┌────────┐  ┌────────┐   ┌──────────────┐
│   Display    │  │ Color  │  │ Object │   │   PWM/Pin    │
│   & Touch    │  │Detector│  │Detector│   │   Hardware   │
└──────────────┘  └────────┘  └────────┘   └──────────────┘
                       │             │
                       └──────┬──────┘
                              │
                       ┌──────────────┐
                       │   Motion     │
                       │   Detector   │
                       └──────────────┘
```

## Performance Optimization

### 1. Color Detection Optimization

#### LAB Color Space
- **Why LAB?** More perceptually uniform than RGB, better for varying lighting
- **Conversion:** Automatic in `find_blobs()` - no manual conversion needed
- **Threshold tuning:** Wide ranges (±25-30) for robustness

```python
# Optimized threshold calculation
l_min = max(0, int(l - 25))      # Prevent underflow
l_max = min(100, int(l + 25))    # Prevent overflow
a_min = max(-128, int(a - 30))   # A channel: -128 to 127
a_max = min(127, int(a + 30))
b_min = max(-128, int(b - 30))   # B channel: -128 to 127
b_max = min(127, int(b + 30))
```

#### Blob Detection Parameters
```python
blobs = img.find_blobs(
    threshold,
    pixels_threshold=min_area,  # Minimum pixels in blob
    area_threshold=min_area,    # Minimum bounding box area
    merge=True                  # Merge overlapping blobs
)
```

**Performance tips:**
- Higher `min_area` = faster processing (fewer blobs)
- `merge=True` reduces blob count, improves speed
- Typical values: 300-1000 depending on object size

### 2. Object Detection Optimization

#### YOLO Model Selection
- **yolov8n.mud** - Nano model, fastest, ~30 FPS @ 640x480
- **yolov8s.mud** - Small model, balanced, ~20 FPS @ 640x480
- **yolov8m.mud** - Medium model, accurate, ~10 FPS @ 640x480

#### Detection Parameters
```python
objs = model.detect(
    img,
    conf_th=0.5,    # Confidence threshold (0.0-1.0)
    iou_th=0.45     # IoU threshold for NMS
)
```

**Tuning guide:**
- `conf_th`: Lower = more detections, more false positives
- `conf_th`: Higher = fewer detections, more accurate
- `iou_th`: Controls overlapping box suppression
- Recommended: 0.4-0.6 for conf_th, 0.4-0.5 for iou_th

#### Performance vs Accuracy Trade-offs

| Resolution | Model  | FPS  | Accuracy | Use Case                |
|------------|--------|------|----------|-------------------------|
| 320x240    | yolov8n| ~60  | Medium   | Fast response needed    |
| 640x480    | yolov8n| ~30  | Good     | Balanced (default)      |
| 640x480    | yolov8s| ~20  | Better   | More accuracy needed    |
| 1280x720   | yolov8n| ~15  | Best     | Maximum quality         |

### 3. Motion Detection Optimization

#### Frame Differencing
```python
diff = img.difference(prev_frame)
stats = diff.get_statistics()
motion_detected = stats.l_mean() > sensitivity
```

**Sensitivity tuning:**
- Low (20-40): Detect large movements only
- Medium (40-60): Balanced (default: 50)
- High (60-80): Detect small movements

**Performance:**
- Fastest detection method (~60 FPS @ 640x480)
- No model loading required
- Minimal CPU usage

### 4. Camera Configuration

#### Resolution Impact
```python
# Resolution vs FPS (approximate on MaixCAM)
320x240   -> ~60 FPS (color), ~60 FPS (motion), ~40 FPS (object)
640x480   -> ~30 FPS (color), ~30 FPS (motion), ~20 FPS (object)
1280x720  -> ~15 FPS (color), ~15 FPS (motion), ~10 FPS (object)
```

#### Format Selection
```python
camera.Camera(width, height, image.Format.FMT_RGB888)
```
- **FMT_RGB888**: Best quality, required for YOLO
- **FMT_RGB565**: Faster, lower quality (not recommended for YOLO)

## Hardware Specifications

### PWM Configuration

#### Servo Control Timing
```python
# Standard servo: 50Hz (20ms period)
# Pulse width: 0.5ms (0°) to 2.5ms (180°)
# Duty cycle calculation:
duty = 2.5 + (angle / 180.0) * 10.0

# Examples:
# 0°   -> 2.5% duty  -> 0.5ms pulse
# 90°  -> 7.5% duty  -> 1.5ms pulse
# 180° -> 12.5% duty -> 2.5ms pulse
```

#### PWM Pin Mapping
```python
# MaixCAM PWM pins (verify with your board)
A18 -> PWM6  (default)
A19 -> PWM7
A20 -> PWM8
A21 -> PWM9
```

### Power Requirements

#### Servo Current Draw
- **Idle:** 10-20mA
- **Moving:** 100-300mA (depends on load)
- **Stall:** 500-800mA (avoid!)

#### Power Supply Recommendations
- **Minimum:** USB 5V 1A (may cause brownouts)
- **Recommended:** USB 5V 2A or external 5V 2A
- **Multiple servos:** External 5V 3-5A power supply

### Timing Characteristics

#### Servo Response Time
- **SG90:** ~0.1s per 60° (no load)
- **MG90S:** ~0.1s per 60° (no load)
- **With load:** Add 50-100% to response time

#### Detection Latency
```
Color Detection:  ~30ms (@ 30 FPS)
Object Detection: ~50ms (@ 20 FPS)
Motion Detection: ~30ms (@ 30 FPS)
Servo Response:   ~100-200ms
Total Latency:    ~130-250ms
```

## Software Architecture

### State Machine

```
┌─────────┐
│  ARMED  │◄─────────────────────┐
└────┬────┘                      │
     │                           │
     │ Detection                 │ Rearm
     │                           │
     ▼                           │
┌─────────┐                 ┌────┴────┐
│  OPEN   │────Timeout─────▶│ CLOSED  │
└─────────┘                 └─────────┘
     │                           ▲
     │ Repeat Trigger            │
     └───────────────────────────┘
```

### Configuration Management

#### Config File Structure
```json
{
  "servo_pin": "A18",           // Hardware config
  "pwm_id": 6,
  "servo_angle_open": 90,
  "servo_angle_close": 0,
  
  "close_delay": 10,            // Timing config
  "rearm_mode": true,
  "rearm_delay": 2,
  "repeat_trigger": false,
  "repeat_interval": 10,
  
  "detection_mode": "color",    // Detection config
  "color_preset": "Yellow",
  "object_preset": "person",
  "confidence_threshold": 0.5,
  "min_area": 500,
  "motion_sensitivity": 50,
  
  "camera_width": 640,          // Camera config
  "camera_height": 480,
  "fps_target": 30,
  
  "custom_threshold": [         // Custom color
    [50, 80, 0, 30, 40, 80]
  ]
}
```

#### Config Loading Priority
1. Load defaults from `DEFAULT_CONFIG`
2. Override with `/root/advanced_servo_config.json` if exists
3. Runtime changes via UI
4. Save on user request

### Memory Management

#### Typical Memory Usage
- **Base application:** ~50MB
- **YOLOv8n model:** ~10MB
- **Frame buffers:** ~5MB (640x480 RGB)
- **Total:** ~65-70MB

#### Optimization Tips
- Release unused models: `detector = None`
- Reuse frame buffers: `prev_frame = img.copy()`
- Avoid creating large lists of detections

## Algorithm Details

### Color Calibration Algorithm

```python
def calibrate_color(img, x, y, radius=30):
    # 1. Extract region of interest
    roi = (x-radius, y-radius, radius*2, radius*2)
    
    # 2. Calculate statistics in LAB space
    stats = img.get_statistics(roi=roi)
    l, a, b = stats.l_mean(), stats.a_mean(), stats.b_mean()
    
    # 3. Create threshold with tolerance
    tolerance_l = 25
    tolerance_ab = 30
    
    threshold = [
        max(0, l - tolerance_l),
        min(100, l + tolerance_l),
        max(-128, a - tolerance_ab),
        min(127, a + tolerance_ab),
        max(-128, b - tolerance_ab),
        min(127, b + tolerance_ab)
    ]
    
    return threshold
```

**Why this works:**
- LAB space separates luminance (L) from color (A, B)
- Larger tolerance for robustness to lighting changes
- Clamping prevents invalid values

### Servo Control Logic

```python
def update_servo(detected, current_time):
    # 1. Update detection timestamp
    if detected:
        last_detection_time = current_time
    
    # 2. Check for object disappearance
    if not detected and servo_opened:
        time_since_detection = current_time - last_detection_time
        
        if time_since_detection >= 1.0:  # Grace period
            if rearm_mode:
                # Start rearm countdown
                if rearm_timer == 0:
                    rearm_timer = current_time
                
                # Check if rearm delay passed
                if current_time - rearm_timer >= rearm_delay:
                    close_servo()
                    armed = True
    
    # 3. Auto-close after delay
    if servo_opened:
        if current_time - open_time >= close_delay:
            close_servo()
    
    # 4. Repeat trigger
    if detected and servo_opened and repeat_trigger:
        if current_time - last_trigger_time >= repeat_interval:
            open_servo()  # Re-trigger
    
    # 5. New detection trigger
    if detected and not servo_opened and armed:
        open_servo()
```

## Testing & Validation

### Unit Tests

#### Servo Test
```bash
python3 servo_test.py
```
Expected: Servo moves through angles 0° -> 45° -> 90° -> 135° -> 180° -> 90° -> 0°

#### Color Detection Test
```python
# Test color threshold
threshold = [[50, 80, 0, 30, 40, 80]]  # Yellow
blobs = img.find_blobs(threshold, pixels_threshold=500)
assert len(blobs) > 0, "No yellow objects detected"
```

#### Object Detection Test
```python
# Test YOLO model
model = nn.YOLOv8(model="/root/models/yolov8n.mud")
objs = model.detect(img, conf_th=0.5)
assert model is not None, "Model failed to load"
```

### Performance Benchmarks

#### FPS Measurement
```python
frame_count = 0
fps_time = time.time()

while True:
    img = cam.read()
    # ... processing ...
    
    frame_count += 1
    if frame_count % 30 == 0:
        fps = 30 / (time.time() - fps_time)
        fps_time = time.time()
        print(f"FPS: {fps:.1f}")
```

#### Latency Measurement
```python
t0 = time.time()
img = cam.read()
t1 = time.time()
detected, blobs = detector.detect(img)
t2 = time.time()
servo.update(detected)
t3 = time.time()

print(f"Camera: {(t1-t0)*1000:.1f}ms")
print(f"Detection: {(t2-t1)*1000:.1f}ms")
print(f"Servo: {(t3-t2)*1000:.1f}ms")
print(f"Total: {(t3-t0)*1000:.1f}ms")
```

## Troubleshooting Guide

### Debug Mode

Add debug output:
```python
DEBUG = True

if DEBUG:
    print(f"[DEBUG] Detected: {detected}")
    print(f"[DEBUG] Blobs: {len(blobs)}")
    print(f"[DEBUG] Servo: {servo_opened}")
    print(f"[DEBUG] Armed: {armed}")
```

### Common Issues

#### Issue: Servo jitters
**Cause:** Insufficient power or noisy PWM signal
**Solution:**
- Use external 5V power supply
- Add capacitor (100-470µF) across servo power
- Check ground connection

#### Issue: Detection too sensitive
**Cause:** Thresholds too loose
**Solution:**
- Increase `min_area` (500 -> 1000)
- Increase `confidence_threshold` (0.5 -> 0.7)
- Use calibration for precise color matching

#### Issue: Detection not sensitive enough
**Cause:** Thresholds too strict
**Solution:**
- Decrease `min_area` (500 -> 300)
- Decrease `confidence_threshold` (0.5 -> 0.3)
- Improve lighting conditions

#### Issue: Low FPS
**Cause:** Resolution too high or heavy processing
**Solution:**
- Reduce resolution (640x480 -> 320x240)
- Use color detection instead of object detection
- Increase `min_area` to filter small objects

## Advanced Customization

### Custom Detection Engine

```python
class CustomDetector:
    def __init__(self, state):
        self.state = state
    
    def detect(self, img):
        # Your custom detection logic here
        detected = False
        detections = []
        
        # Example: Edge detection
        edges = img.find_edges(image.EDGE_CANNY)
        # ... process edges ...
        
        return detected, detections
```

### Custom Servo Patterns

```python
def custom_servo_pattern():
    # Wave pattern
    for angle in range(0, 180, 10):
        set_servo(angle)
        time.sleep(0.05)
    
    # Pulse pattern
    for _ in range(3):
        set_servo(90)
        time.sleep(0.2)
        set_servo(0)
        time.sleep(0.2)
```

### Multi-Servo Control

```python
# Initialize multiple servos
servo1 = pwm.PWM(6, freq=50, duty=7.5, enable=True)
servo2 = pwm.PWM(7, freq=50, duty=7.5, enable=True)

# Synchronized control
def set_both_servos(angle1, angle2):
    duty1 = 2.5 + (angle1 / 180.0) * 10.0
    duty2 = 2.5 + (angle2 / 180.0) * 10.0
    servo1.duty(duty1)
    servo2.duty(duty2)
```

## References

- [MaixPy Documentation](https://wiki.sipeed.com/maixpy/)
- [YOLOv8 Paper](https://arxiv.org/abs/2305.09972)
- [LAB Color Space](https://en.wikipedia.org/wiki/CIELAB_color_space)
- [PWM Servo Control](https://learn.adafruit.com/adafruit-arduino-lesson-14-servo-motors)
- [COCO Dataset](https://cocodataset.org/)
