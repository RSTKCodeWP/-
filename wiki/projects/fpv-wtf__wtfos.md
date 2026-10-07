# fpv-wtf/wtfos

> Картка виставки. Зал: [Окуляри і VRX](../halls/goggles.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/wtfos](https://github.com/fpv-wtf/wtfos) |
| Локальна тека | `fpv-library/repos/wtfos-A-framework-for-modifying-the-firmware-o` |
| У бібліотеці | keep |
| Категорії каталогу | `goggles` |
| Зірки (каталог) | 327 |
| Оновлено upstream | 2025-04-13 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**wtfos** is a community framework for modifying the firmware of DJI FPV Goggles and Air Units enabled by [margerine](https://github.com/fpv-wtf/margerine).

It includes anti-bricking measures, a [configurator](https://github.com/fpv-wtf/wtfos-configurator), a [package manager](https://git.yoctoproject.org/opkg/), a [service manager](https://github.com/davmac314/dinit) and a [vendor service modification framework](https://github.com/fpv-wtf/wtfos-modloader).

You can support the project on [Open Collective](https://opencollective.com/fpv-wtf/donate?amount=10) and join us on our [Discord](https://discord.gg/3rpnBBJKtU).

_З README.md, без переказу._

## Для чого

A framework for modifying the firmware of DJI FPV Goggles and Air Units

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «goggles».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: A framework for modifying the firmware of DJI FPV Goggles and Air Units

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `LICENSE`
- `make-packages.sh`
- `README.md`
- `setup/`
- `wtfos/`
- `wtfos-system/`

Типи файлів за вибіркою (12 файлів, глибина до 3): (без суфікса) (8), shell (2), Markdown (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Setup and usage

Use the [configurator](https://fpv.wtf/) to [root](https://fpv.wtf/root) your device, [install](https://fpv.wtf/wtfos/install) wtfos and [manage](https://fpv.wtf/root) [community provided packages](https://repo.fpv.wtf/pigeon/).
### Uninstalling

Should you wish to return to the plain adb root hack, use the configurator to uninstall wtfos.

To also remove adb access and restore compatibility with the Assistant on all the V1 gear run the following in the shell:

    wtfos-remove-adb
    reboot

V2 Goggles do not require removal of adb to work with Assistant.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/wtfos-A-framework-for-modifying-the-firmware-o/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__wtfos.md`.
