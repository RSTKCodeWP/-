import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def build_app(dispatcher, on_startup=None, telemetry_interval_s: float = 0.5) -> FastAPI:
    """Build the websocket API around a dispatcher (injected for testability).

    on_startup: optional zero-arg coroutine awaited once when the event loop starts.
    telemetry_interval_s: period of the server->client telemetry push stream.
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if on_startup is not None:
            await on_startup()
        yield

    app = FastAPI(title="flight-safety", lifespan=lifespan)

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        send_lock = asyncio.Lock()
        current: asyncio.Task | None = None

        async def send(payload: dict) -> None:
            async with send_lock:
                await socket.send_json(payload)

        async def push_loop() -> None:
            # Sleep BEFORE the first emit so a fast request/reply still arrives
            # first (keeps the existing request/reply tests deterministic).
            while True:
                await asyncio.sleep(telemetry_interval_s)
                try:
                    data = await dispatcher.telemetry()
                    await send({"type": "telemetry", "data": data})
                except Exception as e:  # never let the push loop kill the connection
                    await send({"type": "telemetry", "error": str(e)})

        push = asyncio.create_task(push_loop())
        try:
            while True:
                msg = await socket.receive_json()
                kind = msg.get("type")
                mid = msg.get("id")

                def tag(reply: dict) -> dict:
                    return {**reply, "id": mid} if mid is not None else reply

                if kind == "command":
                    if current is not None and not current.done():
                        await send(tag({"status": "rejected",
                                        "reason": "busy: a command is already executing"}))
                    else:
                        async def run_command(command: dict, rid) -> None:
                            try:
                                result = await dispatcher.handle(command)
                            except asyncio.CancelledError:
                                return
                            await send({**result, "id": rid} if rid is not None else result)
                        current = asyncio.create_task(run_command(msg.get("command", {}), mid))
                elif kind == "abort":
                    if current is not None and not current.done():
                        current.cancel()
                    await dispatcher.abort()
                    await send(tag({"status": "aborted"}))
                elif kind == "get_telemetry":
                    try:
                        data = await dispatcher.telemetry()
                        await send(tag({"type": "telemetry", "data": data}))
                    except Exception as e:
                        await send(tag({"type": "telemetry", "error": str(e)}))
                elif kind == "manual":
                    dispatcher.manual_setpoint(
                        float(msg.get("forward", 0.0)), float(msg.get("right", 0.0)),
                        float(msg.get("down", 0.0)), float(msg.get("yaw_rate", 0.0)))
                    # high-rate, fire-and-forget: no reply
                else:
                    await send(tag({"status": "error", "reason": "unknown type"}))
        except WebSocketDisconnect:
            return
        finally:
            push.cancel()
            if current is not None and not current.done():
                current.cancel()

    return app
