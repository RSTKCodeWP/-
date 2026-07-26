"""Operator-promote over the WS command channel (Task 5.10 / M6, transport end).

The JSON channel is bidirectional: the client sends `{"type":"promote","track_id":N}` and the
service replies with the refined ContactRecord for that track on the same socket. Drives real
localhost sockets like test_ws_emit. The .srt fixture is position-only, so the promoted record
is an honest CUE_ONLY (the successful-fuse path is unit-tested in test_promote.py).
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


def test_promote_command_returns_a_refined_record_over_ws():
    import websockets

    async def run() -> None:
        loop = ServiceLoop(
            clip=CLIP, telemetry=SRT,
            detector=StubDetector(box_xyxy=(400.0, 300.0, 460.0, 420.0), conf=0.8),
        )
        server = asyncio.create_task(
            serve(loop, binary_port=8797, json_port=8798, fps=12.0, max_frames=12)
        )
        await asyncio.sleep(0.2)  # let the servers bind

        promoted = None
        try:
            async with websockets.connect("ws://127.0.0.1:8798") as ws:
                # drain until we learn a real track_id from an emitted contact
                track_id = None
                while track_id is None:
                    obj = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                    if obj["type"] == "contact":
                        track_id = obj["track_id"]

                # SEND the promote command for that track
                await ws.send(json.dumps({"type": "promote", "track_id": track_id}))

                # the next contact carrying THIS track_id from the promote reply
                deadline = 3.0
                while promoted is None:
                    obj = json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline))
                    if obj["type"] == "contact" and obj["track_id"] == track_id:
                        promoted = obj
        finally:
            server.cancel()
            with pytest.raises((asyncio.CancelledError, Exception)):
                await server

        assert promoted is not None
        assert promoted["type"] == "contact"
        # position-only fixture → honest CUE_ONLY with no fabricated coordinate
        assert promoted["actionability_class"] == "CUE_ONLY"
        assert promoted["lat"] is None and promoted["lon"] is None

    asyncio.run(run())


def test_malformed_command_does_not_crash_the_service():
    import websockets

    async def run() -> None:
        loop = ServiceLoop(
            clip=CLIP, telemetry=SRT,
            detector=StubDetector(box_xyxy=(400.0, 300.0, 460.0, 420.0), conf=0.8),
        )
        server = asyncio.create_task(
            serve(loop, binary_port=8799, json_port=8800, fps=12.0, max_frames=12)
        )
        await asyncio.sleep(0.2)
        ok = False
        try:
            async with websockets.connect("ws://127.0.0.1:8800") as ws:
                await ws.send("{not json")  # garbage
                await ws.send(json.dumps({"type": "promote"}))  # missing track_id
                await ws.send(json.dumps({"type": "unknown"}))  # unknown command
                # the service still streams normally after garbage
                obj = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                ok = obj["type"] in {"detection", "contact"}
        finally:
            server.cancel()
            with pytest.raises((asyncio.CancelledError, Exception)):
                await server
        assert ok  # garbage commands ignored; the feed keeps flowing

    asyncio.run(run())
