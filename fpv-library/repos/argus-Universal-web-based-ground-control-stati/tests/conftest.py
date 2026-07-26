"""
Shared fixtures: simulator + backend + WebSocket client.
"""

import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
SIM_SCRIPT = ROOT_DIR / "scripts" / "sim_pllink.py"

SIM_PORT = 15770
BACKEND_PORT = 18100


def _wait_tcp(port, timeout=10):
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            s.close()
            return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"port {port} not ready within {timeout}s")


@pytest.fixture(scope="session")
def sim_process():
    proc = subprocess.Popen(
        [sys.executable, str(SIM_SCRIPT), str(SIM_PORT)],
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _wait_tcp(SIM_PORT, timeout=10)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def backend_process(sim_process):
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
            "--log-level",
            "warning",
        ],
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.3)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def backend_url(backend_process):
    return f"http://127.0.0.1:{BACKEND_PORT}"


@pytest.fixture(scope="session")
def ws_url(backend_process):
    return f"ws://127.0.0.1:{BACKEND_PORT}/ws"


@pytest.fixture
def sim_port():
    return SIM_PORT


@pytest.fixture(autouse=True)
def _reset_backend_globals():
    """Reset mutable module-level globals after each test to prevent leakage."""
    yield
    import backend.tiles as _tiles

    _tiles._tile_count = -1

    import backend.auth as _auth

    _auth._token = None

    import backend.video as _video

    if _video._active_proc is not None:
        try:
            _video._active_proc.terminate()
        except Exception:
            pass
        _video._active_proc = None

    import backend.commands._mission as _mission

    if _mission._mission_timer is not None:
        _mission._mission_timer.cancel()
        _mission._mission_timer = None
