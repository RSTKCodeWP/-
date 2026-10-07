# iBz-04/Cevheri

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [iBz-04/Cevheri](https://github.com/iBz-04/Cevheri) |
| Локальна тека | `fpv-library/repos/Cevheri-Modern-drone-control-station` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc` |
| Зірки (каталог) | 5 |
| Оновлено upstream | 2025-10-01 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

### Introduction

This is a progressive web application drone station. It uses typescript as the frontend interface and FastAPI with MAVSDK as the API backend for drone communication.

_З README.md, без переказу._

## Для чого

Modern drone control station

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «qgroundcontrol».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `autonomous-navigation`, `drone-controller`, `drone-simulation`, `drone-software`, `fastapi`, `gazebo-classic`, `gps-tracker`, `ground-control-station`, `ground-station`, `mavlink-protocol`, `mavsdk`.

## Функція

Список із розділу features / можливості в README:

- Real-time drone telemetry monitoring
- Web-based control interface
- MAVSDK integration for MAVLink communication
- Socket.io for real-time data streaming
- RESTful API endpoints for drone control
- Real-time GPS tracking with Google Maps integration

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `api/`
- `app/`
- `connect_qgc.py`
- `next.config.js`
- `package-lock.json`
- `package.json`
- `pnpm-lock.yaml`
- `postcss.config.js`
- `public/`
- `README.md`
- `requirements.txt`
- `run_video_viewer.sh`
- `setup_video.sh`
- `simple_video_viewer.py`
- `tailwind.config.js`
- `tsconfig.json`
- `video_viewer.py`

Типи файлів за вибіркою (43 файлів, глибина до 3): TypeScript (11), Python (7), .png (6), JavaScript (4), JSON (4), .svg (3).

Фрагмент README про будову:

### How It Works

The Python/FastAPI server is mapped into to Next.js app under `/api/`. The drone controller uses MAVSDK to communicate with drone systems via MAVLink protocol.

This is implemented using [`next.config.js` rewrites](https://github.com/vercel/examples/blob/main/python/nextjs-flask/next.config.js) to map any request to `/api/:path*` to the FastAPI server, which is hosted in the `/api` folder.

On localhost, the rewrite will be made to the `127.0.0.1:5328` port, which is where the FastAPI server is running.

## Що треба

### Prerequisites

Before getting started, ensure you have the following installed on your Linux system:

- **Node.js** (v16 or higher) and **pnpm**
- **Python 3.8+** and **pip**
- **Git**
- **QGroundControl** (for ground control station)
- **PX4 SITL** (for drone simulation)

- Маніфести збірки: Node.js (package.json), Python (requirements.txt).
- npm-скрипти в package.json: `flask-dev`, `next-dev`, `dev`, `build`, `start`, `lint`.
- dependencies: `@types/leaflet`, `@types/node`, `@types/react`, `@types/react-dom`, `autoprefixer`, `concurrently`, `eslint`, `eslint-config-next`, `leaflet`, `next`, `postcss`, `react` і ще 5.
- requirements.txt: `fastapi==0.104.1`, `uvicorn==0.24.0`, `python-socketio==5.10.0`, `python-multipart==0.0.6`, `pydantic==2.4.2`, `pymavlink==2.4.37`, `mavsdk>=2.0.0`, `aiohttp==3.9.1`, `opencv-python==4.7.0.68`, `numpy>=1.23,<2`, `PyQt5>=5.15.0`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Progressive Web App Installation

*Installation button*
### Installing Prerequisites on Linux

```bash
# Install Node.js and pnpm
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
npm install -g pnpm

# Install Python and pip (usually pre-installed)
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Install Git
sudo apt install git
```
### Step 1: Clone and Setup the Project

```bash
# Clone the repository
git clone <your-repo-url>
cd Control-station

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
pnpm install
```
### Step 2: Download and Setup MAVSDK Server

```bash
# Create a directory for MAVSDK server
mkdir -p ~/mavsdk

# Download MAVSDK server (replace with latest version)
cd ~/mavsdk
wget https://github.com/mavlink/MAVSDK/releases/download/v2.12.2/mavsdk_server_linux-x64-musl
chmod +x mavsdk_server_linux-x64-musl

# Create a symlink in your project directory
cd ~/Control-station
ln -sf ~/mavsdk/mavsdk_server_linux-x64-musl mavsdk_server

# OR copy it directly to your project
cp ~/mavsdk/mavsdk_server_linux-x64-musl ./mavsdk_server
chmod +x ./mavsdk_server
```
### Step 3: Install and Setup QGroundControl

```bash
# Download QGroundControl AppImage
cd ~/Downloads
wget https://d176tv9ibo4jno.cloudfront.net/latest/QGroundControl.AppImage
chmod +x QGroundControl.AppImage

# Move to applications directory (optional)
sudo mv QGroundControl.AppImage /opt/
sudo ln -sf /opt/QGroundControl.AppImage /usr/local/bin/qgroundcontrol

# Now you can run QGroundControl from anywhere
qgroundcontrol
```
### Step 4: Install and Setup PX4 SITL (Simulation)

```bash
# Clone PX4 repository
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
cd PX4-Autopilot

# Install PX4 dependencies
bash ./Tools/setup/ubuntu.sh

# Build PX4 for simulation
make px4_sitl_default gazebo-classic

# Or build without Gazebo (lighter)
make px4_sitl_default
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Cevheri-Modern-drone-control-station/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/iBz-04__Cevheri.md`.
