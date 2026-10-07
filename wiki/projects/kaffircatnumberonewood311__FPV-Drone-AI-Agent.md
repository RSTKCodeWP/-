# 🤖 FPV-Drone-AI-Agent - Autonomous Flight Control Made Simple

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [kaffircatnumberonewood311/FPV-Drone-AI-Agent](https://github.com/kaffircatnumberonewood311/FPV-Drone-AI-Agent) |
| Локальна тека | `fpv-library/repos/FPV-Drone-AI-Agent-Control-the-EMAX-Nanohawk-FPV-drone-usin` |
| У бібліотеці | keep |
| Категорії каталогу | `fc`, `elrs`, `goggles`, `ai` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-07-27 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

### 📦 What is FPV-Drone-AI-Agent?

FPV-Drone-AI-Agent is a software application that lets your EMAX Nanohawk 1S FPV drone fly on its own. It uses artificial intelligence to control your drone without the need for you to manually pilot it. This tool combines flight control with AI to make autonomous navigation easier and more reliable.

The app works with the EMAX Nanohawk 1S and supports Betaflight flight controllers. It integrates with common drone systems like ExpressLRS and communicates using MAVLink protocol. You do not need any programming skills to use it.

_З README.md, без переказу._

## Для чого

Control the EMAX Nanohawk FPV drone using natural-language commands via local AI for autonomous flight without FPV goggles.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «goggles».
- Розробник польотного контролера — у тексті є «betaflight».
- Інженер радіолінка — у тексті є «expresslrs».


Теми GitHub: `ai-agent`, `autonomous-drone`, `betaflight`, `drone`, `emax`, `emax-nanohawk`, `expresslrs`, `flight-controller`, `fpv-drone`, `fpv-goggles`, `llama-cpp`, `mavlink`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Control the EMAX Nanohawk FPV drone using natural-language commands via local AI for autonomous flight without FPV goggles.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `BUILD_GUI.bat`
- `BUILD_SUMMARY.md`
- `ci/`
- `CMakeLists.txt`
- `CMakePresets.json`
- `config/`
- `docs/`
- `external/`
- `FPV Drone AI Agent-RAIL.md`
- `img_1.png`
- `include/`
- `models/`
- `QUICKSTART.md`
- `README.md`
- `scripts/`
- `src/`
- `test/`
- `tools/`
- `vcpkg.json`

Типи файлів за вибіркою (133 файлів, глибина до 3): C++ (75), Markdown (10), .bat (10), .exe (6), JSON (5), YAML (5).

Фрагмент README про будову:

### 🔧 How It Works

FPV-Drone-AI-Agent uses artificial intelligence to control your drone’s flight path. The software reads sensor inputs from your flight controller and calculates the best flight commands.

Key features:

- **Autonomous flight:** The drone can take off, navigate, and land on its own.  
- **AI navigation:** It adapts to surroundings using built-in AI logic.  
- **Real-time control:** The software sends commands to your flight controller through MAVLink.  
- **ExpressLRS support:** Works with long-range radio control setups.  
- **FPV compatibility:** Use with your FPV goggles to see drone footage live.  

The app handles all the complex tasks so you can focus on watching your drone fly.

---

## Що треба

### ⚙️ System Requirements

Make sure your computer and drone meet these requirements before running the software:

- **Operating System:** Windows 10 or later (64-bit recommended)  
- **Processor:** Intel Core i5 or equivalent, 2.5 GHz or faster  
- **Memory:** 8 GB RAM minimum  
- **Storage:** At least 500 MB free disk space for installation  
- **USB Ports:** You need a USB port to connect the flight controller  
- **Drone:** EMAX Nanohawk 1S with a Betaflight-compatible flight controller  
- **Additional Hardware:** FPV goggles that support your drone system (optional)  

---

- Маніфести збірки: CMake.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 🚀 Getting Started

Follow these steps to download, install, and run FPV-Drone-AI-Agent on your Windows PC.
### Step 2: Install the Application

1. Locate the downloaded file in your Downloads folder. It will usually be named something like `FPV-Drone-AI-Agent-Setup.exe` or similar.
2. Double-click the file to start the installer.
3. Follow the on-screen prompts to complete the installation. Choose the default options to keep things simple.
4. When installation finishes, you should see a new shortcut on your desktop or in your Start menu.

---
### ⚡ How to Uninstall

If you want to remove FPV-Drone-AI-Agent:

1. Open Control Panel on Windows.  
2. Go to Programs > Programs and Features.  
3. Find FPV-Drone-AI-Agent in the list.  
4. Select it and click Uninstall.  
5. Follow prompts to complete removal.  

You can then delete any leftover files from your installation folder if needed.

---

## Супутні документи в теці

- [`docs/CONFIG_WIRING.md`](../../fpv-library/repos/FPV-Drone-AI-Agent-Control-the-EMAX-Nanohawk-FPV-drone-usin/docs/CONFIG_WIRING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/FPV-Drone-AI-Agent-Control-the-EMAX-Nanohawk-FPV-drone-usin/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/kaffircatnumberonewood311__FPV-Drone-AI-Agent.md`.
