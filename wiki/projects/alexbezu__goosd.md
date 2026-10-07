# GoOSD

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [alexbezu/goosd](https://github.com/alexbezu/goosd) |
| Локальна тека | `fpv-library/repos/goosd-FPV-OSD-HUD-overlay-GUI-for-INAV-Betafli` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-05-13 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

GoOSD is a Go/Ebitengine on-screen display for FPV telemetry. It draws a transparent, always-on-top HUD over an external video or map window.

The application does not decode or receive video packets. Video is expected to be displayed by another process, for example `gst-launch-1.0`. GoOSD listens for MAVLink telemetry over UDP and renders the HUD overlay on top.

Go OSD over a map

Go OSD over FPV video

_З README.md, без переказу._

## Для чого

FPV OSD HUD overlay GUI for INAV/Betaflight/ArduPilot over MAVLink protocol

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: FPV OSD HUD overlay GUI for INAV/Betaflight/ArduPilot over MAVLink protocol

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `assets/`
- `cmd/`
- `go.mod`
- `go.sum`
- `internal/`
- `README.md`

Типи файлів за вибіркою (13 файлів, глибина до 3): Go (7), .jpg (2), .mod (1), Markdown (1), .sum (1), JSON (1).


## Що треба

- Маніфести збірки: Go (go.mod).

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

Run with simulated data:

```sh
go run ./cmd
```

Run with MAVLink UDP input:

```sh
go run ./cmd -mavlink-udp :16000
```

Run as a click-through overlay:

```sh
go run ./cmd -mavlink-udp :16000 -click-through
```

Example H.265 video receiver pipeline:

```sh
gst-launch-1.0 -v udpsrc port=5600 caps='application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string)H265' ! rtph265depay ! avdec_h265 ! videoconvert ! autovideosink sync=false
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/goosd-FPV-OSD-HUD-overlay-GUI-for-INAV-Betafli/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/alexbezu__goosd.md`.
