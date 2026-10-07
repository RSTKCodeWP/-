# 🎯 RunCam Divinus — FPV Streamer for RunCam WiFiLink 2

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RastaDevX/runcam-divinus](https://github.com/RastaDevX/runcam-divinus) |
| Локальна тека | `fpv-library/repos/runcam-divinus-Divinus-streamer-for-RunCam-WiFiLink-2-S` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-04-14 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

> **Maximum video quality at ≤700 KB/s** on SSC338Q (Sigmastar Infinity6E)

_З README.md, без переказу._

## Для чого

Divinus streamer for RunCam WiFiLink 2 (SSC338Q) — optimized FPV encoding

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Divinus streamer for RunCam WiFiLink 2 (SSC338Q) — optimized FPV encoding

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `build.sh`
- `Dockerfile`
- `docs/`
- `LICENSE`
- `official FW/`
- `patches/`
- `README.md`
- `sdcard/`
- `src/`

Типи файлів за вибіркою (23 файлів, глибина до 3): (без суфікса) (5), shell (5), Markdown (4), .ini (2), C (2), .patch (2).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 1. Build Divinus

```bash
git clone https://github.com/OpenIPC/divinus.git
cd divinus
./build.sh star6e
# Output: ./divinus (~300KB ARM binary)
```

## Супутні документи в теці

- [`docs/ENCODING-THEORY.md`](../../fpv-library/repos/runcam-divinus-Divinus-streamer-for-RunCam-WiFiLink-2-S/docs/ENCODING-THEORY.md)
- [`docs/INSTALL.md`](../../fpv-library/repos/runcam-divinus-Divinus-streamer-for-RunCam-WiFiLink-2-S/docs/INSTALL.md)
- [`docs/TROUBLESHOOTING.md`](../../fpv-library/repos/runcam-divinus-Divinus-streamer-for-RunCam-WiFiLink-2-S/docs/TROUBLESHOOTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/runcam-divinus-Divinus-streamer-for-RunCam-WiFiLink-2-S/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RastaDevX__runcam-divinus.md`.
