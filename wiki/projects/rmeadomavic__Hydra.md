# Hydra Detect v2.0

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rmeadomavic/Hydra](https://github.com/rmeadomavic/Hydra) |
| Локальна тека | `fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa` |
| У бібліотеці | keep |
| Категорії каталогу | `fc`, `ai` |
| Зірки (каталог) | 3 |
| Оновлено upstream | 2026-07-20 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-2.0 |

## Ідея

Real-time object detection and tracking payload for uncrewed vehicles running ArduPilot. Runs on NVIDIA Jetson Orin Nano. Processes a camera feed through YOLO + ByteTrack, pushes detection data to the GCS over MAVLink, emits CoT to TAK, and serves an operator dashboard on port 8080. No firmware changes. Drones, boats, rovers, fixed-wing.

_З README.md, без переказу._

## Для чого

Real-time perception and RF detection payload for ArduPilot uncrewed vehicles. Runs on NVIDIA Jetson Orin Nano. YOLOv8 + ByteTrack + MAVLink + TAK.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `bytetrack`, `computer-vision`, `edge-ai`, `jetson-orin-nano`, `mavlink`, `tak`, `uncrewed-systems`, `yolov8`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Real-time perception and RF detection payload for ArduPilot uncrewed vehicles. Runs on NVIDIA Jetson Orin Nano. YOLOv8 + ByteTrack + MAVLink + TAK.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `atak-plugin/`
- `benchmarks/`
- `CHANGELOG.md`
- `compose.dev.yml`
- `config.ini`
- `config.ini.factory`
- `docker-compose.yml`
- `Dockerfile`
- `docs/`
- `enforcer_params.parm`
- `hydra_detect/`
- `IP-PROVENANCE.md`
- `LICENSE`
- `Makefile`
- `mediamtx.yml`
- `models/`
- `profiles.json`
- `pytest.ini`
- `README.md`
- `requirements-dev.txt`
- `requirements-extra.txt`
- `requirements.lock`
- `requirements.txt`
- `scripts/`

Типи файлів за вибіркою (351 файлів, глибина до 3): Python (233), Markdown (52), HTML (14), shell (9), (без суфікса) (7), YAML (7).


## Що треба

### Dependencies

Python 3.10+, OpenCV (CUDA in Docker), ultralytics, supervision,
pymavlink, FastAPI + uvicorn. Optional: Kismet, GStreamer, mgrs,
requests. Base image: `dustynv/l4t-pytorch:r36.4.0`.

- Маніфести збірки: Python (requirements.txt), Make.
- requirements.txt: `opencv-python-headless>=4.13.0.92,<5.0`, `numpy>=1.24,<3.0`, `ultralytics>=8.4.48,<9.0`, `supervision>=0.18,<1.0`, `pymavlink>=2.4.49,<3.0`, `pyserial>=3.5,<4.0`, `mgrs>=1.5.4,<2.0`, `fastapi>=0.139.0,<2.0`, `uvicorn[standard]>=0.51.0,<1.0`, `jinja2>=3.1.6,<4.0`, `requests>=2.34.2,<3.0`, `ntplib>=0.4,<1.0`, `pytak[with-crypto]>=7.3,<8.0`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick start

```bash
# 1. Clone
git clone https://github.com/rmeadomavic/Hydra.git
cd Hydra

# 2. Run the Jetson setup (checks prerequisites, builds, configures, and
#    offers to launch the container)
bash scripts/hydra-setup.sh

# 3. To launch directly after setup, if you declined its launch prompt
docker run --rm --privileged --runtime nvidia --network host \
  -v $(pwd)/config.ini:/app/config.ini \
  -v $(pwd)/models:/models \
  -v $(pwd)/output_data:/data \
  hydra-detect

# 4. Open the dashboard
# http://<jetson-ip>:8080/
```

Edit `config.ini` to set camera source, MAVLink connection, callsign,
and TAK endpoint before the first run. First-boot operators can use
the `/setup` wizard instead of editing the file by hand.

## Супутні документи в теці

- [`docs/analog-camera-setup.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/analog-camera-setup.md)
- [`docs/api-reference.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/api-reference.md)
- [`docs/architecture.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/architecture.md)
- [`docs/autonomous-operations.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/autonomous-operations.md)
- [`docs/configuration.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/configuration.md)
- [`docs/dashboard-user-guide.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/dashboard-user-guide.md)
- [`docs/dashboard.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/dashboard.md)
- [`docs/deployment.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/deployment.md)
- [`docs/field-connectivity.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/field-connectivity.md)
- [`docs/fpv-osd.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/fpv-osd.md)
- [`docs/future-directions.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/future-directions.md)
- [`docs/getting-started.md`](../../fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/docs/getting-started.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Hydra-Real-time-perception-and-RF-detection-pa/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rmeadomavic__Hydra.md`.
