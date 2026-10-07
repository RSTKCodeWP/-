# wildblue FPV Streamer - Ultra-Low Latency Video Streaming Server

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [wildblue/wbstreamingserver](https://github.com/wildblue/wbstreamingserver) |
| Локальна тека | `fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide` |
| У бібліотеці | keep |
| Категорії каталогу | `link`, `ai` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-01-30 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

A comprehensive C++ video streaming server designed specifically for FPV (First Person View) quadcopter applications on ARM Linux SBCs. Features hardware-accelerated encoding, WFB protocol streaming, real-time detection, and an intuitive web interface.

_З README.md, без переказу._

## Для чого

A comprehensive C++ Ultra-Low Latency Video Streaming Server, designed specifically for FPV (First Person View) quadcopter applications on ARM Linux SBCs. Features hardware-accelerated encoding, WFB-ng streaming protocol integration, trainable real-time object detection and an intuitive web interface for configuration and management.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «wfb-ng».


## Функція

Список із розділу features / можливості в README:

- **Broadcast Addressing**: Support for multiple receivers
- **Fragmentation**: Automatic packet splitting for large frames
- **Forward Error Correction**: Reed-Solomon coding for packet loss recovery
- **Sequence Numbering**: Out-of-order packet handling
- **Priority Queuing**: Real-time packet prioritization
- 360° camera support
- Multi-camera stitching
- Advanced AI models
- Cloud recording support
- Mobile app interface
- RTL-SDR integration
- GPS telemetry overlay

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `analyze_startup_issues.py`
- `build.sh`
- `buildroot/`
- `cmake/`
- `CMakeLists.txt`
- `comprehensive_fallback_test.py`
- `create_sample_images.py`
- `debug_startup.py`
- `docs/`
- `fix_js_quotes.py`
- `generate_fixes_report.py`
- `generate_fixes_report_simple.py`
- `imgs/`
- `LICENSE`
- `Makefile`
- `README.md`
- `simple_dual_camera_test.cpp`
- `src/`
- `test.sh`
- `test_fallback_system.py`
- `test_fixes.py`
- `test_logging_improvements.py`
- `validate_implementation.sh`
- `verify_hardware_support.sh`

Типи файлів за вибіркою (92 файлів, глибина до 3): (без суфікса) (18), Markdown (17), C++ (15), Python (11), C (11), .jpg (6).


## Що треба

### Prerequisites

- ARM Linux SBC (Raspberry Pi, Rock Pi, etc.)
- Camera connected to `/dev/video0`
- Linux kernel 4.15+ with V4L2 support

- Маніфести збірки: CMake, Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

1. **Clone and build**:
   ```bash
   git clone <repository>
   cd fpv-streamer
   chmod +x build.sh
   ./build.sh
   ```

2. **Run the server**:
   ```bash
   ./build/fpv-streamer --device /dev/video0 --port 8080
   ```

3. **Access web interface**:
   Open your browser to `http://localhost:8080`
### Development Setup

1. Install development dependencies
2. Build with debug symbols
3. Run tests
4. Submit pull requests

## Супутні документи в теці

- [`docs/BUILDROOT_INTEGRATION.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/BUILDROOT_INTEGRATION.md)
- [`docs/DUAL_CAMERA_GUIDE.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/DUAL_CAMERA_GUIDE.md)
- [`docs/DUAL_CAMERA_TEST_REPORT.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/DUAL_CAMERA_TEST_REPORT.md)
- [`docs/ENHANCED_FEATURES.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/ENHANCED_FEATURES.md)
- [`docs/ENHANCEMENT_SUMMARY.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/ENHANCEMENT_SUMMARY.md)
- [`docs/FPV_CAPTURE_FIX_SUMMARY.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/FPV_CAPTURE_FIX_SUMMARY.md)
- [`docs/FPV_STARTUP_FIXES.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/FPV_STARTUP_FIXES.md)
- [`docs/HARDWARE_ENCODER_IMPLEMENTATION.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/HARDWARE_ENCODER_IMPLEMENTATION.md)
- [`docs/IMPLEMENTATION_COMPLETE.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/IMPLEMENTATION_COMPLETE.md)
- [`docs/IMPLEMENTATION_SUMMARY.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/IMPLEMENTATION_SUMMARY.md)
- [`docs/LOGGING_IMPROVEMENTS_SUMMARY.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/LOGGING_IMPROVEMENTS_SUMMARY.md)
- [`docs/PROJECT_STATUS.md`](../../fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/docs/PROJECT_STATUS.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/wbstreamingserver-A-comprehensive-C-Ultra-Low-Latency-Vide/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/wildblue__wbstreamingserver.md`.
