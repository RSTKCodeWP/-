# 🚁 Canary Ground Control 📡

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [judahpaul16/canarygc](https://github.com/judahpaul16/canarygc) |
| Локальна тека | `fpv-library/repos/canarygc-A-web-based-ground-control-station-GCS-f` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc`, `tools` |
| Зірки (каталог) | 29 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

A web-based ground control station (GCS) for remote autopilot management via the [MAVLink protocol](https://en.wikipedia.org/wiki/MAVLink).

_З README.md, без переказу._

## Для чого

A web-based ground control station (GCS) for remote autopilot management via the MAVLink protocol.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Розробник польотного контролера — у тексті є «betaflight».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `drone`, `gcs`, `iot`, `mavlink`, `plane`, `px4`, `quadcopter`, `raspberry-pi`, `rc`, `rover`, `sitl`.

## Функція

Список із розділу features / можливості в README:

- Live MAVLink telemetry and control (attitude, position, battery, GPS, mode changes, arm/disarm, virtual D-Pad), with flight modes and armed state decoded correctly for both ArduPilot and PX4.
- Gamepad flight streams a connected pad as `MANUAL_CONTROL`, switches the vehicle to its stick mode (PX4 Position, ArduPilot Loiter), and hands back to an autonomous hold on release.
- WebRTC camera feed from an onboard Raspberry Pi camera via [MediaMTX](https://github.com/bluenviron/mediamtx).
- One persistent map behind every page with curved waypoint legs and session-persistent toggles, plus light, dark, and hybrid-satellite basemaps from a MapTiler key or keyless fallbacks, each overridable with a custom XYZ URL.
- Airspace, LAANC ceiling grid, obstacle, and live ADS-B traffic overlays on both maps, from [OpenAIP](https://www.openaip.net) with a key or the FAA's keyless US layers, each with a plain-language popup.
- Plans are stored autopilot-neutral and adjusted to the connected autopilot on upload, ArduPilot running the full command set and PX4 reporting what it substitutes or skips.
- Import QGroundControl `.plan`, Mission Planner `.waypoints`, the app's JSON, a Google Earth `.kml` or `.kmz`, or a coordinate `.csv`.
- Five pattern generators (survey transects, orbit ring, corridor lanes, expanding-square search, structure scan) and one-click path optimization that raises or routes legs around obstacles, buildings, and restricted airspace.
- Pre-flight validation of every waypoint and leg against altitude limits, a home geofence, and fetched airspace, blocking on restricted airspace and prompting on controlled.
- Lost-operator failsafe (return to launch or synthesized autoland), a manual-control deadman, audible callouts, and per-event email alerts with live coordinates.
- MAVLink 2 signing with replay protection, so a publicly reachable link accepts commands only from a key holder.
- Firmware tab flashes ArduPilot, PX4, Betaflight, and INAV, detecting boards over MSP and flashing over USB DFU or the autopilot's CRC-verified serial bootloader.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `compose/`
- `contrib/`
- `CONTRIBUTING.md`
- `docker-compose.yml`
- `LICENSE.md`
- `README.md`
- `screenshots/`

Типи файлів за вибіркою (69 файлів, глибина до 3): JSON (14), TypeScript (11), (без суфікса) (9), .png (9), Markdown (4), shell (4).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Install-Only (Without System Setup)

Skips the host provisioning (installing Docker, nginx, and the other system packages, the UFW firewall and 4G routing rules, the Docker daemon config, and the Raspberry Pi UART overlays) and just brings the app up with Docker Compose, assuming Docker is already installed and running.
```bash
curl -s https://raw.githubusercontent.com/judahpaul16/canarygc/main/contrib/setup.sh | \
    bash -s -- --install-only
```


---

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/canarygc-A-web-based-ground-control-station-GCS-f/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/canarygc-A-web-based-ground-control-station-GCS-f/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/judahpaul16__canarygc.md`.
