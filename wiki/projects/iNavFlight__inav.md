# INAV - navigation capable flight controller

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [iNavFlight/inav](https://github.com/iNavFlight/inav) |
| Локальна тека | `fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s` |
| У бібліотеці | keep |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 4154 |
| Оновлено upstream | 2026-07-26 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

INAV: Navigation-enabled flight control software

_З поля description у catalog.json. Окремого вступу в README немає._

## Для чого

INAV: Navigation-enabled flight control software

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «vtx».
- Розробник польотного контролера — у тексті є «inav».


Теми GitHub: `airplane`, `autopilot`, `fpv`, `hacktoberfest`, `inav`, `quadcopter`, `rc`.

## Функція

Список із розділу features / можливості в README:

- Runs on the most popular F4, AT32, F7 and H7 flight controllers
- On Screen Display (OSD) - both character and pixel style
- DJI OSD integration: all elements, system messages and warnings
- Outstanding performance out of the box
- Position Hold, Altitude Hold, Return To Home and Waypoint Missions
- Excellent support for fixed wing UAVs: airplanes, flying wings
- Blackbox flight recorder logging
- Advanced gyro filtering
- Fully configurable mixer that allows to run any hardware you want: multirotor, fixed wing, rovers, boats and other experimental devices
- Multiple sensor support: GPS, Pitot tube, sonar, lidar, temperature, ESC with BlHeli_32 telemetry
- Logic Conditions, Global Functions and Global Variables: you can program INAV with a GUI
- SmartAudio and IRC Tramp VTX support

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENT.md`
- `AUTHORS`
- `board/`
- `build.sh`
- `build_docs.sh`
- `cmake/`
- `CMakeLists.txt`
- `dev/`
- `Dockerfile`
- `docs/`
- `fake_travis_build.sh`
- `JLinkSettings.ini`
- `lib/`
- `LICENSE`
- `readme.md`
- `src/`
- `Vagrantfile`

Типи файлів за вибіркою (1056 файлів, глибина до 3): C (640), Markdown (149), .png (94), .cmake (29), .txt (26), (без суфікса) (12).


## Що треба

- Маніфести збірки: CMake.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

See: https://github.com/iNavFlight/inav/blob/master/docs/Installation.md

## Супутні документи в теці

- [`docs/1wire.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/1wire.md)
- [`docs/ADSB.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/ADSB.md)
- [`docs/Autotune - fixedwing.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Autotune - fixedwing.md)
- [`docs/Backup and Restore.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Backup and Restore.md)
- [`docs/Battery.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Battery.md)
- [`docs/Blackbox.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Blackbox.md)
- [`docs/Boards.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Boards.md)
- [`docs/Broken USB recovery.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Broken USB recovery.md)
- [`docs/Buzzer.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Buzzer.md)
- [`docs/Channel forwarding.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Channel forwarding.md)
- [`docs/Cli.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Cli.md)
- [`docs/Configuration.md`](../../fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/docs/Configuration.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/inav-INAV-Navigation-enabled-flight-control-s/readme.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/iNavFlight__inav.md`.
