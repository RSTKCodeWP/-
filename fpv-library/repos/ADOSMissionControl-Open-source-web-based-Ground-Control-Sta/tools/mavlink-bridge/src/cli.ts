#!/usr/bin/env node
// SPDX-License-Identifier: GPL-3.0-only
// cli.ts — MAVLink UDP/TCP ↔ WebSocket bridge CLI entry point

import { UdpWsBridge, type UdpMode } from './udp-ws.js';
import { TcpWsBridge } from './tcp-ws.js';
import type { Bridge } from './types.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_WS_PORT = 14551;

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

type InputProto = 'udp-listen' | 'udp-target' | 'tcp';

interface InputSpec {
  proto: InputProto;
  host: string;
  port: number;
}

interface CliArgs {
  input?: string;
  wsPort: number;
  help: boolean;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = { wsPort: DEFAULT_WS_PORT, help: false };

  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    const next = argv[i + 1];

    switch (arg) {
      case '--in':
      case '--input':
        args.input = next;
        i++;
        break;
      case '--ws':
      case '--ws-port':
        args.wsPort = parseInt(next, 10);
        i++;
        break;
      case '--help':
      case '-h':
        args.help = true;
        break;
      default:
        console.error(`Unknown argument: ${arg}`);
        printHelp();
        process.exit(1);
    }
  }

  return args;
}

function parseInputSpec(spec: string): InputSpec {
  // Format: <proto>:<host>:<port>. Split proto off the front, then the port off
  // the back, so IPv6 host literals (which contain colons) survive intact.
  const sep = spec.indexOf(':');
  if (sep === -1) {
    throw new Error(`Invalid --in spec "${spec}". Expected <proto>:<host>:<port>.`);
  }
  const protoToken = spec.slice(0, sep).toLowerCase();
  const rest = spec.slice(sep + 1);

  const lastColon = rest.lastIndexOf(':');
  if (lastColon === -1) {
    throw new Error(`Invalid --in spec "${spec}". Missing port. Expected <proto>:<host>:<port>.`);
  }
  const host = rest.slice(0, lastColon);
  const port = parseInt(rest.slice(lastColon + 1), 10);
  if (!host || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`Invalid --in spec "${spec}". Host or port is malformed.`);
  }

  let proto: InputProto;
  switch (protoToken) {
    case 'udp':
    case 'udpin':
      proto = 'udp-listen';
      break;
    case 'udpout':
      proto = 'udp-target';
      break;
    case 'tcp':
      proto = 'tcp';
      break;
    default:
      throw new Error(
        `Unknown protocol "${protoToken}" in --in spec. Use udp, udpin, udpout, or tcp.`,
      );
  }

  return { proto, host, port };
}

