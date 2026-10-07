# AX12 Tactical Tools

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rmeadomavic/ax12-tac-tools](https://github.com/rmeadomavic/ax12-tac-tools) |
| Локальна тека | `fpv-library/repos/ax12-tac-tools-Turns-the-RadioMaster-AX12-Android-radio` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `bridge`, `radio`, `fc`, `elrs` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-07-19 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

The AX12 is an Android radio. Run the CoT bridge on it and your aircraft shows up on the COP while you fly. The bridge reads MAVLink telemetry off the ELRS link on `/dev/ttyS1` and publishes the track as Cursor-on-Target to ATAK and any TAK server. The radio does it. No laptop, no second GCS.

The bridge sends the aircraft's position, straight from MAVLink. It never needs the operator's own position. That matters here: this radio has no GNSS antenna, so anything that wants the operator's location is dead. The aircraft track is unaffected.

_З README.md, без переказу._

## Для чого

Turns the RadioMaster AX12 Android radio into a field GCS - CoT bridge streaming MAVLink telemetry to ATAK / TAK server, with on-device web and CLI launchers. Termux plus stdlib Python.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «qgroundcontrol».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «expresslrs».


Теми GitHub: `ardupilot`, `atak`, `cot`, `expresslrs`, `mavlink`, `qgroundcontrol`, `radiomaster`, `radiomaster-ax12`, `tak-server`, `termux`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Turns the RadioMaster AX12 Android radio into a field GCS - CoT bridge streaming MAVLink telemetry to ATAK / TAK server, with on-device web and CLI launchers. Termux plus stdlib Python.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `boot/`
- `CHANGELOG.md`
- `CLAUDE.md`
- `docs/`
- `GETTING_STARTED.md`
- `install.sh`
- `launcher.py`
- `LICENSE`
- `README.md`
- `scripts/`
- `SECURITY.md`
- `shortcuts/`
- `tests/`
- `tools/`
- `tools.json`
- `web_launcher.py`

Типи файлів за вибіркою (32 файлів, глибина до 3): Python (10), Markdown (9), shell (8), (без суфікса) (2), JSON (2), YAML (1).


## Що треба

### Prerequisites

- RadioMaster AX12 (stock firmware; root is built in)
- ELRS 3.5+ in MAVLink mode
- ATAK-CIV **4.10.x** (5.x needs Android 10+, won't install on the AX12)


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install

Open Termux, paste this:

```
pkg install -y curl && curl -sL https://raw.githubusercontent.com/rmeadomavic/ax12-tac-tools/main/install.sh | bash
```

Setup walkthrough: [GETTING_STARTED.md](../../fpv-library/repos/ax12-tac-tools-Turns-the-RadioMaster-AX12-Android-radio/GETTING_STARTED.md).

## Супутні документи в теці

- [`docs/elrs-backpack.md`](../../fpv-library/repos/ax12-tac-tools-Turns-the-RadioMaster-AX12-Android-radio/docs/elrs-backpack.md)
- [`docs/mavlink-setup.md`](../../fpv-library/repos/ax12-tac-tools-Turns-the-RadioMaster-AX12-Android-radio/docs/mavlink-setup.md)
- [`docs/tak-setup.md`](../../fpv-library/repos/ax12-tac-tools-Turns-the-RadioMaster-AX12-Android-radio/docs/tak-setup.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ax12-tac-tools-Turns-the-RadioMaster-AX12-Android-radio/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rmeadomavic__ax12-tac-tools.md`.
