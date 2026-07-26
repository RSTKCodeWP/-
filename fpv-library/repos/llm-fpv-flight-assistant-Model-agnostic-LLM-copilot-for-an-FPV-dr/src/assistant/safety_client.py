import asyncio
import json
from typing import Callable

import websockets


class SafetyClient:
    """Websocket client to the flight-safety service.

    A single background reader demultiplexes frames: push telemetry frames
    (no correlation id) go to subscribers; command/abort/get_telemetry replies
    are matched to their request by echoed `id` (FIFO fallback for legacy servers).
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._ws = None
        self._reader: asyncio.Task | None = None
        self._next_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._telemetry_subs: list[Callable[[dict], None]] = []
        self.last_telemetry: dict | None = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(self._url)
        self._reader = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            async for raw in self._ws:
                self._dispatch(json.loads(raw))
        except websockets.ConnectionClosed:
            pass
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("safety link closed"))
            self._pending.clear()

    def _dispatch(self, frame: dict) -> None:
        # Push telemetry frames carry no correlation id.
        if frame.get("type") == "telemetry" and "id" not in frame:
            data = frame.get("data")
            if data is not None:
                self.last_telemetry = data
                for cb in self._telemetry_subs:
                    try:
                        cb(data)
                    except Exception:
                        pass  # a bad subscriber must not kill the reader
            return
        # Otherwise it's a reply: match by id, else FIFO fallback.
        fid = frame.get("id")
        fut = None
        if fid is not None and fid in self._pending:
            fut = self._pending.pop(fid)
        elif self._pending:
            # FIFO fallback (legacy/no-id servers). Safe because callers issue
            # one request at a time, so _pending holds at most one entry.
            fut = self._pending.pop(next(iter(self._pending)))
        if fut is not None and not fut.done():
            fut.set_result(frame)

    async def _request(self, payload: dict) -> dict:
        if self._reader is None or self._reader.done():
            raise ConnectionError("safety link not connected")
        rid = self._next_id
        self._next_id += 1
        fut = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        await self._ws.send(json.dumps({**payload, "id": rid}))
        return await fut

    def subscribe_telemetry(self, callback: Callable[[dict], None]) -> None:
        """Register a callback invoked with each pushed telemetry data dict."""
        self._telemetry_subs.append(callback)

    async def get_telemetry(self) -> dict:
        reply = await self._request({"type": "get_telemetry"})
        if reply.get("error"):
            raise RuntimeError(f"telemetry unavailable: {reply['error']}")
        return reply["data"]

    async def send_command(self, command: dict) -> dict:
        return await self._request({"type": "command", "command": command})

    async def abort(self) -> dict:
        return await self._request({"type": "abort"})

    async def send_manual(self, forward: float, right: float,
                          down: float, yaw_rate: float) -> None:
        if self._reader is None or self._reader.done():
            return  # link down -> drop setpoint (watchdog will hover)
        await self._ws.send(json.dumps({"type": "manual", "forward": forward,
                                        "right": right, "down": down, "yaw_rate": yaw_rate}))

    async def takeover(self) -> dict:
        return await self.send_command({"verb": "takeover"})

    async def handback(self) -> dict:
        return await self.send_command({"verb": "handback"})

    async def close(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            self._reader = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
