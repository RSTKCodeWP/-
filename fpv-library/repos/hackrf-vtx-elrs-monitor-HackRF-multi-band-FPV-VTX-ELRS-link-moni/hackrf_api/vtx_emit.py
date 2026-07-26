"""
Synthesize and emit a fake analog 5.8 GHz FPV video signal.

This is a **test-signal generator** for the VTX detector in this project: it
produces something that *looks like* an analog FPV transmitter on a chosen
channel (a wide, ~18 MHz noisy hump with a residual carrier spike) so you can
exercise the monitor's margin thresholds, analog/digital classifier, and the
Kalman/occupancy latch without flying real gear.

It is **GUARDED** (see ``HackRF.transmit``): nothing goes on the air unless the
caller passes ``i_understand_tx_may_be_illegal=True``. Transmitting on the
5.8 GHz video bands without an appropriate licence is illegal in many places.

------------------------------------------------------------------------------
IMPORTANT — the power number is RELATIVE, not real
------------------------------------------------------------------------------
A HackRF One's uncalibrated output at 5.8 GHz tops out around -5..0 dBm
(~0.3..1 mW) even with the internal amp on. That is 15-30 dB *below* a real
25 mW (+14 dBm) VTX, and much further below 100/400/600 mW. So ``mw`` here is
NOT a calibrated EIRP. It is a *loudness target*: we map it monotonically onto
the TX VGA gain so that, e.g., "100 mw" lands ~6 dB hotter than "25 mw" at your
receiver. That relative spacing is what's useful for testing a detector; the
absolute level is whatever the hardware manages at that frequency. Real output
is also very uneven across the band and full of harmonics/images.
"""
from __future__ import annotations

import math
import os
import tempfile
import time
from typing import Optional

import numpy as np

from .core import HackRF, HackRFError
from .vtx import VTX_BANDS, Channel

# Map common spoken band names to the single-letter band keys in vtx.VTX_BANDS.
BAND_ALIASES: dict[str, str] = {
    "raceband": "R", "race": "R", "r": "R",
    "fatshark": "F", "fatsharks": "F", "irc": "F", "f": "F",
    "boscama": "A", "boscam_a": "A", "banda": "A", "a": "A",
    "boscamb": "B", "boscam_b": "B", "bandb": "B", "b": "B",
    "boscame": "E", "boscam_e": "E", "bande": "E", "dji": "E", "e": "E",
    "lowband": "L", "low": "L", "l": "L",
}

# Reference: a 25 mW (+14 dBm) VTX maps to this TX VGA gain. Higher mW tiers add
# their dB difference on top, clamped to the HackRF's 0..47 dB VGA range.
_REF_MW = 25.0
_REF_GAIN_DB = 20


def resolve_channel(spec: str, index: Optional[int] = None) -> Channel:
    """Resolve a channel from flexible input.

    Accepts ``"R4"``, ``"r4"``, or a band name + index: ``("raceband", 4)``,
    ``("fatshark", 2)``. Raises HackRFError on anything it can't map.
    """
    spec = (spec or "").strip().lower().replace(" ", "").replace("-", "_")
    band: Optional[str] = None
    idx = index

    if idx is None:
        # Try to split a trailing digit off a combined token, e.g. "raceband4".
        m = spec.rstrip("0123456789")
        digits = spec[len(m):]
        if digits:
            idx = int(digits)
            spec = m
    band = BAND_ALIASES.get(spec) or (spec.upper() if spec.upper() in VTX_BANDS else None)

    if band is None:
        raise HackRFError(
            f"unknown VTX band {spec!r}; known: "
            + ", ".join(sorted(set(BAND_ALIASES))) )
    if idx is None or not (1 <= idx <= 8):
        raise HackRFError(f"channel index must be 1..8, got {index!r}")
    freq = VTX_BANDS[band][idx - 1]
    return Channel(f"{band}{idx}", band, idx, float(freq))


def mw_to_tx_gain(mw: float) -> int:
    """Map a (notional) milliwatt level to a TX VGA gain in 0..47 dB.

    Relative only — see the module docstring. dB(mW) above the 25 mW reference
    is added to a reference gain so the *spacing* between power tiers matches a
    real VTX even though the absolute output cannot.
    """
    if mw <= 0:
        raise HackRFError("mw must be positive")
    rel_db = 10.0 * math.log10(mw / _REF_MW)
    return int(max(0, min(47, round(_REF_GAIN_DB + rel_db))))


