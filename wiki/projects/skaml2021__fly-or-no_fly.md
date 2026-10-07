# ✈️ fly-or-no_fly - Easy FPV Flight Condition Monitor

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [skaml2021/fly-or-no_fly](https://github.com/skaml2021/fly-or-no_fly) |
| Локальна тека | `fly-or-no_fly-RaspberryPi-FPV-Flight-Monitor` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

### 📋 What is fly-or-no_fly?

fly-or-no_fly is a simple dashboard for Raspberry Pi that shows whether it is safe to fly your FPV drone. It uses weather forecasts and set limits on wind, rain, and daylight. The results show on a small 2.15-inch Waveshare e-paper screen. You can see a clear "go" or "no-go" status every hour. The system also keeps hourly records of the conditions.

This helps FPV drone pilots decide quickly if flying is safe. It works with Raspberry Pi Zero 2 and other models run Linux. The software uses Python.

_З README.md, без переказу._

## Для чого

### 📋 What is fly-or-no_fly?

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Список із розділу features / можливості в README:

- Fetches weather data from Open-Meteo API hourly
- Checks wind speed, gusts, rain, and daylight rules you can set
- Displays clear “go” or “no-go” status on an e-paper display
- Logs hourly weather and status to a file for review
- Works with commonly used Raspberry Pi e-paper displays

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `docs/`
- `fpv_board/`
- `pytest.ini`
- `README.md`
- `requirements.txt`
- `scripts/`
- `systemd/`
- `tests/`

Типи файлів за вибіркою (51 файлів, глибина до 3): Python (23), .png (9), Markdown (5), .timer (3), .service (3), (без суфікса) (2).


## Що треба

### 💻 System Requirements

To use fly-or-no_fly, you need:

- A Raspberry Pi (model Zero 2 W or newer is best)
- A 2.15″ Waveshare e-paper display connected to Raspberry Pi
- microSD card with at least 8 GB space
- Active internet connection to get weather data
- Power supply for Raspberry Pi
- Basic familiarity connecting hardware and running simple programs

The software runs on Raspberry Pi OS or similar Linux-based systems.

- Маніфести збірки: Python (requirements.txt).
- requirements.txt: `requests>=2.31.0`, `Pillow>=10.0.0`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 🚀 Getting Started - Download fly-or-no_fly

Please visit this page to download the latest version of fly-or-no_fly:


Open the link above in your browser. You will find files under the "Releases" section. Look for the latest release and download the relevant archive file (usually a zip or tar.gz).

Save the file to your Raspberry Pi or another computer where you can transfer it.
### 🛠️ Installing fly-or-no_fly on Raspberry Pi

Follow these steps once you have downloaded the file:

1. **Transfer the downloaded archive** to your Raspberry Pi if you did not download it there directly. You can use a USB drive or SCP from another computer.

2. **Open a Terminal** on your Raspberry Pi.

3. **Extract the archive**. For example, if the file is named `fly-or-no_fly_v1.0.tar.gz`, run:
   
   ```
   tar -xzf fly-or-no_fly_v1.0.tar.gz
   ```
   or
   
   ```
   unzip fly-or-no_fly_v1.0.zip
   ```
   depending on the file type.

4. **Navigate into the extracted folder**:
   
   ```
   cd fly-or-no_fly
   ```

5. **Install dependencies**. Run:
   
   ```
   sudo apt update
   sudo apt install python3-pip python3-dev python3-venv
   pip3 install -r requirements.txt
   ```
   This installs Python and needed packages.

6. **Connect your e-paper display** to the Raspberry Pi GPIO pins following the manufacturer's instructions. Check wiring carefully.

7. **Configure your settings**. Open the `config.json` file in a text editor:
   
   ```
   nano config.json
   ```
   
   Set your wind, gust, rain thresholds, and daylight hours. Save the file.

8. **Run the program**:
   
   ```
   python3 main.py
   ```

The screen will update every hour telling you if conditions are good to fly.
### 🧩 Hardware Setup Tips

- Use female-to-female jumper wires for Raspberry Pi to e-paper display connections.
- Double-check the pin assignments: miswiring can cause your screen not to display.
- Use a stable power supply, as e-paper displays require consistent power.
- If you have trouble with the screen, try rebooting the Pi and running the program again.

## Супутні документи в теці

- [`docs/README_OPERATIONS.md`](../../fly-or-no_fly-RaspberryPi-FPV-Flight-Monitor/docs/README_OPERATIONS.md)
- [`docs/README_SETUP.md`](../../fly-or-no_fly-RaspberryPi-FPV-Flight-Monitor/docs/README_SETUP.md)

## З чого зібрана картка

`catalog.json`, `fly-or-no_fly-RaspberryPi-FPV-Flight-Monitor/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/skaml2021__fly-or-no_fly.md`.
