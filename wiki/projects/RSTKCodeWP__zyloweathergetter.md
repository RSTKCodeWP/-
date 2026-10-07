# RSTKCodeWP/zyloweathergetter

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/zyloweathergetter](https://github.com/RSTKCodeWP/zyloweathergetter) |
| Локальна тека | `zyloweathergetter-JavaScript-Weather-Getter` |
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

- `app.js`
- `model/`
- `package.json`
- `public/`
- `README.md`
- `templates/`

Типи файлів за вибіркою (9 файлів, глибина до 3): JavaScript (4), HTML (2), Markdown (1), JSON (1), (без суфікса) (1).


## Що треба

### Requirements:

* You will build an application that takes data, stores it and displays it. By data, we mean a collection of data points that have at least a date and a numeric value. Examples of some good API sources: https://en.wikipedia.org/wiki/List_of_open_APIs
* We require you to use the same stack we use at Zylo. It means a Node.js & Express backend and JavaScript (React optional) client. Beside that, you are free to use whatever technology you want.
### How This meets Requirements

* Takes Data
  * The way that I handled "taking" data was maybe a bit sneaky, but I essentially made the input based on the browser's GPS coordinates, rather than having the user type something in. 
* Stores it
  * The application stores data in a Mongo DB database using the Mongoose wrapper to control the schemas. The username and password to that mongo instance is provided in the webapp 
* Displays it
  * The data display is a very simple table that shows the tempeture at the given date that the user clicked the button to record the information. While the only information that's shown is temp, much more data is recorded.

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `test`.
- dependencies: `express`, `forecast-io`, `mongodb`, `mongoose`, `pug`.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `zyloweathergetter-JavaScript-Weather-Getter/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__zyloweathergetter.md`.
