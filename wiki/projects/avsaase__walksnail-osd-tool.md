# avsaase/walksnail-osd-tool

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [avsaase/walksnail-osd-tool](https://github.com/avsaase/walksnail-osd-tool) |
| Локальна тека | `fpv-library/repos/walksnail-osd-tool-Cross-platform-tool-for-rendering-the-fl` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `fc` |
| Зірки (каталог) | 146 |
| Оновлено upstream | 2026-03-02 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

Cross-platform tool for rendering the flight controller OSD and SRT data from the Walksnail Avatar HD FPV system on top of the goggle or VRX recording.

_З README.md, без переказу._

## Для чого

Cross-platform tool for rendering the flight controller OSD and SRT data from the Walksnail Avatar HD FPV system on top of the goggle or VRX recording

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «vrx».
- Розробник польотного контролера — у тексті є «flight controller».
- Розробник відеотракту — у тексті є «h.264».


Теми GitHub: `fpv`, `video`, `walksnail`.

## Функція

Список із розділу features / можливості в README:

- Easy to use graphical user interface.
- Native installer for Windows, App bundle for MacOS.
- Hardware-accelerated encoding powered by ffmpeg.
- Choose between H.264 and H.265 codecs (more can be added later).
- View basic information about the video, OSD, SRT and font files.
- Preview OSD frames before rendering.
- Automatically center the OSD or position it manually.
- Render selected info from the SRT file.
- Selectable output video bitrate (more encoder settings will be added later).
- Upscale output video to 1440p for higher quality when uploading to YouTube.
- Mask OSD items ([demo](https://imgur.com/u8xi2tX)).

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `_deploy/`
- `backend/`
- `Cargo.lock`
- `Cargo.toml`
- `CHANGELOG.md`
- `ext/`
- `LICENSE.md`
- `README.md`
- `resources/`
- `rustfmt.toml`
- `ui/`

Типи файлів за вибіркою (75 файлів, глибина до 3): Rust (41), .png (10), TOML (4), .zip (4), Markdown (3), .ttf (3).


## Що треба

- Маніфести збірки: Rust (Cargo.toml).

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/walksnail-osd-tool-Cross-platform-tool-for-rendering-the-fl/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/avsaase__walksnail-osd-tool.md`.
