# INAV Blackbox Explorer

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [iNavFlight/blackbox-log-viewer](https://github.com/iNavFlight/blackbox-log-viewer) |
| Локальна тека | `fpv-library/repos/blackbox-log-viewer-Interactive-log-viewer-for-flight-logs-r` |
| У бібліотеці | keep |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 51 |
| Оновлено upstream | 2024-08-24 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This tool allows you to open logs recorded by INAV's Blackbox feature in your web browser. You can seek through the log to examine graphed values at each timestep. If you have a flight video, you can load that in as well and it'll be played behind the log. You can export the graphs as a WebM video to share with others.

_З Readme.md, без переказу._

## Для чого

Interactive log viewer for flight logs recorded with blackbox

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «inav».


Теми GitHub: `blackbox`, `hacktoberfest`, `inav`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Interactive log viewer for flight logs recorded with blackbox

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `_locales/`
- `assets/`
- `background.js`
- `blackbox-log-viewer.iml`
- `css/`
- `dmg-background.psd`
- `entitlements.plist`
- `fonts/`
- `gulpfile.js`
- `images/`
- `index.html`
- `js/`
- `library/`
- `LICENSE`
- `main_nwjs.html`
- `Makefile`
- `manifest.json`
- `package-lock.json`
- `package.json`
- `Readme.md`
- `screenshots/`
- `test/`

Типи файлів за вибіркою (116 файлів, глибина до 3): JavaScript (32), .svg (19), .png (17), CSS (9), (без суфікса) (6), JSON (5).


## Що треба

- Маніфести збірки: Node.js (package.json), Make.
- npm-скрипти в package.json: `start`, `startosx`, `gulp`, `nw`.
- dependencies: `archiver`, `command-exists`, `del`, `graceful-fs`, `gulp`, `gulp-concat`, `inflection`, `jquery`, `jquery-ui-npm`, `marked`, `minimist`, `nw` і ще 6.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

_INAV Blackbox Explorer_ is distributed as _standalone_ application.
### Usage

Click the "Open log file/video" button at the top right and select your logged ".TXT" file and your flight video (if 
you recorded one).

You can scroll through the log by clicking or dragging on the seek bar that appears underneath the main graph. The 
current time is represented by the vertical red bar in the center of the graph. You can also click and drag left and
right on the graph area to scrub backwards and forwards.
### App build and release

The tasks are defined in `gulpfile.js` and can be run either via `gulp <task-name>` (if the command is in PATH or via `../node_modules/gulp/bin/gulp.js <task-name>`:

1. Optional, install gulp `npm install --global gulp-cli`.
2. Run `gulp <taskname> [[platform] [platform] ...]`.

List of possible values of `<task-name>`:
* **dist** copies all the JS and CSS files in the `./dist` folder.
* **apps** builds the apps in the `./apps` folder [1].
* **debug** builds debug version of the apps in the `./debug` folder [1].
* **release** zips up the apps into individual archives in the `./release` folder [1]. 

[1] Running this task on macOS or Linux requires Wine, since it's needed to set the icon for the Windows app (build for specific platform to avoid errors).

#### Build or release app for one specific platform
To build a specific release, use the command `release --platform="win32"` for example.
Possible OS'es are: `linux64`, `win32` and `osx64`
<br>`--installer` argument can be added to build installers for particular OS. NOTE: MacOS Installer can be built with MacOS only.

#### macOS DMG installation background image

The release distribution for macOS uses a DMG file to install the application.
The PSD source for the DMG backgound image can be found in the root (`dmg-background.png`). After changing the source, export the image to PNG format in folder `./images/`.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/blackbox-log-viewer-Interactive-log-viewer-for-flight-logs-r/Readme.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/iNavFlight__blackbox-log-viewer.md`.
