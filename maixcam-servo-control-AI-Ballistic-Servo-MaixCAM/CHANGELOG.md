# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.0] - 2026-05-10

### Added
- **Full Autonomous Ballistics Engine**: Added a mathematical drop physics engine that calculates time-of-flight and forward distance to draw a dynamic 'Drop Line' on the OSD. Target must intersect this line to trigger the servo.
- **AI Altitude Estimation (Auto Alt)**: The camera now dynamically estimates its altitude by comparing target bounding-box pixel height to known real-world physical heights (e.g., person = 1.7m).
- **Optical Flow Ground Speed (Auto Speed)**: Ground speed is now automatically calculated in real-time by analyzing pixel translation using `find_displacement` (Phase Correlation).
- **Professional UI Overhaul**:
  - Replaced list layout with a full-screen **2-column Grid Layout** for settings menus.
  - Buttons are now **2-line displays** with the value shown in large, high-contrast text.
  - OSD now has a semi-transparent dark background box for perfect readability.
  - **Dynamic Menus**: Menu intelligently hides irrelevant options (e.g., hiding object targets when color detection is active).
  - Software touch debouncing via edge-detection to prevent rapid-cycling.
- **Custom Objects**: Added `custom` to the object preset list for user-trained models.
- **Video Recording UI**: Added a video recording toggle in settings and a flashing `REC` OSD indicator.

## [2.0.0] - 2026-05-10

### Added
- **Autonomous Execution (MaixApp)**: Project is now packaged as a native MaixApp (`advanced_servo_drop_v1.0.0.zip`), enabling installation via the MaixCAM App Store. The app can run autonomously on boot when powered by a power bank without needing a PC connection.
- **New Button UI System**: Completely replaced the brittle Y-axis touch logic with a robust `UIButton` class. The UI now features properly drawn rectangles with strictly defined hitboxes (X, Y, Width, Height) for all interactive elements.
- **Extended Settings**:
  - Pagination for settings menu.
  - Servo Pin selection (A14-A19).
  - Configurable Angle Open and Angle Close (0-180°).
  - Repeat Trigger interval setting.
- **Extended Object Detection**: Added more targets (`bird`, `chair`, `tv`, `laptop`, `book`, `clock`) to the YOLO preset cycling.

## [1.1.0] - 2026-05-10

### Added
- **Resolution settings** in settings menu (320x240, 640x480, 800x600, 1280x720)
- Organized project structure with folders:
  - `examples/` - Example applications
  - `utils/` - Utility scripts
  - `docs/` - Documentation files
- CHANGELOG.md for tracking project changes

### Changed
- Improved settings menu layout with better spacing
- Updated documentation to reflect new folder structure

### Fixed
- Settings menu item spacing for better touch accuracy

## [1.0.0] - 2026-05-10

### Added
- **Main Application** (`advanced_servo_app.py`)
  - Color detection with LAB color space
  - Object detection using YOLOv8 (80 COCO classes)
  - Motion detection using frame differencing
  - Full touchscreen UI with menu system
  - Settings menu for runtime configuration
  - ARM/DISARM mode
  - Rearm mode with configurable delay
  - Repeat trigger mode
  - Color calibration via touchscreen
  - Configuration save/load (JSON)
  - Real-time OSD with status, FPS, timers
  - Detection visualization with bounding boxes

- **Example Applications**
  - `simple_servo_app.py` - Minimal version for quick start
  - `color_servo_app.py` - Color detection with calibration
  - `servo_detector_app.py` - Multi-mode detection with basic menu
  - `yellow_servo_control.py` - Basic yellow color detection

- **Utility Scripts**
  - `servo_test.py` - Hardware test for servo motor
  - `check_pwm_pins.py` - PWM pin availability checker
  - `calibrate_color.py` - Interactive color calibration tool

- **Documentation**
  - `README.md` - Main documentation with badges
  - `QUICKSTART.md` - 5-minute quick start guide
  - `EXAMPLES.md` - 10+ real-world use cases and integration examples
  - `TECHNICAL.md` - Technical deep dive and optimization guide
  - `PROJECT_SUMMARY.md` - Comprehensive project overview
  - `config_examples.json` - Configuration presets and examples

