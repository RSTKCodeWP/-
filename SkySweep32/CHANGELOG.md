# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Runtime Thresholds Now Effective**: `CountermeasureSystem::assessThreat()` read the compile-time `RSSI_THRESHOLD_*` macros instead of the values in `ConfigManager`, so the `/api/calibrate` and `/api/config` endpoints saved new thresholds that never influenced threat detection. Threat assessment now uses the live runtime config.
- **Broken Flash Instructions**: The "Start from Zero" guides (EN/RU) told users to flash `SkySweep32_Starter_v0.5.0.bin`, which does not exist in `releases/`. Corrected to the shipped `v0.5.1` binary.
- **Version Drift**: Unified the firmware version reported in serial/web (`SKYSWEEP_VERSION`) and `TODO.md` to `0.6.0` to match the changelog.
- **CC1101 `receiveData` OOB**: Returned the raw on-air length byte (up to 255) while only copying `maxLength` bytes, so callers read past their 64-byte buffer. It now returns the number of bytes actually copied.
- **CC1101 band/spectrum scans** left the radio tuned to the last-scanned frequency; they now save and restore the real pre-scan frequency.
- **CC1101 `writeRegister`** had an unbounded busy-wait on a hardcoded pin; it now waits on `PIN_SPI_MISO` with a 10 ms timeout so an absent/faulty chip can't hang the task.
- **MAVLink length truncation**: `expectedLength` was `uint8_t`, so payloads of 248–255 bytes wrapped and parsed garbage; widened to `uint16_t`. `parseHeartbeat()` now zero-initializes its result on short payloads.
- **Signal DB scoring**: partial RSSI-match distance was `int8_t` and could overflow (0–100 scale vs negative-dBm bounds), corrupting the score; widened to `int`.
- **Deep-sleep duration**: `sleepDurationUs` was `uint32_t`, truncating sleeps over ~71 minutes; widened to `uint64_t`.
- **GPS geofence name**: `strncpy` could leave the name non-NUL-terminated; now explicitly terminated.
- **Cosmetic/log**: NRF24 spectrum log printed MHz as "GHz"; Meshtastic triangulation log passed `size_t` to `%d`; corrected `power_manager` comments (GPIO36/ADC1_CH0, 12 dB attenuation).
- **cppcheck warnings**: `data_logger` logged a `uint32_t` timestamp with `%lu` (type mismatch); fully initialized the ATAK, CRSF, MAVLink, and Acoustic constructors; gave `GPSModule` deleted copy operations (it owns a raw `HardwareSerial*`).

### Security
- **CRSF parser buffer overflow (critical)**: an attacker-controlled length byte of `0xFE`/`0xFF` wrapped `uint8_t expectedLength` to 0/1, then `memcpy`'d up to ~252 bytes into the 60-byte payload buffer. The length is now range-validated and `expectedLength` widened; the CRC is also read at the correct in-frame offset.
- **Remote ID BLE OOB read**: the BLE Remote ID parsers read fixed offsets (up to byte 22) from variable-length, attacker-controlled service data after only a `length < 2` check. Added per-message-type minimum-length guards.
- **ESP-NOW OOB read**: the receive callback only checked `len >= 4` before dereferencing union payloads at offset 8+. It now validates the full header plus the per-type payload length before handling.
- **Web `/api/logs/download` path traversal**: the `file` parameter was concatenated into a path with no validation; now rejects `..`, path separators, and CR/LF.
- **Web OTA false success**: the endpoint reported success and rebooted even when no firmware was written (`Update.hasError()` is false in that case too); success is now tracked from the upload and gated on a verified write.
- **Web `/api/config` POST**: wrote one byte past the framework buffer (`data[len]=0`) and only handled single-chunk bodies; now accumulates chunks into a bounded `String`.
- **WebSocket handler**: removed a similar one-past-end write; the message is now printed length-bounded.

