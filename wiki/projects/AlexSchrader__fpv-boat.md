# FPV RC Boat

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [AlexSchrader/fpv-boat](https://github.com/AlexSchrader/fpv-boat) |
| Локальна тека | `fpv-boat-RaspberryPi-Quest-VR-RC-Boat` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

An FPV RC boat you pilot from a Meta Quest headset: a Raspberry Pi Zero 2 W streams live camera video over WebRTC into a head-locked WebXR viewer with a telemetry HUD, records H.264 to the Pi while streaming, and takes throttle/steer input from the Quest controllers over a websocket to drive the motors.

_З README.md, без переказу._

## Для чого

An FPV RC boat you pilot from a Meta Quest headset: a Raspberry Pi Zero 2 W streams live camera video over WebRTC into a head-locked WebXR viewer with a telemetry HUD, records H.264 to the Pi while streaming, and takes throttle/steer input from the Quest controllers over a websocket to drive the motors.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник відеотракту — у тексті є «h.264».


## Функція

Список із розділу features / можливості в README:

- **Live FPV video** — WebRTC (`aiortc` + `picamera2`), 1280×720, head-locked
- **Telemetry HUD** — link quality + ping, recording status, storage, battery
- **Simultaneous recording** — H.264 to `~/recordings/`, runs alongside the
- **Controller input** — Quest controllers read via WebXR `inputSources`;
- **Differential-thrust motor control** — `motor_control.py` drives an L298N

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `battery_control.py`
- `CLAUDE.md`
- `clips.html`
- `HARDWARE.md`
- `lights_control.py`
- `motor_control.py`
- `NETWORKING.md`
- `pan_tilt_control.py`
- `README.md`
- `requirements.txt`
- `ROADMAP.md`
- `setup.sh`
- `test_battery_control.py`
- `test_lights_control.py`
- `test_motor_control.py`
- `test_pan_tilt_control.py`
- `three.module.js`
- `watch.html`
- `webrtc_stream.py`
- `webxr_viewer.html`

Типи файлів за вибіркою (21 файлів, глибина до 3): Python (9), Markdown (5), HTML (3), JavaScript (1), shell (1), .txt (1).


## Що треба

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `aiohttp`, `aiortc`, `gpiozero`, `lgpio`, `adafruit-circuitpython-servokit`, `pi-ina219`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Fresh Pi setup / recovery

On a newly-imaged Pi (or after an SD reflash), clone the repo and run the
provisioning script — it enables I2C, installs all the system + Python deps,
generates the TLS cert, and adds the passwordless-shutdown sudoers rule:

```sh
git clone https://github.com/AlexSchrader/fpv-boat.git ~/fpv-boat && cd ~/fpv-boat
bash setup.sh
```

`setup.sh` is idempotent (safe to re-run). Python deps are also in
`requirements.txt` (`pip3 install --break-system-packages -r requirements.txt`);
note **picamera2 comes from apt** (`python3-picamera2`), not pip. On Bookworm
gpiozero uses the **lgpio** pin factory by default — `pigpio` is no longer
packaged and isn't needed.

## З чого зібрана картка

`catalog.json`, `fpv-boat-RaspberryPi-Quest-VR-RC-Boat/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/AlexSchrader__fpv-boat.md`.
