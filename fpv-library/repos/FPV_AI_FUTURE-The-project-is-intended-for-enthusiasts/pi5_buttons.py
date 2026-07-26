"""Two physical operator buttons on the Pi 5 GPIO — debounced rising-edge source for the OperatorConsole.

BUTTON 1 (CAPTURE / LAUNCH) and BUTTON 2 (CHANGE / CANCEL), each wired between a GPIO and GND with the
internal pull-up (pressed = LOW).  gpiozero (lgpio backend) is the Pi-5-correct GPIO library; it is
imported LAZILY so this module and its tests run off-Pi.  Each press latches a rising edge that ``poll()``
consumes once — so a press is never missed between loop ticks and never double-counted.

Default pins (BCM): CAPTURE = GPIO23 (header pin 16), CANCEL = GPIO24 (header pin 18).
"""
from __future__ import annotations

import threading
from typing import Protocol


class ButtonSource(Protocol):
    def poll(self) -> "tuple[bool, bool]": ...   # (capture_edge, cancel_edge), consumed on read
    def close(self) -> None: ...


class GpioButtons:
    """Real Pi-5 GPIO buttons via gpiozero. Rising edges are latched in a callback and drained by poll()."""

    def __init__(self, capture_pin: int = 23, cancel_pin: int = 24, *, bounce_s: float = 0.05) -> None:
        from gpiozero import Button  # lazy: Pi-only (needs lgpio)
        self._lock = threading.Lock()
        self._cap_edge = False
        self._cxl_edge = False
        # pull_up=True -> pressed pulls the line LOW; gpiozero fires when_pressed on that edge.
        self._cap = Button(capture_pin, pull_up=True, bounce_time=bounce_s)
        self._cxl = Button(cancel_pin, pull_up=True, bounce_time=bounce_s)
        self._cap.when_pressed = self._on_capture
        self._cxl.when_pressed = self._on_cancel

    def _on_capture(self) -> None:
        with self._lock:
            self._cap_edge = True

    def _on_cancel(self) -> None:
        with self._lock:
            self._cxl_edge = True

    def poll(self) -> "tuple[bool, bool]":
        with self._lock:
            c, x = self._cap_edge, self._cxl_edge
            self._cap_edge = self._cxl_edge = False
        return c, x

    def close(self) -> None:
        for b in (getattr(self, "_cap", None), getattr(self, "_cxl", None)):
            try:
                if b is not None:
                    b.close()
            except Exception:
                pass


class FakeButtons:
    """Scriptable button source for tests / sim / keyboard bridge. Queue presses, poll drains one tick."""

    def __init__(self) -> None:
        self._cap = False
        self._cxl = False

    def press_capture(self) -> None:
        self._cap = True

    def press_cancel(self) -> None:
        self._cxl = True

    def poll(self) -> "tuple[bool, bool]":
        c, x = self._cap, self._cxl
        self._cap = self._cxl = False
        return c, x

    def close(self) -> None:
        pass


def make_buttons(*, sim: bool = False, capture_pin: int = 23, cancel_pin: int = 24) -> ButtonSource:
    """Factory: FakeButtons in sim, else real GpioButtons (raises off-Pi if gpiozero is missing)."""
    if sim:
        return FakeButtons()
    return GpioButtons(capture_pin, cancel_pin)
