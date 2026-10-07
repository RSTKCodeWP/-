# 🤖 MaixCAM Advanced Servo Control

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/maixcam-servo-control](https://github.com/RSTKCodeWP/maixcam-servo-control) |
| Локальна тека | `maixcam-servo-control-AI-Ballistic-Servo-MaixCAM` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**Advanced AI-powered servo control system for MaixCAM with Autonomous Ballistics, YOLOv8 object detection, color tracking, and motion sensing**

_З README.md, без переказу._

## Для чого

**Advanced AI-powered servo control system for MaixCAM with Autonomous Ballistics, YOLOv8 object detection, color tracking, and motion sensing**

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник відеотракту — у тексті є «h.265».


## Функція

Список із розділу features / можливості в README:

- **Ballistics Physics** (Lead time & Distance)
- **Auto Ground Speed** (Optical flow analysis)
- **Auto Altitude** (AI bounding-box sizing)
- **Standalone App** (Boot without PC)
- **Video Recording** (H.265 toggle)
- **Configurable angles** (0-180°)
- **ARM/DISARM mode** for safety
- **Auto-rearm** with delay
- **Repeat trigger** mode
- **Multiple PWM pins** support
- **Touchscreen Grid menu**
- **Dynamic Options** (Hides irrelevant info)

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `advanced_servo_app.py`
- `CHANGELOG.md`
- `docs/`
- `examples/`
- `LICENSE`
- `maix_app/`
- `README.md`
- `utils/`

Типи файлів за вибіркою (20 файлів, глибина до 3): Python (9), Markdown (6), (без суфікса) (2), .txt (1), JSON (1), YAML (1).


## Що треба

### 🛠️ Requirements

- **Hardware:** MaixCAM (1st gen with screen), SG90 servo (or compatible)
- **Software:** MaixPy 4.x, YOLOv8 model (`/root/models/yolov8n.mud`)
- **Power:** 5V 2A power supply recommended
- **Tools:** MaixVision IDE for deployment
### 🛠️ Требования

- **Железо:** MaixCAM (1-го поколения с экраном), серва SG90 (или аналог)
- **ПО:** MaixPy 4.x, модель YOLOv8 (`/root/models/yolov8n.mud`)
- **Питание:** Блок питания 5V 2A (рекомендуется)
- **Инструменты:** MaixVision IDE для загрузки


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 🚀 Quick Start (5 minutes)

#### 1️⃣ Hardware Setup
```
Servo Signal (yellow) → A18 (configurable in UI: A14-A19)
Servo GND (brown)     → GND
Servo Power (red)     → VBUS 5V (2A recommended)
```

#### 2️⃣ Installation (Autonomous Execution)
No PC required after installation! The app runs entirely standalone.
1. Download the `advanced_servo_drop_v1.0.0.zip` from the [Releases](https://github.com/bobberdolle1/maixcam-servo-control/releases).
2. Use MaixVision's App Store or CLI to install the app on your MaixCAM:
   ```bash
   app_store_cli install advanced_servo_drop_v1.0.0.zip
   ```
3. The app **"Servo Drop"** will now appear on your camera's touch screen launcher.

#### 3️⃣ Enable Auto-Boot (Optional)
To have the camera automatically start the app when powered by a drone/power bank:
- On the camera screen, go to **Settings** -> **Boot App**.
- Select **Servo Drop**.

#### 4️⃣ Configure (Touch UI)
- Tap the screen to open the **Menu**.
- The new **Bounding Box UI** makes selecting settings easy.
- Choose Mode (Color/Object/Motion), Pins, Angles (0-180°), and Delays.
### 🎯 Примеры использования

<table>
<tr>
<td>🐾 <b>Кормушка для питомцев</b><br/>Автоматическая кормушка</td>
<td>🎨 <b>Сортировщик</b><br/>Сортировка по цвету</td>
<td>🚨 <b>Безопасность</b><br/>Детектор движения</td>
</tr>
<tr>
<td>👥 <b>Счетчик людей</b><br/>Подсчет посетителей</td>
<td>🚪 <b>Авто-дверь</b><br/>Открывание без рук</td>
<td>🎮 <b>Жесты</b><br/>Управление жестами</td>
</tr>
<tr>
<td>📸 <b>Камера для животных</b><br/>Съемка дикой природы</td>
<td>✅ <b>Контроль качества</b><br/>Детекция дефектов</td>
<td>🅿️ <b>Парковка</b><br/>Мониторинг мест</td>
</tr>
</table>

## Супутні документи в теці

- [`docs/EXAMPLES.md`](../../maixcam-servo-control-AI-Ballistic-Servo-MaixCAM/docs/EXAMPLES.md)
- [`docs/PROJECT_SUMMARY.md`](../../maixcam-servo-control-AI-Ballistic-Servo-MaixCAM/docs/PROJECT_SUMMARY.md)
- [`docs/QUICKSTART.md`](../../maixcam-servo-control-AI-Ballistic-Servo-MaixCAM/docs/QUICKSTART.md)
- [`docs/TECHNICAL.md`](../../maixcam-servo-control-AI-Ballistic-Servo-MaixCAM/docs/TECHNICAL.md)

## З чого зібрана картка

`catalog.json`, `maixcam-servo-control-AI-Ballistic-Servo-MaixCAM/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__maixcam-servo-control.md`.
