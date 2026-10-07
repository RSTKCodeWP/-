# Target Configuration (config.h) repository

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [betaflight/config](https://github.com/betaflight/config) |
| Локальна тека | `fpv-library/repos/config-Betaflight-target-definitions` |
| У бібліотеці | keep |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 96 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Repository for the storage of config.h files for default board settings. For more information please see https://betaflight.com

The config.h replaces the unified target configuration that is now deprecated from version 4.5.0. This frees up some flash space, and ensures defaults are baked into the build. This has been made possible due to the introduction of the cloud build service. Standard default targets are still available where possible, but they require all configuration to be restored from a backup.

Cloud build takes care of the config repository for the general user, and knowledge of it is generally not needed. The instructions here are predominantly for tinkerers, and for community and manufacturers creating and supporting targets.

_З README.md, без переказу._

## Для чого

Betaflight target definitions

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «betaflight».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Betaflight target definitions

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `configs/`
- `LICENSE`
- `Manufacturers.md`
- `README.md`

Типи файлів за вибіркою (615 файлів, глибина до 3): C (608), (без суфікса) (2), Markdown (2), YAML (1), JSON (1), .mk (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### How to use - Firmware

The config repository will be used directly by the firmware, and is only required if you wish to use one of the targets present here when building locally.

You need to hydrate the target list first with:

```
> make configs
```

Then you can make a build for a specific target configuration e.g.
```
> make BETAFLIGHTF4
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/config-Betaflight-target-definitions/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/betaflight__config.md`.
