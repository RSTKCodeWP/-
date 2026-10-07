# svpcom/wfb-ng-osd

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [svpcom/wfb-ng-osd](https://github.com/svpcom/wfb-ng-osd) |
| Локальна тека | `fpv-library/repos/wfb-ng-osd-Mavlink-OSD-and-video-player-for-wfb-ng` |
| У бібліотеці | keep |
| Категорії каталогу | `link`, `osd` |
| Зірки (каталог) | 107 |
| Оновлено upstream | 2025-08-23 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This project started from https://github.com/TobiasBales/PlayuavOSD.git

Supported platforms: -------------------

Supported autopilots: ---------------------

Building: ---------

1. Build for Linux (X11 or Wayland) (native build):

2. Build for Raspberry PI 0-3 (OpenVG) (native build):

3. Build for Radxa or OrangePi (libdrm) (native build):

Running: --------

Default mavlink port is UDP 14551. Default RTP video port is UDP 5600.

Screenshots: ------------

Wiki: [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/svpcom/wfb-ng-osd) ------------

_З README.md, без переказу._

## Для чого

Mavlink OSD and video player for wfb-ng

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».
- Інженер радіолінка — у тексті є «wfb-ng».
- Розробник відеотракту — у тексті є «gstreamer».


Теми GitHub: `fpv`, `gstreamer`, `osd`, `raspberry-pi`, `video`, `x11`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Mavlink OSD and video player for wfb-ng

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `appsrc.c`
- `docker/`
- `drm_output.c`
- `eglstate.h`
- `font12x18.h`
- `font8x10.h`
- `font_outlined8x14.c`
- `font_outlined8x14.h`
- `font_outlined8x8.c`
- `font_outlined8x8.h`
- `fonts.c`
- `fonts.h`
- `fpv_video/`
- `graphengine.c`
- `graphengine.h`
- `gst-compat.c`
- `LICENSE`
- `m2dlib.c`
- `m2dlib.h`
- `main.c`
- `Makefile`
- `math3d.c`
- `math3d.h`
- `oglinit.c`

Типи файлів за вибіркою (50 файлів, глибина до 3): C (32), (без суфікса) (6), shell (3), Python (2), .png (2), Markdown (1).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/wfb-ng-osd-Mavlink-OSD-and-video-player-for-wfb-ng/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/svpcom__wfb-ng-osd.md`.
