# The fpv.wtf Driver Installer

> Картка виставки. Зал: [Інструменти](../halls/tools.md).

Каталог тримає категорію `other`. Зал «Інструменти» поставлено, бо в назві, описі або шляху є «installer».

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/driver-installer](https://github.com/fpv-wtf/driver-installer) |
| Локальна тека | `fpv-library/repos/driver-installer-Driver-installer-for-FPV-devices` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | 9 |
| Оновлено upstream | 2023-04-05 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This application automatically installs several **DJI FPV System** related drivers on your **Windows PC**. It is required for using certain fpv.wtf published applications such as [butter](https://github.com/fpv-wtf/butter).

The full list is:

_З README.md, без переказу._

## Для чого

Driver installer for FPV devices

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Driver installer for FPV devices

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `deps/`
- `driver_installer.c`
- `driver_installer.exe.manifest`
- `driver_installer.rc`
- `drivers/`
- `fpv-wtf.ico`
- `LICENSE`
- `Makefile`
- `README.md`

Типи файлів за вибіркою (171 файлів, глибина до 3): C (40), (без суфікса) (21), .o (16), .in (13), .txt (9), .lo (9).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Usage

Simply run **driver_installer.exe** and wait a few minutes until you get a success message.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/driver-installer-Driver-installer-for-FPV-devices/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__driver-installer.md`.
