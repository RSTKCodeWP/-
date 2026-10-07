# Skybrush Live

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [skybrush-io/live](https://github.com/skybrush-io/live) |
| Локальна тека | `fpv-library/repos/live-An-open-source-drone-show-and-drone-swar` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs` |
| Зірки (каталог) | 116 |
| Оновлено upstream | 2026-07-23 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This is the official desktop and web frontend for the Skybrush server.

_З README.md, без переказу._

## Для чого

An open-source drone show and drone swarm ground control station GUI frontend

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».


Теми GitHub: `drone`, `drone-show`, `drone-swarm`, `skybrush`, `uav`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: An open-source drone show and drone swarm ground control station GUI frontend

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `assets/`
- `babel.config.json`
- `CHANGELOG.md`
- `config/`
- `DEPENDENCIES.md`
- `electron-builder.json`
- `eslint.config.mjs`
- `etc/`
- `index.html`
- `jest.config.ts`
- `jsconfig.json`
- `launcher.mjs`
- `LICENSE.txt`
- `package-lock.json`
- `package.json`
- `patches/`
- `README.md`
- `src/`
- `test/`
- `tsconfig.json`
- `types/`
- `webpack/`

Типи файлів за вибіркою (837 файлів, глибина до 3): TypeScript (425), JavaScript (307), JSON (21), .png (21), .mjs (20), (без суфікса) (5).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `bundle`, `format:check`, `format:fix`, `lint:check`, `lint:fix`, `postinstall`, `start`, `start:electron`, `start:electron:light`, `start:https`, `stats`, `stats:prod`.
- dependencies: `@collmot/layout-bmfont-text`, `@collmot/ol-react`, `@collmot/react-socket`, `@date-io/core`, `@date-io/date-fns`, `@emotion/react`, `@emotion/styled`, `@fontsource/fira-sans`, `@fvilers/disable-react-devtools`, `@loadable/component`, `@mui/icons-material`, `@mui/material` і ще 135.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Steps to install

1. Install Node.js and `npm` (the Node.js Package Manager). Note that Ubuntu
   Linux may contain an old version of Node.js at the time of writing and we
   need a recent one, so you need to run the following from the command line:

   ```sh
   curl -sL https://deb.nodesource.com/setup_20.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

   If you are running Windows, you should probably download an installer from
   [here](https://nodejs.org/en/download/) that contains both.

2. Install all the dependencies of `skybrush-live` by running `npm install`
   from a fresh checkout of the repository.
   _(Note for Windows: For some reason the `PATH` environment variable of
   `cmd` is not always the same as the one in `PowerShell`, so you may have
   to use the latter one or alternatively `git-shell` for the command above
   to run properly.)_

3. Copy `.env.example` to `.env` and include your Bing Maps / Mapbox / Mapzen
   API key in it if you want to support these map providers. (None of them
   are required).

4. Start a development web server with `npm start` inside `skybrush-live`, and
   navigate to http://localhost:8080 from your browser. Alternatively, run
   `npm run start:electron` to run Skybrush Live within its own desktop app
   window.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/live-An-open-source-drone-show-and-drone-swar/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/skybrush-io__live.md`.