def synthesize_fpv_iq(
    out_path: str,
    sample_rate_hz: float = 10_000_000,
    duration_s: float = 0.4,
    occupied_bw_hz: float = 18e6,
    mod_bw_hz: float = 2e6,
    carrier_frac: float = 0.05,
    amplitude: int = 110,
    seed: Optional[int] = None,
) -> dict:
    """Write an int8 interleaved I/Q file that mimics an analog FPV signal.

    The signal is wideband FM of band-limited noise (constant envelope, so the
    HackRF runs at full efficiency) plus a small residual carrier so the
    detector sees the center-spike-with-skirts shape of analog video. The
    occupied bandwidth follows Carson's rule, ``2*(dev + mod_bw)``, so we pick
    the deviation from the requested ``occupied_bw_hz``.

    Returns a manifest dict. The file is meant to be looped (``transmit
    repeat=True``); ~0.4 s at 20 MS/s is ~16 MB.
    """
    sr = float(sample_rate_hz)
    n = int(sr * duration_s)
    if n < 1024:
        raise HackRFError("duration too short for the chosen sample rate")
    rng = np.random.default_rng(seed)

    # The occupied signal must fit inside the sample rate (Nyquist), with margin,
    # or it aliases. Clamp the requested width to ~0.85*sr. (At 10 Msps this caps
    # the hump near ~8.5 MHz — narrower than a real 18 MHz analog VTX, but this
    # board's USB bus is only reliable to ~10 Msps, so we trade width for a clean
    # transmit.) mod_bw is likewise bounded so it can't swallow the whole budget.
    occupied_bw_hz = min(occupied_bw_hz, 0.85 * sr)
    mod_bw_hz = min(mod_bw_hz, occupied_bw_hz / 4.0)

    # Modulating signal: white noise band-limited to mod_bw_hz via an FFT mask.
    m = rng.standard_normal(n)
    spec = np.fft.rfft(m)
    fr = np.fft.rfftfreq(n, d=1.0 / sr)
    spec[fr > mod_bw_hz] = 0.0
    m = np.fft.irfft(spec, n=n)
    if np.std(m) > 0:
        m /= np.std(m)

    # Carson's rule -> peak deviation for the requested occupied bandwidth.
    dev_hz = max(0.5e6, occupied_bw_hz / 2.0 - mod_bw_hz)
    # FM: instantaneous phase is the integral of the (scaled) modulating signal.
    phase = np.cumsum(m) * (2.0 * math.pi * dev_hz / sr)
    iq = np.exp(1j * phase)

    # Add a residual carrier (DC term) so there's an analog-style center spike.
    cf = float(np.clip(carrier_frac, 0.0, 0.9))
    iq = (1.0 - cf) * iq + cf

    # Scale to int8 with headroom; clip just in case.
    peak = np.max(np.abs(iq)) or 1.0
    scale = float(amplitude) / peak
    i8 = np.clip(np.round(iq.real * scale), -127, 127).astype(np.int8)
    q8 = np.clip(np.round(iq.imag * scale), -127, 127).astype(np.int8)
    inter = np.empty(2 * n, dtype=np.int8)
    inter[0::2] = i8
    inter[1::2] = q8
    inter.tofile(out_path)

    return {
        "path": os.path.abspath(out_path),
        "sample_rate_hz": sr,
        "duration_s": duration_s,
        "num_samples": n,
        "occupied_bw_hz": occupied_bw_hz,
        "deviation_hz": dev_hz,
        "size_bytes": os.path.getsize(out_path),
        "format": "int8 interleaved I,Q",
    }


def emit_vtx(
    channel: str,
    index: Optional[int] = None,
    mw: float = 25.0,
    seconds: float = 10.0,
    sample_rate_hz: float = 10_000_000,
    amp: bool = True,
    tx_vga_gain: Optional[int] = None,
    serial: Optional[str] = None,
    i_understand_tx_may_be_illegal: bool = False,
    keep_iq: bool = False,
) -> dict:
    """Emit a fake analog FPV signal on a VTX channel for ``seconds``. GUARDED.

    Examples
    --------
        emit_vtx("R1", mw=25, seconds=10, i_understand_tx_may_be_illegal=True)
        emit_vtx("raceband", 4, mw=100, i_understand_tx_may_be_illegal=True)

    ``mw`` is a relative loudness target, not a real EIRP (see module docstring).
    Pass ``tx_vga_gain`` to override the gain directly. Returns a result dict
    describing what was emitted.
    """
    ch = resolve_channel(channel, index)
    gain = tx_vga_gain if tx_vga_gain is not None else mw_to_tx_gain(mw)
    hrf = HackRF(serial=serial)

    # A short loop buffer is cheaper than rendering `seconds` of samples; we let
    # transmit(repeat=True) loop it and stop on the timeout.
    fd, iq_path = tempfile.mkstemp(prefix=f"fpv_{ch.name}_", suffix=".iq")
    os.close(fd)
    try:
        synth = synthesize_fpv_iq(
            iq_path, sample_rate_hz=sample_rate_hz, duration_s=min(0.4, seconds),
        )
        tx = hrf.transmit(
            in_path=iq_path,
            freq_hz=ch.freq_hz,
            sample_rate_hz=sample_rate_hz,
            tx_vga_gain=gain,
            amp=amp,
            repeat=True,
            i_understand_tx_may_be_illegal=i_understand_tx_may_be_illegal,
            timeout=seconds,
        )
    finally:
        if not keep_iq and os.path.exists(iq_path):
            try:
                os.remove(iq_path)
            except OSError:
                pass  # transient lock or temp file; the OS will reclaim it

    return {
        "channel": ch.name,
        "band": ch.band,
        "freq_mhz": ch.freq_mhz,
        "requested_mw": mw,
        "tx_vga_gain_db": gain,
        "amp": amp,
        "seconds": seconds,
        "occupied_bw_hz": synth["occupied_bw_hz"],
        "note": ("relative loudness only — HackRF cannot produce real mW at "
                 "5.8 GHz; see vtx_emit module docstring"),
        **{k: tx[k] for k in ("on_air_s",) if k in tx},
    }


