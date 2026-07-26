"""
Core implementation for hackrf_api.

Wraps the vendored HackRF command-line tools and exposes them as a clean Python
API. The heavy lifting is:

  * locating the vendored binaries (and ensuring their DLLs resolve),
  * running them with sane timeouts and error surfacing,
  * parsing hackrf_info text into a DeviceInfo,
  * parsing hackrf_sweep CSV into a Spectrum with peak detection.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Locating the vendored tools
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
# Allow override via env var, else default to ../vendor/bin next to the package.
_DEFAULT_BIN = os.environ.get(
    "HACKRF_BIN_DIR", os.path.join(_PROJECT_ROOT, "vendor", "bin")
)

_TOOLS = (
    "hackrf_info",
    "hackrf_sweep",
    "hackrf_transfer",
    "hackrf_debug",
    "hackrf_clock",
    "hackrf_biast",
)


class HackRFError(RuntimeError):
    """A HackRF tool failed or returned an error."""


class HackRFNotFoundError(HackRFError):
    """No HackRF device is connected / could be opened."""


def _install_hint() -> str:
    """OS-appropriate one-liner for getting the HackRF tools."""
    if sys.platform == "darwin":
        return "Install them with:  brew install hackrf"
    if sys.platform.startswith("linux"):
        return (
            "Install them with your package manager, e.g.:\n"
            "  sudo apt install hackrf     (Debian/Ubuntu)\n"
            "  sudo dnf install hackrf      (Fedora)"
        )
    # Windows / other: the repo vendors prebuilt binaries.
    return "Run:  python bootstrap_vendor.py   (downloads them locally)."


def find_binaries(bin_dir: Optional[str] = None) -> dict:
    """Return {tool_name: full_path} for the HackRF command-line tools.

    Resolution order, per tool:
      1. The vendored ``vendor/bin`` directory (or ``$HACKRF_BIN_DIR`` /
         ``bin_dir`` override) — this is how Windows ships self-contained.
      2. The system ``PATH`` (e.g. a Homebrew or apt install on macOS/Linux).

    This keeps the repo self-contained on Windows while letting macOS/Linux use
    a normal system install. Raises HackRFError with an OS-appropriate hint if
    ``hackrf_info`` can't be found either way.
    """
    bin_dir = bin_dir or _DEFAULT_BIN
    exe = ".exe" if os.name == "nt" else ""
    found = {}
    for t in _TOOLS:
        # 1) vendored binary next to the package
        p = os.path.join(bin_dir, t + exe)
        if os.path.exists(p):
            found[t] = p
            continue
        # 2) fall back to a system install on PATH
        which = shutil.which(t)
        if which:
            found[t] = which
    if "hackrf_info" not in found:
        raise HackRFError(
            f"HackRF tools not found (looked in {bin_dir!r} and on PATH).\n"
            f"{_install_hint()}"
        )
    return found


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DeviceInfo:
    """Identity / firmware details from hackrf_info."""

    serial: Optional[str] = None
    board_id: Optional[str] = None
    board_name: Optional[str] = None
    firmware_version: Optional[str] = None
    api_version: Optional[str] = None
    part_id: Optional[str] = None
    hardware_revision: Optional[str] = None
    libhackrf_version: Optional[str] = None
    found: bool = False
    raw: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass
class Signal:
    """A detected peak in a Spectrum."""

    freq_hz: float
    power_dbm: float

    @property
    def freq_mhz(self) -> float:
        return self.freq_hz / 1e6

    def to_dict(self) -> dict:
        return {
            "freq_hz": self.freq_hz,
            "freq_mhz": round(self.freq_mhz, 6),
            "power_dbm": round(self.power_dbm, 2),
        }


@dataclass
class Spectrum:
    """A power-vs-frequency spectrum produced by a sweep.

    `freqs_hz` and `power_dbm` are parallel, frequency-sorted numpy arrays.
    """

    freqs_hz: np.ndarray
    power_dbm: np.ndarray
    bin_width_hz: float
    sweeps: int = 1
    start_hz: float = 0.0
    stop_hz: float = 0.0

    # -- summary stats -------------------------------------------------------
    @property
    def noise_floor_dbm(self) -> float:
        """Robust noise-floor estimate (median of the spectrum)."""
        return float(np.median(self.power_dbm))

    def power_at(self, freq_hz: float) -> float:
        """Power of the bin nearest to freq_hz."""
        idx = int(np.argmin(np.abs(self.freqs_hz - freq_hz)))
        return float(self.power_dbm[idx])

    def strongest(self, n: int = 10) -> list[Signal]:
        """The n highest-power bins (no grouping)."""
        order = np.argsort(self.power_dbm)[::-1][:n]
        return [Signal(float(self.freqs_hz[i]), float(self.power_dbm[i])) for i in order]

    def peaks(
        self,
        threshold_db: float = 10.0,
        min_separation_hz: Optional[float] = None,
    ) -> list[Signal]:
        """Detect signals standing `threshold_db` above the noise floor.

        Local maxima are grouped so a single wideband signal is reported once.
        `min_separation_hz` defaults to 10x the bin width.
        """
        if self.freqs_hz.size == 0:
            return []
        floor = self.noise_floor_dbm
        cutoff = floor + threshold_db
        if min_separation_hz is None:
            min_separation_hz = self.bin_width_hz * 10

        above = self.power_dbm >= cutoff
        signals: list[Signal] = []
        i = 0
        n = len(self.power_dbm)
        while i < n:
            if not above[i]:
                i += 1
                continue
            j = i
            while j < n and above[j]:
                j += 1
            # peak within the contiguous run [i, j)
            seg = self.power_dbm[i:j]
            k = i + int(np.argmax(seg))
            signals.append(Signal(float(self.freqs_hz[k]), float(self.power_dbm[k])))
            i = j

        # merge peaks closer than min_separation_hz, keeping the stronger
        signals.sort(key=lambda s: s.freq_hz)
        merged: list[Signal] = []
        for s in signals:
            if merged and (s.freq_hz - merged[-1].freq_hz) < min_separation_hz:
                if s.power_dbm > merged[-1].power_dbm:
                    merged[-1] = s
            else:
                merged.append(s)
        merged.sort(key=lambda s: s.power_dbm, reverse=True)
        return merged

    def ascii_plot(self, width: int = 70, height: int = 14) -> str:
        """A quick terminal spectrogram for human eyeballing."""
        if self.freqs_hz.size == 0:
            return "(empty spectrum)"
        # downsample to `width` columns by max-pooling
        f = self.freqs_hz
        p = self.power_dbm
        cols = np.array_split(p, width)
        fcols = np.array_split(f, width)
        colmax = np.array([c.max() for c in cols])
        colfreq = np.array([c.mean() for c in fcols])
        pmin, pmax = float(p.min()), float(p.max())
        span = max(pmax - pmin, 1.0)
        rows = []
        for r in range(height, 0, -1):
            level = pmin + span * (r / height)
            line = "".join("#" if v >= level else " " for v in colmax)
            rows.append(f"{level:6.0f} |{line}")
        axis = f"       +{'-' * width}"
        labels = f"       {colfreq[0]/1e6:.1f} MHz{' ' * (width - 18)}{colfreq[-1]/1e6:.1f} MHz"
        return "\n".join(rows + [axis, labels])

    def to_dict(self, include_full: bool = False) -> dict:
        d = {
            "start_hz": self.start_hz,
            "stop_hz": self.stop_hz,
            "bin_width_hz": self.bin_width_hz,
            "sweeps": self.sweeps,
            "num_bins": int(self.freqs_hz.size),
            "noise_floor_dbm": round(self.noise_floor_dbm, 2),
            "peak_dbm": round(float(self.power_dbm.max()), 2) if self.freqs_hz.size else None,
        }
        if include_full:
            d["freqs_hz"] = self.freqs_hz.tolist()
            d["power_dbm"] = [round(x, 2) for x in self.power_dbm.tolist()]
        return d


@dataclass
class Waterfall:
    """A time x frequency power matrix built from many consecutive sweeps.

    `power_dbm` has shape (n_rows, n_freqs); row 0 is the oldest sweep. Each
    column corresponds to `freqs_hz`.
    """

    freqs_hz: np.ndarray
    power_dbm: np.ndarray            # shape (rows, freqs), dBm
    bin_width_hz: float
    start_hz: float = 0.0
    stop_hz: float = 0.0

    @property
    def num_rows(self) -> int:
        return int(self.power_dbm.shape[0]) if self.power_dbm.ndim == 2 else 0

    def mean_spectrum(self) -> "Spectrum":
        """Collapse all rows into one averaged Spectrum (power-domain mean)."""
        lin = 10 ** (self.power_dbm / 10)
        avg = 10 * np.log10(lin.mean(axis=0))
        return Spectrum(self.freqs_hz, avg, self.bin_width_hz,
                        self.num_rows, self.start_hz, self.stop_hz)

    def to_png(
        self,
        path: str,
        cmap: str = "turbo",
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        title: Optional[str] = None,
        elapsed_s: Optional[float] = None,
    ) -> str:
        """Render the waterfall to a PNG and return its path.

        Requires matplotlib (only imported here so the rest of the library has
        no plotting dependency).
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        data = self.power_dbm
        if data.ndim != 2 or data.size == 0:
            raise HackRFError("waterfall has no data to plot")

        # Robust color limits: clip extremes so a single spike doesn't wash it out
        if vmin is None:
            vmin = float(np.percentile(data, 5))
        if vmax is None:
            vmax = float(np.percentile(data, 99.5))

        f0, f1 = self.freqs_hz[0] / 1e9, self.freqs_hz[-1] / 1e9
        y1 = elapsed_s if elapsed_s else self.num_rows
        ylabel = "elapsed time (s)" if elapsed_s else "sweep #"

        fig, ax = plt.subplots(figsize=(11, 7), dpi=110)
        im = ax.imshow(
            data, aspect="auto", origin="upper", cmap=cmap,
            vmin=vmin, vmax=vmax, extent=[f0, f1, y1, 0],
            interpolation="nearest",
        )
        ax.set_xlabel("frequency (GHz)")
        ax.set_ylabel(ylabel + "  (newest at bottom)")
        ax.set_title(title or
                     f"HackRF waterfall  {f0:.2f}-{f1:.2f} GHz  "
                     f"{self.num_rows} sweeps  ({self.bin_width_hz/1e3:.0f} kHz bins)")
        cbar = fig.colorbar(im, ax=ax, pad=0.01)
        cbar.set_label("power (dBm)")
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return os.path.abspath(path)

    def to_dict(self) -> dict:
        return {
            "start_hz": self.start_hz,
            "stop_hz": self.stop_hz,
            "bin_width_hz": self.bin_width_hz,
            "num_rows": self.num_rows,
            "num_bins": int(self.freqs_hz.size),
            "noise_floor_dbm": round(float(np.median(self.power_dbm)), 2)
            if self.power_dbm.size else None,
            "peak_dbm": round(float(self.power_dbm.max()), 2)
            if self.power_dbm.size else None,
        }


