# ejo_wfb_stabilizer.py

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [ejowerks/wfb-stabilizer](https://github.com/ejowerks/wfb-stabilizer) |
| Локальна тека | `fpv-library/repos/wfb-stabilizer-Scripts-to-stabilize-video-stream-from-w` |
| У бібліотеці | keep |
| Категорії каталогу | `link` |
| Зірки (каталог) | 40 |
| Оновлено upstream | 2023-04-09 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

Demo: https://youtu.be/lo-eb6zSxgQ

A simple rough proof-of-concept starter script to stabilize video stream with low latency from wifibroadcast FPV (or any streaming source). Works out of the box sufficiently well with 720p and lower digital FPV video streams. This is not meant to be a cinema quality stabilizer: It is tool to make a jittery/bumpy FPV feed tolerable while adding the least possible amount of latency to the stream.

About: I put this together because I could not find any simple open-source ultra low latency software stabilization for FPV. Most video stabilization solutions are designed for post-processing video files, and the fastest live-streaming stabilizers that I could find added hundreds of milliseconds latency at best which is not suitable for FPV. I observed that the common solution to reduce processing time is to downsample the frames, run the point-feature matchin…

_З README.md, без переказу._

## Для чого

Scripts to stabilize video stream from wifibroadcast for FPV

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Scripts to stabilize video stream from wifibroadcast for FPV

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `ejo_wfb_stabilizer.py`
- `README.md`
- `UnstabilizedTest10sec.mp4`

Типи файлів за вибіркою (4 файлів, глибина до 3): Python (1), .mp4 (1), Markdown (1), JSON (1).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/wfb-stabilizer-Scripts-to-stabilize-video-stream-from-w/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/ejowerks__wfb-stabilizer.md`.
