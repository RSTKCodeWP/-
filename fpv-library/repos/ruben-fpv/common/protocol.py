#!/usr/bin/env python3
"""
Ruben-FPV Protocol Definitions
Shared between Air and Ground units
"""

import struct

# Protocol constants
MAGIC = b'\x52\x46'  # "RF" for RubenFPV
VERSION = 1

# Packet types
TYPE_VIDEO = 0x01
TYPE_TELEMETRY = 0x02
TYPE_CONTROL = 0x03

# 802.11 constants
BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'
SOURCE_MAC = b'\x02\x52\x55\x42\x45\x4e'  # 02:RU:BE:N (locally administered)

# Default settings
DEFAULT_CHANNEL = 36  # 5GHz, DFS-free
DEFAULT_MTU = 1400
DEFAULT_VIDEO_PORT = 5000


class RubenPacket:
    """
    Ruben-FPV packet header (8 bytes):
    - Magic (2 bytes): 'RF'
    - Version (1 byte)
    - Type (1 byte): video/telemetry/control
    - Sequence (2 bytes): packet sequence number
    - Fragment (1 byte): fragment index
    - Flags (1 byte): total_fragments (upper 4 bits) | flags (lower 4 bits)
    """
    HEADER_SIZE = 8
    HEADER_FORMAT = '<2sBBHBB'

    def __init__(self, pkt_type=TYPE_VIDEO, sequence=0, fragment=0,
                 total_fragments=1, flags=0, payload=b''):
        self.type = pkt_type
        self.sequence = sequence
        self.fragment = fragment
        self.total_fragments = total_fragments
        self.flags = flags
        self.payload = payload

    def pack(self):
        """Serialize packet to bytes"""
        header = struct.pack(
            self.HEADER_FORMAT,
            MAGIC,
            VERSION,
            self.type,
            self.sequence & 0xFFFF,
            self.fragment,
            (self.total_fragments << 4) | (self.flags & 0x0F)
        )
        return header + self.payload

    @classmethod
    def unpack(cls, data):
        """Deserialize packet from bytes"""
        if len(data) < cls.HEADER_SIZE:
            return None

        magic, version, pkt_type, seq, frag, flags_byte = struct.unpack(
            cls.HEADER_FORMAT, data[:cls.HEADER_SIZE]
        )

        if magic != MAGIC:
            return None

        if version != VERSION:
            return None

        total_frags = (flags_byte >> 4) & 0x0F
        flags = flags_byte & 0x0F
        payload = data[cls.HEADER_SIZE:]

        return cls(pkt_type, seq, frag, total_frags, flags, payload)


def build_radiotap_header():
    """Build minimal RadioTap header for injection"""
    return bytes([
        0x00, 0x00,  # Version
        0x08, 0x00,  # Header length (8 bytes)
        0x00, 0x00, 0x00, 0x00  # Present flags (none)
    ])


def build_dot11_header(sequence=0):
    """Build 802.11 data frame header for broadcast"""
    frame_ctrl = struct.pack('<H', 0x0008)  # Data frame
    duration = struct.pack('<H', 0x0000)
    seq_ctrl = struct.pack('<H', (sequence << 4) & 0xFFF0)

    return (frame_ctrl + duration +
            BROADCAST_MAC + SOURCE_MAC + BROADCAST_MAC +
            seq_ctrl)
