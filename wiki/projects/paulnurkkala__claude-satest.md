# claude-satest

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [paulnurkkala/claude-satest](https://github.com/paulnurkkala/claude-satest) |
| Локальна тека | `claude-satest-Betaflight-SmartAudio-Claude-Plugin` |
| У бібліотеці | watch |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-05-19 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A Claude Code plugin that performs an end-to-end SmartAudio sanity test on a connected Betaflight FC: reads `MSP_VTX_CONFIG`, decides whether SA is healthy, and (if it is) runs a visible Raceband 1 → Raceband 2 → wait → Raceband 1 toggle so you can confirm in your goggles that video actually changed channel.

_З README.md, без переказу._

## Для чого

Claude Code plugin: SmartAudio sanity test on a Betaflight FC. /satest

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «goggles».
- Розробник польотного контролера — у тексті є «betaflight».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Claude Code plugin: SmartAudio sanity test on a Betaflight FC. /satest

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `README.md`
- `skills/`

Типи файлів за вибіркою (4 файлів, глибина до 3): Markdown (2), (без суфікса) (1), Python (1).


## Що треба

### Requirements

- macOS/Linux with a Betaflight FC on `/dev/cu.usbmodem*`
- Python 3 with `pyserial` (`pip install pyserial`)
- Goggles powered on and roughly in range — the whole point is for you to *see* the channel change


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install

```
/plugin install satest@paulnurkkala/claude-satest
```
### Usage

```
/satest
```

or ask "test SmartAudio", "check VTX comms", "is SA working".

Flags:

- `--status-only` — print SA health + current channel and exit; skip the toggle dance.
- `--wait SECONDS` — hold the R2 step longer (default 5).

## З чого зібрана картка

`catalog.json`, `claude-satest-Betaflight-SmartAudio-Claude-Plugin/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/paulnurkkala__claude-satest.md`.
