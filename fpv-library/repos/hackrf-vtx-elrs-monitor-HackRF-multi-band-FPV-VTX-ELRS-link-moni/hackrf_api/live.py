"""
Live spectrum + waterfall viewer for the HackRF One.

Opens a matplotlib window with two stacked panels that update in real time:

    +--------------------------------------------------+
    |  live spectrum (power vs frequency)              |   <- top
    +--------------------------------------------------+
    |  waterfall (frequency x time, newest at bottom)  |   <- below
    +--------------------------------------------------+

It drives `hackrf_sweep` in *continuous* mode (no sweep count), reads its CSV
stream on a background thread, reassembles complete sweeps, and feeds them to a
FuncAnimation. Close the window (or Ctrl-C) to stop; the sweep subprocess is
terminated cleanly.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from collections import deque
from typing import Optional

import numpy as np

from .core import HackRF, HackRFError, HackRFNotFoundError, Spectrum

# Where the live viewer publishes its current peak / top signals so other
# processes (e.g. `python -m hackrf_api peak`) can read "what's loudest now".
DEFAULT_STATUS_PATH = os.path.join(tempfile.gettempdir(), "hackrf_live_status.json")


class _SweepStreamer:
    """Runs hackrf_sweep continuously and yields completed sweeps as rows.

    A "sweep" is reassembled from the CSV lines: each frequency bin is emitted
    once per sweep, so the sweep is complete when a bin we've already recorded
    shows up again (and we've covered a meaningful fraction of the band). Each
    completed sweep is resampled onto a fixed uniform frequency grid and pushed
    onto `self.rows` (a queue of 1-D numpy arrays in dBm).
    """

    def __init__(self, hrf: HackRF, start_hz: float, stop_hz: float,
                 bin_width_hz: int, lna_gain: int, vga_gain: int,
                 amp: bool, antenna_power: bool):
        self.hrf = hrf
        self.start_hz = start_hz
        self.stop_hz = stop_hz
        self.bin_width_hz = bin_width_hz
        n = max(2, int(round((stop_hz - start_hz) / bin_width_hz)))
        self.grid = start_hz + bin_width_hz * (np.arange(n) + 0.5)
        self._expected = n

        args = [
            "-f", f"{int(start_hz/1e6)}:{int(round(stop_hz/1e6))}",
            "-w", str(int(bin_width_hz)),
            "-l", str(int(lna_gain)),
            "-g", str(int(vga_gain)),
        ]
        if amp:
            args += ["-a", "1"]
        if antenna_power:
            args += ["-p", "1"]
        if hrf.serial:
            args = ["-d", hrf.serial] + args
        self._cmd = [hrf.bins["hackrf_sweep"]] + args

        self.rows: "queue.Queue[np.ndarray]" = queue.Queue()
        self.error: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def _emit(self, cur: dict):
        xs = np.array(sorted(cur.keys()), dtype=float)
        ys = np.array([cur[int(k)] for k in xs])
        row = np.interp(self.grid, xs, ys)
        self.rows.put(row)

    def _run(self):
        try:
            self._proc = subprocess.Popen(
                self._cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1, cwd=self.hrf._bin_dir,
            )
        except Exception as e:  # pragma: no cover
            self.error = str(e)
            return

        cur: dict[int, float] = {}
        assert self._proc.stdout is not None
        for line in iter(self._proc.stdout.readline, ""):
            if self._stop.is_set():
                break
            parts = line.split(",")
            if len(parts) < 7:
                continue
            try:
                hz_low = float(parts[2])
                bw = float(parts[4])
                dbs = [float(x) for x in parts[6:]]
            except ValueError:
                continue
            key0 = int(round(hz_low + bw * 0.5))
            # sweep boundary: this bin already seen and we've covered enough band
            if key0 in cur and len(cur) >= self._expected * 0.5:
                self._emit(cur)
                cur = {}
            for i, db in enumerate(dbs):
                cur[int(round(hz_low + bw * (i + 0.5)))] = db

        if self._proc.poll() not in (0, None) and not self._stop.is_set():
            err = (self._proc.stderr.read() if self._proc.stderr else "") or ""
            if err.strip():
                self.error = err.strip()


def live_view(
    start_mhz: float,
    stop_mhz: float,
    bin_width_hz: int = 1_000_000,
    history: int = 200,
    lna_gain: int = 32,
    vga_gain: int = 30,
    amp: bool = True,
    antenna_power: bool = False,
    cmap: str = "turbo",
    serial: Optional[str] = None,
    interval_ms: int = 120,
    status_path: Optional[str] = DEFAULT_STATUS_PATH,
):
    """Open the live spectrum + waterfall window. Blocks until the window closes."""
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    hrf = HackRF(serial=serial)
    if not hrf.is_present():
        raise HackRFNotFoundError("no HackRF device found")

    start_hz, stop_hz = start_mhz * 1e6, stop_mhz * 1e6
    streamer = _SweepStreamer(hrf, start_hz, stop_hz, bin_width_hz,
                              lna_gain, vga_gain, amp, antenna_power)
    grid = streamer.grid
    fmhz = grid / 1e6
    nfreq = grid.size

    # rolling waterfall buffer, newest appended on the right of the deque
    wf = deque(maxlen=history)
    init_floor = -100.0

    fig, (ax_spec, ax_wf) = plt.subplots(
        2, 1, figsize=(12, 8), height_ratios=[1, 2.4], sharex=True,
    )
    fig.canvas.manager.set_window_title(
        f"HackRF live  {start_mhz:.0f}-{stop_mhz:.0f} MHz")

    # --- top: spectrum line ---
    (line,) = ax_spec.plot(fmhz, np.full(nfreq, init_floor), lw=0.8, color="#00b3ff")
    (peakline,) = ax_spec.plot([], [], "r.", ms=6)
    ax_spec.set_ylabel("power (dBm)")
    ax_spec.set_ylim(-100, -10)
    ax_spec.grid(alpha=0.25)
    title = ax_spec.set_title("waiting for first sweep…")

    # --- bottom: waterfall ---
    img0 = np.full((history, nfreq), init_floor)
    im = ax_wf.imshow(
        img0, aspect="auto", origin="upper", cmap=cmap,
        extent=[fmhz[0], fmhz[-1], history, 0],
        vmin=-90, vmax=-30, interpolation="nearest",
    )
    ax_wf.set_xlabel("frequency (MHz)")
    ax_wf.set_ylabel("time  (newest at bottom)  ←")
    cbar = fig.colorbar(im, ax=ax_wf, pad=0.01)
    cbar.set_label("power (dBm)")
    fig.tight_layout()

    state = {"running": True, "sweeps": 0, "last_status": 0.0}

    def publish_status(newest):
        """Write current peak + top signals to the sidecar JSON (throttled)."""
        if not status_path:
            return
        now = time.time()
        if now - state["last_status"] < 0.4:
            return
        state["last_status"] = now
        spec = Spectrum(grid, newest, float(bin_width_hz),
                        1, start_hz, stop_hz)
        peaks = spec.peaks(threshold_db=8.0)[:8]
        pk = int(np.argmax(newest))
        payload = {
            "timestamp": now,
            "start_mhz": start_mhz,
            "stop_mhz": stop_mhz,
            "bin_width_hz": bin_width_hz,
            "sweeps": state["sweeps"],
            "noise_floor_dbm": round(spec.noise_floor_dbm, 2),
            "loudest": {
                "freq_mhz": round(float(fmhz[pk]), 3),
                "power_dbm": round(float(newest[pk]), 2),
            },
            "top_signals": [s.to_dict() for s in peaks],
        }
        tmp = status_path + ".tmp"
        try:
            with open(tmp, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, status_path)
        except OSError:
            pass

    def on_close(_evt):
        state["running"] = False
        streamer.stop()
        if status_path and os.path.exists(status_path):
            try:
                os.remove(status_path)
            except OSError:
                pass

    fig.canvas.mpl_connect("close_event", on_close)

    def update(_frame):
        if streamer.error:
            title.set_text(f"hackrf_sweep error: {streamer.error}")
            return line, im, title

        newest = None
        drained = 0
        while True:
            try:
                row = streamer.rows.get_nowait()
            except queue.Empty:
                break
            wf.append(row)
            newest = row
            drained += 1
            state["sweeps"] += 1

        if newest is None:
            return line, im, title

        # top spectrum = newest sweep
        line.set_ydata(newest)
        pk = int(np.argmax(newest))
        peakline.set_data([fmhz[pk]], [newest[pk]])
        publish_status(newest)

        # adaptive y-limits on the spectrum
        lo = np.percentile(newest, 5) - 5
        hi = newest.max() + 5
        ax_spec.set_ylim(lo, hi)

        # build the waterfall image: bottom rows = newest
        arr = np.full((history, nfreq), np.nan)
        rows = list(wf)
        if rows:
            block = np.array(rows[-history:])
            arr[history - block.shape[0]:, :] = block
        im.set_data(arr)
        # robust colour limits from recent data
        valid = arr[~np.isnan(arr)]
        if valid.size:
            im.set_clim(np.percentile(valid, 5), np.percentile(valid, 99))

        title.set_text(
            f"{start_mhz:.0f}-{stop_mhz:.0f} MHz   "
            f"bin {bin_width_hz/1e3:.0f} kHz   "
            f"peak {newest[pk]:.1f} dBm @ {fmhz[pk]:.1f} MHz   "
            f"sweeps {state['sweeps']}"
        )
        return line, peakline, im, title

    streamer.start()
    anim = FuncAnimation(fig, update, interval=interval_ms,
                         blit=False, cache_frame_data=False)
    try:
        plt.show()
    finally:
        state["running"] = False
        streamer.stop()
    return anim
