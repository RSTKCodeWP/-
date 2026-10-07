# Recce - Tethered FPV Drone

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [atulakella/recee-drone](https://github.com/atulakella/recee-drone) |
| Локальна тека | `fpv-library/repos/recee-drone-A-tethered-5-inch-FPV-quad-with-wireless` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fiber` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-06-25 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A tethered 5-inch FPV quad with wireless control over ESP-NOW, a hot-swap power switching circuit, MAVLink telemetry, and a full Python GCS with a dark avionics GUI.

_З README.md, без переказу._

## Для чого

A tethered 5-inch FPV quad with wireless control over ESP-NOW, a hot-swap power switching circuit, MAVLink telemetry, and a full Python GCS with a dark avionics GUI.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: A tethered 5-inch FPV quad with wireless control over ESP-NOW, a hot-swap power switching circuit, MAVLink telemetry, and a full Python GCS with a dark avionics GUI.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `bigController.py`
- `CRSF_ESP_NowReciever/`
- `CRSF_ESP_NowSender/`
- `README.md`
- `Schematic_Recce-Switching-Circuit.pdf`
- `VanillaWebserver/`

Типи файлів за вибіркою (12 файлів, глибина до 3): Arduino (3), Markdown (2), C (2), .pdf (1), Python (1), JSON (1).

Фрагмент README про будову:

### How it works

The drone is physically tethered (power delivery), but control and telemetry run wirelessly over ESP-NOW between two ESP32s. A PS5 DualSense connects to the ground station laptop; `bigController.py` reads gamepad input and sends control packets to the transmitter ESP32 over USB serial. The transmitter broadcasts over ESP-NOW to the receiver ESP32 on the drone, which decodes the packet and outputs CRSF directly to the SpeedyBee F405v3 flight controller running iNav. Telemetry flows the other way, the receiver reads MAVLink from the FC and sends structured telemetry back over ESP-NOW to the GCS.

A hot-swap circuit (see schematic) switches between tether power and onboard LiPo mid-flight via GPIO-controlled MOSFETs, triggered from the ground station.

```
PS5 Controller
      │
      ▼
bigController.py  ──USB Serial──►  CRSF_ESP_NowSender (ESP32)
      ▲                                      │ ESP-NOW
      │ telemetry                            ▼
      └──────────────────────  CRSF_ESP_NowReceiver (ESP32)
                                             │ CRSF
                                             ▼
                                    SpeedyBee F405v3 (iNav)
```

## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/recee-drone-A-tethered-5-inch-FPV-quad-with-wireless/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/atulakella__recee-drone.md`.
