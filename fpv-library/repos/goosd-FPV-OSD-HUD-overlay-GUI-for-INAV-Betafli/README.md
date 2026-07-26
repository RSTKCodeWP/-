# GoOSD

GoOSD is a Go/Ebitengine on-screen display for FPV telemetry. It draws a transparent, always-on-top HUD over an external video or map window.

The application does not decode or receive video packets. Video is expected to be displayed by another process, for example `gst-launch-1.0`. GoOSD listens for MAVLink telemetry over UDP and renders the HUD overlay on top.

Go OSD over a map
![OSD over a map](assets/osd1.jpg)

Go OSD over FPV video
![OSD over video](assets/osd2.jpg)

## Data Flow

Typical OpenIPC/WFB-ng setup:

1. Air unit sends video and MAVLink through WFB-ng.
2. Ground station WFB-ng receives the stream and forwards MAVLink to LAN.
3. A video player or GStreamer pipeline displays the video.
4. GoOSD receives MAVLink telemetry and draws the transparent HUD over that video window.

For WFB-ng, check the ground-station MAVLink forwarding settings, usually in `/etc/wifibroadcast` under `gs_mavlink`.

## Quick Start

Run with simulated data:

```sh
go run ./cmd
```

Run with MAVLink UDP input:

```sh
go run ./cmd -mavlink-udp :16000
```

Run as a click-through overlay:

```sh
go run ./cmd -mavlink-udp :16000 -click-through
```

Example H.265 video receiver pipeline:

```sh
gst-launch-1.0 -v udpsrc port=5600 caps='application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string)H265' ! rtph265depay ! avdec_h265 ! videoconvert ! autovideosink sync=false
```

## Command-Line Flags

| Flag | Default | Description |
| --- | --- | --- |
| `-mavlink-udp` | empty | UDP listen address for MAVLink telemetry. When empty, GoOSD uses simulated data. Example: `:16000`. |
| `-click-through` | `false` | Makes the overlay ignore mouse input so clicks pass through to the window underneath. |

## HUD Rendering

The current HUD draws:

- Center reticle
- Pitch ladder
- Roll scale and roll value
- Heading
- Speed
- Altitude
- GPS fix, satellites, and HDOP
- Battery percentage, voltage, and current
- RC receiver RSSI
- WFB RSSI, link quality, FEC fixed count, RX error count, and link flags
- Flight mode
- Health text: `ARMED`, `DISARMED`, `LOW BAT`, `NO TELEMETRY`, or `FAILSAFE`

HUD text uses Ebitengine `text/v2` with the embedded Go Mono font. Text is drawn with outline passes to stay readable on both dark and light video backgrounds.

## Telemetry State

Telemetry is converted into the renderer-facing DTO in `internal/hud.State`. This keeps MAVLink transport details out of the drawing code.

The state currently includes:

- Attitude: roll, pitch, yaw
- Heading
- Altitude
- Speed
- GPS fix status
- Battery status
- Radio and WFB link status
- Flight mode
- Health flags
- Last update time

## MAVLink Mapping

GoOSD uses `gomavlib` with the MAVLink common dialect.

| MAVLink message | HUD fields |
| --- | --- |
| [`HEARTBEAT` (0)](https://mavlink.io/en/messages/common.html#HEARTBEAT) | Armed flag, failsafe health flag, flight mode |
| [`SYS_STATUS` (1)](https://mavlink.io/en/messages/common.html#SYS_STATUS) | Low battery health flag |
| [`GPS_RAW_INT` (24)](https://mavlink.io/en/messages/common.html#GPS_RAW_INT) | GPS fix type, satellites, HDOP, speed fallback |
| [`ATTITUDE` (30)](https://mavlink.io/en/messages/common.html#ATTITUDE) | Roll, pitch, yaw |
| [`GLOBAL_POSITION_INT` (33)](https://mavlink.io/en/messages/common.html#GLOBAL_POSITION_INT) | Heading, altitude, ground speed fallback |
| [`RC_CHANNELS_RAW` (35)](https://mavlink.io/en/messages/common.html#RC_CHANNELS_RAW) | RC receiver RSSI |
| [`RC_CHANNELS` (65)](https://mavlink.io/en/messages/common.html#RC_CHANNELS) | RC receiver RSSI |
| [`VFR_HUD` (74)](https://mavlink.io/en/messages/common.html#VFR_HUD) | Heading, altitude, ground speed |
| [`RADIO_STATUS` (109)](https://mavlink.io/en/messages/common.html#RADIO_STATUS) | RC RSSI, WFB RSSI, WFB link quality, WFB counters, WFB flags |
| [`BATTERY_STATUS` (147)](https://mavlink.io/en/messages/common.html#BATTERY_STATUS) | Battery percentage, voltage, current |

### Battery Units

`BATTERY_STATUS` values are converted as follows:

- `battery_remaining`: percent
- `voltages` and `voltages_ext`: millivolts to volts
- `current_battery`: centi-amps to amps

Unknown MAVLink sentinel values are ignored rather than displayed as real zeroes.

### Radio and WFB Fields

For `RADIO_STATUS`, GoOSD follows the WFB-ng OSD convention:

- `rssi`: WFB RSSI as signed dBm and also a fallback RC RSSI value
- `remrssi`: WFB link quality percentage
- `rxerrors`: WFB link error counter
- `fixed`: WFB FEC fixed counter
- `remnoise`: WFB flags

Supported WFB flags:

- `1`: link lost
- `2`: link jammed

`RC_CHANNELS_RAW.rssi` and `RC_CHANNELS.rssi` update the RC receiver RSSI display directly. A value of `255` is treated as invalid or unknown.

### Flight Mode

Flight mode is derived from `HEARTBEAT.base_mode` and `HEARTBEAT.custom_mode`.

For Betaflight-compatible heartbeats, GoOSD follows the current telemetry convention:

- `custom_mode = 1`: `ACRO`
- `custom_mode = 0`: `STAB`

For other MAVLink senders, GoOSD falls back to the standard mode flags in priority order:

1. `AUTO`
2. `GUIDED`
3. `STAB`
4. `MANUAL`
5. `HIL`
6. `TEST`
7. `CUSTOM <custom_mode>`

## Development

Run tests:

```sh
go test ./...
```

## TODO

- Add config for window size, position, always-on-top, click-through, and data source.
- Add a background launcher for the video pipeline and GoOSD.

## License

HUD work is based on ideas from Stratux AHRS:

https://github.com/knicholson32/stratux_ahrs/blob/master/LICENSE
