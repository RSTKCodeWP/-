# WildTrap Usage Examples

Real-world configuration examples for different use cases.

---

## 1. Backyard Wildlife Monitoring

**Goal**: Monitor animals visiting your backyard during the day

```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "burst_count": 5,
  "target_objects": ["dog", "cat", "bird", "squirrel"],
  "confidence_threshold": 0.65,
  "cooldown_seconds": 120,
  "camera_width": 1280,
  "camera_height": 720,
  "night_mode": false,
  "telegram_enabled": true,
  "telegram_bot_token": "YOUR_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID",
  "telegram_throttle_minutes": 10,
  "storage_max_gb": 8,
  "storage_keep_days": 14,
  "armed": true
}
```

**Why these settings:**
- Hybrid mode: Energy efficient, accurate
- Burst 5 photos: Capture animal behavior sequence
- 120s cooldown: Avoid spam from same animal
- Telegram: Get notified of visitors
- 14 days retention: Review weekly patterns

---

## 2. Security Camera (Home/Office)

**Goal**: Detect people and vehicles 24/7

```json
{
  "detection_mode": "hybrid",
  "capture_mode": "video",
  "video_duration": 20,
  "target_objects": ["person", "car", "truck", "motorcycle"],
  "confidence_threshold": 0.75,
  "cooldown_seconds": 30,
  "camera_width": 1920,
  "camera_height": 1080,
  "night_mode": true,
  "telegram_enabled": true,
  "telegram_throttle_minutes": 2,
  "webhook_enabled": true,
  "webhook_url": "https://your-server.com/security-alert",
  "storage_max_gb": 20,
  "storage_keep_days": 30,
  "armed": true
}
```

**Why these settings:**
- Video mode: Capture full event context
- High resolution: Better identification
- Night mode: 24/7 operation
- Short throttle: Immediate alerts
- Webhook: Integration with security system
- 30 days retention: Legal/insurance requirements

---

## 3. Bird Feeder Observation

**Goal**: Photograph birds visiting feeder

```json
{
  "detection_mode": "ai",
  "capture_mode": "burst",
  "burst_count": 10,
  "target_objects": ["bird"],
  "confidence_threshold": 0.55,
  "min_object_size": 500,
  "cooldown_seconds": 5,
  "camera_width": 1280,
  "camera_height": 720,
  "night_mode": false,
  "telegram_enabled": false,
  "storage_max_gb": 10,
  "storage_keep_days": 7,
  "armed": true
}
```

**Why these settings:**
- AI-only mode: Skip motion (wind, leaves)
- Burst 10: Capture feeding behavior
- Low cooldown: Multiple birds
- Lower confidence: Catch rare species
- Min size filter: Ignore distant birds
- No notifications: Review manually

---

## 4. Trail Camera (Remote Location)

**Goal**: Long-term wildlife monitoring with minimal power

```json
{
  "detection_mode": "motion",
  "capture_mode": "photo",
  "target_objects": ["person", "dog", "cat", "horse", "cow", "deer", "bear"],
  "motion_sensitivity": 60,
  "cooldown_seconds": 300,
  "camera_width": 640,
  "camera_height": 480,
  "night_mode": true,
  "jpeg_quality": 75,
  "telegram_enabled": false,
  "storage_max_gb": 4,
  "storage_keep_days": 60,
  "auto_cleanup": true,
  "armed": true
}
```

**Why these settings:**
- Motion-only: Maximum battery life
- Single photo: Minimal storage
- Low resolution: Longer operation
- 5min cooldown: Reduce captures
- No notifications: No network needed
- 60 days retention: Monthly collection

---

## 5. Research Project (Detailed Data)

**Goal**: Scientific wildlife study with comprehensive data

```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "burst_count": 7,
  "target_objects": ["dog", "cat", "horse", "cow", "sheep", "deer", "bear", "elephant"],
  "confidence_threshold": 0.70,
  "min_object_size": 2000,
  "cooldown_seconds": 60,
  "camera_width": 1920,
  "camera_height": 1080,
  "night_mode": true,
  "jpeg_quality": 95,
  "telegram_enabled": false,
  "webhook_enabled": true,
  "webhook_url": "https://research-server.edu/wildlife-data",
  "storage_max_gb": 50,
  "storage_keep_days": 365,
  "auto_cleanup": false,
  "armed": true
}
```

**Why these settings:**
- High resolution: Detailed analysis
- High quality: Publication-ready
- Webhook: Automated data pipeline
- Large storage: Full dataset
- No auto-cleanup: Preserve all data
- Metadata logging: Research documentation

