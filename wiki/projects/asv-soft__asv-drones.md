# Asv.Drones

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [asv-soft/asv-drones](https://github.com/asv-soft/asv-drones) |
| Локальна тека | `fpv-library/repos/asv-drones-Open-source-implementation-of-ground-con` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc` |
| Зірки (каталог) | 217 |
| Оновлено upstream | 2026-07-31 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

### 1. Introduction

Asv.Drones: Empowering Innovation in Unmanned Aerial Systems

Welcome to Asv.Drones, an advanced and modular open-source application designed to revolutionize the field of Unmanned Aerial Systems (UAS). Committed to fostering innovation and collaboration, Asv.Drones is not just a drone application; it's a community-driven platform that opens the doors to limitless possibilities.

Key Features:

1. **Plugins:** Asv.Drones supports plugins that extend the application without modifying its core. Plugins are loaded from the `plugins` directory and use the `Asv.Drones.Plugin.` assembly prefix.

2. **Open Source Philosophy:** Transparency and collaboration lie at the heart of Asv.Drones. The entire application, along with its constituent modules, is open source. This means that not only can users benefit from the software, but they can also actively contribute to its enhan…

_З README.md, без переказу._

## Для чого

Open source implementation of ground control station application for ArduPilot and PX4 autopilot

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `drones`, `linux`, `mac-osx`, `mavlink`, `missionplanner`, `px4`, `qgroundcontrol`, `windows`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Open source implementation of ground control station application for ArduPilot and PX4 autopilot

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `api_build.bat`
- `api_publish_github.bat`
- `img/`
- `LICENSE`
- `publish.bat`
- `README.md`
- `src/`
- `win-64-install.nsi`
- `win-arm-install.iss`
- `win-arm64-install.iss`
- `win-x64-install.iss`
- `win-x86-install.iss`

Типи файлів за вибіркою (71 файлів, глибина до 3): .cs (14), .png (9), .csproj (6), (без суфікса) (5), JSON (5), .iss (4).


## Що треба

### 3.1 Prerequisites

- **Operating System:** This project is compatible with Windows, macOS and Linux. Ensure that your development machine runs one of these supported operating systems.
- **IDE (Integrated Development Environment):** We recommend using [Visual Studio](https://visualstudio.microsoft.com/) or [JetBrains Rider](https://www.jetbrains.com/rider/) as your IDE for C# development. 
- Make sure to install the necessary extensions and plugins for a better development experience.
### 3.5 Restore Dependencies

- Navigate to the `src` directory and restore the dependencies for the desktop project.
There are three possible platform directories to build and debug our app: __Asv.Drones.Desktop__, __Asv.Drones.Android__, __Asv.Drones.iOS__.
Currently, we support only the desktop platform.

   ```bash
   cd asv-drones/src
   dotnet restore Asv.Drones.Desktop/Asv.Drones.Desktop.csproj
   ```


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Example of Usage with GBS

**Ground Base Station Integration:** Asv.Drones offers seamless integration with ground base stations through our proprietary implementation called [Asv.Drones.Gbs](https://github.com/asv-soft/asv-drones-gbs). 
Built to operate via the MAVLink protocol, Asv.Drones.Gbs allows users to remotely manage and monitor drone operations from a centralized platform. 
Moreover, any other ground base station software compatible with MAVLink can seamlessly interface with our application, ensuring flexibility and interoperability across different systems (development of additional UI controls may be required).
With Asv.Drones.Gbs, users can plan missions, monitor telemetry data and adjust flight parameters with ease.
To connect to a GBS, create a new connection (usually TCP) in the connection settings.

<div align="center">
</div>
### 3.2 .NET Installation

- This project is built using [.NET 10.0](https://dotnet.microsoft.com/download/dotnet/10.0).
We recommend installing .NET 10.0 by following the instructions provided on the official [.NET website](https://dotnet.microsoft.com/download/dotnet/10.0).

   ```bash
   # Check your current .NET version
   dotnet --version
   ```
### 3.6 Build and Run

- Build the desktop project:

   ```bash
   dotnet build Asv.Drones.Desktop/Asv.Drones.Desktop.csproj
   ```

- Run the desktop project:

   ```bash
   dotnet run --project Asv.Drones.Desktop/Asv.Drones.Desktop.csproj
   ```

Congratulations! Your development environment is now set up, and you are ready to start contributing to the project. 
If you encounter any issues during the setup process, refer to the project's documentation or reach out to the development team for assistance.
### 7. Build and Deployment

The build and deployment processes are crucial parts of our development workflow. 
This section outlines the steps for building the project and deploying it using GitHub Actions.
### 7.1 Build Process

To compile the project, use the following command:

```bash
dotnet build
```

This command compiles the code and produces executable binaries.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/asv-drones-Open-source-implementation-of-ground-con/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/asv-soft__asv-drones.md`.
