# claude-mgrsosd

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [paulnurkkala/claude-mgrsosd](https://github.com/paulnurkkala/claude-mgrsosd) |
| Локальна тека | `claude-mgrsosd-Betaflight-OSD-Layout-Claude-Plugin` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-05-19 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A Claude Code plugin that pushes a Betaflight OSD layout (`.rtf` exported from TextEdit) directly to an attached flight controller over MSP/CLI.

Minimal by design: enter CLI, ensure `feature OSD` is on, paste the file line-by-line, stop after `save`. No `dump master`, no reset, no readback verification — earlier "smart" versions kept wedging the FC mid-flash.

_З README.md, без переказу._

## Для чого

Claude Code plugin: push a Betaflight OSD layout .rtf to an attached FC. /mgrsosd

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Claude Code plugin: push a Betaflight OSD layout .rtf to an attached FC. /mgrsosd

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `README.md`
- `skills/`

Типи файлів за вибіркою (4 файлів, глибина до 3): Markdown (2), (без суфікса) (1), Python (1).


## Що треба

### Requirements

- macOS or Linux with a Betaflight FC enumerated as `/dev/cu.usbmodem*` (or pass `--port`)
- Python 3 with `pyserial` installed (`pip install pyserial`)
- An OSD `.rtf` exported from TextEdit (Cocoa RTF — uses `\cf0 ` content marker and `\<newline>` line terminators)


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install

```
/plugin install mgrsosd@paulnurkkala/claude-mgrsosd
```
### Usage

In Claude Code, type:

```
/mgrsosd
```

or ask "push the OSD layout" / "apply the OSD file".

By default it looks for `./diff_bf_osd.rtf` in the current working directory. Override with:

```
/mgrsosd --file path/to/layout.rtf
```

## З чого зібрана картка

`catalog.json`, `claude-mgrsosd-Betaflight-OSD-Layout-Claude-Plugin/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/paulnurkkala__claude-mgrsosd.md`.
