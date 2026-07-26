"""Manual smoke: prints the first few frames the dashboard pushes to a browser.

Prereqs (separate terminals): SITL, `python -m flight_safety`, `python -m dashboard`.
Usage: python scripts/dashboard_smoke.py
"""
import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect("ws://127.0.0.1:8080/ws") as ws:
        await ws.send(json.dumps({"type": "chat", "text": "what is my battery?"}))
        for _ in range(10):
            print(json.loads(await ws.recv()))


if __name__ == "__main__":
    asyncio.run(main())
