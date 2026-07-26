# @altnautica/mavlink-bridge

MAVLink UDP/TCP to WebSocket bridge for browser-based ground control stations.

Browsers cannot open raw UDP or TCP sockets, so a browser-based GCS cannot talk
directly to a flight controller, drone, or simulator that speaks MAVLink over
UDP or TCP. This tool sits in the middle: it attaches to a MAVLink UDP or TCP
endpoint and re-exposes it as a WebSocket that the browser GCS can connect to.
It relays raw binary frames in both directions and does no MAVLink parsing.

## Architecture

```
  Flight controller / drone / SITL
   (MAVLink over UDP or TCP)
              │
        UDP 14550  /  TCP 5760
              │
       ┌──────┴───────┐
       │ mavlink      │  raw binary relay (zero MAVLink parsing)
       │ bridge       │
       └──────┬───────┘
              │
          WS 14551
              │
         Browser GCS
```

## Prerequisites

- Node.js 20+

## Install / Build

```bash
cd tools/mavlink-bridge
npm install
npm run build
```

Or run it without a global install:

```bash
npx @altnautica/mavlink-bridge --in udp:0.0.0.0:14550 --ws 14551
```

## Usage

```bash
# Listen for UDP MAVLink and serve it to the GCS on ws://localhost:14551
mavlink-bridge --in udp:0.0.0.0:14550 --ws 14551

# Bridge a TCP MAVLink server (e.g. a SITL instance on 5760)
mavlink-bridge --in tcp:127.0.0.1:5760 --ws 14551

# Send to a fixed UDP target instead of listening
mavlink-bridge --in udpout:127.0.0.1:14550 --ws 14551
```

Then point the GCS connection at `ws://localhost:14551`.

### With MAVProxy and a serial flight controller

Run MAVProxy against the FC and forward a UDP stream to the bridge:

```bash
mavproxy.py --master=/dev/ttyUSB0 --out=udp:127.0.0.1:14550
mavlink-bridge --in udp:127.0.0.1:14550 --ws 14551
```

The bridge listens on `127.0.0.1:14550`, learns MAVProxy as the peer from the
first datagram, and relays both directions. Connect the GCS to
`ws://localhost:14551`.

## Input spec (`--in`)

`--in` takes a `<proto>:<host>:<port>` spec:

| Spec | Mode | Behavior |
|------|------|----------|
| `udp:HOST:PORT` | listen | Bind to `HOST:PORT`, learn the remote peer from the first inbound datagram, then send GCS traffic back to that peer. |
| `udpin:HOST:PORT` | listen | Same as `udp:` (explicit). |
| `udpout:HOST:PORT` | target | Send to a fixed `HOST:PORT` from the start, and receive replies on the same socket. |
| `tcp:HOST:PORT` | tcp | Connect out to a TCP MAVLink server, with automatic reconnect and exponential backoff. |

The `listen` mode follows MAVProxy semantics: the drone or simulator sends to
the bridge, the bridge learns where it came from, and replies route back to that
learned peer.

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--in <spec>` | (required) | Input endpoint to bridge (see above) |
| `--ws <port>` | `14551` | WebSocket listen port for the GCS |
| `-h`, `--help` | — | Show help |

`--input` and `--ws-port` are accepted as aliases of `--in` and `--ws`.

## Notes

- The bridge does not parse MAVLink. It moves raw bytes, so it works with any
  MAVLink dialect and version, and with non-MAVLink byte streams too.
- UDP is connectionless. In `listen` mode the bridge cannot send GCS traffic
  until it has seen at least one inbound datagram and learned the peer. On a
  socket error it rebinds with exponential backoff.
- TCP reconnects automatically with exponential backoff if the upstream server
  drops or is not yet up.

## License

GPL-3.0-only
