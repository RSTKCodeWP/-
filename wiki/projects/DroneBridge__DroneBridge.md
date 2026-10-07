# DroneBridge

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [DroneBridge/DroneBridge](https://github.com/DroneBridge/DroneBridge) |
| Локальна тека | `fpv-library/repos/DroneBridge-DroneBridge-is-a-system-based-on-the-Wif` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `link`, `osd`, `fc` |
| Зірки (каталог) | 938 |
| Оновлено upstream | 2022-01-07 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-2.0 |

## Ідея

DroneBridge is a system based on the [WifiBroadcast](https://befinitiv.wordpress.com/wifibroadcast-analog-like-transmission-of-live-video-data/) approach. A bidirectional digital radio link between two endpoints is established using standard WiFi hardware and a custom protocol. DroneBridge is optimized for use in UAV applications and is a complete system. It is intended be a real alternative to other similar systems, such as DJI Lightbridge or OcuSync.

DroneBridge features support for **Raspberry Pi**, **ESP32** on the UAV/ground station side and an **android app**.

Visit **["Not just another drone project"](http://wolfgangchristl.de/not-just-another-drone-project/)** for additional information about the project and its goals

_З README.md, без переказу._

## Для чого

DroneBridge is a system based on the WifiBroadcast approach. A bidirectional digital radio link between two endpoints is established using standard WiFi hardware and a custom protocol. DroneBridge is optimized for use in UAV applications and is a complete system. It is intended be a real alternative to other similar systems, such as DJI Lightbridge or OcuSync.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground station».
- Розробник польотного контролера — у тексті є «inav».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `aerial-imagery`, `ardupilot`, `arial-photography`, `drone`, `dronebridge`, `fpv`, `hd`, `hdfpv`, `inav`, `lightbridge`, `long-range`, `mavlink`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: DroneBridge is a system based on the WifiBroadcast approach. A bidirectional digital radio link between two endpoints is established using standard WiFi hardware and a custom protocol. DroneBridge is optimized for use in UAV applications and is a complete system. It is intended be a real alternative to other similar systems, such as DJI Lightbridge or OcuSync.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `apconfig.txt`
- `bpf/`
- `CMakeLists.txt`
- `common/`
- `communication/`
- `control/`
- `db_version.txt`
- `dhcpcd.conf`
- `DroneBridgeConfig.ini`
- `GPL2_license.txt`
- `InjectionTest/`
- `install_scripts/`
- `LICENSE`
- `logrotate_rsyslog_conf`
- `osd/`
- `plugin/`
- `plugins/`
- `proxy/`
- `README.md`
- `recorder/`
- `rsyslog.conf`
- `splash/`
- `splash_gtk/`
- `start_db`

Типи файлів за вибіркою (214 файлів, глибина до 3): C (101), Python (26), .txt (24), (без суфікса) (22), Markdown (11), .png (9).

Фрагмент README про будову:

### System Architecture

[Read more in the wiki](https://dronebridge.gitbook.io/docs/developer-guide/system-architecture)

## Що треба

- Маніфести збірки: CMake.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Exemplary hardware setup

DroneBridge is available for the Raspberry Pi & ESP32 (no video, telemetry only - WiFi based)
By compiling the libraries on your Linux computer any device can become an AIR or GND unit. This means DroneBridge is not restricted to the Raspberry Pi.
However many single board computers do not offer the same kind of stability and hardware/software support as the Raspberry Pi (camera, H.264 en-/decoding etc.).

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/DroneBridge-DroneBridge-is-a-system-based-on-the-Wif/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/DroneBridge__DroneBridge.md`.