# ---------------------------------------------------------------------------
# The device
# ---------------------------------------------------------------------------


class HackRF:
    """High-level handle to a HackRF One via the vendored CLI tools.

    Parameters
    ----------
    serial:
        Optional device serial (or unique suffix) to target a specific board
        when several are connected. Passed through as ``-d``.
    bin_dir:
        Override the directory containing the hackrf_* binaries.
    """

    def __init__(self, serial: Optional[str] = None, bin_dir: Optional[str] = None):
        self.serial = serial
        self.bins = find_binaries(bin_dir)
        # The exe directory is also where the DLLs live; Windows resolves a
        # binary's own folder first, so running by full path "just works".
        self._bin_dir = os.path.dirname(self.bins["hackrf_info"])

    # -- low-level runner ----------------------------------------------------
    def _run(self, tool: str, args: Sequence[str], timeout: float = 60.0,
             check: bool = True) -> subprocess.CompletedProcess:
        if tool not in self.bins:
            raise HackRFError(f"tool {tool!r} is not available in {self._bin_dir!r}")
        cmd = [self.bins[tool]]
        if self.serial and tool != "hackrf_info":
            cmd += ["-d", self.serial]
        cmd += list(args)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                cwd=self._bin_dir,
            )
        except subprocess.TimeoutExpired as e:
            raise HackRFError(f"{tool} timed out after {timeout}s") from e
        if check and proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip()
            if "No HackRF boards found" in msg or "libusb_open() failed" in msg:
                raise HackRFNotFoundError(msg or "no HackRF device found")
            raise HackRFError(
                f"{tool} failed (exit {proc.returncode}): {msg or '<no output>'}"
            )
        return proc

    # -- device info ---------------------------------------------------------
    def info(self) -> DeviceInfo:
        """Parse `hackrf_info` into a DeviceInfo."""
        proc = self._run("hackrf_info", [], timeout=20, check=False)
        text = proc.stdout
        info = DeviceInfo(raw=text)
        if "No HackRF boards found" in text or proc.returncode != 0 and "Found HackRF" not in text:
            if "Found HackRF" not in text:
                info.found = False
                if proc.returncode != 0 and "No HackRF" not in text:
                    # genuine error (not just "no device")
                    err = (proc.stderr or text).strip()
                    if err and "No HackRF" not in err:
                        raise HackRFError(err)
                return info
        info.found = "Found HackRF" in text

        def grab(pattern):
            m = re.search(pattern, text)
            return m.group(1).strip() if m else None

        info.libhackrf_version = grab(r"libhackrf version:\s*(.+)")
        info.serial = grab(r"Serial number:\s*(\S+)")
        info.board_id = grab(r"Board ID Number:\s*(\d+)")
        info.board_name = grab(r"Board ID Number:\s*\d+\s*\((.+)\)")
        info.firmware_version = grab(r"Firmware Version:\s*([^\(]+)")
        info.api_version = grab(r"API:([\d.]+)")
        info.part_id = grab(r"Part ID Number:\s*(.+)")
        info.hardware_revision = grab(r"Hardware Revision:\s*(\S+)")
        if info.firmware_version:
            info.firmware_version = info.firmware_version.strip()
        return info

    def is_present(self) -> bool:
        """True if a HackRF can be opened right now."""
        try:
            return self.info().found
        except HackRFError:
            return False

    # -- spectrum scanning (primary capability) ------------------------------
    def scan(
        self,
        start_mhz: float,
        stop_mhz: float,
        bin_width_hz: int = 100_000,
        sweeps: int = 1,
        lna_gain: int = 16,
        vga_gain: int = 20,
        amp: bool = False,
        antenna_power: bool = False,
        timeout: Optional[float] = None,
    ) -> Spectrum:
        """Sweep [start_mhz, stop_mhz] and return a Spectrum.

        Parameters
        ----------
        start_mhz, stop_mhz:
            Frequency range in MHz (1 .. 7250; practical RX 1 .. 6000).
        bin_width_hz:
            FFT bin width / resolution in Hz (2445 .. 5_000_000). Smaller =
            finer resolution but slower. 100 kHz is a good general default.
        sweeps:
            Number of full sweeps to average (>=1). More sweeps = steadier
            noise floor.
        lna_gain:
            RX IF (LNA) gain, 0..40 in steps of 8.
        vga_gain:
            RX baseband (VGA) gain, 0..62 in steps of 2.
        amp:
            Enable the +14 dB RF front-end amplifier.
        antenna_power:
            Enable bias-tee (3.3V on the antenna port) for powered antennas/LNAs.
        """
        if stop_mhz <= start_mhz:
            raise ValueError("stop_mhz must be greater than start_mhz")
        if not (2445 <= bin_width_hz <= 5_000_000):
            raise ValueError("bin_width_hz must be between 2445 and 5_000_000")
        sweeps = max(1, int(sweeps))

        args = [
            "-f", f"{int(start_mhz)}:{int(round(stop_mhz))}",
            "-w", str(int(bin_width_hz)),
            "-l", str(int(lna_gain)),
            "-g", str(int(vga_gain)),
            "-N", str(sweeps),
        ]
        if amp:
            args += ["-a", "1"]
        if antenna_power:
            args += ["-p", "1"]

        if timeout is None:
            # generous: scales with span and sweep count
            span = stop_mhz - start_mhz
            timeout = 20.0 + sweeps * (span / 20.0) * 1.5

        proc = self._run("hackrf_sweep", args, timeout=timeout, check=False)
        if proc.returncode != 0 and not proc.stdout.strip():
            msg = (proc.stderr or "").strip()
            if "No HackRF" in msg or "libusb_open" in msg:
                raise HackRFNotFoundError(msg)
            raise HackRFError(f"hackrf_sweep failed: {msg or '<no output>'}")

        return self._parse_sweep(proc.stdout, bin_width_hz, sweeps,
                                 start_mhz * 1e6, stop_mhz * 1e6)

    @staticmethod
    def _parse_sweep(text: str, bin_width_hz: int, sweeps: int,
                     start_hz: float, stop_hz: float) -> Spectrum:
        """Parse hackrf_sweep CSV into frequency-sorted arrays.

        Each line:
          date, time, hz_low, hz_high, hz_bin_width, num_samples, dB, dB, ...
        where the trailing dB values map to bins centered at
          hz_low + hz_bin_width * (i + 0.5).
        Repeated frequencies (multiple sweeps / overlap) are averaged in the
        power domain.
        """
        acc: dict[int, list[float]] = {}
        for line in text.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 7:
                continue
            try:
                hz_low = float(parts[2])
                bw = float(parts[4])
                db_values = [float(x) for x in parts[6:]]
            except ValueError:
                continue
            for i, db in enumerate(db_values):
                center = hz_low + bw * (i + 0.5)
                key = int(round(center))
                acc.setdefault(key, []).append(db)

        if not acc:
            return Spectrum(np.array([]), np.array([]), float(bin_width_hz),
                            sweeps, start_hz, stop_hz)

        freqs = np.array(sorted(acc.keys()), dtype=float)
        powers = np.array([
            10 * np.log10(np.mean(10 ** (np.array(acc[int(f)]) / 10)))
            for f in freqs
        ])
        return Spectrum(freqs, powers, float(bin_width_hz), sweeps, start_hz, stop_hz)

    # -- waterfall (time x frequency) ----------------------------------------
    def waterfall(
        self,
        start_mhz: float,
        stop_mhz: float,
        rows: int = 80,
        bin_width_hz: int = 1_000_000,
        lna_gain: int = 16,
        vga_gain: int = 20,
        amp: bool = False,
        antenna_power: bool = False,
        timeout: Optional[float] = None,
    ) -> Waterfall:
        """Capture `rows` consecutive sweeps and stack them into a Waterfall.

        Same tuning parameters as `scan`, but each sweep is kept as its own row
        instead of being averaged, giving a time x frequency power matrix.

        A coarser default `bin_width_hz` (1 MHz) is used than `scan` because a
        waterfall trades frequency resolution for capturing many sweeps quickly.
        """
        if stop_mhz <= start_mhz:
            raise ValueError("stop_mhz must be greater than start_mhz")
        if not (2445 <= bin_width_hz <= 5_000_000):
            raise ValueError("bin_width_hz must be between 2445 and 5_000_000")
        rows = max(1, int(rows))

        args = [
            "-f", f"{int(start_mhz)}:{int(round(stop_mhz))}",
            "-w", str(int(bin_width_hz)),
            "-l", str(int(lna_gain)),
            "-g", str(int(vga_gain)),
            "-N", str(rows),
        ]
        if amp:
            args += ["-a", "1"]
        if antenna_power:
            args += ["-p", "1"]

        if timeout is None:
            span = stop_mhz - start_mhz
            # each sweep ~ (span/20) hops; budget generously, plus headroom
            timeout = 30.0 + rows * (span / 20.0) * 0.15
            timeout = max(timeout, 30.0)

        proc = self._run("hackrf_sweep", args, timeout=timeout, check=False)
        if proc.returncode != 0 and not proc.stdout.strip():
            msg = (proc.stderr or "").strip()
            if "No HackRF" in msg or "libusb_open" in msg:
                raise HackRFNotFoundError(msg)
            raise HackRFError(f"hackrf_sweep failed: {msg or '<no output>'}")

        return self._parse_waterfall(proc.stdout, bin_width_hz,
                                     start_mhz * 1e6, stop_mhz * 1e6)

    @staticmethod
    def _parse_waterfall(text: str, bin_width_hz: int,
                         start_hz: float, stop_hz: float) -> Waterfall:
        """Parse multi-sweep hackrf_sweep CSV into a (rows x freqs) matrix.

        hackrf_sweep does NOT emit bins in monotonic frequency order within a
        sweep (it alternates between the halves of each tuning step), so sweep
        boundaries can't be found by "hz_low decreased". Instead, every sweep
        begins tuning at the lowest frequency, so each line whose hz_low equals
        the global minimum marks the start of a new sweep. Each sweep becomes
        one row; columns are the union of bin-center frequencies.
        """
        rows_raw = []  # list of (hz_low, bw, [db...])
        for line in text.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 7:
                continue
            try:
                hz_low = float(parts[2])
                bw = float(parts[4])
                db_values = [float(x) for x in parts[6:]]
            except ValueError:
                continue
            rows_raw.append((hz_low, bw, db_values))

        sweeps: list[dict[int, float]] = []
        if rows_raw:
            min_low = min(r[0] for r in rows_raw)
            cur: dict[int, float] = {}
            for hz_low, bw, db_values in rows_raw:
                if abs(hz_low - min_low) < 1.0 and cur:
                    sweeps.append(cur)
                    cur = {}
                for i, db in enumerate(db_values):
                    key = int(round(hz_low + bw * (i + 0.5)))
                    cur[key] = db
            if cur:
                sweeps.append(cur)

        if not sweeps:
            return Waterfall(np.array([]), np.empty((0, 0)), float(bin_width_hz),
                             start_hz, stop_hz)

        # common frequency grid = sorted union of all bin centers
        all_keys = sorted({k for s in sweeps for k in s})
        freqs = np.array(all_keys, dtype=float)
        idx = {k: j for j, k in enumerate(all_keys)}
        mat = np.full((len(sweeps), len(all_keys)), np.nan, dtype=float)
        for r, s in enumerate(sweeps):
            for k, v in s.items():
                mat[r, idx[k]] = v
        # fill any gaps (a row missing a bin) with that column's median
        if np.isnan(mat).any():
            col_med = np.nanmedian(mat, axis=0)
            inds = np.where(np.isnan(mat))
            mat[inds] = np.take(col_med, inds[1])

        return Waterfall(freqs, mat, float(bin_width_hz), start_hz, stop_hz)

    # -- IQ recording (RX) ---------------------------------------------------
    def record(
        self,
        out_path: str,
        freq_hz: float,
        sample_rate_hz: float = 10_000_000,
        seconds: float = 1.0,
        lna_gain: int = 16,
        vga_gain: int = 20,
        amp: bool = False,
        baseband_filter_hz: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> dict:
        """Record raw IQ to a file (interleaved signed 8-bit I,Q).

        Returns a small manifest dict describing the capture (so it can be
        re-interpreted later, e.g. loaded as numpy complex64 via load_iq()).
        """
        num_samples = int(sample_rate_hz * seconds)
        args = [
            "-r", out_path,
            "-f", str(int(freq_hz)),
            "-s", str(int(sample_rate_hz)),
            "-n", str(num_samples),
            "-l", str(int(lna_gain)),
            "-g", str(int(vga_gain)),
        ]
        if amp:
            args += ["-a", "1"]
        if baseband_filter_hz:
            args += ["-b", str(int(baseband_filter_hz))]
        if timeout is None:
            timeout = seconds + 30.0
        self._run("hackrf_transfer", args, timeout=timeout)
        return {
            "path": os.path.abspath(out_path),
            "freq_hz": float(freq_hz),
            "sample_rate_hz": float(sample_rate_hz),
            "seconds": float(seconds),
            "num_samples": num_samples,
            "format": "int8 interleaved I,Q",
            "size_bytes": os.path.getsize(out_path) if os.path.exists(out_path) else 0,
        }

    def transmit(
        self,
        in_path: str,
        freq_hz: float,
        sample_rate_hz: float = 2_000_000,
        tx_vga_gain: int = 0,
        amp: bool = False,
        repeat: bool = False,
        i_understand_tx_may_be_illegal: bool = False,
        timeout: Optional[float] = None,
    ) -> dict:
        """Transmit raw IQ from a file. GUARDED.

        Transmitting on most frequencies without a licence is illegal in most
        jurisdictions and can interfere with safety-critical services. This
        method refuses to run unless you explicitly pass
        ``i_understand_tx_may_be_illegal=True``.

        ``repeat=True`` loops the file (hackrf_transfer ``-R``) until ``timeout``
        elapses, so a short buffer can drive a long, continuous emission. The
        ``timeout`` firing is the *normal* way a repeating transmission ends; it
        returns cleanly rather than raising.
        """
        if not i_understand_tx_may_be_illegal:
            raise HackRFError(
                "Refusing to transmit: pass i_understand_tx_may_be_illegal=True "
                "and ensure you are legally permitted to transmit on this "
                "frequency/power in your jurisdiction."
            )
        if not os.path.exists(in_path):
            raise HackRFError(f"input IQ file not found: {in_path}")
        args = [
            "-t", in_path,
            "-f", str(int(freq_hz)),
            "-s", str(int(sample_rate_hz)),
            "-x", str(int(tx_vga_gain)),
        ]
        if amp:
            args += ["-a", "1"]
        if timeout is None:
            timeout = 120.0

        if not repeat:
            self._run("hackrf_transfer", args, timeout=timeout)
            return {"transmitted": os.path.abspath(in_path),
                    "freq_hz": float(freq_hz), "repeat": False, "on_air_s": None}

        # Bounded continuous TX. We loop a short buffer with -R but CAP the total
        # with -n (sample_rate * seconds), so hackrf_transfer stops and EXITS
        # CLEANLY on its own, releasing the USB device. Force-killing it mid-TX
        # (terminate/kill) wedges the HackRF's USB interface — requiring a
        # power-cycle — so we never do that in the normal path. We still use
        # Popen + DEVNULL (not _run) because capturing the endless -R stats
        # stream and killing the child can deadlock the reader on Windows.
        seconds = float(timeout)
        num_samples = max(1, int(sample_rate_hz * seconds))
        cmd = [self.bins["hackrf_transfer"]]
        if self.serial:
            cmd += ["-d", self.serial]
        cmd += args + ["-R", "-n", str(num_samples)]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=self._bin_dir,
        )
        try:
            rc = proc.wait(timeout=seconds + 10.0)   # -n bounds it; margin for safety
        except subprocess.TimeoutExpired:
            # Should not happen. Killing here can wedge the radio, so it's the
            # explicit unhappy path, surfaced as an error.
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            proc.wait()
            raise HackRFError(
                f"hackrf_transfer did not stop after {seconds}s+margin; killed "
                "(radio may need a power-cycle)"
            )
        if rc != 0:
            raise HackRFError(
                f"hackrf_transfer exited with code {rc} — transmission failed"
            )
        return {"transmitted": os.path.abspath(in_path),
                "freq_hz": float(freq_hz), "repeat": True, "on_air_s": seconds}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_iq(path: str) -> np.ndarray:
    """Load an int8 interleaved IQ capture as a complex64 numpy array."""
    raw = np.fromfile(path, dtype=np.int8).astype(np.float32)
    raw /= 127.0
    return (raw[0::2] + 1j * raw[1::2]).astype(np.complex64)
