# HDZero Converter

A small native macOS app (SwiftUI) that wraps **ffmpeg** to convert HDZero / FPV
goggle recordings into a format every device can play.

HDZero footage is stored as **full-range `yuvj420p` H.264** with odd framerate and
high level. VLC plays it, but Apple decoders mis-read the color range → **QuickTime
shows black, iPhone shows washed-out white**. This app fixes that and re-wraps the
file for broad compatibility.

## Build / run

```bash
./build_app.sh          # compiles + embeds ffmpeg + bundles "HDZero Converter.app"
open "HDZero Converter.app"
```

Then drag `HDZero Converter.app` anywhere (e.g. `/Applications`) — or copy it to
another Mac. **It is fully portable: ffmpeg + ffprobe and all their dynamic
libraries are embedded inside the bundle** (`Contents/Resources/ffmpeg/`, paths
rewritten to `@executable_path` via `dylibbundler`). No Homebrew or ffmpeg install
is required on the target machine. The green “ffmpeg embedded” badge in the header
confirms it's running the bundled copy.

Build-time only requirements (on *your* dev Mac): Xcode toolchain, a Homebrew
`ffmpeg`, and `dylibbundler` (`brew install dylibbundler`).

## What each field does

| Field | What it does |
|---|---|
| **Input** | Source video (drag-and-drop or Choose). Duration is read to drive the progress bar. |
| **Output** | Destination `.mp4`. Defaults to `<name>_compatible.mp4` next to the input. |
| **Fix color range (HDZero)** | **The key fix.** Converts full-range `yuvj420p` → limited-range `yuv420p` with BT.709 tags. Leave ON. |
| **Frame rate** | HDZero's ~90fps variable timebase trips up some players. `60` is the safe universal choice. |
| **Resolution** | Keep native or downscale (aspect preserved). |
| **Encoder** | `x264` = best quality + reliable color (recommended). `VideoToolbox` = much faster (hardware), larger files. |
| **Quality (CRF)** | x264 only. Lower = better/bigger. 18 ≈ lossless, 20–23 balanced, 28+ soft. Default 20. |
| **Bitrate** | VideoToolbox only. Target average Mbps. 15–25 is plenty for 720p. |
| **Encoding speed** | x264 preset. `medium` is the sweet spot; faster = quicker, slightly bigger. |
| **H.264 profile** | `high` = best, supported everywhere modern. `main`/`baseline` for old hardware. |
| **Level** | Caps res/fps/bitrate for constrained decoders. Source's `5.1` is what chokes players; `4.2` is widely safe. |
| **Audio** | `Re-encode AAC` (safe) / `Copy` (fast, untouched) / `Remove`. |
| **Audio bitrate** | AAC quality. 192 kbps is transparent for most content. |
| **Fast start** | Moves the index to the front so it streams / previews instantly. Leave ON. |
| **Advanced → tool paths** | Override `ffmpeg`/`ffprobe` locations if needed. |

## Default recipe (matches the validated conversion)

```
ffmpeg -y -i INPUT \
  -vf "scale=in_range=full:out_range=tv,format=yuv420p,fps=60" \
  -c:v libx264 -preset medium -crf 20 -profile:v high -level 4.2 -pix_fmt yuv420p \
  -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -c:a aac -b:a 192k -ac 2 -movflags +faststart OUTPUT
```
