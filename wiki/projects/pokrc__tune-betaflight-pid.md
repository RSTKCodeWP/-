# Tune Betaflight PID from Blackbox Logs

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [pokrc/tune-betaflight-pid](https://github.com/pokrc/tune-betaflight-pid) |
| Локальна тека | `fpv-library/repos/tune-betaflight-pid-Codex-skill-turn-Betaflight-Blackbox-bbl` |
| У бібліотеці | keep |
| Категорії каталогу | `link`, `fc` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

**An evidence-first Codex skill for turning Betaflight Blackbox data into a reviewable tuning CLI.**

Useful to your FPV workflow? <a href="https://github.com/pokrc/tune-betaflight-pid/stargazers">Star the project</a> so reproducible, data-driven tuning stays easy to find.

Give Codex one or more Betaflight Blackbox `.bbl` logs and receive an auditable analysis plus an adaptive CLI stage for PID, D-term/gyro filtering, RPM validation, and TPA decisions. Raw `.bbl` input is decoded locally; manual CSV conversion is optional rather than required.

This tool is designed for real symptoms—resonance, noisy flight sound, hot motors, D-term noise, suspicious RPM filtering, and before/after flight comparisons. It is a decision aid, not a universal preset: every output must be reviewed against the actual frame, propellers, motors, ESC firmware, battery, firmware version, and motor temperature.

_З README.md, без переказу._

## Для чого

Codex skill: turn Betaflight Blackbox .bbl logs into evidence-gated, paste-ready CLI stages with local diagnostics and RPM validation.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «betaflight».


Теми GitHub: `bbl`, `betaflight`, `blackbox`, `blackbox-tools`, `codex`, `codex-skill`, `control-systems`, `drone`, `dshot`, `flight-controller`, `flight-log-analysis`, `fpv`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Codex skill: turn Betaflight Blackbox .bbl logs into evidence-gated, paste-ready CLI stages with local diagnostics and RPM validation.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `assets/`
- `CONTRIBUTING.md`
- `LICENSE.md`
- `NOTICE.md`
- `README.md`
- `requirements.txt`
- `tune-betaflight-pid/`

Типи файлів за вибіркою (20 файлів, глибина до 3): Markdown (10), Python (4), JSON (2), .txt (1), .png (1), .svg (1).


## Що треба

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `numpy>=1.24,<3`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install in Codex

Install the bundled skill directory, then start a new Codex task:

```bash
git clone --depth 1 https://github.com/pokrc/tune-betaflight-pid.git /tmp/tune-betaflight-pid
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R /tmp/tune-betaflight-pid/tune-betaflight-pid "${CODEX_HOME:-$HOME/.codex}/skills/"
```

Then attach a log and use:

```text
Use $tune-betaflight-pid to analyze this Betaflight .bbl and produce a staged CLI.
```

For the best result, attach the `.bbl`, the relevant `diff all` backup, Betaflight version, board and craft details, motor/propeller/battery information, and a short description of the symptom. A matched baseline log can be supplied for before/after analysis.

The skill automatically chooses the safest supported mode. It does **not** enable bidirectional DShot from a log alone. RPM setup requires both `--esc-bidir-confirmed` and `--motor-poles-confirmed <bell-magnet-count>` after independently confirming ESC firmware support and counting magnets on the motor bell.

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/tune-betaflight-pid-Codex-skill-turn-Betaflight-Blackbox-bbl/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/tune-betaflight-pid-Codex-skill-turn-Betaflight-Blackbox-bbl/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/pokrc__tune-betaflight-pid.md`.
