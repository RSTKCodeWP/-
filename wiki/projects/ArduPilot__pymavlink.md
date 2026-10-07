# Pymavlink

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [ArduPilot/pymavlink](https://github.com/ArduPilot/pymavlink) |
| Локальна тека | `fpv-library/repos/pymavlink-python-MAVLink-interface-and-utilities` |
| У бібліотеці | keep |
| Категорії каталогу | `fc` |
| Зірки (каталог) | 716 |
| Оновлено upstream | 2026-07-31 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This is a Python implementation of the MAVLink protocol. It includes a source code generator (generator/mavgen.py) to create MAVLink protocol implementations for other programming languages as well. Also contains tools for analyzing flight logs.

_З README.md, без переказу._

## Для чого

python MAVLink interface and utilities

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: python MAVLink interface and utilities

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `__init__.py`
- `APM_Mavtest/`
- `COPYING`
- `CSVReader.py`
- `dfindexer/`
- `DFReader.py`
- `dialects/`
- `examples/`
- `fgFDM.py`
- `generator/`
- `MANIFEST.in`
- `mavexpression.py`
- `mavextra.py`
- `mavftp.py`
- `mavftp_op.py`
- `mavftpfs.py`
- `mavparm.py`
- `mavtestgen.py`
- `mavutil.py`
- `mavwp.py`
- `mission.proto`
- `mission2.pb`
- `pyproject.toml`
- `pytest.ini`

Типи файлів за вибіркою (251 файлів, глибина до 3): Python (129), (без суфікса) (18), .xml (12), JavaScript (10), shell (8), Markdown (8).


## Що треба

### Dependencies

Pymavlink has several dependencies :

    - [lxml](http://lxml.de/installation.html) : for checking and parsing xml file 

Optional :

    - numpy : for FFT
    - pytest : for tests

- Маніфести збірки: Python (requirements.txt), Python (pyproject.toml).
- requirements.txt: `fastcrc`, `lxml>=3.6.0`, `setuptools>=42`, `wheel>=0.37.1`, `pytest<=7.4.4`, `syrupy;`, `wsproto`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Installation

Pymavlink supports Python 3.  Python 2 support has been removed.

The following instructions assume you are using a Debian-based (like Ubuntu) installation.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/pymavlink-python-MAVLink-interface-and-utilities/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/ArduPilot__pymavlink.md`.