# ---------------------------------------------------------------------------
# Sweep (sequential / round-robin) + bandwidth-limited simultaneous multi-carrier
# ---------------------------------------------------------------------------

def _write_iq(iq: np.ndarray, amplitude: int, out_path: str) -> int:
    """Scale a complex waveform to int8 interleaved I,Q and write it."""
    peak = float(np.max(np.abs(iq))) or 1.0
    scale = float(amplitude) / peak
    i8 = np.clip(np.round(iq.real * scale), -127, 127).astype(np.int8)
    q8 = np.clip(np.round(iq.imag * scale), -127, 127).astype(np.int8)
    inter = np.empty(2 * iq.size, dtype=np.int8)
    inter[0::2] = i8
    inter[1::2] = q8
    inter.tofile(out_path)
    return iq.size


def synthesize_cw_iq(out_path: str, sample_rate_hz: float = 10_000_000,
                     duration_s: float = 0.2, offset_hz: float = 1_000_000,
                     amplitude: int = 115) -> dict:
    """Write a pure CW tone `offset_hz` from center. All power lands in one bin
    (the most visible probe). Pick offset so it clears the receiver's DC spike
    and offset*duration is an integer cycle count for a seamless -R loop."""
    sr = float(sample_rate_hz)
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    iq = np.exp(2j * np.pi * float(offset_hz) * t)
    _write_iq(iq, amplitude, out_path)
    return {"path": os.path.abspath(out_path), "sample_rate_hz": sr,
            "num_samples": n, "offset_hz": float(offset_hz),
            "occupied_bw_hz": 0.0, "kind": "cw"}


def emit_sweep(channels=None, band: str = "R", waveform: str = "fpv",
               mw: float = 25.0, tx_vga_gain: Optional[int] = None,
               seconds_each: float = 2.0, gap_s: float = 0.0, cycles: int = 1,
               sample_rate_hz: float = 10_000_000, amp: bool = True,
               serial: Optional[str] = None,
               i_understand_tx_may_be_illegal: bool = False,
               on_step=None, before_step=None, should_stop=None) -> list:
    """Emit a band's channels one after another (optionally looping). GUARDED.

    ``cycles=1`` is a single R1..R8 pass. ``cycles>1`` with a short
    ``seconds_each`` is a fast round-robin that *looks* simultaneous on a
    persistent/max-hold waterfall (the one radio can't truly transmit them at
    once — see ``emit_multi``). ``waveform`` is "fpv" (wide noise hump, the
    realistic VTX shape) or "cw" (single carrier — far more visible over air).
    The baseband buffer is identical per channel, so we synthesize it once and
    only retune between channels. ``on_step(dict)`` / ``before_step(dict)`` fire
    after / before each hop. ``should_stop()`` is polled between hops and during
    the off-gap; when it returns True the sweep ends early (used for a UI toggle
    that runs until switched off — pass a large ``cycles`` for "until stopped").
    """
    stop = should_stop or (lambda: False)
    if not i_understand_tx_may_be_illegal:
        raise HackRFError("Refusing to transmit: pass "
                          "i_understand_tx_may_be_illegal=True")
    if channels is None:
        channels = [f"{band}{i}" for i in range(1, 9)]
    chans = [resolve_channel(c) for c in channels]
    gain = tx_vga_gain if tx_vga_gain is not None else mw_to_tx_gain(mw)
    hrf = HackRF(serial=serial)

    fd, iq_path = tempfile.mkstemp(prefix=f"sweep_{waveform}_", suffix=".iq")
    os.close(fd)
    results: list = []
    try:
        if waveform == "cw":
            synthesize_cw_iq(iq_path, sample_rate_hz=sample_rate_hz)
        else:
            synthesize_fpv_iq(iq_path, sample_rate_hz=sample_rate_hz, duration_s=0.4)
        for cyc in range(int(cycles)):
            if stop():
                break
            for ch in chans:
                if stop():
                    break
                step = {"cycle": cyc, "channel": ch.name, "freq_mhz": ch.freq_mhz,
                        "seconds": seconds_each, "waveform": waveform}
                if before_step:
                    before_step(step)
                hrf.transmit(in_path=iq_path, freq_hz=ch.freq_hz,
                             sample_rate_hz=sample_rate_hz, tx_vga_gain=gain,
                             amp=amp, repeat=True,
                             i_understand_tx_may_be_illegal=True,
                             timeout=seconds_each)
                results.append(step)
                if on_step:
                    on_step(step)
                if gap_s > 0:   # responsive off-gap: poll stop while idle
                    deadline = time.time() + gap_s
                    while time.time() < deadline and not stop():
                        time.sleep(0.1)
            else:
                continue
            break
    finally:
        if os.path.exists(iq_path):
            try:
                os.remove(iq_path)
            except OSError:
                pass
    return results


