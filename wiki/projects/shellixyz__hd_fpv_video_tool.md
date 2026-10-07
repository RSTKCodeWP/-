# HD FPV video tool

> Картка виставки. Зал: [Окуляри і VRX](../halls/goggles.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [shellixyz/hd_fpv_video_tool](https://github.com/shellixyz/hd_fpv_video_tool) |
| Локальна тека | `fpv-library/repos/hd_fpv_video_tool-A-software-tool-to-manipulate-video-file` |
| У бібліотеці | keep |
| Категорії каталогу | `osd`, `goggles` |
| Зірки (каталог) | 23 |
| Оновлено upstream | 2026-02-23 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

A software tool to manipulate video files and OSD files recoded with the DJI and Walksnail Avatar FPV systems

_З поля description у catalog.json. Окремого вступу в README немає._

## Для чого

A software tool to manipulate video files and OSD files recoded with the DJI and Walksnail Avatar FPV systems

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «osd».


Теми GitHub: `avatar`, `dji`, `fpv`, `walksnail`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: A software tool to manipulate video files and OSD files recoded with the DJI and Walksnail Avatar FPV systems

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `appimage_builder/`
- `Cargo.lock`
- `Cargo.toml`
- `Dockerfile`
- `git/`
- `hd_fpv_video_tool.code-workspace`
- `Justfile`
- `LICENSE`
- `man_pages/`
- `podman_build`
- `README.md`
- `rustfmt.toml`
- `shell.nix`
- `shell_completions/`
- `src/`

Типи файлів за вибіркою (84 файлів, глибина до 3): Rust (49), .1 (10), (без суфікса) (8), TOML (4), .lock (2), .nix (2).


## Що треба

- Маніфести збірки: Rust (Cargo.toml).
- Cargo package: `hd_fpv_video_tool`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Example usage

For these examples we are assuming that:

* You have installed the fonts in the default directory so that they will be found automatically
* These files are present in the current directory:
  * DJIG0000.osd (the OSD file recorded by your goggles hacked with FPV.WTF)
  * DJIG0000.mp4 (video recorded by your goggles)
  * DJIU0000.mp4 (video recorded by your air unit if it has the capability)

#### Transcoding a video and burning the OSD onto it

`hd_fpv_video_tool transcode-video --osd DJIG0000.mp4`

Will automatically use the `DJIG0000.osd` file in the same directory as the video and automatically select a name for the output file: `DJIG0000_transcoded.mp4`. The OSD file can automatically be found if it is named with the same `DJIGXXXX` prefix as the video file or with the same name but with `.osd` extension. You can also specify the OSD file to use and the output file name manually. The default encoder is `libx265` so the output is encoded with the H.265 codec but the video encoder used can be selected with the `--video-encoder` option. The above command is equivalent to:

`hd_fpv_video_tool transcode-video --osd-file DJIG0000.osd DJIG0000.mp4 DJIG0000_transcoded.mp4`

If you want to burn the OSD onto a video coming from a DJI FPV air unit with audio you can do so while also fixing the audio synchronization and volume using this command:

`hd_fpv_video_tool transcode-video --fix-audio --osd DJIU0000.mp4`

Run `hd_fpv_video_tool transcode-video --help` or `hd_fpv_video_tool help transcode-video` for a list of all the options available for this command.

#### Generating a transparent OSD overlay video and playing an unmodified video with OSD

First we need to generate the transparent OSD overlay video:

`hd_fpv_video_tool generate-overlay-video --target-video-file DJIG0000.mp4 DJIG0000.osd`

This command will encode a transparent OSD overlay video encoded with the VP8 codec by default and write it into the `DJIG0000_osd.webm` file. The original video `DJIG0000.mp4` will not be modified. It is only used to choose the right resolution and OSD scaling for the output video. We can then use the `play-video-with-osd` command to play the `DJIG0000.mp4` file with overlayed OSD:

`hd_fpv_video_tool play-video-with-osd DJIG0000.mp4`

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/hd_fpv_video_tool-A-software-tool-to-manipulate-video-file/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/shellixyz__hd_fpv_video_tool.md`.
