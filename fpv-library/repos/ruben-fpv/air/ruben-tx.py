#!/usr/bin/env python3
"""
Ruben-FPV Raw Packet Transmitter (Air Unit)
Reads video stream from UDP and injects as raw 802.11 frames.
"""

import socket
import sys
import os
import signal
import time

# Add common module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'common'))
from protocol import (RubenPacket, TYPE_VIDEO, build_radiotap_header,
                      build_dot11_header, DEFAULT_MTU, DEFAULT_VIDEO_PORT)

# Try scapy first, fall back to raw sockets
try:
    from scapy.all import RadioTap, Dot11, sendp, conf
    HAVE_SCAPY = True
except ImportError:
    HAVE_SCAPY = False
    print("[!] Scapy not found, using raw sockets")

# Configuration from environment
INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan1')
UDP_PORT = int(os.environ.get('VIDEO_PORT', str(DEFAULT_VIDEO_PORT)))
MTU_SIZE = int(os.environ.get('MTU_SIZE', str(DEFAULT_MTU)))


class RubenTX:
    def __init__(self, interface, port):
        self.interface = interface
        self.port = port
        self.sequence = 0
        self.running = True
        self.packets_sent = 0
        self.bytes_sent = 0
        self.start_time = time.time()

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Setup raw socket for injection
        if HAVE_SCAPY:
            conf.iface = interface
            self.raw_sock = None
        else:
            self._setup_raw_socket()

        # Setup UDP receiver
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_sock.bind(('127.0.0.1', port))
        self.udp_sock.settimeout(1.0)

        print(f"[+] Ruben TX initialized")
        print(f"    Interface: {interface}")
        print(f"    UDP port: {port}")
        print(f"    MTU: {MTU_SIZE}")

    def _setup_raw_socket(self):
        """Setup raw socket for packet injection (non-scapy fallback)"""
        try:
            self.raw_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                                          socket.htons(0x0003))
            self.raw_sock.bind((self.interface, 0))
        except PermissionError:
            print("[-] Need root permissions for raw sockets")
            sys.exit(1)
        except OSError as e:
            print(f"[-] Failed to bind to {self.interface}: {e}")
            sys.exit(1)

    def _signal_handler(self, signum, frame):
        print("\n[*] Shutting down...")
        self.running = False

    def _inject_packet(self, payload):
        """Inject a raw 802.11 frame"""
        if HAVE_SCAPY:
            frame = (RadioTap() /
                     Dot11(type=2, subtype=0,
                           addr1="ff:ff:ff:ff:ff:ff",
                           addr2="02:52:55:42:45:4e",
                           addr3="ff:ff:ff:ff:ff:ff") /
                     payload)
            sendp(frame, iface=self.interface, verbose=False)
        else:
            radiotap = build_radiotap_header()
            dot11 = build_dot11_header(self.sequence)
            frame = radiotap + dot11 + payload
            self.raw_sock.send(frame)

        self.packets_sent += 1
        self.bytes_sent += len(payload)

    def _fragment_and_send(self, data):
        """Fragment data and send as multiple packets"""
        max_payload = MTU_SIZE - RubenPacket.HEADER_SIZE
        fragments = [data[i:i + max_payload] for i in range(0, len(data), max_payload)]
        total = len(fragments)

        for i, frag in enumerate(fragments):
            pkt = RubenPacket(
                pkt_type=TYPE_VIDEO,
                sequence=self.sequence,
                fragment=i,
                total_fragments=total,
                payload=frag
            )
            self._inject_packet(pkt.pack())

        self.sequence = (self.sequence + 1) & 0xFFFF

    def run(self):
        """Main transmit loop"""
        print("[*] Starting transmission...")
        last_stats = time.time()

        while self.running:
            try:
                data, addr = self.udp_sock.recvfrom(65535)
                if data:
                    self._fragment_and_send(data)

                # Print stats every 5 seconds
                now = time.time()
                if now - last_stats >= 5.0:
                    elapsed = now - self.start_time
                    rate = self.bytes_sent / elapsed / 1024 / 1024
                    print(f"[*] TX: {self.packets_sent} pkts, "
                          f"{self.bytes_sent / 1024 / 1024:.1f} MB, "
                          f"{rate:.2f} MB/s avg")
                    last_stats = now

            except socket.timeout:
                continue
            except Exception as e:
                print(f"[-] Error: {e}")
                continue

        print(f"[*] Final: {self.packets_sent} packets, "
              f"{self.bytes_sent / 1024 / 1024:.2f} MB sent")


def main():
    if os.geteuid() != 0:
        print("[-] This script requires root privileges")
        sys.exit(1)

    tx = RubenTX(INTERFACE, UDP_PORT)
    tx.run()


if __name__ == '__main__':
    main()
