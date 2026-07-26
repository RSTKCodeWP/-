#!/usr/bin/env python3
"""Standalone entry point for the HackRF multi-band monitor.

Bundled by PyInstaller into a single self-contained executable (see
packaging/build_macos.sh and .github/workflows/build-executables.yml). It:

  1. locates the HackRF SDK tools (hackrf_info / hackrf_sweep + native libs)
     packaged alongside it under ``hackrf_tools/``,
  2. points hackrf_api at them via HACKRF_BIN_DIR (+ the dynamic-loader path on
     macOS / PATH on Windows so the bundled libs resolve),
  3. starts the web dashboard and opens a browser.

Run from source it just falls back to a system install (brew / vendor/bin).
"""
import os
import sys
import time
import threading
import webbrowser


def _resource_dir():
    # PyInstaller unpacks bundled data to sys._MEIPASS at runtime.
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _setup_bundled_tools():
    """If SDK tools are bundled, make them the ones hackrf_api uses."""
    tools = os.path.join(_resource_dir(), "hackrf_tools")
    if not os.path.isdir(tools):
        return None
    os.environ["HACKRF_BIN_DIR"] = tools
    if sys.platform == "darwin":
        cur = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = tools + (os.pathsep + cur if cur else "")
    elif sys.platform.startswith("win"):
        os.environ["PATH"] = tools + os.pathsep + os.environ.get("PATH", "")
    # onefile extraction can drop the exec bit; restore it for the binaries.
    if not sys.platform.startswith("win"):
        for fn in os.listdir(tools):
            try:
                os.chmod(os.path.join(tools, fn), 0o755)
            except OSError:
                pass
    return tools


def main():
    _setup_bundled_tools()
    port = int(os.environ.get("HACKRF_PORT", os.environ.get("PORT", "8080")))
    # Import only after the env is set so core.find_binaries picks up HACKRF_BIN_DIR.
    from hackrf_api.webapp import serve

    def _open():
        time.sleep(2.0)
        try:
            webbrowser.open(f"http://127.0.0.1:{port}/")
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()
    print(f"HackRF Multi-Band Monitor → http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    serve(port=port)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("\nERROR:", e)
        print("\nMake sure a HackRF is connected. If a scan fails with error -1005, "
              "the device firmware is too old for sweep mode — update it (see README).")
        if sys.platform.startswith("win"):
            try:
                input("\nPress Enter to close...")
            except EOFError:
                pass
        sys.exit(1)
