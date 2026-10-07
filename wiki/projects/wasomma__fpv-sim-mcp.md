# fpv-sim-mcp

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [wasomma/fpv-sim-mcp](https://github.com/wasomma/fpv-sim-mcp) |
| Локальна тека | `fpv-library/repos/fpv-sim-mcp-MCP-server-exposing-the-fpv-sim-force-on` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-07-23 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

An [MCP](https://modelcontextprotocol.io) server that exposes [fpv-sim](https://github.com/wasomma/fpv-sim) — a deterministic force-on-force simulation of FPV sUAS vs counter-UAS RF direction finding — as tools an AI agent can call.

All data is **notional**. The area of operations ("AO KATANA"), unit positions, sensor parameters, and outcomes are invented for demonstration purposes. Unclassified throughout.

_З README.md, без переказу._

## Для чого

MCP server exposing the fpv-sim force-on-force sUAS/cUAS simulation as agent-callable tools. Notional data only.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: MCP server exposing the fpv-sim force-on-force sUAS/cUAS simulation as agent-callable tools. Notional data only.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CHANGELOG.md`
- `CLAUDE.md`
- `deploy/`
- `DESIGN_NOTES.md`
- `docs/`
- `examples/`
- `LICENSE.md`
- `package-lock.json`
- `package.json`
- `README.md`
- `scripts/`
- `src/`
- `test/`
- `tsconfig.json`

Типи файлів за вибіркою (41 файлів, глибина до 3): TypeScript (24), Markdown (8), JSON (5), (без суфікса) (2), .service (1), .mjs (1).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `build`, `test`, `demo`, `goldens`, `start`, `start:http`.
- dependencies: `@modelcontextprotocol/sdk`, `zod`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick start

Requires Node 20+.

```sh
git clone https://github.com/wasomma/fpv-sim-mcp.git
cd fpv-sim-mcp
npm install
npm test        # builds and proves browser-parity + unit tests (17 tests)
npm run demo    # exercises the server through a real MCP stdio client
```
### Remote (no local install)

The server also ships a **Streamable HTTP** entry point
(`dist/src/server/http.js`) for hosting on any box with Node 20+ —
[deploy/DEPLOY.md](../../fpv-library/repos/fpv-sim-mcp-MCP-server-exposing-the-fpv-sim-force-on/deploy/DEPLOY.md) is a complete VPS runbook (systemd,
Caddy TLS, bearer-token auth).

A hosted demo instance runs at `https://wasomma-fpv.duckdns.org/mcp`
(health probe at [/healthz](https://wasomma-fpv.duckdns.org/healthz)). It is
bearer-token protected — it exposes CPU, not secrets, but an open sim
endpoint invites abuse. If you'd like to try it without building anything,
ask me for a token ([GitHub](https://github.com/wasomma) /
[LinkedIn](https://www.linkedin.com/in/wesleyfine/)), then:

```sh
claude mcp add --transport http fpv-sim https://wasomma-fpv.duckdns.org/mcp \
  --header "Authorization: Bearer <token>"
```

Determinism makes the hosted instance verifiable: `run_engagement(20260719)`
returns the same BLUFOR victory at T+311.1s from the cloud that the local
build produces — same seed, same engagement, any machine.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/fpv-sim-mcp-MCP-server-exposing-the-fpv-sim-force-on/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/wasomma__fpv-sim-mcp.md`.
