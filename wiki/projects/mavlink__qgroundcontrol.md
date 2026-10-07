# mavlink/qgroundcontrol

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [mavlink/qgroundcontrol](https://github.com/mavlink/qgroundcontrol) |
| Локальна тека | `fpv-library/repos/qgroundcontrol-Cross-platform-ground-control-station-fo` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc` |
| Зірки (каталог) | 4795 |
| Оновлено upstream | 2026-08-02 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

**QGroundControl** (QGC) is a Ground Control Station (GCS) for UAVs, providing full flight control and mission planning for any *MAVLink-enabled* drone, including *PX4* and *ArduPilot* platforms.

_З README.md, без переказу._

## Для чого

Cross-platform ground control station for drones (Android, iOS, Mac OS, Linux, Windows)

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».
- Розробник відеотракту — у тексті є «gstreamer».


Теми GitHub: `ardupilot`, `drone`, `hacktoberfest`, `mavlink`, `pixhawk`, `px4`, `qt`, `uas`, `uav`.

## Функція

Список із розділу features / можливості в README:

- **Mission planning** — plan, edit, and fly autonomous waypoint, survey, and structure-scan missions.
- **Live Fly View** — real-time flight display with map, instruments, and full vehicle telemetry.
- **Vehicle setup** — guided wizards for sensor calibration, radio, flight modes, and power.
- **Parameter tuning** — inspect and edit every vehicle parameter through the Fact System.
- **Video streaming** — GStreamer-based UDP RTP / RTSP video with recording in the Flight Display.
- **Multi-vehicle** — connect to and monitor multiple vehicles simultaneously.
- **MAVLink tooling** — built-in MAVLink Inspector, console, and log download/analysis.
- **Cross-platform** — Windows, macOS, Linux, Android, and iOS from a single codebase.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `android/`
- `CHANGELOG.md`
- `CLAUDE.md`
- `cmake/`
- `CMakeLists.txt`
- `CMakePresets.json.template`
- `CODING_STYLE.md`
- `crowdin.yml`
- `CTestCustom.cmake.in`
- `custom-example/`
- `deploy/`
- `docs/`
- `Doxyfile`
- `justfile`
- `LICENSE-APACHE`
- `LICENSE-GPL`
- `package-lock.json`
- `package.json`
- `pyrightconfig.json`
- `qgcresources.qrc`
- `README.md`
- `resources/`
- `ruff.toml`

Типи файлів за вибіркою (обрізано після 2000 файлів, глибина до 3): C (463), .qml (441), C++ (426), .jpg (149), JSON (112), .svg (108).


## Що треба

- Маніфести збірки: Node.js (package.json), CMake.
- npm-скрипти в package.json: `docs:dev`, `docs:build`, `docs:preview`, `start`.
- dependencies: `vitepress`.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## Супутні документи в теці

- [`docs/index.md`](../../fpv-library/repos/qgroundcontrol-Cross-platform-ground-control-station-fo/docs/index.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/qgroundcontrol-Cross-platform-ground-control-station-fo/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/mavlink__qgroundcontrol.md`.
