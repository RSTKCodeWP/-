# 🎯 MaixCAM WildTrap v1.0.0 - Production Release

**AI-Powered Camera Trap for Wildlife Monitoring & Security**

---

## 🚀 What's New

First production-ready release of MaixCAM WildTrap - a complete AI-powered camera trap solution combining motion detection, YOLOv8 object recognition, and intelligent capture strategies.

---

## ✨ Key Features

### Detection Modes
- **Motion Detection** - Fast, energy-efficient frame differencing
- **AI Detection** - YOLOv8 object recognition (80 COCO classes)
- **Hybrid Mode** ⭐ - Motion trigger → AI verification (recommended)
- **Scheduled Mode** - Timelapse capture at intervals

### Capture Modes
- **Photo** - Single high-quality image
- **Burst** - Series of 3/5/10 photos
- **Video** - Record 5/10/15/30 second clips
- **Timelapse** - Periodic scheduled capture

### Smart Features
- 🎯 Object filtering (target specific animals/people)
- 🌙 Night mode (automatic brightness/contrast enhancement)
- 📊 Metadata logging (JSON + CSV)
- 🔔 Notifications (Telegram Bot + HTTP Webhook)
- 💾 Auto storage management
- ⚡ Energy saving optimizations
- 📱 Touchscreen UI framework

---

## 📦 What's Included

- **wildtrap_app.py** (24KB) - Production application
- **simple_wildtrap.py** (7.2KB) - Educational version
- **wildtrap_config.json** - Configuration template
- **Complete Documentation** (EN + RU)
- **Quick Start Guide** (5 minutes)
- **8 Real-World Examples**
- **Technical Architecture Docs**

---

## 🎯 Use Cases

- Wildlife monitoring and research
- Home/office security
- Bird watching and photography
- Trail cameras
- Pet activity monitoring
- Construction site security
- Nature timelapse projects

---

## 🚀 Quick Start

```bash
# 1. Download release
wget https://github.com/bobberdolle1/maixcam-wildtrap/releases/download/v1.0.0/maixcam-wildtrap-v1.0.0.zip

# 2. Copy to MaixCAM
scp wildtrap_app.py wildtrap_config.json root@maixcam:/root/

# 3. Setup
ssh root@maixcam
mkdir -p /root/wildtrap/{captures,logs,temp}

# 4. Run
python3 wildtrap_app.py
```

---

## 📖 Documentation

- **[START_HERE.md](START_HERE.md)** - Navigation guide
- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup
- **[README.md](README.md)** - Full documentation (English)
- **[README_RU.md](README_RU.md)** - Полная документация (Русский)
- **[EXAMPLES.md](EXAMPLES.md)** - 8 real-world configurations
- **[PROJECT_INFO.md](PROJECT_INFO.md)** - Technical architecture

---

## 🔧 Requirements

### Hardware
- MaixCAM device (Sipeed)
- SD card (4GB+ recommended)
- Optional: Internet for notifications

### Software
- MaixPy 4.x
- YOLOv8n model (3.2MB)
- Python 3.x

---

## 🎓 Example Configuration

### Wildlife Monitoring
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "burst",
  "burst_count": 5,
  "target_objects": ["dog", "cat", "bird", "deer", "bear"],
  "confidence_threshold": 0.7,
  "cooldown_seconds": 60
}
```

### Security Camera
```json
{
  "detection_mode": "hybrid",
  "capture_mode": "video",
  "video_duration": 15,
  "target_objects": ["person", "car"],
  "night_mode": true,
  "telegram_enabled": true
}
```

More examples in [EXAMPLES.md](EXAMPLES.md)

---

## 📊 Performance

| Mode | FPS | Power | Accuracy |
|------|-----|-------|----------|
| Motion | ~30 | Low | Medium |
| AI | ~20 | High | High |
| Hybrid | ~25 | Medium | High |

---

## 🐛 Known Limitations

- Touchscreen menu is framework-only (not fully implemented)
- Video mode saves frames as images (no H.264 encoding)
- Single camera support only

---

## 🔮 Roadmap

- [ ] Full touchscreen menu implementation
- [ ] Native video encoding
- [ ] Multi-camera support
- [ ] Web interface
- [ ] Cloud storage integration
- [ ] Advanced statistics dashboard

---

## 🤝 Contributing

Contributions welcome! Please read [PROJECT_INFO.md](PROJECT_INFO.md) for architecture details.

---

## 📄 License

MIT License - Free for personal and commercial use

---

## 🙏 Credits

- **Platform**: MaixCAM by Sipeed
- **AI Model**: YOLOv8 by Ultralytics
- **Community**: MaixPy developers and wildlife enthusiasts

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/bobberdolle1/maixcam-wildtrap/issues)
- **MaixPy Wiki**: https://wiki.sipeed.com/maixpy
- **Community**: https://maixhub.com

---

## 🏷️ Tags

`#MaixCAM` `#AI` `#WildlifeCameraTraps` `#YOLOv8` `#ComputerVision` `#IoT` `#Python` `#MaixPy` `#ObjectDetection` `#MotionDetection` `#Security` `#Wildlife` `#Photography` `#OpenSource` `#MIT`

---

**Download, configure, and start trapping! 🎯**
