# N-Defender Drone Detection System

> Картка виставки. Зал: [Зір і алгоритми](../halls/ai.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [flyspark015/N-Defender-Drone-Detection-System](https://github.com/flyspark015/N-Defender-Drone-Detection-System) |
| Локальна тека | `fpv-library/repos/N-Defender-Drone-Detection-System-N-Defender-Wideband-Drone-Detection-Loca` |
| У бібліотеці | keep |
| Категорії каталогу | `detection`, `ai` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2025-12-05 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

**7" Touchscreen, 1 MHz–6 GHz RF Coverage, Analog FPV Receive, DF & Triangulation**

> Status: **Draft v0.1** > Owner: AnuShakti Infotech Pvt. Ltd. (FlySpark) > Target use: FPV/RC spectrum monitoring, drone presence detection, Remote ID display, direction finding (DF), coarse-to-precise localization, and optional analog 5.8 GHz video reception.

_З README.md, без переказу._

## Для чого

N-Defender: Wideband Drone Detection & Localization System (1 MHz–6 GHz | DF | FPV | Remote ID)

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: N-Defender: Wideband Drone Detection & Localization System (1 MHz–6 GHz | DF | FPV | Remote ID)

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `hardware_list.md`
- `info/`
- `README.md`
- `v1 hardware list`

Типи файлів за вибіркою (6 файлів, глибина до 3): Markdown (4), JSON (1), (без суфікса) (1).

Фрагмент README про будову:

### 5) System Architecture (High-Level)

**Blocks**

1. **Compute/UI**: Raspberry Pi 4/5 running kiosk UI (React/Browser) + control daemons.
2. **Wideband SDR**: 1 MHz–6 GHz scanning (HackRF or USRP tier).
3. **Coherent DF array**: 5‑channel coherent SDR for sub‑GHz AoA (Kraken‑class).
4. **Analog FPV Receiver**: 5.8 GHz (RX5808/diversity) → USB capture → UI window.
5. **RSSI Heads**: AD8318 log detectors with directional antennas for fast 2.4/5.8 bearing.
6. **GNSS & IMU**: GPS for geotagging; IMU/compass for heading stabilization.
7. **Networking**: Wi‑Fi/LTE for multi‑node triangulation & remote viewing.

**Data Flow**

* SDR/DF pipelines → Detection service → Event bus (WebSocket) → UI.
* RID receiver → RID service → Map overlays & database.
* Analog RX → UVC capture → UI video panel.
* Logs → SQLite/CSV/KML exporters.

---

## Що треба

### 8.4 Non‑Functional Requirements

* Boot‑to‑UI ≤ 30 s; watchdog for service restarts.
* Data integrity: graceful power‑loss handling; journaled FS.
* Security: local‑only by default; optional VPN for remote nodes; API token for writes.

---


## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/N-Defender-Drone-Detection-System-N-Defender-Wideband-Drone-Detection-Loca/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/flyspark015__N-Defender-Drone-Detection-System.md`.
