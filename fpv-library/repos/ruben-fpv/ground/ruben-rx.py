#!/usr/bin/env python3
"""
Ruben-FPV Raw Packet Receiver (Ground Station)
Captures raw 802.11 frames and outputs video stream to UDP for decoding.
"""

import socket
import sys
import os
import signal
import time
from collections import defaultdict

# Add common module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'common'))
from protocol import (RubenPacket, TYPE_VIDEO, MAGIC, SOURCE_MAC,
                      DEFAULT_VIDEO_PORT)

# Try scapy first
try:
    from scapy.all import sniff, Dot11, Raw, conf
    HAVE_SCAPY = True
except ImportError:
    HAVE_SCAPY = False
    print("[!] Scapy not found, using raw sockets")

# Configuration from environment
INTERFACE = os.environ.get('WIFI_INTERFACE', 'wlan1')
UDP_PORT = int(os.environ.get('VIDEO_PORT', str(DEFAULT_VIDEO_PORT)))


class RubenRX:
    def __init__(self, interface, port):
        self.interface = interface
        self.port = port
        self.running = True
        self.packets_received = 0
        self.bytes_received = 0
        self.packets_dropped = 0
        self.start_time = time.time()
        self.last_sequence = -1

        # Fragment reassembly buffer: {sequence: {frag_idx: data}}
        self.fragment_buffer = defaultdict(dict)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Setup UDP sender (to video decoder)
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.decoder_addr = ('127.0.0.1', port)

        # Setup raw socket for capture
        if not HAVE_SCAPY:
            self._setup_raw_socket()

        print(f"[+] Ruben RX initialized")
        print(f"    Interface: {interface}")
        print(f"    Output UDP port: {port}")

    def _setup_raw_socket(self):
        """Setup raw socket for packet capture"""
        try:
            self.raw_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                                          socket.htons(0x0003))
            self.raw_sock.bind((self.interface, 0))
            self.raw_sock.settimeout(1.0)
        except PermissionError:
            print("[-] Need root permissions for raw sockets")
            sys.exit(1)
        except OSError as e:
            print(f"[-] Failed to bind to {self.interface}: {e}")
            sys.exit(1)

    def _signal_handler(self, signum, frame):
        print("\n[*] Shutting down...")
        self.running = False

    def _process_packet(self, data):
        """Process a received Ruben packet"""
        pkt = RubenPacket.unpack(data)
        if pkt is None:
            return

        if pkt.type != TYPE_VIDEO:
            return

        self.packets_received += 1
        self.bytes_received += len(pkt.payload)

        # Track dropped packets
        if self.last_sequence >= 0:
            expected = (self.last_sequence + 1) & 0xFFFF
            if pkt.sequence != expected and pkt.fragment == 0:
                # New sequence started, check if we missed any
                gap = (pkt.sequence - expected) & 0xFFFF
                if gap < 1000:  # Sanity check
                    self.packets_dropped += gap

        # Handle fragmentation
        if pkt.total_fragments == 1:
            # Single packet, send directly
            self.udp_sock.sendto(pkt.payload, self.decoder_addr)
            self.last_sequence = pkt.sequence
        else:
            # Fragmented packet, reassemble
            self.fragment_buffer[pkt.sequence][pkt.fragment] = pkt.payload

            # Check if we have all fragments
            if len(self.fragment_buffer[pkt.sequence]) == pkt.total_fragments:
                # Reassemble in order
                reassembled = b''.join(
                    self.fragment_buffer[pkt.sequence][i]
                    for i in range(pkt.total_fragments)
                )
                self.udp_sock.sendto(reassembled, self.decoder_addr)
                del self.fragment_buffer[pkt.sequence]
                self.last_sequence = pkt.sequence

            # Clean up old fragments (prevent memory leak)
            old_seqs = [s for s in self.fragment_buffer
                        if ((pkt.sequence - s) & 0xFFFF) > 100]
            for s in old_seqs:
                del self.fragment_buffer[s]

    def _scapy_callback(self, pkt):
        """Scapy packet callback"""
        if not pkt.haslayer(Dot11):
            return

        # Check if it's from our transmitter
        if pkt.addr2 != "02:52:55:42:45:4e":
            return

        if pkt.haslayer(Raw):
            self._process_packet(bytes(pkt[Raw].load))

    def run(self):
        """Main receive loop"""
        print("[*] Starting reception...")
        last_stats = time.time()

        if HAVE_SCAPY:
            # Use scapy sniff
            conf.iface = self.interface
            while self.running:
                try:
                    sniff(iface=self.interface, prn=self._scapy_callback,
                          timeout=1, store=False)

                    now = time.time()
                    if now - last_stats >= 5.0:
                        self._print_stats()
                        last_stats = now
                except Exception as e:
                    print(f"[-] Error: {e}")
        else:
            # Use raw socket
            while self.running:
                try:
                    data = self.raw_sock.recv(65535)

                    # Skip radiotap and 802.11 headers (rough estimate)
                    # In practice, header sizes vary
                    if len(data) > 40:
                        # Look for our magic bytes
                        for i in range(len(data) - 8):
                            if data[i:i+2] == MAGIC:
                                self._process_packet(data[i:])
                                break

                    now = time.time()
                    if now - last_stats >= 5.0:
                        self._print_stats()
                        last_stats = now

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[-] Error: {e}")

        self._print_stats()

    def _print_stats(self):
        elapsed = time.time() - self.start_time
        rate = self.bytes_received / elapsed / 1024 / 1024 if elapsed > 0 else 0
        loss = self.packets_dropped / max(1, self.packets_received + self.packets_dropped) * 100
        print(f"[*] RX: {self.packets_received} pkts, "
              f"{self.bytes_received / 1024 / 1024:.1f} MB, "
              f"{rate:.2f} MB/s, "
              f"loss: {loss:.1f}%")


def main():
    if os.geteuid() != 0:
        print("[-] This script requires root privileges")
        sys.exit(1)

    rx = RubenRX(INTERFACE, UDP_PORT)
    rx.run()


if __name__ == '__main__':
    main()
