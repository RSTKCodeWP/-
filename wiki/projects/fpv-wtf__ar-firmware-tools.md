# fpv-wtf/ar-firmware-tools

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/ar-firmware-tools](https://github.com/fpv-wtf/ar-firmware-tools) |
| Локальна тека | `fpv-library/repos/ar-firmware-tools-OTRA-firmware-format-tools` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | 20 |
| Оновлено upstream | 2023-07-03 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

OTRA firmware format tools

_З поля description у catalog.json. Окремого вступу в README немає._

## Для чого

OTRA firmware format tools

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: OTRA firmware format tools

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `LICENSE`
- `otra.js`
- `otra.ksy`
- `otra_reader/`
- `otra_sirius.ksy`
- `otra_spl.ksy`
- `package-lock.json`
- `package.json`
- `README.md`
- `scripts/`

Типи файлів за вибіркою (15 файлів, глибина до 3): JavaScript (4), .ksy (3), JSON (3), (без суфікса) (2), shell (2), Markdown (1).


## Що треба

- Маніфести збірки: Node.js (package.json).
- dependencies: `kaitai-struct`, `lzo`, `yargs`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installing

git clone https://github.com/fpv-wtf/ar-firmware-tools
    cd ar-firmware-tools
    npm install
### Usage

otra.js <command>

    Commands:
    otra.js extract <image> [folder]  extract the OTRA image
    otra.js info <image>              show info on the OTRA image

    Options:
    --help     Show help                                 [boolean]
    --version  Show version number                       [boolean]

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ar-firmware-tools-OTRA-firmware-format-tools/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__ar-firmware-tools.md`.
