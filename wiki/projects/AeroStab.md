# AeroStab

> Картка виставки. Зал: [Власна розробка](../halls/own.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | немає upstream (власна тека) |
| Локальна тека | `AeroStab` |
| У бібліотеці | own |
| Категорії каталогу | `own` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

GPS-free optical navigation for **ArduPilot** multicopters.

**Target:** Raspberry Pi Zero 2W + Frank-S01-V1.0 (OV5647) → **PosHold hover without GPS**.

_З README.md, без переказу._

## Для чого

GPS-free optical navigation for **ArduPilot** multicopters.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Список із розділу features / можливості в README:

- Lucas–Kanade optical flow + optional PMW3901 blend
- MAVLink ExternalNav (`VISION_POSITION_ESTIMATE` + `VISION_SPEED_ESTIMATE`)
- Hold-last on quality drop · FOV live update · metric 1 m grid
- Camera mask editor · RTL path · preflight health gate
- SITL mock FC · GitHub CI · flight log analyzer

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `aerostab/`
- `config/`
- `deploy/`
- `docs/`
- `flash-sd/`
- `FLIGHT.md`
- `image/`
- `LICENSE`
- `logs/`
- `pyproject.toml`
- `README.md`
- `requirements.txt`
- `scripts/`
- `tests/`

Типи файлів за вибіркою (88 файлів, глибина до 3): Python (37), shell (13), Markdown (11), .service (4), YAML (3), (без суфікса) (2).


## Що треба

- Маніфести збірки: Python (requirements.txt), Python (pyproject.toml).
- requirements.txt: `numpy>=1.21.0`, `opencv-python-headless>=4.5.0`, `pymavlink>=2.4.37`, `pyyaml>=6.0`, `flask>=2.0.0`, `waitress>=2.1.0`.
- pyproject name: `aerostab`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install (Pi)

**SD flash kit (рекомендовано):** [`flash-sd/README.md`](../../AeroStab/flash-sd/README.md)

```bash
bash flash-sd/build.sh
sudo bash flash-sd/prepare-sd.sh /media/$USER/bootfs --auto-install
```

**Вже є OS на Pi:** `sudo bash deploy/install_pi.sh && sudo reboot`

Детальніше: [docs/FLASH.md](../../AeroStab/docs/FLASH.md) · звірка з StabX: [flash-sd/STABX-CHECKLIST.md](../../AeroStab/flash-sd/STABX-CHECKLIST.md)

1. Open **http://aerostab.local:8080** → tab **Політ** / **Інструкція**
2. Wire UART: Pi TX→FC RX, Pi RX→FC TX, GND, 5V
3. Load `deploy/ardupilot_aerostab.param` (SERIAL2 TELEM2 @ 230400 — change if needed)
4. Arm **PosHold** only when UI shows **FLIGHT OK**

## Супутні документи в теці

- [`docs/FLASH.md`](../../AeroStab/docs/FLASH.md)
- [`docs/INSTALL.md`](../../AeroStab/docs/INSTALL.md)
- [`docs/SETTINGS.md`](../../AeroStab/docs/SETTINGS.md)
- [`docs/STABX_IMAGE_ANALYSIS.md`](../../AeroStab/docs/STABX_IMAGE_ANALYSIS.md)
- [`docs/STABX_REVERSE.md`](../../AeroStab/docs/STABX_REVERSE.md)
- [`docs/WIRE.md`](../../AeroStab/docs/WIRE.md)
- [`FLIGHT.md`](../../AeroStab/FLIGHT.md)

## З чого зібрана картка

`catalog.json`, `AeroStab/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/AeroStab.md`.
