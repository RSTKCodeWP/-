# Live Video 10ms Android

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [Consti10/LiveVideo10ms](https://github.com/Consti10/LiveVideo10ms) |
| Локальна тека | `fpv-library/repos/LiveVideo10ms-Real-time-video-decoding-on-android` |
| У бібліотеці | keep |
| Категорії каталогу | `link` |
| Зірки (каталог) | 100 |
| Оновлено upstream | 2023-10-30 |
| Ліцензія (з файлу LICENSE або згадки) | LGPL |

## Ідея

**Description** \ Library for live video playback with ultra low latency (below 10ms) on android devices. Supports playback of .h264 encoded live video data transmitted via UDP encapsulated in RAW or RTP and simple file playback. \ Latency data (see example for more information)

**Example App** \

This library has been optimized for low latency and tested on a wide variety of devices, including those running FPV-VR for wifibroadcast. The example library also contains test cases that can be executed on the 'gooogle firebase test lab'. These tests include feeding the decoder with faulty NALUs, created by a lossy connection. (e.g. wifibroadcast).

The 2 most important factors for low latency are 1. HW-accelerated decoding via the MediaCodec api 2. Receiving,Parsing and decoding is done in cpp code (multi-threaded). This decouples it from the java runtime, which increases performance and ma…

_З README.md, без переказу._

## Для чого

Real time video decoding on android

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник відеотракту — у тексті є «h264».


Теми GitHub: `android`, `cpp`, `decoding`, `latency`, `live-streaming`, `mediacodec`, `rtp-streaming`, `udp`, `wifibroadcast`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Real time video decoding on android

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `build.gradle`
- `Example/`
- `gradle/`
- `gradle.properties`
- `gradlew`
- `gradlew.bat`
- `LICENSE`
- `README.md`
- `Screenshots/`
- `settings.gradle`
- `Shared/`
- `TelemetryCore/`
- `TestVideos/`
- `uvcintegration/`
- `VideoCore/`

Типи файлів за вибіркою (124 файлів, глибина до 3): .h264 (29), (без суфікса) (18), C (15), .txt (9), .gradle (7), Markdown (7).


## Що треба

- Маніфести збірки: Gradle.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/LiveVideo10ms-Real-time-video-decoding-on-android/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/Consti10__LiveVideo10ms.md`.
