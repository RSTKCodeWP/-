# LoRa UAV Ground Control Station

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [ShivamMathtech/UAV-gorund-controller-telmetry](https://github.com/ShivamMathtech/UAV-gorund-controller-telmetry) |
| Локальна тека | `fpv-library/repos/UAV-gorund-controller-telmetry-A-portable-long-range-UAV-Ground-Control` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `link` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-05-30 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

### Project Overview

This project implements a custom UAV Ground Control Station using:

The system is designed for:

_З readme.md, без переказу._

## Для чого

A portable long-range UAV Ground Control Station (GCS) designed for telemetry, mission monitoring, FPV streaming, and UAV communication using LoRa telemetry systems.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `arduino`, `controller`, `esp32`, `ground-station`, `hardware`, `rasberry-pi`, `telemetry`, `uav`.

## Функція

Список із розділу features / можливості в README:

- Long-range LoRa telemetry
- UAV manual control
- Real-time telemetry monitoring
- MAVLink communication
- GPS location tracking
- Battery monitoring
- FPV video streaming
- Flight mode switching
- Touchscreen control interface
- Mission monitoring dashboard
- LoRa packet transmission
- Joystick reading

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `arduino/`
- `Hardware/`
- `LICENCE`
- `rasberrypi/`
- `readme.md`

Типи файлів за вибіркою (40 файлів, глибина до 3): Python (18), C (8), C++ (5), .png (2), Arduino (2), Markdown (1).

Фрагмент README про будову:

### System Architecture

```text
+------------------------------------------------+
|            Ground Control Station              |
|------------------------------------------------|
| Arduino Mega                                   |
| Raspberry Pi                                   |
| LoRa SX1278 Telemetry                          |
| HDMI LCD Display                               |
| Joysticks + Buttons                            |
| FPV Video Receiver                             |
| MAVLink Communication                          |
+------------------------------------------------+
                     |
                     | LoRa RF Link
                     |
+------------------------------------------------+
|                UAV Flight System               |
|------------------------------------------------|
| Flight Controller                              |
| GPS Module                                     |
| ESC + Motors                                   |
| LoRa Telemetry                                 |
| FPV Camera                                     |
+------------------------------------------------+
```

---

## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Raspberry Pi Setup

Update system:

```bash
sudo apt update
sudo apt upgrade
```

Install dependencies:

```bash
pip3 install pyserial
pip3 install pymavlink
pip3 install opencv-python
pip3 install numpy
pip3 install folium
```

---

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/UAV-gorund-controller-telmetry-A-portable-long-range-UAV-Ground-Control/readme.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/ShivamMathtech__UAV-gorund-controller-telmetry.md`.
