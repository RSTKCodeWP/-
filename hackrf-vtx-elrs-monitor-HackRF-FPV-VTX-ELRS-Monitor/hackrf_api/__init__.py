"""
hackrf_api — a small, dependency-light Python API for the HackRF One.

It drives the official Great Scott Gadgets command-line tools (vendored locally
under ../vendor/bin by bootstrap_vendor.py — no system install required) and
returns structured Python objects instead of text you have to scrape.

Quick start
-----------
    from hackrf_api import HackRF

    hrf = HackRF()
    print(hrf.info())                     # device identity / firmware

    spec = hrf.scan(start_mhz=2400, stop_mhz=2483)   # Wi-Fi / BLE band
    for sig in spec.peaks():
        print(f"{sig.freq_mhz:.3f} MHz  {sig.power_dbm:.1f} dBm")

Design notes
------------
* Spectrum scanning (hackrf_sweep) is the primary capability and returns a
  `Spectrum` object backed by numpy arrays, with peak detection built in.
* Everything is also reachable from the command line with JSON output:
      python -m hackrf_api info --json
      python -m hackrf_api scan 2400 2483 --json
  which is what an autonomous agent should call.
"""
from .core import (
    HackRF,
    HackRFError,
    HackRFNotFoundError,
    Spectrum,
    Waterfall,
    Signal,
    DeviceInfo,
    find_binaries,
)
from .vtx_emit import emit_vtx, synthesize_fpv_iq, resolve_channel, mw_to_tx_gain

__all__ = [
    "HackRF",
    "HackRFError",
    "HackRFNotFoundError",
    "Spectrum",
    "Waterfall",
    "Signal",
    "DeviceInfo",
    "find_binaries",
    "emit_vtx",
    "synthesize_fpv_iq",
    "resolve_channel",
    "mw_to_tx_gain",
]

__version__ = "0.1.0"