def synthesize_multitone_iq(out_path: str, center_hz: float, tone_freqs_hz,
                            sample_rate_hz: float = 20_000_000,
                            duration_s: float = 0.4, amplitude: int = 115) -> dict:
    """Sum of carriers at each `tone_freqs_hz`, relative to `center_hz`. Every
    tone must fall within +/-0.45*sample_rate of center or it aliases."""
    sr = float(sample_rate_hz)
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    offsets = [float(f) - float(center_hz) for f in tone_freqs_hz]
    lim = 0.45 * sr
    if any(abs(o) > lim for o in offsets):
        raise HackRFError(
            f"tones exceed the radio bandwidth: need |offset| <= {lim/1e6:.1f} MHz "
            f"at {sr/1e6:.0f} Msps, got {max(abs(o) for o in offsets)/1e6:.1f} MHz")
    iq = np.zeros(n, dtype=complex)
    for o in offsets:
        iq += np.exp(2j * np.pi * o * t)
    _write_iq(iq, amplitude, out_path)
    return {"path": os.path.abspath(out_path), "center_hz": float(center_hz),
            "tones": len(offsets), "sample_rate_hz": sr, "num_samples": n}


def emit_multi(channels, mw: float = 25.0, tx_vga_gain: Optional[int] = None,
               seconds: float = 10.0, sample_rate_hz: float = 20_000_000,
               amp: bool = True, serial: Optional[str] = None,
               i_understand_tx_may_be_illegal: bool = False) -> dict:
    """Emit several channels AT ONCE as one multi-carrier signal. GUARDED.

    Only possible when all channels fit inside one ~0.9*sample_rate window.
    Raceband channels are 37 MHz apart, so two of them won't fit even at 20 Msps
    — this raises a clear error pointing you to ``emit_sweep`` round-robin.
    """
    chans = [resolve_channel(c) for c in channels]
    freqs = [c.freq_hz for c in chans]
    center = sum(freqs) / len(freqs)
    span = max(freqs) - min(freqs)
    if span > 0.9 * sample_rate_hz:
        raise HackRFError(
            f"channels span {span/1e6:.0f} MHz but one HackRF can only synthesize "
            f"~{0.9*sample_rate_hz/1e6:.0f} MHz at once ({sample_rate_hz/1e6:.0f} "
            f"Msps). Can't emit {', '.join(c.name for c in chans)} simultaneously "
            f"— use emit_sweep(cycles=N) for a round-robin instead.")
    gain = tx_vga_gain if tx_vga_gain is not None else mw_to_tx_gain(mw)
    hrf = HackRF(serial=serial)
    fd, p = tempfile.mkstemp(prefix="multi_", suffix=".iq")
    os.close(fd)
    try:
        synthesize_multitone_iq(p, center, freqs, sample_rate_hz=sample_rate_hz)
        hrf.transmit(in_path=p, freq_hz=center, sample_rate_hz=sample_rate_hz,
                     tx_vga_gain=gain, amp=amp, repeat=True,
                     i_understand_tx_may_be_illegal=i_understand_tx_may_be_illegal,
                     timeout=seconds)
    finally:
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    return {"channels": [c.name for c in chans], "center_mhz": center / 1e6,
            "span_mhz": span / 1e6, "seconds": seconds, "tx_vga_gain_db": gain}
