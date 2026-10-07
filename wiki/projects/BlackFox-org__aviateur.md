# Aviateur

> Картка виставки. Зал: [OpenIPC](../halls/openipc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [BlackFox-org/aviateur](https://github.com/BlackFox-org/aviateur) |
| Локальна тека | `fpv-library/repos/aviateur-Cross-platform-OpenIPC-FPV-ground-statio` |
| У бібліотеці | keep |
| Категорії каталогу | `openipc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-02-23 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Aviateur is a high-performance, low-latency FPV ground station specifically designed for the [OpenIPC](https://openipc.org/) ecosystem. It allows you to receive and display digital video streams from your drone with minimal lag, supporting modern codecs and hardware acceleration.

_З README.md, без переказу._

## Для чого

Cross-platform OpenIPC FPV ground station for Linux/Windows/macOS

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground station».
- Розробник відеотракту — у тексті є «openipc».


## Функція

Список із розділу features / можливості в README:

- **Ultra-Low Latency**: Optimized for real-time FPV flight.
- **Cross-Platform**: Native support for Linux, Windows, and macOS.
- **Flight Recording**: Capture your flights in MP4 or GIF formats.
- **Snapshots**: Save high-quality JPEG screenshots during flight.
- **Hardware Acceleration**: Utilizes GPU for efficient video decoding and rendering (Vulkan/OpenGL).
- **Audio Support**: Real-time audio streaming from the drone.
- **Telemetry & Stats**: Monitor bitrate and link quality in real-time.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `80-my8812au.rules`
- `assets/`
- `aviateur.desktop`
- `build-appimage.sh`
- `CMakeLists.txt`
- `LICENSE`
- `pack-for-macos.sh`
- `pack-for-windows.ps1`
- `README.md`
- `src/`
- `test-local-rtp`
- `tutorials/`
- `wsl-map-usb.md`

Типи файлів за вибіркою (100 файлів, глибина до 3): C (36), C++ (24), .svg (6), .txt (5), (без суфікса) (5), .jpg (5).


## Що треба

### Prerequisites

- CMake 3.18+
- C++20 compatible compiler
- Dependencies: FFmpeg, libusb, libsodium, OpenCV, SDL3

#### Windows (using vcpkg)

1. Install [vcpkg](https://github.com/microsoft/vcpkg).
2. Install dependencies:
   ```powershell
   .\vcpkg install libusb ffmpeg libsodium opencv sdl3
   ```
3. Set `VCPKG_ROOT` environment variable to your vcpkg path.
4. Build:
   ```bash
   git clone --recursive https://github.com/OpenIPC/aviateur
   mkdir build && cd build
   cmake ..
   cmake --build .
   ```

#### Linux (Ubuntu/Debian)

```bash
sudo apt install cmake libavformat-dev libavcodec-dev libswresample-dev \
                 libswscale-dev libavutil-dev libvulkan-dev libusb-1.0-0-dev \
                 libsodium-dev libopencv-dev xorg-dev libpcap-dev
git clone --recursive https://github.com/OpenIPC/aviateur
mkdir build && cd build
cmake ..
make
```

#### macOS (Homebrew)

```bash
brew install pkgconf libusb ffmpeg libsodium opencv libpcap cmake sdl3
git clone --recursive https://github.com/OpenIPC/aviateur
mkdir build && cd build
cmake ..
make
```

- Маніфести збірки: CMake.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/aviateur-Cross-platform-OpenIPC-FPV-ground-statio/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/BlackFox-org__aviateur.md`.
