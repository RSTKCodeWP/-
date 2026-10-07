# Stellar.js

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/stellar-js](https://github.com/RSTKCodeWP/stellar-js) |
| Локальна тека | `stellar-js-Parallax-Scrolling-Library` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

У джерелах цього репозиторію цього немає.

## Для чого

У джерелах цього репозиторію цього немає.

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `component.json`
- `grunt.js`
- `jquery.stellar.js`
- `jquery.stellar.min.js`
- `libs/`
- `LICENSE-MIT`
- `package.json`
- `README.md`
- `src/`
- `stellar.jquery.json`
- `test/`

Типи файлів за вибіркою (20 файлів, глибина до 3): JavaScript (10), JSON (3), (без суфікса) (2), CSS (2), YAML (1), Markdown (1).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `test`.
- dependencies: `jquery`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Getting Started

Stellar.js is a jQuery plugin that provides parallax scrolling effects to any scrolling element. The first step is to run `.stellar()` against the element:

``` js
// For example:
$(window).stellar();
// or:
$('#main').stellar();
```

If you're running Stellar.js on 'window', you can use the shorthand:

``` js
$.stellar();
```

This will look for any parallax backgrounds or elements within the specified element and reposition them when the element scrolls.
### How to Build

Stellar.js uses [Node.js](../../stellar-js-Parallax-Scrolling-Library/nodejs.org), [Grunt](http://gruntjs.com) and [PhantomJS](http://phantomjs.org/).

Once you've got Node and PhantomJS set up, install the dependencies:

`$ npm install`

To lint, test and minify the project, simply run the following command:

`$ grunt`

Each of the build steps are also available individually.

`$ grunt test` to test the code using QUnit and PhantomJS: 

`$ grunt lint` to validate the code using JSHint.

`$ grunt watch` to continuously lint and test the code while developing.

## З чого зібрана картка

`catalog.json`, `stellar-js-Parallax-Scrolling-Library/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__stellar-js.md`.
