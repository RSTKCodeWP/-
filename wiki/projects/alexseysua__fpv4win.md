# WiFi Broadcast FPV client for Windows platform.

> Картка виставки. Зал: [OpenIPC](../halls/openipc.md).

Каталог тримає категорію `other`. Зал «OpenIPC» поставлено, бо в назві, описі або шляху є «openipc».

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [alexseysua/fpv4win](https://github.com/alexseysua/fpv4win) |
| Локальна тека | `fpv-library/repos/fpv4win-WiFi-Broadcast-FPV-client-for-Windows-pl` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2024-06-26 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

fpv4win is an app for Windows that packages multiple components together to decode an H264/H265 video feed broadcasted by wfb-ng over the air.

Supported rtl8812au WiFi adapter only.

It is recommended to use with [OpenIPC](https://github.com/OpenIPC) FPV

_З README.md, без переказу._

## Для чого

WiFi Broadcast FPV client for Windows platform

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «wfb-ng».
- Розробник відеотракту — у тексті є «h264».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: WiFi Broadcast FPV client for Windows platform

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CMakeLists.txt`
- `gs.key`
- `img/`
- `LICENSE`
- `qml/`
- `qml.qrc`
- `README.md`
- `src/`

Типи файлів за вибіркою (45 файлів, глибина до 3): C (18), C++ (12), (без суфікса) (4), .png (3), .qml (3), .txt (1).


## Що треба

- Маніфести збірки: CMake.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Usage

- 1. Download [Zadig](https://github.com/pbatard/libwdi/releases/download/v1.5.0/zadig-2.8.exe)
- 2. Repair the libusb driver (you may need to enable [Options] -> [List All Devices] to show your adapter).


- 3. Install [vcredist_x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- 4. Select your 8812au adapter.
- 5. Select your WFB key.
- 6. Select your drone channel.
- 7. Enjoy!
### How to build

- Take a look at
[GithubAction](https://github.com/openipc/fpv4win/blob/main/.github/workflows/msbuild.yml)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/fpv4win-WiFi-Broadcast-FPV-client-for-Windows-pl/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/alexseysua__fpv4win.md`.
