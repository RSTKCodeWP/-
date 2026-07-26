import asyncio
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles


class Broadcaster:
    """Fan-out of server->browser frames to every connected socket sender."""

    def __init__(self) -> None:
        self._senders: list = []

    def register(self, send) -> None:
        self._senders.append(send)

    def unregister(self, send) -> None:
        if send in self._senders:
            self._senders.remove(send)

    async def broadcast(self, message: dict) -> None:
        for send in list(self._senders):
            try:
                await send(message)
            except Exception:
                self.unregister(send)


def attach_telemetry(safety_client, broadcaster: Broadcaster) -> None:
    """Forward safety telemetry pushes to all browsers (scheduled on the loop)."""
    tasks: set[asyncio.Task] = set()

    def on_telemetry(data: dict) -> None:
        task = asyncio.create_task(broadcaster.broadcast({"type": "telemetry", "data": data}))
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    safety_client.subscribe_telemetry(on_telemetry)


def build_app(hub, video_stream_url: str, broadcaster: Broadcaster | None = None,
              static_dir: str | None = None, client=None) -> FastAPI:
    app = FastAPI(title="dashboard")
    bc = broadcaster or Broadcaster()

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        lock = asyncio.Lock()

        async def send(msg: dict) -> None:
            async with lock:
                await socket.send_json(msg)

        async def emit(frame: dict) -> None:
            await bc.broadcast(frame)

        bc.register(send)
        await send({"type": "video_status", "url": video_stream_url, "ok": True})
        await send({"type": "control_state", "who": hub.control})
        try:
            while True:
                msg = await socket.receive_json()
                kind = msg.get("type")
                try:
                    if kind == "chat":
                        await hub.handle_chat(msg.get("text", ""), emit)
                    elif kind == "confirm":
                        await hub.handle_confirm(emit)
                    elif kind == "cancel":
                        await hub.handle_cancel(emit)
                    elif kind == "abort":
                        await hub.handle_abort(emit)
                    elif kind == "take_control":
                        await hub.handle_take_control(emit)
                    elif kind == "release_control":
                        await hub.handle_release_control(emit)
                    elif kind == "quick":
                        await hub.handle_quick(msg.get("verb", ""), msg.get("args", {}), emit)
                    elif kind == "manual" and client is not None:
                        await client.send_manual(
                            float(msg.get("forward", 0.0)), float(msg.get("right", 0.0)),
                            float(msg.get("down", 0.0)), float(msg.get("yaw_rate", 0.0)))
                    else:
                        await send({"type": "narration", "text": "Unknown message."})
                except Exception as e:
                    # A hub/agent/safety failure must surface as feedback, not drop the socket.
                    await send({"type": "narration", "text": f"Error handling request: {e}"})
        except WebSocketDisconnect:
            return
        finally:
            bc.unregister(send)

    if static_dir and os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app
