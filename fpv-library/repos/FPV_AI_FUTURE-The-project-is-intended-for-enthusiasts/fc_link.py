"""FC MSP link adapter — reads the operator TOGGLE (AUX) and sends the body-YAW override to the FC.

Un-stubs the two hardware hooks the supervisor needs in the field:
  * ``read_activation`` — is the pilot's MSP_OVERRIDE toggle up? (an AUX channel over the RX, read via MSP_RC)
  * ``send_body_yaw``   — command the cylinder/FPV body yaw as an RC override on the YAW channel ONLY;
                          the pilot's roll/pitch/throttle are read and passed back UNCHANGED, so the seeker
                          turns the body while the pilot keeps thrust and reclaims instantly by the toggle.

Reuses the proven ``msp_codec`` path. DEFAULT-DENY: a link glitch (no fresh RC) -> toggle reads False and
yaw is not commanded. The FC's own MSP_OVERRIDE mode + arming still gate whether any of this reaches a motor;
this adapter only computes and streams the channels. The pure helpers below are unit-tested with no hardware.
"""
from __future__ import annotations

import time
from typing import Optional

from fpv_ai.betaflight_link.msp_codec import (US_MID, US_MIN, US_MAX, RC_CHANNEL_ORDER, MSP_RC,
                                              encode_set_raw_rc, decode_rc)

_YAW_INDEX = RC_CHANNEL_ORDER.index("yaw")


def toggle_is_up(rc: Optional[list], switch_index: int, threshold_us: int) -> bool:
    """Pure: is the AUX at ``switch_index`` at/above the engage threshold? None/short RC -> False (deny)."""
    if rc is None or switch_index >= len(rc):
        return False
    return rc[switch_index] >= threshold_us


def yaw_override_channels(rc: Optional[list], norm: float, *, yaw_index: int = _YAW_INDEX) -> list:
    """Pure: the RC channel list to transmit — the pilot's channels unchanged EXCEPT yaw = commanded.

    ``norm`` in [-1,1] maps to [US_MIN, US_MAX] about centre. With no fresh RC we fall back to a neutral,
    idle-throttle frame (safe: the FC only applies masked axes while the toggle is up)."""
    if rc is not None and len(rc) >= 4:
        ch = list(rc)
    else:
        ch = [US_MID, US_MID, US_MID, US_MIN, US_MIN, US_MIN, US_MIN, US_MIN]
    n = -1.0 if norm < -1.0 else 1.0 if norm > 1.0 else norm
    yaw_us = int(round(US_MID + n * (US_MAX - US_MID)))
    yaw_us = US_MIN if yaw_us < US_MIN else US_MAX if yaw_us > US_MAX else yaw_us
    if yaw_index < len(ch):
        ch[yaw_index] = yaw_us
    return ch


def _read_rc(link, attempts: int = 12, sleep_s: float = 0.001) -> Optional[list]:
    try:
        link.request(MSP_RC)
        for _ in range(attempts):
            for fr in link.poll():
                if fr.function == MSP_RC:
                    return decode_rc(fr.payload)
            time.sleep(sleep_s)
    except Exception:
        return None
    return None


class FcLink:
    """Thin MSP I/O wrapper giving the supervisor its ``read_activation`` and ``send_body_yaw`` hooks."""

    def __init__(self, port: str = "/dev/ttyACM0", baud: int = 115200, *,
                 switch_index: int = 5, switch_threshold_us: int = 1600, link=None) -> None:
        if link is None:
            from fpv_ai.betaflight_link.serial_link import MspLink
            link = MspLink.open_serial(port, baud, hardware_authorized=True)
        self.link = link
        self.switch_index = int(switch_index)
        self.switch_threshold_us = int(switch_threshold_us)

    def read_activation(self) -> bool:
        return toggle_is_up(_read_rc(self.link), self.switch_index, self.switch_threshold_us)

    def send_body_yaw(self, norm: float) -> None:
        ch = yaw_override_channels(_read_rc(self.link), norm)
        try:
            self.link._channel.write(encode_set_raw_rc(ch))
        except Exception:
            pass