### Changed
- **Reproducible Builds**: Pinned the PlatformIO platform to `espressif32 @ ^6.9.0`. This firmware depends on IDF 4.4 APIs (legacy `driver/adc.h`, `esp_task_wdt_init(timeout, panic)`) that changed in `espressif32` 7.x, so the pin prevents an accidental incompatible-major upgrade.
- **Simpler RF Task Loops**: Replaced the repeated `#ifndef MODULE_*` guard blocks in the RF-scan and display tasks with a single `rfModuleEnabled()` helper (behavior unchanged).

### Added
- **CI Coverage for Optional Modules**: New `esp32dev_full` PlatformIO env plus a CI step compiles the ATAK / Compass / Acoustic / GPS code paths that no release tier enables, so they no longer rot undetected.
- **CI Maintenance**: Bumped GitHub Actions (`checkout@v4`, `setup-python@v5`, `cache@v4`, `action-gh-release@v2`) and added a `workflow_dispatch` trigger for manual runs.
- **Build Status Badge**: Added the GitHub Actions CI badge to the README.
- **Host Unit Tests for Parsers**: Added `test/host/` — desktop-compiled tests (system `g++`, no ESP32 toolchain/PlatformIO registry) that build the CRSF/MAVLink parsers against a minimal `Arduino.h` stub with AddressSanitizer/UBSan. They lock in the buffer-safety fixes (hostile length bytes rejected, valid frames round-trip), the CRSF RC-channel pack/unpack round-trip, the GPS/heartbeat `parse*` bounds guards, and a deterministic ~460k-frame fuzz pass over both parsers; run in CI via a new `host-tests.yml` workflow.
- **Static Analysis (cppcheck)**: the host workflow (renamed *Host Tests & Static Analysis*) now also runs cppcheck warning-level checks over the full feature set — a system tool, so it needs no PlatformIO registry and gates on likely defects.

### Documentation
- Refreshed the README software-architecture tree (EN + RU) to list every current module (it previously showed only 4 of ~20) and added a **Testing** section.
- Documented the `/api/calibrate` endpoint in the EN + RU API references (it was implemented but undocumented).
- Added a "Running tests locally" guide (host tests + cppcheck) to `CONTRIBUTING.md`.

## [0.6.0] - 2026-06-12

### Added
- **ATAK Integration (Cursor on Target)**: Added `#ifdef MODULE_ATAK`. Sends CoT UDP packets for drone targets directly to Android Team Awareness Kit on port 6969.
- **Stealth Mode (Dark Mode)**: Added `stealthMode` config to instantly silence buzzers and switch to vibration motor (`PIN_VIBRATION`), disabling OLED to prevent visual signature at night.
- **Hardware Compass Direction Finding**: Integrated QMC5883L I2C compass (`#ifdef MODULE_COMPASS`). Displays azimuth on OLED and sends vector data (course) to ATAK CoT packets for precise triangulation.
- **TinyML AI Classification**: Replaced rule-based engine with TensorFlow Lite Micro via `EloquentTinyML` (`#ifdef MODULE_ML`). Predicts drone class based on RSSI variance and multi-band spectral data tensor.
- **Optional Feature Flags**: Added `-DMODULE_COMPASS`, `-DMODULE_ML`, and `-DMODULE_ATAK` to `platformio.ini` to keep base footprint small.

## [0.5.1] - 2026-06-09

### Added
- **SD Card Logs Web UI**: Added dynamic card in web dashboard allowing users to list and download raw forensic logs directly from their browser (requires active SD card module).
- **LoRa Mesh Triangulation Math**: Implemented RSSI-based trilateration solver inside `MeshtasticClient` to calculate and log the approximate geographic position of a detected operator/drone using reports from multiple nodes.

### Fixed
- **Pro Tier Compile Bug**: Fixed missing `<SD.h>` include in `src/web_server.cpp` when compiling with `MODULE_SD_CARD` enabled.
- **License Alignment**: Corrected landing page license references from MIT to GNU General Public License v3.0 to match the repository's license.
- **GitHub Pages Jekyll Errors**: Added `.nojekyll` bypass to prevent Jekyll from causing compilation failures on index.html assets.

