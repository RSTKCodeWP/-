"""Tests for backend/server.py — sidecar entry point."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.server import _open_browser, main


class TestOpenBrowser:
    @patch("webbrowser.open")
    @patch("urllib.request.urlopen")
    def test_opens_browser_after_health_ok(self, mock_urlopen, mock_open):
        mock_urlopen.return_value = MagicMock()
        _open_browser(8100)
        mock_open.assert_called_once_with("http://localhost:8100")

    @patch("webbrowser.open")
    @patch("urllib.request.urlopen", side_effect=OSError("not ready"))
    def test_retries_on_failure(self, mock_urlopen, mock_open):
        _open_browser(8100)
        assert mock_urlopen.call_count == 30
        mock_open.assert_not_called()


class TestMain:
    @patch("backend.server.uvicorn.run")
    def test_default_args(self, mock_run):
        # Patch Thread: without --no-browser, main() spawns a daemon that
        # polls http://127.0.0.1:8100/health every 0.3s for ~9s. Left running,
        # that thread's real urlopen leaks into whatever test patches urlopen
        # next (backend.tiles.urlreq is the same module object) — a cross-test
        # flake that fails test_unit_tile_proxy's assert_called_once.
        with patch("sys.argv", ["server.py"]), patch("backend.server.threading.Thread"):
            main()
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["port"] == 8100
        assert call_kwargs.kwargs["host"] == "127.0.0.1"

    @patch("backend.server.uvicorn.run")
    def test_custom_port(self, mock_run):
        with patch("sys.argv", ["server.py", "--port", "9000", "--no-browser"]):
            main()
        assert mock_run.call_args.kwargs["port"] == 9000

    @patch("backend.server.uvicorn.run")
    def test_no_browser_flag(self, mock_run):
        with patch("sys.argv", ["server.py", "--no-browser"]), patch("backend.server.threading.Thread") as mock_thread:
            main()
            mock_thread.assert_not_called()