- **Features**
  - 8 color presets (Yellow, Red, Green, Blue, Orange, Purple, White, Black)
  - Custom color calibration
  - 80 object classes support (COCO dataset)
  - Configurable servo angles (0-180°)
  - Configurable PWM pins
  - Close delay (3-60 seconds)
  - Rearm delay (1-10 seconds)
  - Min area threshold (300-2000 pixels)
  - Confidence threshold (0.3-0.8)
  - Motion sensitivity (30-80)
  - Camera resolution (640x480 default)
  - FPS counter
  - Detection timers

- **Performance**
  - ~30 FPS @ 640x480 (color detection)
  - ~20 FPS @ 640x480 (object detection)
  - ~30 FPS @ 640x480 (motion detection)
  - ~30ms detection latency
  - Optimized LAB color space processing
  - Efficient blob detection

- **Configuration System**
  - JSON-based configuration
  - Persistent settings storage
  - Runtime configuration changes
  - Default configuration fallback
  - Configuration backup support

### Technical Details
- **Hardware Support**
  - MaixCAM (1st generation with screen)
  - SG90 servo motor (and compatible)
  - PWM pins: A18 (default), A19, A20, A21
  - 5V power supply (2A recommended)

- **Software Stack**
  - MaixPy 4.x framework
  - YOLOv8 neural network
  - LAB color space processing
  - PWM servo control
  - Touchscreen input handling
  - JSON configuration management

- **Code Statistics**
  - Total lines: 3900+
  - Main app: ~700 lines
  - Documentation: 2500+ lines
  - Examples: 700+ lines

### Documentation
- Comprehensive README with installation and usage
- Quick start guide for 5-minute setup
- 10+ real-world use case examples
- Technical documentation with algorithms and optimization
- Configuration examples and presets
- Troubleshooting guides
- API documentation

### Examples Included
1. Automatic pet feeder
2. Color-based sorting system
3. Motion-activated security
4. People counter
5. Automatic door opener
6. Gesture-controlled system
7. Wildlife camera trigger
8. Quality control system
9. Parking space monitor
10. Interactive art installation

### Integration Examples
- MQTT event publishing
- HTTP API integration
- SQLite database logging
- Performance optimization techniques
- Multi-servo control
- Custom detection engines

## [0.1.0] - 2026-05-10 (Initial Development)

### Added
- Initial project structure
- Basic servo control
- Simple color detection
- Hardware testing scripts

---

## Release Notes

### Version 1.1.0
This release adds resolution configuration in the settings menu, allowing users to adjust camera resolution for better detection accuracy or performance. The project structure has been reorganized into logical folders for better maintainability.

### Version 1.0.0
First stable release with full feature set including color, object, and motion detection, comprehensive UI, configuration system, and extensive documentation. Production-ready for real-world applications.

---

## Upgrade Guide

### From 1.0.0 to 1.1.0
1. No breaking changes
2. Configuration file is backward compatible
3. New resolution setting will use default (640x480) if not specified
4. Update file paths if you referenced old locations:
   - `simple_servo_app.py` → `examples/simple_servo_app.py`
   - `servo_test.py` → `utils/servo_test.py`
   - `QUICKSTART.md` → `docs/QUICKSTART.md`

---

## Future Roadmap

### Planned for 1.2.0
- [ ] Face detection mode
- [ ] QR code detection
- [ ] Multi-servo support
- [ ] Web interface
- [ ] REST API

### Planned for 1.3.0
- [ ] Mobile app control
- [ ] Cloud integration
- [ ] Data analytics dashboard
- [ ] Custom model training support

### Planned for 2.0.0
- [ ] Complete UI redesign
- [ ] Plugin system
- [ ] Multi-language support
- [ ] Advanced scheduling
- [ ] Remote monitoring

---

## Contributing

See [README.md](README.md) for contribution guidelines.

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Links

- **Repository:** https://github.com/bobberdolle1/maixcam-servo-control
- **Issues:** https://github.com/bobberdolle1/maixcam-servo-control/issues
- **Documentation:** [docs/](docs/)
- **Examples:** [examples/](examples/)
