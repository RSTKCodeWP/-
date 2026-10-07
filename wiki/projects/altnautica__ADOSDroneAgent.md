# ADOS Drone Agent

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

Каталог тримає категорію `other`. Зал «Наземні станції» поставлено, бо в назві, описі або шляху є «ground station».

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [altnautica/ADOSDroneAgent](https://github.com/altnautica/ADOSDroneAgent) |
| Локальна тека | `fpv-library/repos/ADOSDroneAgent-ADOS-Drone-Agent-Software-defined-drone` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 20 |
| Оновлено upstream | 2026-08-01 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

**Open-source onboard agent for software-defined drones. Long-range data link. HD video. Full remote control.**

ADOS Drone Agent is the onboard software for a software-defined drone. It runs on the companion computer next to your flight controller, reads MAVLink off the FC and routes it to any ground station, streams HD video over radio or the internet, and lets you fly and manage the aircraft from a browser. The flight-critical paths are native Rust. AI, vision, and plugins run in Python.

> **Part of the ADOS ecosystem.** Pairs with [ADOS Mission Control](https://github.com/altnautica/ADOSMissionControl) (the browser ground station) for mission planning, 3D simulation, AI PID tuning, and gamepad flight control. The agent runs on the drone; Mission Control runs in your browser. Extend either side with [ADOS Extensions](https://github.com/altnautica/ADOSExtensions), the first-party plug…

_З README.md, без переказу._

## Для чого

ADOS Drone Agent — Software-defined drone network agent. Install on any companion computer to make your drone smart, autonomous, and fleet-ready.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground station».
- Розробник польотного контролера — у тексті є «flight controller».
- Інженер радіолінка — у тексті є «mavlink».


## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: ADOS Drone Agent — Software-defined drone network agent. Install on any companion computer to make your drone smart, autonomous, and fleet-ready.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `CHANGELOG.md`
- `cockpit/`
- `CONTRIBUTING.md`
- `crates/`
- `dashboard/`
- `data/`
- `docs/`
- `etc/`
- `LICENSE`
- `pyproject.toml`
- `README.md`
- `RELEASE.md`
- `schemas/`
- `scripts/`
- `src/`
- `tests/`
- `tools/`
- `uv.lock`

Типи файлів за вибіркою (1123 файлів, глибина до 3): Rust (418), Python (353), TypeScript (126), .service (46), TOML (36), Markdown (32).

Фрагмент README про будову:

### Architecture at a glance

`ados-control`, a native Rust HTTP front, owns port `:8080`. It serves the control, telemetry, pairing, parameter, fleet, and ground-station routes natively, and reverse-proxies a small Python feature service on an internal socket for the parts that stay in Python: AI and vision inference, the plugin runtime, the setup webapp, and WHEP video.

```
              ┌────────────────────────────────────┐
   CLI  ────▶ │  HTTP control surface  ·  :8080     │ ◀──── Mission Control / HTTP clients
              │  ados-control (native Rust front)   │
              └───────────────┬────────────────────┘
                              │ proxies the Python feature
                              │ service on an internal socket
   ┌──────────────────────────┴────────────────────────────────┐
   │              Rust core services (systemd units)             │
   │   supervisor · MAVLink router · video · cloud relay ·       │
   │   WFB-ng radio · vision · ground-station receive / uplink   │
   └────┬───────────────────┬────────────────────┬──────────────┘
        ▼                   ▼                     ▼
  flight controller   RTL8812EU + wfb (C)    camera / NPU
  (serial / USB)      ffmpeg · mediamtx       (Python + C)

  Python feature service: AI + vision inference · plugin runtime ·
                          setup webapp · WHEP video
```

On a device the agent installs as a set of systemd services plus a Python virtualenv, both placed by the prebuilt Rust installer. Routes read FC status, telemetry, video, radio, and parameter state through named accessors, so the control surface stays independent of service internals.

---

## Що треба

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| OS | Linux with systemd (ARM64 or x86_64) | Raspberry Pi OS, Debian, Ubuntu, Armbian |
| RAM | 1 GB | 2 GB+ |
| Storage | 500 MB | 2 GB+ |
| Python | 3.11+ | 3.12 |
| FC connection | Serial (UART or USB) | UART at 921600 baud |

Also runs on macOS for local development (the installer points you to `cargo` there). Boards with less than 1 GB of RAM are not supported by the standard profile.

---

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `ados-drone-agent`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

Deploy to a companion computer (Raspberry Pi, Radxa, Jetson, and similar ARM64 Linux boards):

```bash
curl -sSL https://raw.githubusercontent.com/altnautica/ADOSDroneAgent/main/scripts/install.sh | sudo bash
```

Root is required. The one-line bootstrap fetches and verifies a prebuilt Rust installer, which places the native Rust service binaries, provisions a Python virtualenv for the feature services, configures the systemd units, and starts the setup webapp on the device.

After install, SSH into the node and run:

```bash
ados
```

The terminal status page shows the local setup URL, LAN or hotspot URLs, MAVLink state, video state, services, and remote-access state.

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/ADOSDroneAgent-ADOS-Drone-Agent-Software-defined-drone/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ADOSDroneAgent-ADOS-Drone-Agent-Software-defined-drone/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/altnautica__ADOSDroneAgent.md`.
