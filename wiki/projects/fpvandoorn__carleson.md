# Formalization of a generalized Carleson's theorem

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpvandoorn/carleson](https://github.com/fpvandoorn/carleson) |
| Локальна тека | `fpv-library/repos/carleson-A-formalized-proof-of-Carleson-s-theorem` |
| У бібліотеці | skip |
| Категорії каталогу | `other` |
| Зірки (каталог) | 101 |
| Оновлено upstream | 2026-07-25 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-2.0 |

## Ідея

A formalized proof of a generalized Carleson's theorem in the [Lean interactive theorem prover](https://lean-lang.org/).

_З README.md, без переказу._

## Для чого

A formalized proof of Carleson's theorem in Lean

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

Теми GitHub: `lean4`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: A formalized proof of Carleson's theorem in Lean

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `blueprint/`
- `Carleson/`
- `Carleson.lean`
- `Challenge.lean`
- `CODE_OF_CONDUCT.md`
- `comparator_config.json`
- `CONTRIBUTING.md`
- `docs/`
- `lake-manifest.json`
- `lakefile.toml`
- `lean-toolchain`
- `LICENSE`
- `paper/`
- `README.md`
- `review_checklist.md`
- `scripts/`
- `Solution.lean`
- `tasks.py`

Типи файлів за вибіркою (127 файлів, глибина до 3): .lean (84), (без суфікса) (8), .tex (8), Markdown (6), JSON (4), HTML (3).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Build the blueprint

To test the Blueprint locally, you can compile `print.tex` using XeLaTeX (i.e. `xelatex print.tex` in the folder `blueprint/src`). If you have the Python package `invoke` you can also run `inv bp` which puts the output in `blueprint/print/print.pdf`.
If you want to build the web version of the blueprint locally, you need to install some packages by following the instructions [here](https://pypi.org/project/leanblueprint/). But if the pdf builds locally, you can also just make a pull request and use the online blueprint.

## Супутні документи в теці

- [`docs/index.md`](../../fpv-library/repos/carleson-A-formalized-proof-of-Carleson-s-theorem/docs/index.md)
- [`docs/upstreaming.md`](../../fpv-library/repos/carleson-A-formalized-proof-of-Carleson-s-theorem/docs/upstreaming.md)
- [`CONTRIBUTING.md`](../../fpv-library/repos/carleson-A-formalized-proof-of-Carleson-s-theorem/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/carleson-A-formalized-proof-of-Carleson-s-theorem/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpvandoorn__carleson.md`.
