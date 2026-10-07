# 🚀 Pico NAND Flasher — Professional NAND Flash Programmer for Raspberry Pi Pico

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/Pico-Nand-Flasher](https://github.com/RSTKCodeWP/Pico-Nand-Flasher) |
| Локальна тека | `Pico-Nand-Flasher-RaspberryPi-Pico-NAND` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

Turn your Raspberry Pi Pico into a powerful, cross‑platform NAND Flash programmer with a modern, user‑friendly GUI.

_З README.md, без переказу._

## Для чого

Turn your Raspberry Pi Pico into a powerful, cross‑platform NAND Flash programmer with a modern, user‑friendly GUI.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CHANGELOG.md`
- `dev-requirements.txt`
- `LICENSE`
- `main/`
- `pyproject.toml`
- `README.md`
- `README_RU.md`
- `requirements.txt`

Типи файлів за вибіркою (50 файлів, глибина до 3): Python (32), Markdown (7), (без суфікса) (5), .txt (3), YAML (1), TOML (1).


## Що треба

- Маніфести збірки: Python (requirements.txt), Python (pyproject.toml).
- requirements.txt: `PyQt6==6.7.0`, `pyserial==3.5`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

1) Flash MicroPython to Pico
```bash
# Download latest MicroPython for RP2040 from micropython.org
# Hold BOOTSEL, plug USB, copy .uf2 to RPI-RP2 drive
```

2) Upload Pico firmware (v2.5)
```bash
# Use Thonny → File → Save to MicroPython
main/pico/main.py
```

3) Install desktop dependencies
```bash
pip install -r main/requirements.txt
```

4) Launch the GUI
```bash
python main/gui/main_app.py
```

The launcher starts the Modern GUI and the Dump Analyzer.

## З чого зібрана картка

`catalog.json`, `Pico-Nand-Flasher-RaspberryPi-Pico-NAND/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__Pico-Nand-Flasher.md`.
