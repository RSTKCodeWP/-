# Altnautica Mission Control

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [altnautica/ADOSMissionControl](https://github.com/altnautica/ADOSMissionControl) |
| Локальна тека | `fpv-library/repos/ADOSMissionControl-Open-source-web-based-Ground-Control-Sta` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc`, `tools` |
| Зірки (каталог) | 219 |
| Оновлено upstream | 2026-08-01 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

**Open-source web ground station for software-defined drones. ArduPilot, PX4, Betaflight, and iNav. Mission planning, AI tuning, and gamepad flight, in the browser.**

Command any drone from any browser. ADOS Mission Control is a full ground control station for software-defined drones. Configure flight controllers panel by panel, plan missions with pattern generators, fly with a gamepad at 50 Hz, and tune PIDs with AI. No install. No locked hardware.

> **Part of the ADOS ecosystem.** Pairs with [ADOS Drone Agent](https://github.com/altnautica/ADOSDroneAgent), the Rust-first onboard companion, for the long-range data link, HD video, and cloud fleet management. Works standalone with any MAVLink drone over USB or WebSocket. Add features with [ADOS Extensions](https://github.com/altnautica/ADOSExtensions), the first-party plugin repo.

_З README.md, без переказу._

## Для чого

Open-source web-based Ground Control Station for autonomous drones. FC config, sensor calibration, mission planning, MAVLink protocol, manual flight control. Supports multi drone fleet and companion software for true software defined drones.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground control».
- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Розробник польотного контролера — у тексті є «betaflight».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `ardupilot-companion`, `betaflight`, `betaflight-configurator`, `drone`, `gcs`, `ground-control-station`, `inav`, `inav-configurator`, `mavlink`, `mission-planner`, `sitl`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Open-source web-based Ground Control Station for autonomous drones. FC config, sensor calibration, mission planning, MAVLink protocol, manual flight control. Supports multi drone fleet and companion software for true software defined drones.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `convex/`
- `Dockerfile`
- `electron/`
- `electron-builder.yml`
- `eslint.config.mjs`
- `i18n.ts`
- `LICENSE`
- `locales/`
- `next.config.ts`
- `package-lock.json`
- `package.json`
- `patches/`
- `postcss.config.mjs`
- `public/`
- `README.md`
- `scripts/`
- `SELFHOSTING.md`
- `src/`
- `tests/`
- `tools/`
- `tsconfig.json`

Типи файлів за вибіркою (1716 файлів, глибина до 3): TypeScript (1556), JSON (37), .png (18), Rust (16), .mjs (15), (без суфікса) (14).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `copy:cesium`, `predev`, `prebuild`, `predemo`, `dev`, `build`, `postbuild`, `start`, `demo`, `lint`, `typecheck`, `typecheck:app`.
- dependencies: `@convex-dev/auth`, `@fontsource/inter`, `@fontsource/jetbrains-mono`, `@fontsource/space-grotesk`, `@mkkellogg/gaussian-splats-3d`, `@react-pdf/renderer`, `@react-three/drei`, `@react-three/fiber`, `@rerun-io/web-viewer`, `@tanstack/react-virtual`, `@types/shpjs`, `@xyflow/react` і ще 30.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

Try it right now at [command.altnautica.com](https://command.altnautica.com). No install needed. Demo mode loads simulated drones with live telemetry, mission planning, and full FC configuration.

Or run locally:

```bash
git clone https://github.com/altnautica/ADOSMissionControl.git
cd ADOSMissionControl
npm install
npm run demo
```

Open [http://localhost:4000](http://localhost:4000). Simulated drones, no hardware required.

---

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/ADOSMissionControl-Open-source-web-based-Ground-Control-Sta/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ADOSMissionControl-Open-source-web-based-Ground-Control-Sta/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/altnautica__ADOSMissionControl.md`.