## [0.5.0] - 2026-03-28

### Added
- **Beginner Guides ("Start from Zero")**: New comprehensive assembly guides for both [English](docs/en/start_from_zero.md) and [Russian](docs/ru/start_from_zero.md) users. No soldering required, focus on modular Starter Tier assembly.
- **Universal Flash Script**: Added `flash.bat` as a one-click firmware installer for Windows users, simplifying the setup process for non-technical users.

### Localized
- **Full Russian Web Dashboard**: Translated all real-time UI elements including Uptime, RAM usage, Battery percentages, Power modes, and Threat classifications into Russian.

### Fixed
- **WebServer Config Ref**: Corrected `RuntimeConfig` reference handling in `web_server.cpp` to ensure UI actions (like calibration) persist correctly.
- **ConfigManager Cleanup**: Standardized configuration saving logic across the core architecture.

## [0.4.0] - 2026-03-28

### Added
- **Interactive Map** (Leaflet.js + OpenStreetMap): Live drone positions on dashboard map with blue markers. Operators shown as orange markers. Auto-centers on first detection
- **Multi-Band RF Scanning**: CC1101 now scans 433/868/915 MHz ISM bands in rotation. `setBand()`, `scanAllBands()`, and `spectrumScan()` methods
- **Power Management** (`power_manager.h/cpp`):
  - 4 power modes: Full (240MHz) → Balanced (160MHz) → Low (80MHz) → Deep Sleep
  - Battery voltage monitoring via ADC (voltage divider on GPIO36)
  - Auto-low-power on critical battery (<5%)
  - Deep sleep / light sleep with timer wakeup
  - CPU frequency scaling, WiFi/BLE power state control
  - Estimated runtime calculation
- **Dashboard: Battery + Power**: Battery %, voltage, power mode, and estimated runtime shown live on web dashboard
- **API: Power Mode**: `POST /api/power?mode=0-3` — remotely switch power modes
- **Runtime Config Integration**: RF scan interval now uses `configManager` value (changeable via API)
- **NRF24 Spectrum Scanner**: Hardware 125-channel 2.4 GHz spectrum sweep via RPD.
- **Signal Database (`signal_database.h/cpp`)**: Preloaded with 8 unique drone RF signatures (DJI, FPV, ArduPilot, etc.) with advanced ML-like factor matching based on bands and RSSI variance.
- **ESP-NOW Mesh (`espnow_mesh.h/cpp`)**: Free decentralized node-to-node communication sharing threats, telemetry, and heartbeats autonomously between active SkySweep nodes.
- **Alert Manager (`alert_manager.h/cpp`)**: External notifications module with non-blocking buzzer tones and LED control corresponding to dynamic threat levels.
- **3D Enclosures Documentation**: Added EN & RU guides (`docs/en/enclosures.md`) with design recommendations, optimal materials, cooling, and antenna placement strategies for 3D printed cases.
- **Auto-Calibrate UI Button**: Added `/api/calibrate` endpoint and dashboard GUI button to automatically zero background RF noise and adjust threat thresholds.

## [0.3.1] - 2026-03-28

### Added
- **OTA Firmware Updates**: Upload firmware via `POST /api/ota` endpoint
- **Runtime Configuration**: JSON config stored on SPIFFS (`config_manager.h/cpp`)
  - WiFi, RSSI thresholds, scan intervals, LoRa settings editable without recompile
  - REST API: `GET/POST /api/config`, `POST /api/config/reset`
  - Partial updates supported (only send changed fields)
- **Watchdog Timer**: 30-second hardware watchdog prevents system hangs
- **`#ifdef` Guards on All Drivers**: CC1101, NRF24, RX5808 drivers wrapped in module guards for clean conditional compilation
- **Software Guide**: `docs/en/software.md` and `docs/ru/software.md` — Quick start, API reference, OTA, troubleshooting
- **Contributing Guide**: `CONTRIBUTING.md` — Code conventions, priority areas

