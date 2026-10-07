# UAV Log Viewer

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [ArduPilot/UAVLogViewer](https://github.com/ArduPilot/UAVLogViewer) |
| Локальна тека | `fpv-library/repos/UAVLogViewer-An-online-viewer-for-UAV-log-files` |
| У бібліотеці | keep |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 251 |
| Оновлено upstream | 2026-06-30 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This is a Javascript based log viewer for Mavlink telemetry and dataflash logs. [Live demo here](http://plot.ardupilot.org).

_З README.md, без переказу._

## Для чого

An online viewer for UAV log files

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: An online viewer for UAV log files

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `babel.config.js`
- `blender/`
- `config/`
- `docker-entrypoint.sh`
- `Dockerfile`
- `index.html`
- `LICENSE`
- `package-lock.json`
- `package.json`
- `patches/`
- `preview.gif`
- `README.md`
- `scripts/`
- `src/`
- `static/`
- `test/`

Типи файлів за вибіркою (110 файлів, глибина до 3): JavaScript (40), Vue (20), (без суфікса) (9), .xml (8), .glb (7), .png (6).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `dev`, `start`, `start:dev`, `unit`, `e2e`, `test`, `lint`, `lint:fix`, `build`, `postinstall`.
- dependencies: `@babel/register`, `@fortawesome/free-solid-svg-icons`, `@fortawesome/vue-fontawesome`, `assert`, `bootstrap-vue`, `browserify-zlib`, `buffer`, `color`, `colormap`, `crypto-browserify`, `d3`, `dji-log-parser-js` і ще 29.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### local Build Setup

``` bash
# initialize submodules
git submodule update --init --recursive

# install dependencies
npm install

# enter Cesium token
export VUE_APP_CESIUM_TOKEN=<your token>

# serve with hot reload at localhost:8080
npm run dev

# build for production with minification
npm run build

# run production build locally
npm start

# run unit tests
npm run unit

# run e2e tests
npm run e2e

# run all tests
npm test
```
### build local Docker image

``` bash

# Build Docker Image
docker build -t <your username>/uavlogviewer .

# Run Docker Image (token is read at container startup)
docker run -e VUE_APP_CESIUM_TOKEN=<Your cesium ion token> -it -p 8080:8080 -v ${PWD}:/usr/src/app <your username>/uavlogviewer

# Navigate to localhost:8080 in your web browser

# changes should automatically be applied to the viewer

```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/UAVLogViewer-An-online-viewer-for-UAV-log-files/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/ArduPilot__UAVLogViewer.md`.
