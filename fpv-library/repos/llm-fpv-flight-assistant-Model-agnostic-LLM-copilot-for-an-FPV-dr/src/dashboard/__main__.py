import asyncio
import os

import httpx
import uvicorn

from assistant.agent import Agent
from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider
from assistant.safety_client import SafetyClient
from dashboard.app import Broadcaster, attach_telemetry, build_app
from dashboard.config import DashboardSettings
from dashboard.hub import DashboardHub


async def poll_once(http, health_url: str, stream_url: str) -> dict:
    """One video-status probe; never raises (unreachable bridge -> ok:false)."""
    try:
        resp = await http.get(health_url)
        resp.raise_for_status()
        ok = bool(resp.json().get("ok"))
    except Exception:
        ok = False
    return {"type": "video_status", "ok": ok, "url": stream_url}


async def _video_status_loop(broadcaster, dash: DashboardSettings) -> None:
    async with httpx.AsyncClient(timeout=2.0) as http:
        while True:
            await broadcaster.broadcast(
                await poll_once(http, dash.video_health_url, dash.video_stream_url))
            await asyncio.sleep(dash.video_poll_interval_s)


async def run() -> None:
    a_settings = AssistantSettings()
    dash = DashboardSettings()
    if not a_settings.openrouter_api_key:
        raise SystemExit("Set AS_OPENROUTER_API_KEY in .env")

    client = SafetyClient(dash.safety_url)
    try:
        await client.connect()
    except OSError as e:
        raise SystemExit(
            f"Safety service unreachable at {dash.safety_url} ({e}); "
            f"start it first: python -m flight_safety")
    agent = Agent(OpenRouterProvider.from_settings(a_settings), client)
    hub = DashboardHub(agent, client)

    broadcaster = Broadcaster()
    attach_telemetry(client, broadcaster)

    static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    app = build_app(hub, dash.video_stream_url, broadcaster=broadcaster,
                    static_dir=os.path.abspath(static_dir), client=client)

    poll_task = asyncio.create_task(_video_status_loop(broadcaster, dash))
    config = uvicorn.Config(app, host=dash.host, port=dash.port, log_level="info")
    try:
        await uvicorn.Server(config).serve()
    finally:
        poll_task.cancel()
        await client.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
