# Leoflight

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

Каталог тримає категорію `other`. Зал «Польотні контролери і прошивки» поставлено, бо в назві, описі або шляху є «ardupilot».

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/leoflight-dual-thrustmasters](https://github.com/RSTKCodeWP/leoflight-dual-thrustmasters) |
| Локальна тека | `leoflight-dual-thrustmasters-Jetson-Dual-Thrustmaster-MAVLink` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

Dual Thrustmaster T.16000M FCS joystick-to-ArduPilot MAVLink bridge with real-time 3D visualization, running on an NVIDIA Jetson.

_З README.md, без переказу._

## Для чого

Dual Thrustmaster T.16000M FCS joystick-to-ArduPilot MAVLink bridge with real-time 3D visualization, running on an NVIDIA Jetson.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `config.py`
- `input_monitor.py`
- `leoflight.py`
- `README.md`
- `requirements.txt`
- `SETUP_GUIDE.md`

Типи файлів за вибіркою (7 файлів, глибина до 3): Python (3), Markdown (2), .txt (1), (без суфікса) (1).


## Що треба

### Prerequisites

- NVIDIA Jetson (tested on Jetson Nano, Linux 4.9.253-tegra)
- ArduPilot flight controller connected via USB-C
- Two Thrustmaster T.16000M FCS joysticks connected via USB
- Python 3.6+ with pygame, pymavlink, pyserial

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `pygame`, `pymavlink`, `pyserial`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install

```bash
# System dependencies
sudo apt-get install -y python3-pip \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libfreetype6-dev libxml2-dev libxslt1-dev

# Python packages
pip3 install cython
pip3 install -r requirements.txt

# Joystick permissions
sudo usermod -aG input $USER
```
### Flight Controller Setup

The application automatically configures the FC on startup:

1. Disables pre-arm checks (`ARMING_CHECK=0`)
2. Disables battery failsafe (`BATT_FS_LOW_ACT=0`)
3. Sets ACRO flight mode
4. Force arms the vehicle

See [`SETUP_GUIDE.md`](../../leoflight-dual-thrustmasters-Jetson-Dual-Thrustmaster-MAVLink/SETUP_GUIDE.md) for the full setup guide including network configuration, SSH setup, deployment from a Mac, and troubleshooting.

## З чого зібрана картка

`catalog.json`, `leoflight-dual-thrustmasters-Jetson-Dual-Thrustmaster-MAVLink/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__leoflight-dual-thrustmasters.md`.
