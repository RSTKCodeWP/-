# ShlkOfTheRa/scarab-osd

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [ShlkOfTheRa/scarab-osd](https://github.com/ShlkOfTheRa/scarab-osd) |
| Локальна тека | `fpv-library/repos/scarab-osd-MWOSD-UAV-HUD` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc` |
| Зірки (каталог) | 1473 |
| Оновлено upstream | 2026-03-03 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

Current development repository status : [![Build Status](https://travis-ci.com/ShikOfTheRa/scarab-osd.svg?branch=master)](https://app.travis-ci.com/ShikOfTheRa/scarab-osd)

##

_З README.md, без переказу._

## Для чого

MWOSD - UAV HUD

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».


Теми GitHub: `apm`, `arduino`, `ardupilot`, `betaflight`, `inav`, `osd`, `pixhawk`, `px4`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: MWOSD - UAV HUD

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `FIRMWARE/`
- `MW_OSD/`
- `MW_OSD_GUI/`
- `OTHER/`
- `platformio.ini`
- `README.md`

Типи файлів за вибіркою (121 файлів, глибина до 3): .hex (35), C (24), .jpg (14), .png (12), Arduino (11), Markdown (6).


## Що треба

- Маніфести збірки: PlatformIO (platformio.ini).
- PlatformIO env: `utilities.eeprom.clear`, `utilities.display.test`, `utilities.font.default`, `utilities.font.large`, `utilities.font.bold`, `utilities.debug.115kMSP`, `utilities.debug.56kAPM`, `utilities.debug.56kPX4`.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/scarab-osd-MWOSD-UAV-HUD/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/ShlkOfTheRa__scarab-osd.md`.
