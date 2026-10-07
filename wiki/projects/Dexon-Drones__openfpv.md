# openfpv

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [Dexon-Drones/openfpv](https://github.com/Dexon-Drones/openfpv) |
| Локальна тека | `fpv-library/repos/openfpv-An-open-transparent-compatibility-engine` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | 3 |
| Оновлено upstream | 2025-09-21 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**An open, transparent compatibility engine for DIY FPV drone parts.**

_З README.md, без переказу._

## Для чого

An open, transparent compatibility engine for DIY FPV drone parts.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: An open, transparent compatibility engine for DIY FPV drone parts.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CHANGELOG.md`
- `cli/`
- `docs/`
- `examples/`
- `LICENSE`
- `openfpv_compat/`
- `pyproject.toml`
- `README.md`
- `workflows/`

Типи файлів за вибіркою (16 файлів, глибина до 3): Python (6), Markdown (4), JSON (2), (без суфікса) (1), TOML (1), YAML (1).


## Що треба

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `openfpv-compat`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quickstart

Try the demo dataset and write one CSV per pair into `./edges_out`:

```bash
openfpv-compat --in examples/parts.min.json --out edges_out --print-summary
```

Create a single merged CSV:

```bash
openfpv-compat -i examples/parts.min.json -o edges.csv --merge
```

Create an Excel workbook (one sheet per pair) with stricter ESC↔motor headroom:

```bash
openfpv-compat -i examples/parts.min.json -o edges.xlsx --headroom 1.3
```

---

## Супутні документи в теці

- [`docs/rules.md`](../../fpv-library/repos/openfpv-An-open-transparent-compatibility-engine/docs/rules.md)
- [`docs/schema.md`](../../fpv-library/repos/openfpv-An-open-transparent-compatibility-engine/docs/schema.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/openfpv-An-open-transparent-compatibility-engine/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/Dexon-Drones__openfpv.md`.
