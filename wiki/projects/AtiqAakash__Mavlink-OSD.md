# 🛩️ Drone OSD — FPV-Style Transparent MAVLink Overlay

> Картка виставки. Зал: [OSD](../halls/osd.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [AtiqAakash/Mavlink-OSD](https://github.com/AtiqAakash/Mavlink-OSD) |
| Локальна тека | `fpv-library/repos/Mavlink-OSD-Drone-OSD-FPV-Style-Transparent-MAVLink` |
| У бібліотеці | keep |
| Категорії каталогу | `osd` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-03-05 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

A lightweight **always-on-top** on-screen display for drone telemetry on Ubuntu. Perfect for **dual-monitor FPV** setups: one screen for QGroundControl, the other for your **Ant Media FPV feed** — with the OSD overlaying telemetry.

_З README.md, без переказу._

## Для чого

🛩️ Drone OSD — FPV-Style Transparent MAVLink Overlay

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «qgroundcontrol».
- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Список із розділу features / можливості в README:

- 🟡 **Transparent overlay** with crisp Hi-DPI fonts
- 🟨 Bright **Yellow labels** + **White values** for maximum visibility over video
- 📊 Two-row layout with all key flight data
- 🎛️ **Drag handle (⠿)** to move • **Close button (✕)** to exit
- 🔌 Auto-requests MAVLink streams from PX4 / ArduPilot
- 🔗 Works with **QGroundControl → MAVLink Forwarding** in real-time
- 🔋 Shows **battery per-cell voltage** (set your own cell count)
- 🛰️ “AS Det” field (currently mapped from GPS sats; can be replaced by any custom sensor)

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `LICENSE`
- `osd.py`
- `README.md`
- `screenshot.png`

Типи файлів за вибіркою (5 файлів, глибина до 3): (без суфікса) (1), Markdown (1), Python (1), .png (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 🚀 Quick Start

```bash
# Dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-pyqt5
pip3 install pymavlink geographiclib

# Clone & run
git clone https://github.com/BeagleSystems/OSD.git
cd OSD
chmod +x osd.py
python3 osd.py
```

> **Default telemetry endpoint:** `udpin:0.0.0.0:14551`  
> *(Configure QGroundControl to forward MAVLink to this port — see below)*

---

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Mavlink-OSD-Drone-OSD-FPV-Style-Transparent-MAVLink/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/AtiqAakash__Mavlink-OSD.md`.
