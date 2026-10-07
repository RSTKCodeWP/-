# ExpressLRS / TBS Crossfire WiFi Joystick for Windows

> Картка виставки. Зал: [Радіо](../halls/radio.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [juricabi/ELRS-Crossfire-WiFi-Joystick-Windows](https://github.com/juricabi/ELRS-Crossfire-WiFi-Joystick-Windows) |
| Локальна тека | `fpv-library/repos/ELRS-Crossfire-WiFi-Joystick-Windows-Turn-an-ExpressLRS-ELRS-or-TBS-Crossfire` |
| У бібліотеці | keep |
| Категорії каталогу | `radio`, `elrs`, `tools` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-08-01 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**Use your ExpressLRS or TBS Crossfire/Tracer radio as a wireless joystick on Windows — with a live visual app**

This app turns your **ExpressLRS (ELRS)** *or* **TBS Crossfire / Tracer** TX module's WiFi output into a virtual joystick (via vJoy), so you can fly flight simulators like VelociDrone, Liftoff, or DRL — **wirelessly, no cables** — plus anything on Windows that takes joystick input.

Both radios use the same "WiFi joystick" protocol (the one VelociDrone Mobile speaks), so setup is identical: put the module on your WiFi and run the app. The only difference is the discovery beacon — ELRS announces itself as `ELRS`, Crossfire as `VELOCIDRONE` — and the app handles both automatically.

> **v3.0** is a ground-up WPF interface: vector-rendered, so it is pixel-perfect on **any** display scale (100/125/150/200%), with GPU-composited live axis bars, packet rate + jitter, connection sta…

_З README.md, без переказу._

## Для чого

Turn an ExpressLRS (ELRS) or TBS Crossfire/Tracer WiFi module into a vJoy virtual joystick on Windows for FPV simulators like VelociDrone and Liftoff. No cables, no MAVLink.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «expresslrs».


Теми GitHub: `crossfire`, `drone`, `elrs`, `expresslrs`, `fpv`, `gamepad`, `joystick`, `liftoff`, `rc`, `simulator`, `tbs`, `tracer`.

## Функція

Список із розділу features / можливості в README:

- 🎮 **Virtual joystick** - creates a Windows vJoy device from your radio's WiFi output
- 📡 **ELRS + Crossfire/Tracer** - full support for the ELRS/Crossfire WiFi joystick protocol (16 channels, 15-bit)
- 🖥️ **Live visual app (WPF)** - real-time GPU-composited axis bars, packet **rate + jitter**, and connection status at a glance
- 🌐 **Auto-discovery** - detects and activates ELRS *and* TBS Crossfire/Tracer modules automatically (or type the IP)
- 🛡️ **One-click firewall** - detects and adds the required Windows Firewall rule for you (the #1 "no data" cause)
- 🔒 **Single-source lock** - if two modules are on the network, only one drives the joystick; pick a specific one by IP
- 📉 **Accurate metrics** - high-resolution jitter/rate measurement
- ❓ **Built-in Help** - a Help button with short tutorials for every feature
- 🪶 **Light & CPU-friendly** - minimize to the system tray to pause the on-screen bars and drop CPU to ~1% (the joystick keeps working); single-instance
- 📦 **No install** - self-contained single-file `.exe`, runs on Windows 7 SP1 through Windows 11 (64-bit)
- ⌨️ **CLI edition too** - `ELRSWifiJoystickCli.exe` (~9 MB, instant start): the same engine and features in a console app - live channel readout, stats, firewall handling, `--tx`, plus interactive keys while running (`s` start/stop, `t` modu
- 🖥️ **DPI-perfect** - WPF vector rendering: crisp on every display scale (100/125/150/200%), including per-monitor DPI

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `app.manifest`
- `App.xaml`
- `App.xaml.cs`
- `build.bat`
- `docs/`
- `ELRSWifiJoystick.Cli/`
- `ELRSWifiJoystick.csproj`
- `ELRSWifiJoystick.Tests/`
- `FirewallHelper.cs`
- `HelpWindow.xaml`
- `HelpWindow.xaml.cs`
- `icons/`
- `JoystickEngine.cs`
- `lib/`
- `LICENSE`
- `MainViewModel.cs`
- `MainWindow.xaml`
- `MainWindow.xaml.cs`
- `publish-cli.bat`
- `publish.bat`
- `README.md`
- `RelayCommand.cs`

Типи файлів за вибіркою (34 файлів, глибина до 3): .cs (16), .bat (3), .csproj (3), .xaml (3), (без суфікса) (2), .txt (2).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Option 2: Build from Source

#### Prerequisites

- **vJoy Driver** - Download from [vjoystick.sourceforge.net](http://vjoystick.sourceforge.net/)
- **.NET 6.0 SDK** - Download from [dotnet.microsoft.com](https://dotnet.microsoft.com/download/dotnet/6.0)

#### Build Steps

1. **Clone** this repository

2. **Setup vJoy Libraries**
   - Install vJoy from the official website
   - Copy `vJoyInterfaceWrap.dll` from `C:\Program Files\vJoy\x64\` to the `lib\` folder

3. **Build the Application**
   
   **Option A: Using Build Scripts (Recommended)**
   ```bash
   # Development build (multiple files, good for testing)
   .\build.bat
   
   # Production build (single executable, good for distribution)
   .\publish.bat
   ```
   
   **Option B: Manual Commands**
   ```bash
   # Development build
   dotnet build -c Release
   
   # Production build (single executable)
   dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
   ```
### Build Scripts Explained

| Script | Purpose | Output | Use Case |
|--------|---------|--------|----------|
| `build.bat` | Development build | Multiple files (DLLs, runtime, etc.) | Testing, debugging, development |
| `publish.bat` | Production build (GUI) | Single executable + ZIP distribution | Distribution, deployment |
| `publish-cli.bat` | Production build (CLI) | Trimmed ~9 MB console exe + ZIP | Lightweight/headless use |

**build.bat** creates a development build with separate files, making it easier to debug and modify.  
**publish.bat** creates a single-file executable perfect for distribution to end users.
### vJoy Setup

1. Install vJoy from [vjoystick.sourceforge.net](http://vjoystick.sourceforge.net/)
### ExpressLRS TX Module Setup

1. **Connect to WiFi**:
   - Put your ELRS TX module in WiFi mode
   - Connect to the TX module's WiFi access point OR connect it to your local WiFi network

2. **Access Web Interface**:
   - Open `http://10.0.0.1` or `http://elrs_tx.local` in your browser
   - ELRS should automaticaly send data for WIFI gamepad if connected
### TBS Crossfire / Tracer Setup

Setup is the same as ELRS — the module just needs to be on the same WiFi network. This uses
the "Velocidrone Mobile" support built into the TBS WiFi module.

> ### 🛑 Check your firmware first
>
> | Component | Works | Broken |
> |-----------|-------|--------|
> | **Crossfire TX (XF)** | **6.31**, **6.36** | **6.42 public, 6.48 beta, 6.48 public** |
> | **WiFi module** | **v2.17** up to **v3.10** (v2.25.49mb recommended) | **v3.20** |
>
> On a broken version the module streams normally but **never sends stick data** — this app,
> VelociDrone Mobile, and every other client see the same dead stream, and nothing on the PC
> side can fix it. Details and source:
> [firmware compatibility](#-crossfire-firmware-compatibility-important).

1. **Connect to WiFi**:
   - Enable WiFi on the Crossfire/Tracer TX (WiFi module powered).
   - Either connect the module to your local WiFi network (recommended), or connect your PC
     to the module's own access point (`tbs_crossfire_XXXXXXXXXXXX` / `192.168.4.1`).
   - Your PC and the module must be on the same network.

2. **Run the app** — no extra configuration needed:
   - The module continuously broadcasts a `VELOCIDRONE` discovery beacon (~every 8 s). The
     app detects it and automatically sends the activation request, then starts receiving
     channel data.
   - To skip the beacon wait and activate instantly, pass the module's IP:
     `ELRSWifiJoystick.exe --tx 192.168.2.138`
     (find the IP on the module's WiFi web page).

> **How it works:** the app POSTs `action=joystick_begin` to the module's `/udpcontrol`
> endpoint — the same request ELRS uses — and the module streams RC channels over UDP on
> port 11000. No radio-to-FC wiring, MAVLink, or ground-control software is involved; the
> WiFi module sends stick data directly.
### 🎮 Usage

1. **Run `ELRSWifiJoystick.exe`.** The app opens, initializes vJoy, and starts listening
   automatically. The first time, accept the one-time Windows permission (UAC) prompt so the
   firewall lets the joystick data through.

2. **Watch the status banner:**
   - 🟠 *Searching for module…* — make sure your module is on the same WiFi.
   - 🟢 *Connected — streaming* — the axis bars move with your sticks, and you'll see the
     packet **rate** and **jitter**.

3. **Use in your flight simulator:** open VelociDrone / Liftoff / DRL etc., select
   **"vJoy Device"** as the controller, and calibrate the axes.

4. **Optional controls:**
   - **Module IP** — leave blank for auto-discovery, or type your module's IP and press
     **Connect** to target a specific module (skips the beacon wait; find the IP on the
     module's WiFi web page).
   - **Port** — the UDP port (default `11000`); change it while stopped.
   - **Fix Firewall** — appears only if the firewall is blocking data.
   - **Help** — opens short tutorials for every feature.
   - Minimizing to the tray pauses the on-screen bars and drops CPU to ~1% — the joystick
     keeps working, so **minimize while flying** for best performance.
   - Closing the window centers the vJoy axes and releases the device.

**Command-line (optional):** `ELRSWifiJoystick.exe [port] [--tx <module-ip>]` — e.g.
`ELRSWifiJoystick.exe --tx 192.168.2.138` pre-fills the module IP on launch.

> **Stopping the module's stream:** the ELRS/Crossfire WiFi module has **no remote stop
> command** — once activated it keeps broadcasting channel data until it is powered off,
> rebooted, or its WiFi drops. Closing this app only stops *reading* the stream; it does not
> (and cannot) stop the module from sending. This is a module-firmware behaviour, not an app
> limitation.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ELRS-Crossfire-WiFi-Joystick-Windows-Turn-an-ExpressLRS-ELRS-or-TBS-Crossfire/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/juricabi__ELRS-Crossfire-WiFi-Joystick-Windows.md`.
