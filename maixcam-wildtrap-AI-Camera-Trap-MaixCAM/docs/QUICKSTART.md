
# WildTrap Quick Start ⚡

Get your AI camera trap running in 5 minutes!

---

## Step 1: Copy Files (1 min)

```bash
# From your computer
scp wildtrap_app.py wildtrap_config.json root@<MAIXCAM_IP>:/root/
```

---

## Step 2: Setup (1 min)

```bash
# SSH into MaixCAM
ssh root@<MAIXCAM_IP>

# Create directories
mkdir -p /root/wildtrap/{captures,logs,temp}

# Verify YOLOv8 model exists
ls /root/models/yolov8n.mud
```

If model missing:
```bash
cd /root/models
wget https://github.com/sipeed/MaixPy/releases/download/v4.0.0/yolov8n.mud
```

---

## Step 3: Configure (2 min)

Edit `wildtrap_config.json`:

### Basic Setup (No Notifications)
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "burst_count": 5,
  "target_objects": ["person", "dog", "cat", "bird"],
  "confidence_threshold": 0.6,
  "cooldown_seconds": 30,
  "armed": true
}
```

### With Telegram Notifications
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "burst_count": 5,
  "target_objects": ["person", "dog", "cat"],
  "telegram_enabled": true,
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID",
  "armed": true
}
```

**Get Telegram Credentials:**
1. Message [@BotFather](https://t.me/botfather) → `/newbot`
2. Copy bot token
3. Message [@userinfobot](https://t.me/userinfobot) → Copy your ID

---

## Step 4: Run (1 min)

```bash
python3 wildtrap_app.py
```

**Expected Output:**
```
WildTrap v1.0.0 - Initializing...
Camera initialized: 1280x720
YOLOv8 model loaded
Initialization complete
WildTrap running. Press Ctrl+C to exit.
```

---

## Step 5: Test

1. **ARM the system** - Set `"armed": true` in config
2. **Trigger detection** - Walk in front of camera
3. **Check captures** - `ls /root/wildtrap/captures/`
4. **View logs** - `cat /root/wildtrap/logs/detections.csv`

---

## Common Configurations

### Wildlife Camera (Daytime)
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "burst_count": 5,
  "target_objects": ["dog", "cat", "bird", "horse", "cow", "deer", "bear"],
  "confidence_threshold": 0.7,
  "cooldown_seconds": 60,
  "night_mode": false,
  "armed": true
}
```

### Security Camera (24/7)
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "video",
  "video_duration": 15,
  "target_objects": ["person", "car"],
  "confidence_threshold": 0.8,
  "cooldown_seconds": 30,
  "night_mode": true,
  "telegram_enabled": true,
  "armed": true
}
```

### Bird Feeder Monitor
```json
{
  "detection_mode": "ai",
  "capture_mode": "burst",
  "burst_count": 10,
  "target_objects": ["bird"],
  "confidence_threshold": 0.6,
  "cooldown_seconds": 10,
  "armed": true
}
```

---

## Touchscreen Controls

**Main Screen:**
- Shows live preview with detection overlays
- Status: ARMED / STANDBY
- Captures count
- Storage usage
- TAP anywhere to open menu

**Menu (Coming Soon):**
- ARM/DISARM toggle
- View gallery
- Change settings
- View statistics

---

## Viewing Captures

### On Device
```bash
ls -lh /root/wildtrap/captures/
```

### Copy to Computer
```bash
# From your computer
scp -r root@<MAIXCAM_IP>:/root/wildtrap/captures/ ./wildtrap_captures/
```

### View Metadata
```bash
cat /root/wildtrap/captures/20260510_143022_dog_0.87.json
```

---

## Stopping the App

Press `Ctrl+C` in the terminal:
```
^C
Shutting down...
Cleanup complete
```

---

## Auto-Start on Boot (Optional)

Create systemd service:

```bash
cat > /etc/systemd/system/wildtrap.service << 'EOF'
[Unit]
Description=WildTrap Camera Trap
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
ExecStart=/usr/bin/python3 /root/wildtrap_app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
systemctl enable wildtrap
systemctl start wildtrap

# Check status
systemctl status wildtrap
```

---

## Troubleshooting

### "Camera module not available"
```bash
# Check camera
v4l2-ctl --list-devices

# Restart
reboot
```

### "Model not found"
```bash
# Download model
cd /root/models
wget https://github.com/sipeed/MaixPy/releases/download/v4.0.0/yolov8n.mud
```

### No detections
- Check `"armed": true` in config
- Lower `confidence_threshold` to 0.5
- Verify target_objects includes what you're testing
- Check lighting conditions

### Storage full
```bash
# Enable auto-cleanup in config
"auto_cleanup": true,
"storage_max_gb": 5,
"storage_keep_days": 7

# Or manual cleanup
rm -rf /root/wildtrap/captures/*
```

---

## Next Steps

- Read full [README.md](README.md) for advanced features
- Customize detection settings
- Setup Telegram notifications
- Explore simple_wildtrap.py for learning

---

**You're all set! Happy trapping! 🎯**
