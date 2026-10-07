# claude-osdfont

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [paulnurkkala/claude-osdfont](https://github.com/paulnurkkala/claude-osdfont) |
| Локальна тека | `claude-osdfont-Betaflight-OSD-Font-Claude-Plugin` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-05-19 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A Claude Code plugin that uploads a stock Betaflight OSD font (`.mcm`) to a connected MAX7456-based analog FC over MSP. Pulls the `.mcm` straight from the `betaflight-configurator` GitHub repo, parses the 256 × 54-byte character data, and writes one character at a time via `MSP_OSD_CHAR_WRITE` (cmd 87).

_З README.md, без переказу._

## Для чого

Claude Code plugin: upload an OSD .mcm font to a Betaflight FC over MSP. /osdfont

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Claude Code plugin: upload an OSD .mcm font to a Betaflight FC over MSP. /osdfont

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `README.md`
- `skills/`

Типи файлів за вибіркою (4 файлів, глибина до 3): Markdown (2), (без суфікса) (1), Python (1).


## Що треба

### Requirements

- macOS/Linux with a Betaflight FC on `/dev/cu.usbmodem*`
- Python 3 with `pyserial` and `requests` (`pip install pyserial requests`)
- A MAX7456-based analog OSD (this plugin is SD/analog only — HD fonts for HDZero/Walksnail/DJI use a different upload path and are NOT supported)


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install

```
/plugin install osdfont@paulnurkkala/claude-osdfont
```
### Usage

```
/osdfont clarity
/osdfont bold
/osdfont default
```

or ask "upload the Clarity font", "change OSD font to Bold", "set the font to digital".

Supported font names (case-insensitive, prefix-matched):

`betaflight`, `bold`, `clarity`, `default`, `digital`, `extra_large` (alias `xl`), `impact`, `impact_mini` (alias `mini`), `large`, `vision`

Flags:

- `--list` — print supported font names
- `--probe` — preflight only (camera/OSD status + last-known font), no upload
- `--dry-run` — download + parse only, no FC contact
- `--page {1,2}` — page 1 (chars 0–255, default) or page 2 (chars 256–511)
- `--port PATH` — override port autodetect

## З чого зібрана картка

`catalog.json`, `claude-osdfont-Betaflight-OSD-Font-Claude-Plugin/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/paulnurkkala__claude-osdfont.md`.
