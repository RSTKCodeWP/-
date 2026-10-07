# DroneBridge for Desktop

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [DroneBridge/Desktop](https://github.com/DroneBridge/Desktop) |
| Локальна тека | `fpv-library/repos/Desktop-DroneBridge-modules-kernel-patches-to-co` |
| У бібліотеці | keep |
| Категорії каталогу | `link`, `fc` |
| Зірки (каталог) | 21 |
| Оновлено upstream | 2020-08-02 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-2.0 |

## Ідея

Moules &amp; kernel patches to compile a working linux image (x86/ AMD64) that can be used as a ground station for the DroneBridge system. It can be used instead of the Raspberry Pi ground station. A working image based on Linux Mint 19 (x64) is provided.

The image comes with all sorts of preinstalled tools like:

Additionally to all DroneBridge Raspberry Pi modules there are new modules:

DroneBridge for Desktop is a fully capable ground station for the DroneBridge system. It can receive and process the DroneBridge raw protocol. Its Kernel is patched with the same modifications as the "original" Raspberry Pi images. DroneBridge for Desktop can be used to receive and transmit data over a long range link, however the main focus is on receiving & RC (ground station functionality)

## DroneBridge Monitor

_З README.md, без переказу._

## Для чого

DroneBridge modules & kernel patches to compile a working linux image (x86/ AMD64) that can be used as a ground station for the DroneBridge system. It can be used instead of the Raspberry Pi ground station. A working image is provided

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground station».
- Розробник польотного контролера — у тексті є «inav».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `drone`, `dronebridge`, `inav`, `linux-mint`, `long-range`, `mavlink`, `multicopter`, `pixhawk`, `radio-link`, `uav`, `wifibroadcast`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: DroneBridge modules & kernel patches to compile a working linux image (x86/ AMD64) that can be used as a ground station for the DroneBridge system. It can be used instead of the Raspberry Pi ground station. A working image is provided

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CMakeLists.txt`
- `LICENSE`
- `monitor/`
- `README.md`
- `scripts/`
- `wiki/`

Типи файлів за вибіркою (14 файлів, глибина до 3): (без суфікса) (4), .txt (2), .png (2), Markdown (1), JSON (1), C (1).


## Що треба

- Маніфести збірки: CMake.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Desktop-DroneBridge-modules-kernel-patches-to-co/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/DroneBridge__Desktop.md`.
