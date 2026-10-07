# JAGCS

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [MishkaRogachev/JAGCS](https://github.com/MishkaRogachev/JAGCS) |
| Локальна тека | `fpv-library/repos/JAGCS-Just-another-ground-control-station` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc` |
| Зірки (каталог) | 205 |
| Оновлено upstream | 2024-06-13 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Joint architecture ground control station. Or just another ground control station:)

Can be used as ground software for the MAVLink compatible drones, but other information protocols can be integrated. Build with Qt and works on Windows/Linux/Android(Mac support will be later).

_З README.md, без переказу._

## Для чого

Just another ground control station

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `copter`, `drone`, `gcs`, `ground-control-station`, `mav`, `mavlink`, `pixhawk`, `plane`, `qml`, `qt5`, `raspberry-pi`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Just another ground control station

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `app/`
- `cmake/`
- `CMakeLists.txt`
- `LICENSE`
- `platforms/`
- `README.md`
- `resources/`
- `sources/`
- `tests/`
- `translations/`
- `ui.png`

Типи файлів за вибіркою (195 файлів, глибина до 3): .svg (92), C (36), C++ (35), .txt (6), (без суфікса) (5), shell (3).


## Що треба

### Dependencies

* C++14 compiler
  * Qt 5.9 or higher
  * CMake 3.0 or higher

  GCC version 4.9 or higher required for MapBox GL QtLocation plugin
  ANGLE API is required for MapBox GL under windows

- Маніфести збірки: CMake.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/JAGCS-Just-another-ground-control-station/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/MishkaRogachev__JAGCS.md`.
