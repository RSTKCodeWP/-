# QOpenHD

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [OpenHD/QOpenHD](https://github.com/OpenHD/QOpenHD) |
| Локальна тека | `fpv-library/repos/QOpenHD-QOpenHD-App` |
| У бібліотеці | keep |
| Категорії каталогу | `link` |
| Зірки (каталог) | 279 |
| Оновлено upstream | 2026-07-26 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

QOpenHD is the default OpenHD companion app that runs on the OHD Ground station or any other "external" devices connected to the ground station.

It is responsible for displaying the main video stream to the user, composed with the OSD, and changing OpenHD settings.

As the name suggests, it is based on QT (5.15.X) and will not run on older versions.

_З README.md, без переказу._

## Для чого

QOpenHD App

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground station».
- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».


Теми GitHub: `app`, `camera`, `fpv`, `hd`, `hd-video`, `long-range`, `openhd`, `qt`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: QOpenHD App

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `after-install.sh`
- `android/`
- `androidqt6/`
- `app/`
- `asset_catalog_compiler.Info.plist`
- `before-install.sh`
- `build_chroot.sh`
- `build_cmake.sh`
- `build_qmake.sh`
- `checks.json`
- `CMakeLists.txt`
- `deploy/`
- `docs/`
- `git.pri`
- `icons/`
- `install_build_dep.sh`
- `install_qt6_build_dep.sh`
- `integration/`
- `ios/`
- `lib/`
- `LICENSE`
- `mac/`
- `old_readme.md`
- `package.sh`

Типи файлів за вибіркою (837 файлів, глибина до 3): C++ (230), C (154), .qml (149), .png (62), .ttf (54), .txt (36).


## Що треба

- Маніфести збірки: CMake.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installing

Like every OpenHD app or module, we publish packages into our [Cloudsmith Repository](https://cloudsmith.io/~openhd/repos/openhd-2-3-evo/). There are Packages for X86 (ubuntu 22.04,23.04), armhf (rpi, arm64 rockchip). Android releases are available on the Playstore and can be downloaded from there.

## Супутні документи в теці

- [`docs/map_api_key.md`](../../fpv-library/repos/QOpenHD-QOpenHD-App/docs/map_api_key.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/QOpenHD-QOpenHD-App/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/OpenHD__QOpenHD.md`.
