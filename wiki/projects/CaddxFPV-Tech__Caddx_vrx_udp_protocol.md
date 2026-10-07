# CaddxFPV-Tech/Caddx_vrx_udp_protocol

> Картка виставки. Зал: [Окуляри і VRX](../halls/goggles.md).

Каталог тримає категорію `other`. Зал «Окуляри і VRX» поставлено, бо в назві, описі або шляху є «vrx».

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [CaddxFPV-Tech/Caddx_vrx_udp_protocol](https://github.com/CaddxFPV-Tech/Caddx_vrx_udp_protocol) |
| Локальна тека | `fpv-library/repos/Caddx_vrx_udp_protocol-he-Ascent-VRX-UART-protocol-is-a-binary` |
| У бібліотеці | skip |
| Категорії каталогу | `other` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-07-29 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

﻿# Ascent VRX UDP Protocol Client

Python UDP client for the **Ascent VRX** binary frame protocol. It supports the Ctrl UDP control channel, the independent OSD UDP channel, MSP frame diagnostics, one-shot CLI commands, and interactive keyboard input.

This repository also includes protocol documentation and a troubleshooting guide for host–VRX communication over UDP.

_З README.md, без переказу._

## Для чого

he Ascent VRX UART protocol is a **binary frame-based communication protocol** that uses a structured packet format to exchange commands and data between a host controller and the VRX device. This document provides a comprehensive guide on how to **assemble (pack)** outgoing command packets and **disassemble (unpack)** incoming response packets.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «vrx».


## Функція

Список із розділу features / можливості в README:

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

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `msp_osd.py`
- `osd_png_font.py`
- `README.md`
- `startup.md`
- `udp_vrx_client.py`
- `UserManuals/`

Типи файлів за вибіркою (12 файлів, глибина до 3): Markdown (7), Python (3), JSON (1), (без суфікса) (1).


## Що треба

### Requirements

- Python 3.10+ (type hints such as `list[str] | None` are used)
- Network path to the VRX (Ethernet RJ45 or USB Type-C network)
- Host IP in a compatible subnet (see [Network](#network))

No third-party packages are required. The UDP client, MSP parser, and OSD PNG font pipeline use the Python standard library only.


## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick start

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
### CLI usage

```text
python udp_vrx_client.py [--profile {rj45,usb-c}] [--host HOST] [--ctrl-port PORT] [--osd-port PORT] <operation> ...
```
### Library usage

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

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/Caddx_vrx_udp_protocol-he-Ascent-VRX-UART-protocol-is-a-binary/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/CaddxFPV-Tech__Caddx_vrx_udp_protocol.md`.
