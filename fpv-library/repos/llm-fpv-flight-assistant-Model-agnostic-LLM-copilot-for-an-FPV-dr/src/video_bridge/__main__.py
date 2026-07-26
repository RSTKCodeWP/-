import asyncio

import uvicorn

from video_bridge.config import VideoBridgeSettings
from video_bridge.frames import FrameBuffer
from video_bridge.mjpeg import build_video_app
from video_bridge.source import subscribe


async def run() -> None:
    settings = VideoBridgeSettings()
    buffer = FrameBuffer()
    node = None
    if settings.topic:
        try:
            # node stays referenced as a local for the lifetime of serve() below, keeping the gz subscription alive.
            node = subscribe(settings.topic, buffer, settings.jpeg_quality, settings.channels)
            print(f"video-bridge: subscribed to {settings.topic}")
        except Exception as e:  # no gz / no camera -> serve unhealthy, dashboard falls back
            print(f"video-bridge: camera unavailable ({e}); serving without frames")
    else:
        print("video-bridge: VB_TOPIC unset; serving without frames (set it from the spike)")

    app = build_video_app(buffer)
    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
