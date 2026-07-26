import asyncio

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

_BOUNDARY = "frame"


def mjpeg_chunk(jpeg: bytes) -> bytes:
    """One multipart/x-mixed-replace part wrapping a JPEG frame."""
    return (
        f"--{_BOUNDARY}\r\n"
        f"Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg)}\r\n\r\n"
    ).encode() + jpeg + b"\r\n"


def build_video_app(buffer, max_age_s: float = 2.0, frame_interval_s: float = 0.05) -> FastAPI:
    app = FastAPI(title="video-bridge")

    @app.get("/health")
    def health() -> dict:
        return {"ok": buffer.is_fresh(max_age_s), "age_s": buffer.age_s()}

    @app.get("/stream.mjpg")
    def stream() -> StreamingResponse:
        async def gen():
            while True:
                jpeg = buffer.latest()
                if jpeg is not None:
                    yield mjpeg_chunk(jpeg)
                await asyncio.sleep(frame_interval_s)
        return StreamingResponse(
            gen(), media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}")

    return app
