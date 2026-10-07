# margerine

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/margerine](https://github.com/fpv-wtf/margerine) |
| Локальна тека | `fpv-library/repos/margerine-It-s-not-butter-but-it-s-root` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | 220 |
| Оновлено upstream | 2023-06-08 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

It's not butter, but it's root.

_З поля description у catalog.json. Окремого вступу в README немає._

## Для чого

It's not butter, but it's root.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: It's not butter, but it's root.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `LICENSE`
- `margerine.js`
- `package-lock.json`
- `package.json`
- `README.md`
- `src/`

Типи файлів за вибіркою (14 файлів, глибина до 3): JavaScript (8), JSON (3), (без суфікса) (2), Markdown (1).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `test`.
- dependencies: `@sentry/node`, `@sentry/tracing`, `add`, `chalk`, `serialport`, `yargs`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Advanced usage

node margerine --help
    margerine <command>
    
    Commands:
      margerine unlock [serialport]        unlock device and enable adb
      margerine lock [serialport]          disable adb and relock device
      margerine proxy [port]               start the built in http -> https proxy
      margerine.js shell <command> [port]  execute a command on rooted device,
                                           once per reboot
    Options:
      --help     Show help                                               
      --version  Show version number

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/margerine-It-s-not-butter-but-it-s-root/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__margerine.md`.
