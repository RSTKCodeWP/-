# BlackFiber — FOG Drone Fiber-Tether Neutralization System

> Картка виставки. Зал: [Оптика і трос](../halls/fiber.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [jusstinn/Katena](https://github.com/jusstinn/Katena) |
| Локальна тека | `fpv-library/repos/Katena-C-UAV-solution-for-fiber-optic-drones` |
| У бібліотеці | skip |
| Категорії каталогу | `fiber` |
| Зірки (каталог) | 3 |
| Оновлено upstream | 2026-05-03 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

> **One sentence:** Jammers don't work on Fiber-Optic-Guided drones. > We don't jam — we corrupt the optical channel by damaging the fiber's > cladding with a precision laser, dropping the control link in > milliseconds. > > National Security Hackathon 2026 · Palantir track · Built on CASK.

_З README.md, без переказу._

## Для чого

C-UAV solution for fiber optic drones

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: C-UAV solution for fiber optic drones

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `dashboard.py`
- `DroneKill.gif`
- `DroneKill.mp4`
- `hardware.jpg`
- `jetson/`
- `macbook/`
- `Makefile`
- `optical_injection_proof.gif`
- `optical_injection_proof.mp4`
- `pico/`
- `pyproject.toml`
- `README.md`
- `requirements.txt`
- `scripts/`
- `tests/`

Типи файлів за вибіркою (65 файлів, глибина до 3): Python (48), Markdown (3), .mp4 (2), .gif (2), (без суфікса) (2), shell (2).

Фрагмент README про будову:

### Smooth-motion architecture (why the gimbal isn't jittery)

Two things kept biting us before this iteration:

1. **Bursty motion** when YOLO ran at 6 fps — the gimbal stepped once
   per detection, so 167 ms gaps were visible to the eye.
2. **"Bang-bang" velocity** — the slew limiter capped angular speed
   but allowed instantaneous velocity changes (0 → 90 °/s in one
   frame), which made cheap servos visibly twitch.

Both are now solved by `GimbalDriver` (in
[`scripts/jetson_live_detect.py`](../../fpv-library/repos/Katena-C-UAV-solution-for-fiber-optic-drones/scripts/jetson_live_detect.py)):

- A **background thread ticks at 100 Hz**, decoupled from the
  detection rate. The detection loop just calls
  `driver.set_target(pan, tilt, rot, mode)` whenever it has a new
  desired aim.
- Each tick runs a **trapezoidal motion profile per axis**:
  velocity ramps up at most `a_max·dt` per tick, cruises at `v_max`,
  then decelerates along the `√(2·a_max·|error|)` envelope so the
  servo lands on target without overshoot.
- Commands are sent to the Pico at a separate rate cap (`30 Hz` by
  default) so the serial link is never flooded.

End result: even when the upstream detector is at 6 fps, the gimbal
moves continuously at 100 Hz with smooth acceleration.

## Що треба

- Маніфести збірки: Python (requirements.txt), Python (pyproject.toml), Make.
- requirements.txt: `altair==6.1.0`, `annotated-types==0.7.0`, `anyio==4.13.0`, `attrs==26.1.0`, `blinker==1.9.0`, `cachetools==7.1.0`, `certifi==2026.4.22`, `charset-normalizer==3.4.7`, `click==8.3.3`, `contourpy==1.3.3`, `coverage==7.13.5`, `cycler==0.12.1`, `filelock==3.29.0`, `fonttools==4.62.1`, `foundry-platform-sdk==1.82.0`.
- pyproject name: `blackfiber`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quickstart (MacBook)

```bash
cd ~/Desktop/Katena
source .venv/bin/activate

make test           # 156 unit tests, ~3s, no hardware needed
make tracker        # full pipeline against laptop webcam in mock-Pico mode
make calibrate      # local calibration tool (camera + Pico same machine)
make dashboard      # Streamlit ops dashboard
make seed           # pre-seed dashboard with demo engagements
make smoke          # camera + YOLO + serial + Foundry live checks
make help           # all available commands
```

Before each commit:

```bash
bash scripts/run_tests.sh        # syntax + unit tests, < 5s
bash scripts/run_tests.sh --smoke # also exercises camera/YOLO/serial/Foundry
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Katena-C-UAV-solution-for-fiber-optic-drones/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/jusstinn__Katena.md`.
