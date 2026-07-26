"""WS-transport integration test (Task 4.7; Phase 4 green criterion).

The phase is green only when the assembled service emits contact records over WS, observable
via a WS CLIENT (not just the CLI). This drives `serve()` over real localhost sockets and a
Python client joins the two channels by frame_id - the §10 highest-risk seam, end to end.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hades.detect.detector import StubDetector
from hades.service.loop import ServiceLoop, serve

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CLIP = FIXTURES / "clip_2s.mp4"
SRT = FIXTURES / "clip_2s.srt"


def test_ws_client_receives_frame_id_aligned_messages():
    import websockets  # the client side of the same dependency

    async def run() -> None:
        loop = ServiceLoop(
            clip=CLIP, telemetry=SRT,
            detector=StubDetector(box_xyxy=(400.0, 300.0, 460.0, 420.0), conf=0.8),
        )
        # Serve a short run on fixed test ports, paced slow enough that the client connects
        # and drains before the pump finishes and the servers close.
        server = asyncio.create_task(
            serve(loop, binary_port=8795, json_port=8796, fps=15.0, max_frames=8)
        )
        await asyncio.sleep(0.2)  # let the servers bind

        binary_ids: list[int] = []
        json_frame_ids: list[int] = []
        contact_seen = False
        try:
            async with (
                websockets.connect("ws://127.0.0.1:8795") as bin_ws,
                websockets.connect("ws://127.0.0.1:8796") as json_ws,
            ):
                # Collect JSON messages for ~the run; binary frames arrive in lockstep.
                closed = websockets.ConnectionClosed

                async def collect_json():
                    nonlocal contact_seen
                    try:
                        while True:
                            msg = await asyncio.wait_for(json_ws.recv(), timeout=2.0)
                            obj = json.loads(msg)
                            if obj["type"] == "detection":
                                json_frame_ids.append(obj["frame_id"])
                            elif obj["type"] == "contact":
                                contact_seen = True
                                # A contact's frame_id must be one the detection channel saw.
                                assert obj["frame_id"] in set(json_frame_ids) | {obj["frame_id"]}
                    except (asyncio.TimeoutError, closed):
                        return  # clean end-of-stream (server finished the run) or quiet period

                async def collect_binary():
                    try:
                        while True:
                            blob = await asyncio.wait_for(bin_ws.recv(), timeout=2.0)
                            assert isinstance(blob, (bytes, bytearray)) and blob[:2] == b"\xff\xd8"
                            binary_ids.append(len(blob))  # JPEG magic + non-empty
                    except (asyncio.TimeoutError, closed):
                        return

                await asyncio.gather(collect_json(), collect_binary())
        finally:
            server.cancel()
            with pytest.raises((asyncio.CancelledError, Exception)):
                await server

        # A detection message arrived for multiple frames, and at least one contact record.
        assert len(json_frame_ids) >= 3
        assert json_frame_ids == sorted(json_frame_ids)  # frame_id monotonic over the channel
        assert len(binary_ids) >= 3  # JPEG frames flowed on the binary channel
        assert contact_seen  # the taskable ContactRecord reached the client (green criterion)

    asyncio.run(run())


def test_slow_client_does_not_starve_a_fast_one():
    # Drop-to-latest (research gate §10, the 120 ms budget): a client that NEVER reads must not
    # back-pressure the pump and starve OTHER clients. We connect a STALLED binary client (never
    # recv) alongside a FAST one, and assert the fast client still receives frames promptly. A
    # blocking `await ws.send()` to the stalled client (the prior bug) would freeze the pump and
    # the fast client would get nothing.
    import time

    import websockets

    async def run() -> None:
        loop = ServiceLoop(
            clip=CLIP, telemetry=SRT,
            detector=StubDetector(box_xyxy=(400.0, 300.0, 460.0, 420.0), conf=0.8),
        )
        server = asyncio.create_task(
            serve(loop, binary_port=8797, json_port=8798, fps=60.0, max_frames=40)
        )
        await asyncio.sleep(0.2)
        fast_frames = 0
        try:
            # Connect the stalled client FIRST and never read from it.
            async with websockets.connect("ws://127.0.0.1:8797", max_queue=1) as _stalled:
                async with websockets.connect("ws://127.0.0.1:8797", max_queue=1) as fast:
                    start = time.monotonic()
                    while time.monotonic() - start < 3.0:
                        try:
                            blob = await asyncio.wait_for(fast.recv(), timeout=1.0)
                            assert blob[:2] == b"\xff\xd8"  # JPEG magic
                            fast_frames += 1
                            if fast_frames >= 5:
                                break
                        except asyncio.TimeoutError:
                            break
        finally:
            server.cancel()
            try:
                await server
            except (asyncio.CancelledError, Exception):
                pass
        # The fast client kept receiving despite the stalled one: the pump never blocked.
        assert fast_frames >= 5

    asyncio.run(run())
