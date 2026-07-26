#!/usr/bin/env python3
"""
elrs_calibrate.py — capture labeled ELRS-band data to characterize what a
*bound* link looks like versus TX-only / RX-only, so the detector can avoid
false positives.

Usage:
    python elrs_calibrate.py bound      # both controller (TX) and rx powered & linked
    python elrs_calibrate.py no_tx      # controller OFF, receiver ON  (rx only)
    python elrs_calibrate.py no_rx      # controller ON, receiver OFF  (tx only)
    python elrs_calibrate.py baseline   # everything OFF (ambient)

Saves calib/<label>__<band>.json with summary metrics + the max-hold / mean
traces, and prints a comparison-friendly summary. Run it once per condition.
"""
from __future__ import annotations
import json
import os
import sys
import numpy as np

from hackrf_api import HackRF
from hackrf_api import elrs

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "calib")
SWEEPS = 90          # per band, for decent statistics
BIN_HZ = 500_000


def capture(hrf, band: elrs.ELRSBand, label: str) -> dict:
    wf = hrf.waterfall(band.sweep_lo_mhz, band.sweep_hi_mhz, rows=SWEEPS,
                       bin_width_hz=BIN_HZ, lna_gain=32, vga_gain=30, amp=False)
    freqs = wf.freqs_hz
    rows = wf.power_dbm                      # (sweeps, bins)
    det = elrs.ELRSDetector(band)
    res = det.detect(freqs, rows).to_dict()

    # focus sub-band stats for discrimination
    fm = freqs / 1e6
    sel = (fm >= band.focus_lo_mhz) & (fm <= band.focus_hi_mhz)
    sub = rows[:, sel]
    mean = sub.mean(axis=0)
    floor = float(np.median(mean))
    thr = floor + 9.0
    # per-sweep: how many bins are "lit" (hop activity present this instant)
    active_per_sweep = (sub > thr).sum(axis=1).astype(float)
    # energy above floor (linear), per sweep
    lin = 10 ** ((sub - floor) / 10.0)
    energy_per_sweep = lin.sum(axis=1)

    summary = {
        "label": label,
        "band": band.name,
        "sweeps": int(rows.shape[0]),
        "floor_dbm": round(floor, 1),
        "peak_dbm": round(float(sub.max()), 1),
        # FHSS comb (max-hold over the window)
        "n_hops": res["n_hops"],
        "hop_spread_mhz": res["hop_spread_mhz"],
        "intermittency_db": res["intermittency_db"],
        "confidence": res["confidence"],
        "present": res["present"],
        # per-sweep activity — bidirectional (bound) link tends to have more
        # bins lit per instant and steadier presence than a lone TX
        "active_bins_mean": round(float(active_per_sweep.mean()), 2),
        "active_bins_std": round(float(active_per_sweep.std()), 2),
        "active_bins_max": int(active_per_sweep.max()),
        "duty_any": round(float((active_per_sweep > 0).mean()), 3),
        "energy_mean": round(float(energy_per_sweep.mean()), 1),
        "energy_std": round(float(energy_per_sweep.std()), 1),
    }
    # full traces for later offline analysis / plotting
    detail = {
        **summary,
        "focus_freqs_mhz": [round(x, 3) for x in fm[sel].tolist()],
        "maxhold_dbm": [round(float(v), 1) for v in sub.max(axis=0).tolist()],
        "mean_dbm": [round(float(v), 1) for v in mean.tolist()],
        "active_per_sweep": [int(x) for x in active_per_sweep.tolist()],
    }
    return summary, detail


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    label = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    hrf = HackRF()
    if not hrf.is_present():
        print("No HackRF found.")
        return 1
    print(f"=== capturing condition: {label!r}  ({SWEEPS} sweeps/band) ===")
    for band in (elrs.BAND_24, elrs.BAND_900):
        summary, detail = capture(hrf, band, label)
        safe = band.name.replace(" ", "_").replace(".", "").replace("/", "")
        path = os.path.join(OUT, f"{label}__{safe}.json")
        with open(path, "w") as f:
            json.dump(detail, f)
        print(f"\n[{band.name}]  -> {os.path.relpath(path, HERE)}")
        for k in ("present", "confidence", "n_hops", "hop_spread_mhz",
                  "intermittency_db", "active_bins_mean", "active_bins_std",
                  "active_bins_max", "duty_any", "energy_mean", "peak_dbm", "floor_dbm"):
            print(f"    {k:18s} {summary[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
