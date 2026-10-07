# ardupilot-mcp

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rmeadomavic/ardupilot-mcp](https://github.com/rmeadomavic/ardupilot-mcp) |
| Локальна тека | `fpv-library/repos/ardupilot-mcp-MCP-server-for-talking-to-ArduPilot-vehi` |
| У бібліотеці | keep |
| Категорії каталогу | `gcs`, `fc`, `tools` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-07-20 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

An [MCP](https://modelcontextprotocol.io) server that lets an AI agent talk to an ArduPilot vehicle over MAVLink. Read state, inspect and change parameters, switch modes, read prearm failures, and (gated) arm or disarm. SITL-first.

Install: `pipx install ardupilot-mavlink-mcp`

`mcp-name: io.github.rmeadomavic/ardupilot-mavlink-mcp`

> [!WARNING] > **This tool can ARM and command a real aircraft.** A bad command can spin props or fly a vehicle away. Defaults are built to stop that: actuation is OFF unless you pass `--enable-actuation`, and even then it refuses a real (non-loopback) link unless you also pass `--allow-real-vehicle`. Develop against SITL. On hardware, bench-test with **props off** first. No warranty — you own the outcome.

_З README.md, без переказу._

## Для чого

MCP server for talking to ArduPilot vehicles over MAVLink. SITL-first, safety-gated.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Розробник польотного контролера — у тексті є «ardupilot».
- Інженер радіолінка — у тексті є «mavlink».


Теми GitHub: `ardupilot`, `claude`, `drone`, `gcs`, `mavlink`, `mcp`, `model-context-protocol`, `pymavlink`, `sitl`, `uav`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: MCP server for talking to ArduPilot vehicles over MAVLink. SITL-first, safety-gated.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `LICENSE`
- `pyproject.toml`
- `README.md`
- `ROADMAP.md`
- `scripts/`
- `SECURITY.md`
- `server.json`
- `src/`
- `tests/`

Типи файлів за вибіркою (28 файлів, глибина до 3): Python (15), Markdown (5), (без суфікса) (3), JSON (2), YAML (1), TOML (1).

Фрагмент README про будову:

### Architecture

```
  agent (MCP client)                    ardupilot-mcp                     vehicle
 ┌──────────────────┐   JSON-RPC    ┌──────────────────────┐   MAVLink   ┌──────────┐
 │ Claude / etc.    │ ───stdio────▶ │  FastMCP tools       │ ──udp/tcp/  │ ArduPilot│
 │                  │ ◀───────────  │   │                  │   serial──▶ │  (SITL   │
 └──────────────────┘               │   ▼                  │ ◀────────── │  or FC)  │
                                    │  recv thread (1 reader)            └──────────┘
                                    │   ├─▶ message cache (latest/type)
                                    │   ├─▶ param store (request/collect)
                                    │   └─▶ COMMAND_ACK + STATUSTEXT
                                    └──────────────────────┘
```

MAVLink is an async stream; MCP tools are synchronous. One background thread owns the link and is the only reader — it caches the latest message of each type and routes `PARAM_VALUE` into a param store. Tool calls read from those caches (params block until the data arrives). No two threads ever call `recv_match`.

## Що треба

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `ardupilot-mavlink-mcp`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick start (SITL)

You need an ArduPilot SITL instance. From an `ardupilot` checkout:

```bash
# starts ArduCopter SITL; serves MAVLink on tcp:127.0.0.1:5760
sim_vehicle.py -v ArduCopter --console
```

Install and run the server (read-only by default):

```bash
pipx install ardupilot-mavlink-mcp          # or: uv tool install ardupilot-mavlink-mcp
ardupilot-mavlink-mcp --connect tcp:127.0.0.1:5760
```

To allow parameter writes, mode changes, and arm/disarm against SITL, add `--enable-actuation`.

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/ardupilot-mcp-MCP-server-for-talking-to-ArduPilot-vehi/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ardupilot-mcp-MCP-server-for-talking-to-ArduPilot-vehi/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rmeadomavic__ardupilot-mcp.md`.
