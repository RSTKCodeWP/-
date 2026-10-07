# Run and deploy your AI Studio app

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [hazarvolga/fpv-test](https://github.com/hazarvolga/fpv-test) |
| Локальна тека | `fpv-library/repos/fpv-test` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-05-29 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/e3807f1f-f853-47af-b881-817fe0b25b36

_З README.md, без переказу._

## Для чого

test

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: test

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `index.html`
- `metadata.json`
- `package.json`
- `README.md`
- `src/`
- `tsconfig.json`
- `vite.config.ts`

Типи файлів за вибіркою (23 файлів, глибина до 3): TypeScript (12), JSON (4), .png (2), .example (1), Markdown (1), HTML (1).


## Що треба

- Маніфести збірки: Node.js (package.json).
- npm-скрипти в package.json: `dev`, `build`, `preview`, `clean`, `lint`.
- dependencies: `@google/genai`, `@tailwindcss/vite`, `@vitejs/plugin-react`, `lucide-react`, `react`, `react-dom`, `vite`, `express`, `dotenv`, `motion`.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/fpv-test/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/hazarvolga__fpv-test.md`.
