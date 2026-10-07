# Wifibroadcast OSD

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [SamuelBrucksch/wifibroadcast_osd](https://github.com/SamuelBrucksch/wifibroadcast_osd) |
| Локальна тека | `fpv-library/repos/wifibroadcast_osd-OSD-for-HD-wireless-FPV-system-based-on` |
| У бібліотеці | keep |
| Категорії каталогу | `link`, `osd` |
| Зірки (каталог) | 44 |
| Оновлено upstream | 2017-01-06 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

OSD for HD wireless FPV system based on wifibroadcast from befi

This project uses the openvg library to draw 2d objects onto the screen. It is an OSD that uses the telemetry of already existing systems like mavlink, frsky direct GPS and so on.

If some steps in setting up the osd is unclear visit the blog from befi and check if it helps: https://befinitiv.wordpress.com/2015/07/06/telemetry-osd-for-wifibroadcast/

Most of the steps should be the same. **Requires latest wifibroadcast version**

_З README.md, без переказу._

## Для чого

OSD for HD wireless FPV system based on wifibroadcast from befi

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: OSD for HD wireless FPV system based on wifibroadcast from befi

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `frsky.c`
- `frsky.h`
- `ltm.c`
- `ltm.h`
- `main.c`
- `Makefile`
- `mavlink/`
- `mavlink.c`
- `mavlink.h`
- `osd.sh`
- `osdconfig.h`
- `raw_dump.txt`
- `README.md`
- `render.c`
- `render.h`
- `start_scripts/`
- `telemetry.c`
- `telemetry.h`

Типи файлів за вибіркою (185 файлів, глибина до 3): C (172), shell (7), (без суфікса) (2), Markdown (1), .txt (1), JSON (1).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/wifibroadcast_osd-OSD-for-HD-wireless-FPV-system-based-on/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/SamuelBrucksch__wifibroadcast_osd.md`.
