# RSTKCodeWP/comm-slackbot

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/comm-slackbot](https://github.com/RSTKCodeWP/comm-slackbot) |
| Локальна тека | `comm-slackbot-Slack-COMMGamers-Bot` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Slackbot for COMMGamers.us python-rtmbot

A Slack bot written in python that connects via the RTM API.

Python-rtmbot is a callback based bot engine. The plugins architecture should be familiar to anyone with knowledge to the [Slack API](https://api.slack.com) and Python. The configuration file format is YAML.

Some differences to webhooks:

1. Doesn't require a webserver to receive messages 2. Can respond to direct messages from users 3. Logs in as a slack user (or bot) 4. Bot users must be invited to a channel

Dependencies ----------

Installation -----------

1. Download the python-rtmbot code

git clone git@github.com:slackhq/python-rtmbot.git cd python-rtmbot

2. Install dependencies ([virtualenv](http://virtualenv.readthedocs.org/en/latest/) is recommended.)

pip install -r requirements.txt

3. Configure rtmbot (https://api.slack.com/bot-users)

cp doc/example-config/rtmbot.conf .…

_З README.md, без переказу._

## Для чого

Slackbot for COMMGamers.us python-rtmbot

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `doc/`
- `LICENSE`
- `LICENSE.txt`
- `plugins/`
- `README.md`
- `requirements.txt`
- `rtmbot.conf`
- `rtmbot.py`

Типи файлів за вибіркою (23 файлів, глибина до 3): Python (13), (без суфікса) (5), .conf (2), .txt (2), Markdown (1).


## Що треба

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `requests`, `python-daemon`, `pyyaml`, `websocket-client`, `slackclient`.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `comm-slackbot-Slack-COMMGamers-Bot/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__comm-slackbot.md`.
