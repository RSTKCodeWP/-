from __future__ import annotations

import glob
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .auth import auth_middleware, auth_required, generate_token, verify_token, verify_ws_token
from .config import ROOT_DIR, VERSION, aio, cfg
from .drone_link import DroneLink
from .firmware import router as firmware_router
from .param_meta import get_metadata
from .terrain import router as terrain_router
from .tiles import router as tiles_router
from .video import router as video_router
from .ws_manager import WSManager

DIST_DIR = ROOT_DIR / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.link = DroneLink()
    app.state.ws_mgr = WSManager(app.state.link)
    yield
    app.state.link.disconnect()


app = FastAPI(
    title="Argus GCS API",
    description="Universal Web Ground Control Station — REST API for MAVLink vehicle control",
    version=VERSION,
    lifespan=lifespan,
)

_cors_origins = [
    s.strip()
    for s in os.environ.get(
        "ARGUS_CORS_ORIGINS",
        "http://localhost:5173,http://localhost:8100,http://127.0.0.1:5173,http://127.0.0.1:8100",
    ).split(",")
    if s.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(video_router)
app.include_router(tiles_router)
app.include_router(terrain_router)
app.include_router(firmware_router)
app.middleware("http")(auth_middleware)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint."""
    return {"ok": True}


@app.get("/api/session", tags=["System"])
async def api_session(request: Request):
    """Current session info: connected clients, vehicle state."""
    link = request.app.state.link
    mgr = request.app.state.ws_mgr
    return {
        "clients": mgr.client_count,
        "connected": link.connected,
        "armed": link.vehicle.armed,
        "sysid": link.vehicle.sysid,
        "mode": link.vehicle.mode,
        "vtype": link.vehicle.vtype_raw,
    }


@app.get("/api/version", tags=["System"])
async def api_version():
    import subprocess

    def _git_hash() -> str:
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=str(ROOT_DIR),
                    timeout=cfg.GIT_HASH_TIMEOUT,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except (OSError, subprocess.SubprocessError):
            return ""

    git_hash = await aio(_git_hash)
    return {
        "version": VERSION,
        "git": git_hash,
        "protocols": ["standard", "pllink"],
        "vehicles": ["copter", "plane", "rover", "sub"],
        "features": ["i18n", "param_meta", "gamepad", "pwa", "global_tiles"],
    }


@app.post("/api/auth/login", tags=["Auth"])
async def api_auth_login(request: Request):
    """Authenticate with token. Returns ok if valid."""
    body = await request.json()
    token = body.get("token", "")
    if verify_token(token):
        return {"ok": True}
    return JSONResponse(status_code=401, content={"ok": False, "error": "invalid token"})


@app.get("/api/auth/status", tags=["Auth"])
async def api_auth_status():
    """Check if authentication is enabled."""
    return {"auth_required": auth_required()}


@app.post("/api/auth/generate", tags=["Auth"])
async def api_auth_generate(request: Request):
    """Generate a new auth token (only works if no token exists yet)."""
    client = request.client
    if not client or client.host not in ("127.0.0.1", "::1"):
        return JSONResponse(status_code=403, content={"error": "token generation only allowed from localhost"})
    if auth_required():
        return JSONResponse(status_code=403, content={"error": "token already exists"})
    token = generate_token()
    return {"token": token}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    origin = (ws.headers.get("origin") or "").rstrip("/")
    if origin and origin not in _cors_origins:
        await ws.close(code=4003, reason="origin not allowed")
        return
    if not verify_ws_token(ws):
        await ws.close(code=4001, reason="unauthorized")
        return
    await app.state.ws_mgr.handle_client(ws)


@app.get("/api/param_meta")
async def api_param_meta(vehicle: str = "copter"):
    return await aio(get_metadata, vehicle)


@app.get("/api/ports")
async def api_ports():
    if sys.platform == "win32":
        ports = []
        try:
            from serial.tools.list_ports import comports

            ports = sorted(p.device for p in comports())
        except (ImportError, OSError):
            pass
        return {"ports": ports or ["COM3"]}
    else:
        found = await aio(lambda: sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")))
        return {"ports": found or ["/dev/ttyUSB0"]}


@app.get("/api/log")
async def api_log():
    link: DroneLink = app.state.link
    path = link.get_log_path()
    if path:
        import os

        return FileResponse(
            path,
            media_type="text/csv",
            filename=os.path.basename(path),
        )
    return Response(status_code=404, content="No active log")


if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")
    if (DIST_DIR / "images").exists():
        app.mount("/images", StaticFiles(directory=str(DIST_DIR / "images")), name="images")
    if (DIST_DIR / "lib").exists():
        app.mount("/lib", StaticFiles(directory=str(DIST_DIR / "lib")), name="lib")

    @app.get("/manifest.json")
    async def manifest():
        return FileResponse(str(DIST_DIR / "manifest.json"))

    @app.get("/sw.js")
    async def service_worker():
        return FileResponse(str(DIST_DIR / "sw.js"), media_type="application/javascript")

    @app.get("/")
    async def index():
        return FileResponse(str(DIST_DIR / "index.html"))
