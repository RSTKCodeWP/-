# ArduPilot Drone Security Research

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [hassan-hfk/Ardupilot-Drone-Security-Research](https://github.com/hassan-hfk/Ardupilot-Drone-Security-Research) |
| Локальна тека | `fpv-library/repos/Ardupilot-Drone-Security-Research-ArduPilot-SITL-waypoint-missions-MATLAB` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc`, `tools` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-05-18 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A collection of work I did covering drone operations, flight controller internals, MAVLink protocol analysis, and UAV security. Everything here runs on ArduPilot SITL — no real hardware needed to try any of it.

The work is split into five areas, each building on the previous one:

_З README.md, без переказу._

## Для чого

ArduPilot SITL : waypoint missions, MATLAB fallback controller, MAVLink traffic analysis, geofence Lua scripting, and MAVLink DoS PoC

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «qgroundcontrol».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `cybersecurity`, `drone-security`, `lua`, `matlab`, `mavlink`, `qgroundcontrol`, `sitl`, `uav`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: ArduPilot SITL : waypoint missions, MATLAB fallback controller, MAVLink traffic analysis, geofence Lua scripting, and MAVLink DoS PoC

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `01-sitl-operations/`
- `02-fallback-controller/`
- `03-mavlink-traffic-analysis/`
- `04-geofence-lua/`
- `05-mavlink-dos-poc/`
- `README.md`

Типи файлів за вибіркою (45 файлів, глибина до 3): .jpg (19), .pdf (8), Markdown (6), .docx (3), (без суфікса) (2), Lua (2).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Setup

You need ArduPilot SITL running for everything here. The quickest way:

```bash
# Clone ArduPilot
git clone https://github.com/ArduPilot/ardupilot.git
cd ardupilot
git submodule update --init --recursive

# Install dependencies
./Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile

# Launch a copter SITL
cd ArduCopter
sim_vehicle.py -v ArduCopter --console --map
```

Then connect QGroundControl to `udp:127.0.0.1:14550`.

For the MATLAB fallback controller, you also need MATLAB R2021b+ with the ArduPilot SITL JSON connector.

---

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Ardupilot-Drone-Security-Research-ArduPilot-SITL-waypoint-missions-MATLAB/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/hassan-hfk__Ardupilot-Drone-Security-Research.md`.
