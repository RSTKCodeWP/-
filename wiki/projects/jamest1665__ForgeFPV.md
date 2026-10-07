# ForgeFPV

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [jamest1665/ForgeFPV](https://github.com/jamest1665/ForgeFPV) |
| Локальна тека | `fpv-library/repos/ForgeFPV-American-FPV-Tactical-Drone-Trainer-High` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | 2 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

**American FPV Tactical Drone Trainer** — SkyForge Dynamics

High-fidelity FPV drone training simulator built in Godot 4. Rate-mode flight, wind, EW, swarm/hivemind scenarios, multiple battlefields, and an aquatic training module.

_З README.md, без переказу._

## Для чого

American FPV Tactical Drone Trainer - High-fidelity physics reference implementation (Python) and future Godot 4 production prototype for SkyForge Dynamics. Rate-mode FPV with wind, EW, precision engagement training.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Список із розділу features / можливості в README:

- 6DoF Newton-Euler rate-mode flight model
- Wind + turbulence + EW jamming
- Hivemind swarm system (MultiMesh path)
- Multiple maps (Donbas, Urban, Taiwan scaffold, Flood Basin, more)
- Mission / scenario system + scoring + debrief
- Aquatic module (surface USV, hybrid, ROV)
- Full HUD, pause menu, help overlay, path trail

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `docs/`
- `END_TO_END_SETUP.md`
- `export_presets.cfg`
- `forge_fpv_sim_v0_1.py`
- `forge_fpv_sim_v0_2.py`
- `godot_prototype/`
- `MERGE_PLAN.md`
- `PRODUCTION_READY_STATUS.md`
- `project.godot`
- `README-PLAY.md`
- `README.md`
- `scenes/`
- `tools/`

Типи файлів за вибіркою (80 файлів, глибина до 3): .gd (56), Markdown (10), .tscn (6), Python (4), .cfg (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## Супутні документи в теці

- [`docs/AquaticTrainingModule.md`](../../fpv-library/repos/ForgeFPV-American-FPV-Tactical-Drone-Trainer-High/docs/AquaticTrainingModule.md)
- [`docs/BattlefieldCatalog.md`](../../fpv-library/repos/ForgeFPV-American-FPV-Tactical-Drone-Trainer-High/docs/BattlefieldCatalog.md)
- [`docs/RELEASE_BUILD.md`](../../fpv-library/repos/ForgeFPV-American-FPV-Tactical-Drone-Trainer-High/docs/RELEASE_BUILD.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/ForgeFPV-American-FPV-Tactical-Drone-Trainer-High/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/jamest1665__ForgeFPV.md`.