### Fixed
- **`config.h` RF_MODULE_COUNT Macro**: Replaced broken `defined()` in `#define` arithmetic with proper `#ifdef` chain
- **Duplicate `#define` Conflict**: Removed duplicated RSSI threshold defines from `countermeasures.cpp` (now in `config.h`)

## [0.3.0] - 2026-03-28

### Added
- **Modular Tier System**: Three hardware tiers (Starter $15 / Hunter $35 / Sentinel $60+)
- **Central `config.h`**: All pins, modules, and settings in one file
- **SPI Bus Manager**: FreeRTOS mutex for safe multi-device SPI access (`spi_manager.h/cpp`)
- **FreeRTOS Multi-Task Architecture**: 7+ tasks across dual ESP32 cores
- **Full Web Dashboard**: Dark-themed HTML dashboard with real-time WebSocket updates, RSSI graphs, drone detection list, system status, and module badges
- **Rule-Based ML Classifier**: Classifies drones by protocol detection (MAVLink/CRSF), frequency band patterns, and RSSI variance analysis
- **Protocol Integration**: MAVLink and CRSF parsers connected to RF scanning pipeline
- **Modular Upgrade Guide**: `docs/en/modules.md` and `docs/ru/modules.md` with BOM, wiring, and upgrade paths

### Fixed
- **CRITICAL: Pin Conflicts Resolved**: GPS (GPIO 16/17) no longer conflicts with RF CS pins; LoRa (GPIO 26/33/32/25) no longer conflicts with CC1101/NRF24
- **CRITICAL: `web_server.cpp` Implemented**: Was completely empty (0 bytes), now full dashboard
- **WiFi Mode Conflict**: Remote ID no longer calls `WiFi.mode(WIFI_STA)` — web server manages WiFi in `WIFI_AP_STA` mode
- **Remote ID Memory Leak**: Replaced unbounded `std::vector` with fixed-size array (`MAX_DETECTED_DRONES = 20`)
- **Acoustic Detector I2S Mismatch**: Changed from `I2S_BITS_PER_SAMPLE_32BIT` to `16BIT` to match `int16_t` buffer
- **Data Logger File Handle Leaks**: All `File` objects now properly closed after iteration
- **Data Logger `deleteOldestLog()`**: Now builds full path with `LOG_DIR` prefix
- **ML Classifier Stub Removed**: No longer returns hardcoded values

### Changed
- **main.cpp**: Complete rewrite from monolithic `loop()` to FreeRTOS task-based architecture
- **All modules**: Wrapped in `#ifdef MODULE_*` guards for conditional compilation
- **All headers**: Use `config.h` instead of scattered local `#define` statements
- **Countermeasures**: Use SPI mutex, threshold values from `config.h`
- **Meshtastic Client**: Packet buffer limited to 50 entries to prevent memory issues

### Security
- Countermeasures require both `ENABLE_COUNTERMEASURES` build flag AND runtime `armSystem(true)` call
- WebSocket connections limited to `MAX_WEBSOCKET_CLIENTS` (4) to prevent crash

## [0.2.0] - 2026-03-28

### Added
- Remote ID Detection (FAA ANSI/CTA-2063)
- Web Interface (placeholder)
- Data Logging to SD card
- GPS Module integration
- Meshtastic LoRa mesh networking
- Machine Learning placeholder
- Full RF driver implementations
- MAVLink/CRSF protocol parsers
- Countermeasure system
- Bilingual documentation (EN/RU)
- GPL-3.0 license

## [0.1.0] - 2026-03-28

### Added
- Initial project structure
- Basic ESP32 configuration
- Placeholder RF module support
- OLED display integration
- PlatformIO build system

[0.3.0]: https://github.com/bobberdolle1/SkySweep32/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/bobberdolle1/SkySweep32/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bobberdolle1/SkySweep32/releases/tag/v0.1.0
