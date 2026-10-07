# ExpressLRS Configurator

> Картка виставки. Зал: [ELRS і RC-лінк](../halls/elrs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [ExpressLRS/ExpressLRS-Configurator](https://github.com/ExpressLRS/ExpressLRS-Configurator) |
| Локальна тека | `fpv-library/repos/ExpressLRS-Configurator-Cross-platform-configuration-build-tool` |
| У бібліотеці | keep |
| Категорії каталогу | `elrs`, `tools` |
| Зірки (каталог) | 831 |
| Оновлено upstream | 2026-07-22 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

**ExpressLRS Configurator** is a cross-platform build & configuration tool for the [ExpressLRS](https://github.com/ExpressLRS/ExpressLRS) - open source RC link for RC applications. Developed and maintained by **ExpressLRS LLC** and its passionate open source community, working together to advance reliable, high-performance radio control technology.

_З README.md, без переказу._

## Для чого

Cross platform configuration & build tool for the ExpressLRS radio link

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «expresslrs».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Cross platform configuration & build tool for the ExpressLRS radio link

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `assets/`
- `codegen.yml`
- `crowdin.yml`
- `dependencies/`
- `devices/`
- `docs/`
- `eslint.config.mjs`
- `graphql.schema.json`
- `LICENSE`
- `package.json`
- `README.md`
- `release/`
- `src/`
- `tsconfig.json`
- `yarn.lock`

Типи файлів за вибіркою (151 файлів, глибина до 3): JSON (46), TypeScript (29), .pyd (20), .png (15), .dll (8), (без суфікса) (6).

Фрагмент README про будову:

### Architecture

```
 - - - - - - - - - - - - - - - - - - - -
|          ExpressLRS-Configurator      |
|                   |                   |
|     renderer      |        main       |
|                   |                   |
|   configurator <----->  api-server    |
|                   |          |        |
|                   |          V        |
|                   |      platformio   |
|_ _ _ _ _ _ _ _ _ _|_ _ _ _ _ | _ _ _ _|
                               V
                      ExpressLRS hardware
```

This Electron application is split into two parts: a local API server that does all the work, and a UI layer. Both of
these application layers communicate within each other using Graphql protocol.

Heavy use of TypeScript and `@graphql-codegen/cli` is made throughout the repository to ensure the datatypes transmitted
between the API and UI layers are consistent at compile-time and Graphql ensuring the datatypes are consistent at
runtime.

## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `build`, `build-dll`, `build:main`, `build:renderer`, `rebuild`, `lint`, `lint:fix`, `package`, `postinstall`, `start`, `start:main`, `start:preload`.
- dependencies: `@apollo/client`, `@apollo/server`, `@as-integrations/express5`, `@emotion/react`, `@emotion/styled`, `@fontsource/roboto`, `@mui/icons-material`, `@mui/material`, `@octokit/rest`, `autosuggest-highlight`, `bluejay-rtttl-parse`, `class-validator` і ще 36.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start Guide

If you have hardware that you want to flash, please refer to our guides on the [website](https://www.expresslrs.org/),
and our [FAQ](https://www.expresslrs.org/3.0/faq/)
### Installation

We provide a standalone program for 64bit Windows, Linux and Mac.

Download the installer from [Releases](https://github.com/ExpressLRS/ExpressLRS-Configurator/releases) page.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ExpressLRS-Configurator-Cross-platform-configuration-build-tool/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/ExpressLRS__ExpressLRS-Configurator.md`.