---

## 6. Pet Activity Monitor

**Goal**: Track your pet's outdoor activities

```json
{
  "detection_mode": "ai",
  "capture_mode": "burst",
  "burst_count": 3,
  "target_objects": ["dog", "cat"],
  "confidence_threshold": 0.80,
  "cooldown_seconds": 60,
  "camera_width": 1280,
  "camera_height": 720,
  "night_mode": false,
  "telegram_enabled": true,
  "telegram_throttle_minutes": 15,
  "storage_max_gb": 5,
  "storage_keep_days": 7,
  "armed": true
}
```

**Why these settings:**
- AI-only: Ignore other motion
- High confidence: Only your pet
- Telegram: Know when pet is outside
- Weekly retention: Review behavior patterns

---

## 7. Construction Site Security

**Goal**: Monitor unauthorized access and vehicle movement

```json
{
  "detection_mode": "hybrid",
  "capture_mode": "video",
  "video_duration": 30,
  "target_objects": ["person", "car", "truck", "motorcycle", "bus"],
  "confidence_threshold": 0.80,
  "cooldown_seconds": 20,
  "camera_width": 1920,
  "camera_height": 1080,
  "night_mode": true,
  "telegram_enabled": true,
  "telegram_throttle_minutes": 1,
  "webhook_enabled": true,
  "webhook_url": "https://security-company.com/alert",
  "storage_max_gb": 30,
  "storage_keep_days": 90,
  "armed": true
}
```

**Why these settings:**
- Long video: Capture full incident
- High resolution: License plate reading
- Immediate alerts: Security response
- 90 days retention: Investigation period

---

## 8. Timelapse Nature Study

**Goal**: Scheduled captures regardless of activity

```json
{
  "detection_mode": "scheduled",
  "capture_mode": "photo",
  "timelapse_interval": 300,
  "camera_width": 1920,
  "camera_height": 1080,
  "night_mode": true,
  "jpeg_quality": 90,
  "telegram_enabled": false,
  "storage_max_gb": 20,
  "storage_keep_days": 30,
  "armed": true
}
```

**Why these settings:**
- Scheduled mode: Regular intervals
- 5min interval: Capture environmental changes
- High quality: Timelapse video creation
- No notifications: Batch processing

---

## Testing Your Configuration

### Quick Test Procedure

1. **Set short cooldown for testing:**
```json
"cooldown_seconds": 5
```

2. **Enable verbose logging:**
```bash
python3 wildtrap_app.py 2>&1 | tee wildtrap.log
```

3. **Trigger detection:**
- Walk in front of camera
- Wave an object
- Use a photo/video of target animal

4. **Check results:**
```bash
ls -lh /root/wildtrap/captures/
cat /root/wildtrap/logs/detections.csv
```

5. **Adjust settings based on results:**
- Too many false positives → Increase `confidence_threshold`
- Missing detections → Lower `confidence_threshold`
- Too frequent captures → Increase `cooldown_seconds`
- Wrong objects → Adjust `target_objects`

---

## Performance Tuning

### Maximize Battery Life
```json
{
  "detection_mode": "motion",
  "camera_width": 640,
  "camera_height": 480,
  "cooldown_seconds": 300,
  "jpeg_quality": 70
}
```

### Maximize Accuracy
```json
{
  "detection_mode": "ai",
  "camera_width": 1920,
  "camera_height": 1080,
  "confidence_threshold": 0.75,
  "min_object_size": 2000
}
```

### Balance (Recommended)
```json
{
  "detection_mode": "hybrid",
  "camera_width": 1280,
  "camera_height": 720,
  "confidence_threshold": 0.65,
  "cooldown_seconds": 60
}
```

---

## Common Adjustments

### Reduce False Positives
- Increase `confidence_threshold` (0.6 → 0.75)
- Increase `min_object_size` (1000 → 2000)
- Use `ai` or `hybrid` mode instead of `motion`

### Catch More Detections
- Decrease `confidence_threshold` (0.7 → 0.55)
- Decrease `min_object_size` (1000 → 500)
- Decrease `cooldown_seconds` (60 → 30)

### Improve Night Performance
- Enable `night_mode: true`
- Lower resolution (1280x720 → 640x480)
- Increase `confidence_threshold` (0.6 → 0.7)

### Save Storage Space
- Lower resolution
- Reduce `jpeg_quality` (90 → 75)
- Use `photo` instead of `burst` or `video`
- Enable `auto_cleanup: true`
- Reduce `storage_keep_days`

---

**Experiment and find what works best for your use case!**
