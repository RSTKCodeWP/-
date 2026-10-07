# wkumik/waybeam_venc

> Картка виставки. Зал: [Наземні станції](../halls/gcs.md).

Каталог тримає категорію `other`. Зал «Наземні станції» поставлено, бо в назві, описі або шляху є «ground station».

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [wkumik/waybeam_venc](https://github.com/wkumik/waybeam_venc) |
| Локальна тека | `fpv-library/repos/waybeam_venc-Standalone-Video-Encoder-Streamer-for-FP` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-06-13 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

Waybeam is the camera-side daemon for the Waybeam FPV ecosystem. It owns the ISP, sensor, and VENC channel on the vehicle, captures audio, streams RTP / compact UDP / Unix / SHM video to a ground station, optionally records to SD card, and exposes the whole pipeline through a single zero-restart HTTP API and a built-in web dashboard.

Two SoC backends share one source tree:

Both binaries are produced from the same `make build` invocation with different `SOC_BUILD=` flags. All MI vendor libraries are loaded via `dlopen` so the binary stays small and the Maruko bundle can ship its own copies of libs that stock OpenIPC Infinity6C firmware does not.

> **Note on naming.** The product, binary, config file, init script, > and release tarball are all named `waybeam`. The GitHub repository > is still `waybeam_venc` for historical URL stability — that is the > only place the old name survives.

_З README.md, без переказу._

## Для чого

Standalone Video Encoder & Streamer for FPV

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Оператор наземної станції — у тексті є «ground station».
- Розробник відеотракту — у тексті є «h.265».


## Функція

Список із розділу features / можливості в README:

- H.265 (HEVC) encoding with CBR / VBR / AVBR / FIXQP rate control
- RTP packetization (single-NAL + FU-A, fixed `maxPayloadSize`); compact UDP raw-NAL mode
- Built-in web dashboard at `/` for configuration, API docs, and IQ tuning
- HTTP API for live parameter tuning without pipeline restart
- ISP IQ parameter system: 60+ params, multi-field structs, JSON export/import (both backends)
- Custom 3A: built-in AE and AWB with configurable gain limits and convergence
- ROI-based QP gradient for FPV center-priority encoding
- Sensor FPS unlock for IMX415 / IMX335 (in-tree drivers; up to 144 fps
- Optional audio capture (Opus / G.711a / G.711µ / raw PCM) on both
- SD card recording: MPEG-TS mux (HEVC + audio in TS, PCM / A-law / µ-law / Opus
- Gemini / dual-VENC: concurrent stream + high-quality record (both backends)
- Adaptive recording bitrate: auto-reduces if SD card can't keep up

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `CLAUDE.md`
- `config/`
- `docs/`
- `documentation/`
- `drivers/`
- `GOAL.md`
- `HISTORY.md`
- `include/`
- `init.d/`
- `iq-profiles/`
- `lib/`
- `libs/`
- `LICENSE`
- `Makefile`
- `README.md`
- `scripts/`
- `sdk/`
- `sensors/`
- `specs/`
- `src/`
- `tests/`
- `tools/`
- `vendor-libs/`

Типи файлів за вибіркою (491 файлів, глибина до 3): C (306), Markdown (84), .so (26), shell (20), (без суфікса) (19), .o (7).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Build

From the repo root:

```sh
# Star6E (Infinity6E)
make build SOC_BUILD=star6e

# Maruko (Infinity6C)
make build SOC_BUILD=maruko
```

The toolchain is auto-downloaded on first build. Each backend builds to
its own output directory:

```
out/star6e/waybeam   # Star6E binary
out/maruko/waybeam   # Maruko binary
```

Both backends can coexist; no clean is needed when switching.

Stage a deployable bundle with vendored libraries:

```sh
make stage SOC_BUILD=star6e
# Output: out/star6e/waybeam + out/star6e/lib/*.so (Maruko also stages drivers/ + isp-bins/)
```

Run host tests:

```sh
make test-ci
```
### Usage Examples

**Start streaming to a receiver:**

```sh
curl "http://<device-ip>:<port>/api/v1/set?outgoing.server=udp://<receiver-ip>:5600"
curl "http://<device-ip>:<port>/api/v1/set?outgoing.enabled=true"
```

**Switch to 720p at 90 fps with lower bitrate:**

```sh
curl "http://<device-ip>:<port>/api/v1/set?video0.size=1280x720"
curl "http://<device-ip>:<port>/api/v1/set?video0.fps=90"
curl "http://<device-ip>:<port>/api/v1/set?video0.bitrate=4096"
```

**Manual white balance at 6500 K:**

```sh
curl "http://<device-ip>:<port>/api/v1/set?isp.awb_mode=ct_manual"
curl "http://<device-ip>:<port>/api/v1/set?isp.awb_ct=6500"
```

**Enable center-priority ROI encoding:**

```sh
curl "http://<device-ip>:<port>/api/v1/set?fpv.roi_enabled=true"
curl "http://<device-ip>:<port>/api/v1/set?fpv.roi_qp=-18"
curl "http://<device-ip>:<port>/api/v1/set?fpv.roi_steps=2"
```

**Request an IDR keyframe (useful after stream start):**

```sh
curl http://<device-ip>:<port>/request/idr
```

**Start/stop SD card recording:**

```sh
# Start recording (MPEG-TS with audio)
curl "http://<device-ip>:<port>/api/v1/record/start"

# Check recording status
curl "http://<device-ip>:<port>/api/v1/record/status"

# Stop recording
curl "http://<device-ip>:<port>/api/v1/record/stop"
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/waybeam_venc-Standalone-Video-Encoder-Streamer-for-FP/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/wkumik__waybeam_venc.md`.
