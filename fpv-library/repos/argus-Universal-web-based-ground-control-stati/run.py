#!/usr/bin/env python3
"""
Argus GCS — one-click launcher.
Starts simulator + backend on a single port, opens browser.

Usage:
    python run.py              (backend only, connect real hardware)
    python run.py --sim        (start simulator for testing)
"""
import argparse
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SIM_SCRIPT = ROOT_DIR / 'scripts' / 'sim_pllink.py'


def main():
    parser = argparse.ArgumentParser(description='Argus GCS')
    parser.add_argument('--sim', action='store_true', help='Start simulator on port 5770')
    parser.add_argument('--host', default='127.0.0.1', help='Bind address (default: 127.0.0.1; use 0.0.0.0 to expose on LAN)')
    parser.add_argument('--port', type=int, default=8100, help='HTTP port (default: 8100)')
    args = parser.parse_args()

    sim_proc = None
    if args.sim:
        print('[SIM] Starting simulator on port 5770...')
        sim_proc = subprocess.Popen(
            [sys.executable, str(SIM_SCRIPT), '5770'],
            cwd=str(ROOT_DIR),
        )
        # Poll for the sim TCP port instead of a blind sleep — on slow boxes
        # the previous `time.sleep(1)` could let the backend start before the
        # sim bound its listener, producing a confusing first connect failure.
        import socket
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                s = socket.create_connection(('127.0.0.1', 5770), timeout=0.3)
                s.close()
                break
            except OSError:
                if sim_proc.poll() is not None:
                    print('[SIM] simulator exited unexpectedly (code %d)' % sim_proc.returncode)
                    sim_proc = None
                    break
                time.sleep(0.1)

    print('=' * 50)
    print('  Argus GCS')
    print('  http://localhost:%d' % args.port)
    if args.sim:
        print('  Simulator: tcp:localhost:5770')
    print('  Ctrl+C to stop')
    print('=' * 50)

    import os
    if not (ROOT_DIR / 'dist' / 'index.html').exists():
        # Without a build, backend/app.py never registers the "/" route —
        # auto-opening :8100 would just show a 404.
        print('[WEB] No production build (dist/) found — not opening a browser.')
        print('[WEB] Dev mode: run "npm run dev" in another terminal, then open http://127.0.0.1:5173')
    elif not os.environ.get('ARGUS_NO_BROWSER'):
        webbrowser.open('http://localhost:%d' % args.port)

    try:
        import logging  # noqa: I001

        import uvicorn

        class _ShutdownFilter(logging.Filter):
            def filter(self, record):
                if record.exc_info and record.exc_info[1]:
                    name = type(record.exc_info[1]).__name__
                    if name in ('CancelledError', 'KeyboardInterrupt'):
                        return False
                return True

        logging.getLogger('uvicorn.error').addFilter(_ShutdownFilter())

        if sys.platform == 'win32':
            import asyncio
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        uvicorn.run(
            'backend.app:app',
            host=args.host,
            port=args.port,
            log_level='warning',
        )
    except KeyboardInterrupt:
        pass
    finally:
        if sim_proc:
            sim_proc.terminate()
            try:
                sim_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # SIGTERM ignored — sim is wedged inside socket recv. Force-kill
                # so the launcher doesn't hang on Ctrl+C.
                sim_proc.kill()
                sim_proc.wait()


if __name__ == '__main__':
    main()
