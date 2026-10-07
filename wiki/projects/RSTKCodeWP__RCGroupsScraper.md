# RCGroupsScraper

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/RCGroupsScraper](https://github.com/RSTKCodeWP/RCGroupsScraper) |
| Локальна тека | `RCGroupsScraper-Python-RCGroups-Search-Notifier` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

Most documentation details found here: [RCGroupsScraper Docs](http://paulnurkkala.com/rc-groups-scraper/)

A python tool to scrape RC groups home page to do automated searching for you, and notifies you when something that you're searching for pops up.

My goal is to have this grab all of the useful information from RC groups -- price, location, etc. Allow the user to decide what they want to be notified about, how they want to get that notification, and then be able to define what exactly they want the notification to include (price, location, URL, description, etc)

_З README.md, без переказу._

## Для чого

Most documentation details found here: [RCGroupsScraper Docs](http://paulnurkkala.com/rc-groups-scraper/)

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `__init__.py`
- `check_rc_classifieds.py`
- `example.json`
- `LICENSE`
- `rcg_bot.py`
- `README.md`
- `requirements.txt`
- `runner.py`

Типи файлів за вибіркою (9 файлів, глибина до 3): Python (4), (без суфікса) (2), JSON (1), Markdown (1), .txt (1).


## Що треба

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `ipdb`, `requests`, `beautifulsoup4`, `pushbullet.py`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation and First Run

* virtualenv env
 * . env/bin/activate
 * pip install -r requirements.txt
 * touch urls.json ( the service saves new results in a file called urls.json — these results are saved here so that the app can recognize if the url that you saved is “new” as in the script hasn’t found that unique URL before)
 * set up your settings in rcg_bot.py ( they are the first arguments of the file )
 * if you aren’t going to use pushbullet, set pushbullet_key to null (more on pushbullet below)
 * python rcg_bot.py ( and it will start running and keep running )

## З чого зібрана картка

`catalog.json`, `RCGroupsScraper-Python-RCGroups-Search-Notifier/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__RCGroupsScraper.md`.
