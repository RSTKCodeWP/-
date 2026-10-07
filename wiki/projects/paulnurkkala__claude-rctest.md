# claude-rctest

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [paulnurkkala/claude-rctest](https://github.com/paulnurkkala/claude-rctest) |
| Локальна тека | `claude-rctest-Betaflight-RC-Test-Claude-Plugin` |
| У бібліотеці | watch |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-05-19 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A Claude Code plugin that verifies a connected Betaflight FC is actually receiving live RC frames from its receiver. Samples `MSP_RC` for a few seconds, decodes `MSP_STATUS_EX` failsafe flags, and renders a LIVE / NOT-LIVE verdict with per-channel jitter, switch positions, and throttle annotations.

_З README.md, без переказу._

## Для чого

Claude Code plugin: verify a Betaflight FC is receiving live RC frames from its receiver. /rctest

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «betaflight».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Claude Code plugin: verify a Betaflight FC is receiving live RC frames from its receiver. /rctest

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `README.md`
- `skills/`

Типи файлів за вибіркою (4 файлів, глибина до 3): Markdown (2), (без суфікса) (1), Python (1).


## Що треба

### Requirements

- macOS/Linux with a Betaflight FC on `/dev/cu.usbmodem*`
- Python 3 with `pyserial` (`pip install pyserial`)


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install

```
/plugin install rctest@paulnurkkala/claude-rctest
```
### Usage

```
/rctest
```

or ask "verify RX", "check the receiver", "is BF getting input from the radio", "did the bind take", "test the controller".

Flags:

- `--duration SECONDS` — sample longer (default 3). Longer windows catch slower switch movements.
- `--channels N` — how many channels to show in the table (default 12).
- `--raw` — print every individual sample as it arrives instead of the min/max summary. Useful when physically wiggling a stick to watch values update.
- `--port PATH` — override port autodetect.

## З чого зібрана картка

`catalog.json`, `claude-rctest-Betaflight-RC-Test-Claude-Plugin/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/paulnurkkala__claude-rctest.md`.
