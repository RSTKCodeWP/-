# Блок 03 — FPV-ПЕРЕХВАТЧИК

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [karim012901/FPV_AI_FUTURE](https://github.com/karim012901/FPV_AI_FUTURE) |
| Локальна тека | `fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-07-23 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

> ## 📍 Начинать с [`docs/CHECKPOINT.md`](docs/CHECKPOINT.md) > > Это **единый источник правды**: что система умеет и чем это доказано, что НЕ умеет, открытые > дефекты и отозванные заявления. Остальные документы — снимки того, во что мы верили на их дату; > при расхождении побеждает CHECKPOINT. > > Гейт (~1:41): `PYTHONPATH=.:fpv python3 -m pytest fpv/ -q -m "not slow"`

> Собственный FPV-дрон. Мгновенный авто-старт ТОЛЬКО по подтверждению оператора. > Три задачи миссии: разведка -> установление контакта -> кинетическое поражение > подтверждённой неотвечающей угрозы.

Этот блок начался в форке `гоночная фпв на ии` (пакет `fpv_ai`). Принцип владельца: «брать лучшее отовсюду». Здесь собрано лучшее: реальный движок управления полётом, движок захвата/перезахвата цели, экран запуска для оператора и ядро безопасности.

_З README.md, без переказу._

## Для чого

The project is intended for enthusiasts who are interested in the fact that FPV could do something that it could not do before (The project is exclusively for peaceful purposes and is not intended for real use)

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: The project is intended for enthusiasts who are interested in the fact that FPV could do something that it could not do before (The project is exclusively for peaceful purposes and is not intended for real use)

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `__init__.py`
- `aimpoint.py`
- `bench/`
- `betaflight_link/`
- `blob.py`
- `BRINGUP.md`
- `BRINGUP_ZYNQMINI_BOCHEN.md`
- `classify/`
- `closing_target_sim.py`
- `CODE_REVIEW_BUNDLE.md`
- `conftest.py`
- `console/`
- `contracts/`
- `control/`
- `correlation.py`
- `datasets/`
- `demo/`
- `derotate.py`
- `detect.py`
- `docs/`
- `egomotion.py`
- `evaluation/`
- `event_channel.py`
- `evidence/`

Типи файлів за вибіркою (413 файлів, глибина до 3): Python (275), Markdown (44), .mp4 (22), .v (18), .bin (16), JSON (14).


## Що треба

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `fpv-interceptor`.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## Супутні документи в теці

- [`docs/AUDIT_2026-06-25_MATH_PHYSICS_SYSTEMS.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/AUDIT_2026-06-25_MATH_PHYSICS_SYSTEMS.md)
- [`docs/BENCH_BRINGUP_SEQUENCE.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/BENCH_BRINGUP_SEQUENCE.md)
- [`docs/BLOCK03_MASTER_PLAN.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/BLOCK03_MASTER_PLAN.md)
- [`docs/BLOCK03_MATURE_GSN_DOCTRINE.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/BLOCK03_MATURE_GSN_DOCTRINE.md)
- [`docs/BLOCK03_THERMAL_INTERCEPTOR_DESIGN.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/BLOCK03_THERMAL_INTERCEPTOR_DESIGN.md)
- [`docs/BODY_AND_VV_BRIEFING.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/BODY_AND_VV_BRIEFING.md)
- [`docs/CHECKPOINT.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/CHECKPOINT.md)
- [`docs/FIELD_TRIAL_READINESS_2026-07-21.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/FIELD_TRIAL_READINESS_2026-07-21.md)
- [`docs/FIRE_AND_FORGET_AUTONOMY_BRIEFING.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/FIRE_AND_FORGET_AUTONOMY_BRIEFING.md)
- [`docs/FLASH_AND_BRINGUP.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/FLASH_AND_BRINGUP.md)
- [`docs/FLIGHT_TEST_OVERRIDE.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/FLIGHT_TEST_OVERRIDE.md)
- [`docs/FPGA_MIGRATION_ZYNQ7020_FT640LM.md`](../../fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/docs/FPGA_MIGRATION_ZYNQ7020_FT640LM.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/FPV_AI_FUTURE-The-project-is-intended-for-enthusiasts/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/karim012901__FPV_AI_FUTURE.md`.
