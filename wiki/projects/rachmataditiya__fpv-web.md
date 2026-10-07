# FPV Web

> Картка виставки. Зал: [Інструменти](../halls/tools.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [rachmataditiya/fpv-web](https://github.com/rachmataditiya/fpv-web) |
| Локальна тека | `fpv-library/repos/fpv-web-Browser-FPV-drone-racing-simulator-real` |
| У бібліотеці | keep |
| Категорії каталогу | `tools` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**▶ Play it now: [simulator.arkana.app](https://simulator.arkana.app)** — fly with keyboard, gamepad, or a real DJI FPV RC 3 over USB. Race the built-in tracks, free-fly the cinematic valley, or upload a classic Counter-Strike 1.6 map and shoot barrels in it.

FPV Web is a browser-based FPV drone racing simulator running entirely in-browser (Chromium desktop) without a backend. Its key differentiator is native DJI FPV RC 3 support via WebHID (Gamepad API cannot see it) and a full calibration wizard (hardware calibration + per-axis mappings). It renders with Three.js and uses a hand-rolled 240 Hz rigid-body flight model in acro/rate mode.

_З README.md, без переказу._

## Для чого

Browser FPV drone racing simulator — real DJI RC over WebHID, 240Hz physics, CS 1.6 BSP maps, track editor, drone combat. Three.js + TypeScript, no backend.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Browser FPV drone racing simulator — real DJI RC over WebHID, 240Hz physics, CS 1.6 BSP maps, track editor, drone combat. Three.js + TypeScript, no backend.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CLAUDE.md`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `deploy/`
- `DJI-RC-WEBHID.md`
- `docs/`
- `gamepad.js`
- `index.html`
- `LICENSE`
- `package-lock.json`
- `package.json`
- `public/`
- `README.md`
- `src/`
- `tsconfig.json`
- `vite.config.ts`

Типи файлів за вибіркою (114 файлів, глибина до 3): TypeScript (85), Markdown (9), JSON (4), .png (4), (без суфікса) (2), .hdr (2).

Фрагмент README про будову:

### Architecture

```
src/
  input/          hidSource.ts (WebHID), profiles.ts (calibration), 
                  gamepad.ts, keyboard.ts
  physics/        loop.ts (fixed-timestep 240 Hz), params.ts (tuning)
  world/          race mode, gates, checkpoint/lap timing
  render/         Three.js scene, camera rig, interpolation
  ui/             ControllerPanel (calibration wizard), HUD
```

The core loop (`loop.ts`) runs a fixed-timestep physics tick at `PHYS_DT` (1/240 s) followed by rendering with linear interpolation of the current transform state. For deterministic testing without RAF, use:

```js
window.__fpv.step(n)  // advance n physics frames manually
```

## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `dev`, `build`, `preview`, `test`, `typecheck`.
- dependencies: `simplex-noise`, `three`, `three-mesh-bvh`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

```bash
npm install
npm run dev       # Vite dev server (http://localhost:5173)
npm test          # Vitest runner
npm run build     # production build (tsc --noEmit && vite build)
```

To test DJI input without hardware, open the dev server with `?mockhid=1` appended to the URL — a mock HID source fakes the 13-byte report.

## Супутні документи в теці

- [`docs/GDLC.md`](../../fpv-library/repos/fpv-web-Browser-FPV-drone-racing-simulator-real/docs/GDLC.md)
- [`docs/asset-research.md`](../../fpv-library/repos/fpv-web-Browser-FPV-drone-racing-simulator-real/docs/asset-research.md)
- [`CONTRIBUTING.md`](../../fpv-library/repos/fpv-web-Browser-FPV-drone-racing-simulator-real/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/fpv-web-Browser-FPV-drone-racing-simulator-real/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/rachmataditiya__fpv-web.md`.
