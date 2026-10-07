# rubenCodeforges/ardudeck

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rubenCodeforges/ardudeck](https://github.com/rubenCodeforges/ardudeck) |
| Локальна тека | `fpv-library/repos/ardudeck-One-GCS-to-rule-them-all-ArduPilot-Betaf` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `osd`, `fc`, `tools` |
| Зірки (каталог) | 129 |
| Оновлено upstream | 2026-07-29 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

ArduDeck is an open-source ground control station built with Electron, React, and TypeScript. One app covers the whole workflow: connect, configure, calibrate, plan, fly, and analyze, for vehicles running ArduPilot (MAVLink) or Betaflight/iNav (MSP), from a single quad on USB to a fleet of vehicles on radio, IP, or cellular links.

> **Beta 1 (0.1.0)** - ArduDeck is in beta. It is used in real flight operations, but expect rough edges and keep a backup configuration tool available. Ask questions and share setups on the [community forum](https://forum.ardudeck.com) or [Discord](https://discord.gg/JX2JdVXPPC), read the [documentation](https://ardudeck.com/docs/), or use the built-in [bug reporting](#bug-reporting) to help improve the project.

_З README.md, без переказу._

## Для чого

One GCS to rule them all. ArduPilot, Betaflight, iNav - all in one app. Mission planning, PID tuning, OSD simulator, SITL with FlightGear. Cross-platform (Win/Mac/Linux)

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `betaflight`, `drone`, `flight-controller`, `fpv`, `gcs`, `ground-control-station`, `inav`, `inav-configurator`, `mavlink`, `mission-planner`, `msp`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: One GCS to rule them all. ArduPilot, Betaflight, iNav - all in one app. Mission planning, PID tuning, OSD simulator, SITL with FlightGear. Cross-platform (Win/Mac/Linux)

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `apps/`
- `build-sitl/`
- `CLA.md`
- `CLAUDE.md`
- `CONTRIBUTING.md`
- `crates/`
- `docs/`
- `eslint.config.js`
- `gcs-telemetry.png`
- `LICENSE`
- `package-lock.json`
- `package.json`
- `packages/`
- `pnpm-lock.yaml`
- `pnpm-workspace.yaml`
- `README.md`
- `screenshots/`
- `tools/`
- `tsconfig.base.json`
- `turbo.json`
- `vitest.workspace.ts`
- `wiki/`

Типи файлів за вибіркою (260 файлів, глибина до 3): TypeScript (70), .png (54), JSON (40), Rust (36), Markdown (13), (без суфікса) (13).


## Що треба

### Prerequisites

- **Node.js** 20 or higher
- **pnpm** 9 or higher

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `start`, `build`, `dev`, `lint`, `test`, `test:coverage`, `generate`, `clean`, `sync-version`, `package`, `sitl:build`, `sitl:publish`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Vehicle Setup & Tuning

- **Parameter management** - full parameter list with metadata, search, range/enum/increment validation, modified tracking, and .param file import/export
- **PID tuning** - ArduPilot and Betaflight/iNav tuning with presets, rate curve editors, and a VTOL / fixed-wing controller switch on QuadPlanes
- **Flight modes, safety, and failsafe** - mode channel assignment, failsafe actions, geofence behavior, and MAVLink signing
- **Calibration** - accelerometer, compass (including CompassMot motor-interference calibration and large-vehicle mag cal), with step-by-step wizards
- **Motor test, servo wizard, quick setup** - guided flows for frames, fixed wings, and first-time configuration
- **CLI terminal** - xterm-based terminal with autocomplete and history, including full GUI configuration for legacy F3-era boards driven over CLI
### Download & Install

Most users should download a pre-built release. No need to clone or build anything.

| Platform | Format |
|----------|--------|
| **Windows** | Installer (.exe) and portable (.exe) |
| **macOS** | DMG (Apple Silicon) |
| **Linux** | AppImage and .deb |

All downloads: [Latest Release](https://github.com/rubenCodeforges/ardudeck/releases/latest)

Install, plug in your flight controller via USB (or point ArduDeck at your telemetry link), and you are ready to go.

> **Linux AppImage note:** on Ubuntu 24.04+ and other recent distros the AppImage needs `libfuse2` (`sudo apt install libfuse2`), or run it with `APPIMAGE_EXTRACT_AND_RUN=1`. The `.deb` package has no such dependency.
>
> **Code signing:** ArduDeck binaries are currently unsigned. On macOS, right-click the app and select "Open" (or run `xattr -cr /Applications/ArduDeck.app`). On Windows SmartScreen, click "More info", then "Run anyway".
>
> **Auto-updates:** Windows and Linux update in-app with one click. On macOS, ArduDeck notifies you about new versions and opens the release page for manual download until the app is code-signed.

---
### Setup

```bash
# Fork the repo on GitHub first, then clone your fork
git clone https://github.com/<your-username>/ardudeck.git
cd ardudeck

# Install dependencies
pnpm install

# Build all packages
pnpm build

# Run in development mode
pnpm dev
```

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/ardudeck-One-GCS-to-rule-them-all-ArduPilot-Betaf/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ardudeck-One-GCS-to-rule-them-all-ArduPilot-Betaf/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rubenCodeforges__ardudeck.md`.
