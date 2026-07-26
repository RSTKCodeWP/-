"""Live-source stubs raise behind the same interfaces (Task 1.6)."""

import pytest

from hades.ingest.frame_source import FrameSource
from hades.ingest.live_sources import CrsfSerialSource, UvcFrameSource
from hades.ingest.telemetry_source import TelemetrySource


def test_uvc_frame_source_is_a_framesource():
    assert issubclass(UvcFrameSource, FrameSource)


def test_crsf_serial_source_is_a_telemetry_source():
    assert issubclass(CrsfSerialSource, TelemetrySource)


def test_uvc_frame_source_raises_not_implemented():
    src = UvcFrameSource(device=0)
    with pytest.raises(NotImplementedError):
        list(src)


def test_crsf_serial_source_raises_not_implemented():
    src = CrsfSerialSource(port="/dev/tty.fake")
    with pytest.raises(NotImplementedError):
        list(src)
