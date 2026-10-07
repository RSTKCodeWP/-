# RadioMaster AX12 — Reverse Engineering Reference

> Картка виставки. Зал: [Радіо](../halls/radio.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rmeadomavic/ax12-research](https://github.com/rmeadomavic/ax12-research) |
| Локальна тека | `fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine` |
| У бібліотеці | keep |
| Категорії каталогу | `radio`, `elrs` |
| Зірки (каталог) | 14 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

Independent hardware research on the RadioMaster AX12 RC transmitter. No manufacturer documentation exists for these internals. Everything here came from a stock device — passive `strace` captures on the running app, symbol-level binary analysis, and on-device probing. No firmware was modified.

_З README.md, без переказу._

## Для чого

RadioMaster AX12 hardware reverse engineering — UMBUS protocol spec, native library analysis, device tree, tools, and developer setup guide

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «expresslrs».
- Дослідник протоколів і прошивок — у тексті є «reverse engineering».


Теми GitHub: `android-9`, `at32f435`, `crsf`, `expresslrs`, `fpv`, `mavlink`, `mediatek-mt8788`, `radiomaster`, `radiomaster-ax12`, `reverse-engineering`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: RadioMaster AX12 hardware reverse engineering — UMBUS protocol spec, native library analysis, device tree, tools, and developer setup guide

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `calibration.json`
- `calibration_log.jsonl`
- `captures/`
- `CHANGELOG.md`
- `CLAUDE.md`
- `CONTRIBUTING.md`
- `dashboard/`
- `data/`
- `device-tree/`
- `docs/`
- `LICENSE`
- `lua-scripts/`
- `pyproject.toml`
- `README.md`
- `ROADMAP.md`
- `scripts/`
- `SECURITY.md`
- `THIRD_PARTY_NOTICES.md`
- `tools/`
- `umbus/`

Типи файлів за вибіркою (145 файлів, глибина до 3): Python (49), Markdown (44), Lua (16), shell (8), .txt (8), JSON (7).

Фрагмент README про будову:

### Architecture

The AX12 pairs a MediaTek MT8788 SoC running Android 9 with an AT32F435 coprocessor that owns all physical I/O. The two communicate over UMBUS — a proprietary serial protocol at 921600 baud.

```
┌──────────────┐  UART @ 921600   ┌───────────┐  CRSF  ┌──────────┐
│  MT8788 SoC  │◄───── UMBUS ────►│  AT32 MCU │◄──────►│ ELRS TX  │
│  Android 9   │                  │  AT32F435 │        │ (LR1121) │
│  Flyshark    │                  │           │        └──────────┘
│  Qt6 + Lua   │                  │ Gimbals   │
└──────────────┘                  │ Switches  │
                                  │ Pots/Trims│
                                  └───────────┘
```

The Android side runs Flyshark, a Qt6/QML application with an embedded Lua 5.3 VM. The MCU handles hall-effect gimbals, switches, pots, trims, and drives the ELRS LR1121 RF module over CRSF.

## Що треба

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `radiomaster-umbus`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

```bash
# Parse UMBUS frames from a strace capture
python3 tools/strace-parser.py captures/idle-strace.txt

# Validate CRC checksums
python3 tools/umbus.py captures/umbus-mcu-standalone.bin

# Generate synthetic traffic for offline testing
python3 tools/simulator.py generate --seconds 5
```

On a rooted AX12, see the [Capture Session Guide](../../fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/docs/guides/capture-session-guide.md) to record your own data.

## Супутні документи в теці

- [`docs/DEVELOPER_QUICKSTART.md`](../../fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/docs/DEVELOPER_QUICKSTART.md)
- [`docs/QGC_SETUP.md`](../../fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/docs/QGC_SETUP.md)
- [`docs/README.md`](../../fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/docs/README.md)
- [`docs/TEST_VERIFICATION_SHEET.md`](../../fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/docs/TEST_VERIFICATION_SHEET.md)
- [`docs/VELOCIDRONE_SIM_MODE.md`](../../fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/docs/VELOCIDRONE_SIM_MODE.md)
- [`docs/peripheral-exploration.md`](../../fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/docs/peripheral-exploration.md)
- [`CONTRIBUTING.md`](../../fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ax12-research-RadioMaster-AX12-hardware-reverse-engine/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rmeadomavic__ax12-research.md`.
