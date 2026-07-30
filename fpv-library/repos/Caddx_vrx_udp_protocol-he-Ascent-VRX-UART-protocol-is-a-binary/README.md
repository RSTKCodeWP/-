# Ascent VRX UDP Protocol Client

Python UDP client for the **Ascent VRX** binary frame protocol. It supports the Ctrl UDP control channel, the independent OSD UDP channel, MSP frame diagnostics, one-shot CLI commands, and interactive keyboard input.

This repository also includes protocol documentation and a troubleshooting guide for host–VRX communication over UDP.

## Features

- Packet assemble / parse with header, length, payload checksum, and frame tail validation
- Key simulation (menu navigation, pairing, recording, and related keys)
- Frequency set / get (band, channel, hopping)
- Wireless status query (RSSI, data rate, delay, connection state)
- Power index set / get
- Interactive keyboard control (Windows console)
- Independent Ctrl UDP and OSD UDP channels with ordered OSD startup
- MSP v1/v2 frame reassembly, checksum validation, and MSP_DISPLAYPORT parsing
- OSD mode switching and command-line MSP frame/command output
- Standard-library OSD PNG font loading, validation, page splitting, and glyph preparation
- Continuous UDP response listener with human-readable decoding

## Requirements

- Python 3.10+ (type hints such as `list[str] | None` are used)
- Network path to the VRX (Ethernet RJ45 or USB Type-C network)
- Host IP in a compatible subnet (see [Network](#network))

No third-party packages are required. The UDP client, MSP parser, and OSD PNG font pipeline use the Python standard library only.

## Project layout

```text
.
├── udp_vrx_client.py                 # CLI client and protocol helpers
├── msp_osd.py                        # MSP v1/v2 and MSP_DISPLAYPORT parser
├── osd_png_font.py                   # Portable OSD PNG font loader and glyph cache
├── UART_Protocol_Packet_Summary.md   # Packet frame and command reference
├── VRX_Troubleshooting_Guide_EN_CN.md
├── startup.md                        # Quick start commands
├── tests/
│   ├── test_udp_vrx_client.py
│   ├── test_msp_osd.py
│   └── test_osd_png_font.py
└── README.md
```

## Network

The client provides two built-in connection profiles:

| Profile | Device IP | Ctrl UDP | OSD UDP |
| ------- | --------- | -------: | ------: |
| `rj45` | `192.168.1.100` | 9001 | 9200 |
| `usb-c` | `192.168.3.102` | 9001 | 9200 |

The `rj45` profile is the default. Ctrl and OSD use independent sockets and local ephemeral ports. Ensure the host is on a compatible subnet so UDP traffic can reach the VRX.

Override the selected profile when needed:

```bash
python udp_vrx_client.py --profile usb-c status
python udp_vrx_client.py --host 192.168.1.50 --ctrl-port 9001 --osd-port 9200 osd
```

The legacy `--port` option remains an alias for `--ctrl-port`.

## Quick start

```bash
# Show help
python udp_vrx_client.py

# Wireless status (send request, then listen for replies)
python udp_vrx_client.py status

# Interactive keyboard control (Windows; press Q to quit)
python udp_vrx_client.py keyboard

# Start Ctrl 9001 and OSD 9200, switch to OSD mode, and print MSP traffic
python udp_vrx_client.py osd
```

Stop continuous listening with `Ctrl+C`.

### Real USB-C device validation

For a VRX connected through the USB-C network profile, run:

```powershell
python udp_vrx_client.py --profile usb-c osd
```

This targets `192.168.3.102`, starts Ctrl UDP `9001` and OSD UDP `9200`,
sends the OSD mode-switch frame, waits 500 ms, sends probe bytes `11 12 13 14`,
and then prints both Ctrl responses and parsed MSP traffic. Press `Ctrl+C` to
close both sockets.

## CLI usage

```text
python udp_vrx_client.py [--profile {rj45,usb-c}] [--host HOST] [--ctrl-port PORT] [--osd-port PORT] <operation> ...
```

### Operations

| Operation | Description |
| --------- | ----------- |
| `key <name>` | Simulate a VRX key press |
| `set-frequency --band {A,B,C} --channel N [--hop]` | Set band / channel / hopping |
| `get-frequency` | Request current frequency |
| `status` | Request wireless status |
| `get-power` | Request power index and settable bitmap |
| `set-power <index>` | Set power index (`0`–`19`) |
| `keyboard` | Interactive key control + Ctrl UDP listener (Windows) |
| `set-mode {crsf,osd}` | Send a passthrough-mode switch on Ctrl UDP |
| `osd [--no-mode-switch]` | Start both UDP channels and print reassembled/parsed MSP traffic |

### Key names

`up`, `down`, `left`, `right`, `confirm`, `pairing`, `upgrade`, `recording`, `back`, `force-720p60`, `debug3`

### Examples

```bash
# Simulate Confirm
python udp_vrx_client.py key confirm

# Set frequency: band B, channel 12, hopping on
python udp_vrx_client.py set-frequency --band B --channel 12 --hop

# Read frequency / power
python udp_vrx_client.py get-frequency
python udp_vrx_client.py get-power

# Set power index 5
python udp_vrx_client.py set-power 5

# Switch the device to OSD mode on Ctrl UDP
python udp_vrx_client.py set-mode osd

# Run the complete dual-channel OSD diagnostic flow
python udp_vrx_client.py osd

# Use the USB-C profile
python udp_vrx_client.py --profile usb-c osd

# Listen/probe without sending the OSD mode-switch packet
python udp_vrx_client.py osd --no-mode-switch

# Point at another endpoint
python udp_vrx_client.py --host 192.168.1.50 --ctrl-port 9001 status
```

### Keyboard mode (Windows)

```bash
python udp_vrx_client.py keyboard
```

| Input | Action |
| ----- | ------ |
| `W` / `↑` | Up |
| `S` / `↓` | Down |
| `A` / `←` | Left |
| `D` / `→` | Right |
| `E` / `Enter` | Confirm |
| `Backspace` | Back |
| `P` | Pairing |
| `U` | Upgrade |
| `R` | Recording |
| `Q` | Quit |

Keyboard mode requires the Windows console (`msvcrt`). On other platforms, use the non-interactive subcommands.

## Protocol overview

Each UDP datagram carries one binary frame:

```text
Header (FE EF) | Command (1 B) | Length (2 B BE) | Payload | Checksum (2 B BE) | Tail (0D 0A)
```

- **Write commands** (host → VRX): command `0x22`
- **Read commands** (request / response): command `0xA2`
- **Passthrough mode command**: command `0x23`, set-mode subcommand `0x02`
- **Checksum**: 16-bit sum of payload bytes only (`sum(payload) & 0xFFFF`), big-endian

Common payload `cmd_type` values:

| cmd_type | Role |
| -------- | ---- |
| `0x40` | Key simulation |
| `0x50` | Set frequency |
| `0x51` | Get frequency |
| `0x52` | Wireless status |
| `0x53` | Get power |
| `0x54` | Set power |

The OSD mode payload is `02 05 00 00 00`, producing this Ctrl frame:

```text
FE EF 23 00 05 02 05 00 00 00 00 07 0D 0A
```

Full packing / unpacking rules, key tables, and field layouts: [UART_Protocol_Packet_Summary.md](UART_Protocol_Packet_Summary.md).

### Notes

- **Key simulation** is fire-and-forget: the VRX may not send an ACK. Confirm behavior on the VRX OSD / HDMI output.
- **Force 720p60** can reboot the VRX; reconnect after reboot if the session drops.

## Library usage

Import helpers from `udp_vrx_client` in your own scripts:

```python
from udp_vrx_client import (
    UdpVrxClient,
    WRITE_COMMAND,
    assemble_packet,
    parse_packet,
    decode_payload,
)

# Build a key-simulation packet (Up)
packet = assemble_packet(WRITE_COMMAND, bytes([0x40, 0x00, 0x00, 0x00]))

client = UdpVrxClient("192.168.1.100", 9001)
try:
    client.send(packet)
    client.listen_forever()  # Ctrl+C to stop
finally:
    client.close()
```

## MSP and MSP_DISPLAYPORT parsing

`msp_osd.py` ports the parsing-only path described in
[.md/MSP解析与OSD渲染说明.md](.md/MSP解析与OSD渲染说明.md). It provides:

- stateful MSP v1/v2 frame reassembly across arbitrary UDP datagrams;
- MSP v1 XOR and MSP v2 CRC-8/DVB-S2 validation;
- structured frame, issue, and `MSP_DISPLAYPORT` command results;
- standard DisplayPort subcommands and the device-specific `0x35` full-frame
  format.

The `msp_osd.py` module remains independent from network and console I/O. The
`osd` CLI operation integrates it with the dual-channel session and prints MSP
frames, checksums, parse issues, and decoded DisplayPort commands. This project
does not maintain an OSD character screen or render an RTSP/transparent overlay.

The `osd` startup order is fixed:

1. start Ctrl UDP 9001;
2. start OSD UDP 9200;
3. send the OSD mode-switch frame on Ctrl;
4. wait 500 ms;
5. send probe bytes `11 12 13 14` on OSD;
6. monitor both channels until `Ctrl+C`.

```python
from msp_osd import MspFrameReassembler, MspOsdParser

reassembler = MspFrameReassembler()
complete = reassembler.append(udp_datagram)
if complete:
    parsed, result = MspOsdParser.try_parse(complete)
    if parsed:
        frames = result.frames
        display_port_commands = result.display_port_commands
```

Use `MspOsdParser.parse(data)` for strict parsing. It raises `MspParseError`
when the byte stream contains any warning or error.

## OSD PNG font pipeline

`osd_png_font.py` ports the non-rendering portion of the GroundConfiguration OSD font path described in [.md/OSD-PNG字体加载与切割说明.md](.md/OSD-PNG字体加载与切割说明.md):

- infer character dimensions from the filename and PNG dimensions;
- decode PNG pixels to row-major RGBA bytes without Pillow;
- validate and split up to 16 pages of 256 glyphs;
- convert individual glyphs to premultiplied BGRA lazily through `OsdGlyphCache`.

The transparent WinForms/GDI+ drawing layer is intentionally not included, as this project does not need OSD drawing.

## Tests

```bash
python -m unittest tests.test_udp_vrx_client -v
python -m unittest tests.test_osd_png_font -v
python -m unittest tests.test_msp_osd -v
python -m unittest discover -s tests -v
```

Tests cover VRX framing, profile resolution, mode switching, ordered dual-channel startup, fake-socket behavior, MSP v1/v2 reassembly and validation, MSP_DISPLAYPORT decoding, PNG decoding, font-page splitting, pixel conversion, and glyph caching without requiring a live VRX.

## Troubleshooting

Common issues:

1. **No reply after key commands** — expected for key simulation; verify on the VRX display.
2. **No traffic at all** — check host IP subnet, cable/USB network adapter, and firewall.
3. **Wrong endpoint** — match host/port to Ethernet vs USB-network mode.
4. **Session drops after Force 720p60** — wait for reboot, then reconnect.

Details (EN + CN): [VRX_Troubleshooting_Guide_EN_CN.md](VRX_Troubleshooting_Guide_EN_CN.md).

## Related documents

- [UART_Protocol_Packet_Summary.md](UART_Protocol_Packet_Summary.md) — protocol specification summary
- [VRX_Troubleshooting_Guide_EN_CN.md](VRX_Troubleshooting_Guide_EN_CN.md) — communication troubleshooting
- [startup.md](startup.md) — short launch recipes

## License

Proprietary — Caddx FPV Tech. All rights reserved unless otherwise stated by the project owner.
