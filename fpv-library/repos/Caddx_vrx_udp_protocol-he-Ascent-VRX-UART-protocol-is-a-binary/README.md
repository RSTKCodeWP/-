# Ascent VRX UDP Protocol Client

Python UDP client for the **Ascent VRX** binary frame protocol. Assemble and send control packets, receive and decode responses, and drive the VRX with either one-shot CLI commands or interactive keyboard input.

This repository also includes protocol documentation and a troubleshooting guide for host–VRX communication over UDP.

## Features

- Packet assemble / parse with header, length, payload checksum, and frame tail validation
- Key simulation (menu navigation, pairing, recording, and related keys)
- Frequency set / get (band, channel, hopping)
- Wireless status query (RSSI, data rate, delay, connection state)
- Power index set / get
- Interactive keyboard control (Windows console)
- Continuous UDP response listener with human-readable decoding

## Requirements

- Python 3.10+ (type hints such as `list[str] | None` are used)
- Network path to the VRX (Ethernet RJ45 or USB Type-C network)
- Host IP in a compatible subnet (see [Network](#network))

No third-party packages are required for the client itself. The unit tests use the standard library only.

## Project layout

```text
.
├── udp_vrx_client.py                 # CLI client and protocol helpers
├── UART_Protocol_Packet_Summary.md   # Packet frame and command reference
├── VRX_Troubleshooting_Guide_EN_CN.md
├── startup.md                        # Quick start commands
├── tests/
│   └── test_udp_vrx_client.py
└── README.md
```

## Network

Default endpoint used by the client:

| Setting | Default        |
| ------- | -------------- |
| Host    | `192.168.1.100` |
| Port    | `9001`         |

Typical VRX endpoints (see the troubleshooting guide for details):

| Connection             | Server IP       | Port |
| ---------------------- | --------------- | ---- |
| RJ45 Ethernet          | `192.168.1.100` | 9001 |
| USB Type-C (USB net)   | `192.168.3.102` | 9001 |

Ensure the host is on a compatible LAN segment (commonly `192.168.1.x`) so UDP traffic can reach the VRX.

Override destination when needed:

```bash
python udp_vrx_client.py --host 192.168.1.100 --port 9001 status
```

## Quick start

```bash
# Show help
python udp_vrx_client.py

# Wireless status (send request, then listen for replies)
python udp_vrx_client.py status

# Interactive keyboard control (Windows; press Q to quit)
python udp_vrx_client.py keyboard
```

Stop continuous listening with `Ctrl+C`.

## CLI usage

```text
python udp_vrx_client.py [--host HOST] [--port PORT] <operation> ...
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
| `keyboard` | Interactive key control + UDP listener (Windows) |

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

# Point at another endpoint
python udp_vrx_client.py --host 192.168.1.50 --port 9001 status
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

## Tests

```bash
python -m unittest tests.test_udp_vrx_client -v
```

Tests cover framing, checksum validation, payload builders, and decoding without requiring a live VRX.

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
