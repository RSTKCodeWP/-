# dji-moonlight-shim

> Картка виставки. Зал: [Окуляри і VRX](../halls/goggles.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/dji-moonlight-shim](https://github.com/fpv-wtf/dji-moonlight-shim) |
| Локальна тека | `fpv-library/repos/dji-moonlight-shim-Stream-games-to-your-DJI-FPV-goggles` |
| У бібліотеці | keep |
| Категорії каталогу | `goggles` |
| Зірки (каталог) | 67 |
| Оновлено upstream | 2023-04-10 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Stream games via Moonlight and [fpv.wtf](https://github.com/fpv-wtf) to your DJI FPV Goggles!

The DJI Moonlight project is made up of three parts:

goggle-side app that displays a video stream coming in over USB. _You are here._ Windows app that streams games to the shim via Moonlight and friends. fork of Moonlight Embedded that can stream to the shim. The GUI app uses this internally.

Latency is good, in the 7-14ms range at 120Hz (w/ 5900X + 3080Ti via GeForce Experience).

_З README.md, без переказу._

## Для чого

Stream games to your DJI FPV goggles!

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «goggles».


Теми GitHub: `dji`, `fpv`, `moonlight`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Stream games to your DJI FPV goggles!

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `assets/`
- `build.sh`
- `build_ipk.sh`
- `CMakeLists.txt`
- `include/`
- `ipk/`
- `lib/`
- `LICENSE`
- `media/`
- `README.md`
- `src/`

Типи файлів за вибіркою (42 файлів, глибина до 3): C (18), (без суфікса) (11), .png (3), shell (2), .so (2), .txt (1).


## Що треба

- Маніфести збірки: CMake.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Setup

1. Go to [fpv.wtf](https://fpv.wtf/) with your goggles connected and powered up.
2. Update WTFOS to the latest version.
3. Install
   [dji-moonlight-shim](https://fpv.wtf/package/fpv-wtf/dji-moonlight-shim) via
   the package mangaer.
4. Continue to [dji-moonlight-gui](https://github.com/fpv-wtf/dji-moonlight-gui)
   for PC-side setup.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/dji-moonlight-shim-Stream-games-to-your-DJI-FPV-goggles/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__dji-moonlight-shim.md`.