function printHelp(): void {
  console.log(`
mavlink-bridge — MAVLink UDP/TCP ↔ WebSocket bridge for browser-based GCS

Browsers cannot open raw UDP or TCP sockets. This tool exposes a MAVLink UDP or
TCP endpoint as a WebSocket the browser ground control station can dial. It
relays raw bytes both ways and does no MAVLink parsing.

Usage:
  mavlink-bridge --in <spec> [--ws <port>]

Options:
  --in <spec>     Input endpoint to bridge. One of:
                    udp:HOST:PORT     listen on HOST:PORT and learn the peer
                                      from the first datagram (MAVProxy
                                      --out=udp:HOST:PORT)
                    udpin:HOST:PORT   same as udp: (explicit listen)
                    udpout:HOST:PORT  send to a fixed HOST:PORT from the start
                    tcp:HOST:PORT     connect out to a TCP server
  --ws <port>     WebSocket listen port for the GCS (default: ${DEFAULT_WS_PORT})
  -h, --help      Show this help

Examples:
  # Listen for ArduPilot/MAVProxy UDP output, serve it to the GCS
  mavlink-bridge --in udp:0.0.0.0:14550 --ws 14551
  #   mavproxy.py --master=/dev/ttyUSB0 --out=udp:127.0.0.1:14550
  #   then point the GCS at ws://localhost:14551

  # Bridge a TCP MAVLink server (e.g. a SITL instance on 5760)
  mavlink-bridge --in tcp:127.0.0.1:5760 --ws 14551

  # Send to a fixed UDP target
  mavlink-bridge --in udpout:127.0.0.1:14550 --ws 14551
`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function logError(err: Error, log: (msg: string) => void): void {
  const code = (err as NodeJS.ErrnoException).code;
  // ECONNREFUSED is expected while a TCP target is still starting up.
  if (code === 'ECONNREFUSED') return;
  log(`Bridge error: ${err.message}`);
}

function main(): void {
  const cli = parseArgs(process.argv);

  if (cli.help) {
    printHelp();
    process.exit(0);
  }

  if (!cli.input) {
    console.error('Error: --in <spec> is required.\n');
    printHelp();
    process.exit(1);
  }

  if (!Number.isInteger(cli.wsPort) || cli.wsPort < 1 || cli.wsPort > 65535) {
    console.error(`Error: invalid --ws port "${cli.wsPort}".`);
    process.exit(1);
  }

  let spec: InputSpec;
  try {
    spec = parseInputSpec(cli.input);
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    process.exit(1);
  }

  const log = (msg: string) => {
    const ts = new Date().toISOString();
    console.log(`[${ts}] ${msg}`);
  };

  let bridge: Bridge;

  if (spec.proto === 'tcp') {
    const tcp = new TcpWsBridge({ wsPort: cli.wsPort, host: spec.host, port: spec.port });
    tcp.on('connected', ({ host, port }) => log(`TCP connected to ${host}:${port}`));
    tcp.on('disconnected', ({ host, port }) =>
      log(`TCP disconnected from ${host}:${port}, reconnecting...`),
    );
    tcp.on('ws-client-connected', ({ remoteAddress }) =>
      log(`GCS connected from ${remoteAddress} (${tcp.wsClientCount} client(s))`),
    );
    tcp.on('ws-client-disconnected', ({ remoteAddress }) =>
      log(`GCS disconnected: ${remoteAddress} (${tcp.wsClientCount} client(s))`),
    );
    tcp.on('error', (err) => logError(err, log));
    bridge = tcp;
  } else {
    const mode: UdpMode = spec.proto === 'udp-target' ? 'target' : 'listen';
    const udp = new UdpWsBridge({ wsPort: cli.wsPort, mode, host: spec.host, port: spec.port });
    udp.on('connected', ({ host, port }) =>
      log(
        mode === 'listen'
          ? `UDP listening on ${host}:${port} (waiting for the drone to send)`
          : `UDP sending to ${host}:${port}`,
      ),
    );
    udp.on('disconnected', ({ host, port }) =>
      log(`UDP socket closed (${host}:${port}), rebinding...`),
    );
    udp.on('peer-learned', ({ host, port }) => log(`Learned UDP peer ${host}:${port}`));
    udp.on('ws-client-connected', ({ remoteAddress }) =>
      log(`GCS connected from ${remoteAddress} (${udp.wsClientCount} client(s))`),
    );
    udp.on('ws-client-disconnected', ({ remoteAddress }) =>
      log(`GCS disconnected: ${remoteAddress} (${udp.wsClientCount} client(s))`),
    );
    udp.on('error', (err) => logError(err, log));
    bridge = udp;
  }

  bridge.start();

  // Startup banner
  log('');
  log('=== MAVLink Bridge Ready ===');
  switch (spec.proto) {
    case 'udp-listen':
      log(`Bridging UDP (listen) ${spec.host}:${spec.port}  ->  ws://localhost:${cli.wsPort}`);
      break;
    case 'udp-target':
      log(`Bridging UDP (target) ${spec.host}:${spec.port}  ->  ws://localhost:${cli.wsPort}`);
      break;
    case 'tcp':
      log(`Bridging TCP ${spec.host}:${spec.port}  ->  ws://localhost:${cli.wsPort}`);
      break;
  }
  log(`Point the GCS at:  ws://localhost:${cli.wsPort}`);
  log('');

  // --- Signal handling (clean shutdown) -----------------------------------
  let shuttingDown = false;

  const shutdown = () => {
    if (shuttingDown) return;
    shuttingDown = true;

    log('Shutting down...');
    bridge.shutdown();
    console.log('Bridge stopped. Goodbye.');
    process.exit(0);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main();
