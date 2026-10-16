#!/usr/bin/env python3
"""Host-side checks matching Caddx udp_vrx_max_client framing."""

import sys
import unittest


def assemble(command: int, payload: bytes) -> bytes:
    header = bytes([0xFE, 0xEF])
    tail = bytes([0x0D, 0x0A])
    csum = sum(payload) & 0xFFFF
    return (
        header
        + bytes([command])
        + len(payload).to_bytes(2, "big")
        + payload
        + csum.to_bytes(2, "big")
        + tail
    )


class VrxProtoTest(unittest.TestCase):
    def test_up_key(self):
        pkt = assemble(0x22, bytes([0x40, 0x00, 0x00, 0x00]))
        self.assertEqual(pkt.hex(), "feef2200044000000000400d0a")

    def test_set_mode_crsf(self):
        payload = bytes([0x02, 0x02, 0x00, 0x00, 0x00])
        pkt = assemble(0x23, payload)
        self.assertEqual(
            pkt.hex(),
            "feef230005020200000000040d0a",
        )

    def test_set_mode_osd(self):
        payload = bytes([0x02, 0x05, 0x00, 0x00, 0x00])
        pkt = assemble(0x23, payload)
        self.assertEqual(
            pkt.hex(),
            "feef230005020500000000070d0a",
        )


if __name__ == "__main__":
    unittest.main()
