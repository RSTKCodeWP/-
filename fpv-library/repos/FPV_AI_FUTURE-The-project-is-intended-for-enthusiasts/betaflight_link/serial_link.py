"""Real byte transport for the RPi5 <-> Betaflight MSP link (Block-3 S4).

``transport.py`` defines the FPAI dry-run audit frame and hardcodes the safety flags
(uart_opened=False, ...). THIS module adds the actual byte path: an ``MspLink`` over a
pluggable ``ByteChannel``. Two channels are provided:
  * ``MockFcChannel`` -- a pure-Python minimal Betaflight emulator for HARDWARE-FREE tests
    (the full command->bytes->FC->telemetry loop runs in memory).
  * ``PySerialChannel`` -- the real UART (pyserial), opened ONLY when hardware is authorized.

SAFETY -- the runtime gate
--------------------------
A real serial port is NEVER opened without an explicit ``hardware_authorized=True``. This is
the runtime realisation of transport.py's ``does_not_open_uart`` boundary: dry/bench work uses
``MockFcChannel``; touching real motors requires a deliberate authorization act (owned upstream
by the launch console / arming state machine). ``MspLink`` only moves bytes -- it holds NO
throttle or arming authority; that lives in the arming state machine.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from fpv_ai.betaflight_link import msp_codec as mc
from fpv_ai.betaflight_link.msp_codec import MspDecoder, MspFrame


@runtime_checkable
class ByteChannel(Protocol):
    """A bidirectional byte pipe (a UART, or a mock)."""

    is_hardware: bool

    def write(self, data: bytes) -> int: ...
    def read(self, max_bytes: int = 4096) -> bytes: ...
    def close(self) -> None: ...


# ── Mock Betaflight FC (for hardware-free loopback) ─────────────────────────────
@dataclass
class MockFcChannel:
    """A minimal in-memory Betaflight emulator.

    Reacts to MSP frames written by the RPi: stores the last MSP_SET_RAW_RC, models a
    simplified arm gate (AUX1 high AND throttle low), and answers MSP_RAW_IMU /
    MSP_ATTITUDE requests with the configured telemetry. NOT a flight model -- just enough
    to exercise the link end to end.
    """

    gyro: tuple[int, int, int] = (0, 0, 0)
    accel: tuple[int, int, int] = (0, 0, 0)
    mag: tuple[int, int, int] = (0, 0, 0)
    attitude_ddeg: tuple[int, int, int] = (0, 0, 0)   # roll_dd, pitch_dd, yaw_deg
    arm_aux_us: int = 1700                              # AUX1 threshold to arm
    arm_throttle_max_us: int = 1050                     # throttle must be at/below to arm
    link_up: bool = True                                # set False to simulate the FC/link dying

    is_hardware: bool = field(default=False, init=False)
    last_rc: list[int] | None = field(default=None, init=False)
    armed: bool = field(default=False, init=False)
    rc_frames_received: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._dec = MspDecoder()
        self._out = bytearray()

    # ByteChannel side (called by MspLink) -------------------------------------------------
    def write(self, data: bytes) -> int:
        if not self.link_up:
            return len(data)  # bytes leave the Pi, but a dead FC neither processes nor acks
        for frame in self._dec.feed(bytes(data)):
            self._react(frame)
        return len(data)

    def read(self, max_bytes: int = 4096) -> bytes:
        if not self.link_up:
            return b""
        chunk = bytes(self._out[:max_bytes])
        del self._out[:max_bytes]
        return chunk

    def close(self) -> None:
        self._out.clear()

    # FC behaviour -------------------------------------------------------------------------
    def _react(self, frame: MspFrame) -> None:
        if frame.direction != mc.DIR_TO_FC:
            return
        if frame.function == mc.MSP_SET_RAW_RC:
            channels = mc.decode_rc(frame.payload)
            self.last_rc = channels
            self.rc_frames_received += 1
            self._update_arm(channels)
            self._out.extend(mc.encode_msp_v2(mc.MSP_SET_RAW_RC, b"", direction=mc.DIR_FROM_FC))  # ack
        elif frame.function == mc.MSP_RAW_IMU:
            self._out.extend(mc.encode_msp_v2(mc.MSP_RAW_IMU, self._imu_payload(), direction=mc.DIR_FROM_FC))
        elif frame.function == mc.MSP_ATTITUDE:
            self._out.extend(mc.encode_msp_v2(mc.MSP_ATTITUDE, self._attitude_payload(), direction=mc.DIR_FROM_FC))
        elif frame.function == mc.MSP_API_VERSION:
            self._out.extend(mc.encode_msp_v2(mc.MSP_API_VERSION, bytes([0, 1, 46]), direction=mc.DIR_FROM_FC))

    def _update_arm(self, channels: list[int]) -> None:
        order = mc.RC_CHANNEL_ORDER
        try:
            aux1 = channels[order.index("aux1")]
            throttle = channels[order.index("throttle")]
        except (ValueError, IndexError):
            return
        if aux1 >= self.arm_aux_us:
            # Betaflight refuses to arm unless throttle is low at the arm moment.
            if not self.armed and throttle <= self.arm_throttle_max_us:
                self.armed = True
        else:
            self.armed = False  # AUX1 low always disarms

    def _imu_payload(self) -> bytes:
        vals = list(self.accel) + list(self.gyro) + list(self.mag)
        out = bytearray()
        for v in vals:
            out.extend(int(v).to_bytes(2, "little", signed=True))
        return bytes(out)

    def _attitude_payload(self) -> bytes:
        out = bytearray()
        for v in self.attitude_ddeg:
            out.extend(int(v).to_bytes(2, "little", signed=True))
        return bytes(out)


# ── Real UART channel (pyserial) ────────────────────────────────────────────────
class PySerialChannel:
    """Real UART via pyserial. Lazily imported so tests never need the dependency."""

    is_hardware = True

    def __init__(self, port: str, baud: int = 230400):
        try:
            import serial  # type: ignore
        except ImportError as exc:  # pragma: no cover - hardware path
            raise RuntimeError("pyserial is required for a real UART channel (pip install pyserial)") from exc
        # timeout=0 -> non-blocking reads; write_timeout -> a write never blocks forever if the FC's USB
        # stops draining (a dead/half-connected link). On timeout pyserial raises -> our write() catches it.
        self._ser = serial.Serial(port=port, baudrate=baud, timeout=0, write_timeout=0.1)

    def write(self, data: bytes) -> int:  # pragma: no cover - hardware path
        try:
            return int(self._ser.write(data))
        except Exception:
            return 0                      # transient USB hiccup -> drop this frame, keep the loop alive

    def read(self, max_bytes: int = 4096) -> bytes:  # pragma: no cover - hardware path
        # A flaky USB-CDC link can report readiness then vanish mid-read; treat any transient serial
        # error as "no data this tick" rather than crashing the flight loop (a true persistent loss is
        # then handled upstream / by the FC's own MSP-override failsafe -> reverts to the receiver).
        try:
            waiting = getattr(self._ser, "in_waiting", 0)
            if not waiting:
                return b""
            return bytes(self._ser.read(min(waiting, max_bytes)))
        except Exception:
            return b""

    def close(self) -> None:  # pragma: no cover - hardware path
        self._ser.close()


# ── The link ────────────────────────────────────────────────────────────────────
@dataclass
class LinkStats:
    frames_sent: int = 0
    frames_received: int = 0
    last_tx_s: float | None = None
    last_rx_s: float | None = None


class MspLink:
    """MSP v2 transport over a ByteChannel. Moves bytes only -- no flight authority."""

    def __init__(self, channel: ByteChannel, *, clock: Callable[[], float] = time.monotonic):
        self._channel = channel
        self._clock = clock
        self._decoder = MspDecoder()
        self.stats = LinkStats()

    @classmethod
    def for_bench(cls, fc: MockFcChannel, *, clock: Callable[[], float] = time.monotonic) -> "MspLink":
        return cls(fc, clock=clock)

    @classmethod
    def open_serial(cls, port: str, baud: int = 230400, *, hardware_authorized: bool,
                    clock: Callable[[], float] = time.monotonic) -> "MspLink":
        """Open a REAL UART. Refuses unless hardware_authorized=True (the runtime UART gate)."""
        if not hardware_authorized:
            raise PermissionError(
                "refusing to open a real UART without hardware_authorized=True "
                "(use MspLink.for_bench(MockFcChannel()) for dry/bench work)"
            )
        return cls(PySerialChannel(port, baud), clock=clock)

    @property
    def is_hardware(self) -> bool:
        return bool(getattr(self._channel, "is_hardware", False))

    # tx ----------------------------------------------------------------------------------
    def send(self, function: int, payload: bytes = b"", *, direction: int = mc.DIR_TO_FC) -> int:
        n = self._channel.write(mc.encode_msp_v2(function, payload, direction=direction))
        self.stats.frames_sent += 1
        self.stats.last_tx_s = self._clock()
        return n

    def send_set_raw_rc(self, channels_us: list[int]) -> int:
        n = self._channel.write(mc.encode_set_raw_rc(channels_us))
        self.stats.frames_sent += 1
        self.stats.last_tx_s = self._clock()
        return n

    def request(self, function: int) -> None:
        """Send an empty MSP request (telemetry poll)."""
        self.send(function, b"")

    # rx ----------------------------------------------------------------------------------
    def poll(self) -> list[MspFrame]:
        frames = self._decoder.feed(self._channel.read())
        if frames:
            self.stats.frames_received += len(frames)
            self.stats.last_rx_s = self._clock()
        return frames

    def time_since_rx_s(self, now: float | None = None) -> float | None:
        if self.stats.last_rx_s is None:
            return None
        return (self._clock() if now is None else now) - self.stats.last_rx_s

    def close(self) -> None:
        self._channel.close()
