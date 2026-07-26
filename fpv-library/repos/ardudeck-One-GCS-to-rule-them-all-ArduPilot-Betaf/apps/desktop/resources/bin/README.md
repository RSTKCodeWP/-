# Flashing Tool Binaries

This directory contains the binaries for firmware flashing tools.

## STM32 DFU Flashing

STM32 DFU flashing is now handled natively using the `@ardudeck/stm32-dfu` package.
No external `dfu-util` binary is required - the app uses libusb bindings directly.

## Required Binaries (AVR/Legacy Boards Only)

### Windows (`win32/`)

- `avrdude.exe` - AVR/ATmega flashing tool
- `avrdude.conf` - avrdude configuration file

### macOS (`darwin/`)

- `avrdude` - AVR/ATmega flashing tool
- `avrdude.conf` - avrdude configuration file

### Linux (`linux/`)

- `avrdude` - AVR/ATmega flashing tool
- `avrdude.conf` - avrdude configuration file

## Download Sources

### avrdude

**Windows:**
Download from: https://github.com/avrdudes/avrdude/releases
Get the Windows binary and extract `avrdude.exe` and `avrdude.conf`.

**macOS:**
```bash
brew install avrdude
cp $(which avrdude) darwin/
cp /opt/homebrew/etc/avrdude.conf darwin/
```

**Linux:**
```bash
sudo apt install avrdude
cp $(which avrdude) linux/
cp /etc/avrdude.conf linux/
```

## Camera / Video (media engine)

The detachable Camera panel uses two binaries to turn any RTSP/RTP/SRT/RubyFPV
feed into low-latency WebRTC the renderer can play. Drop them into the same
per-platform folders; the app falls back to system PATH if absent and degrades
gracefully (RTSP/WebRTC still work without ffmpeg; nothing works without mediamtx).

### `mediamtx` (the hub — ingests RTSP/SRT, republishes as WebRTC/WHEP)

- `win32/mediamtx.exe`, `darwin/mediamtx`, `linux/mediamtx`
- Download: https://github.com/bluenviron/mediamtx/releases

### `ffmpeg` (normalizer — bridges raw H.264/UDP, plus snapshot + record)

- `win32/ffmpeg.exe`, `darwin/ffmpeg`, `linux/ffmpeg`
- Use an **LGPL** build to stay license-clean. macOS: `brew install ffmpeg mediamtx`
  then copy each into `darwin/`.

## Notes

- Make sure binaries have execute permissions on macOS/Linux
- The app will fall back to system PATH if binaries are not found here
- For development, you can install these tools system-wide and skip bundling
- STM32 flashing works without any external tools (cross-platform native USB)
