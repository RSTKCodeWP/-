"""
ELRS / FHSS link-activity detection from a HackRF sweep.

ExpressLRS is a LoRa frequency-hopping control link. A single transmitter emits
short, *narrow* (~0.8-1.6 MHz) bursts that hop across the band many times a
second. We can't decode it or prove a link is "bound" from RF alone, but the
hopping leaves an unmistakable signature on an accumulated sweep:

  * a max-hold trace shows a COMB of many narrow peaks spread across the band
    (every channel the hopper has visited), while
  * any single sweep shows only one/two of them lit — so each channel's
    max-hold sits well ABOVE its time-average (high "intermittency").

Wide, continuous occupants (Wi-Fi) fail the narrow-width test; fixed carriers
fail the intermittency test. Other FHSS users (Bluetooth) look similar, so we
report "FHSS / ELRS-like activity" with a confidence, not a definitive bind.

Tuning is per sub-band:
  * 2.4 GHz ELRS lives in 2400-2483 MHz (shared with Wi-Fi/BT)
  * 900 MHz ELRS lives ~860-930 MHz (868 EU / 915 US ISM)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class ELRSBand:
    name: str             # e.g. "2.4G ELRS"
    sweep_lo_mhz: float   # full hackrf sweep range (wide, per user)
    sweep_hi_mhz: float
    focus_lo_mhz: float   # where ELRS actually lives, for scoring
    focus_hi_mhz: float

    def safe_name(self) -> str:
        return self.name.replace(" ", "_").replace(".", "").replace("/", "")


# The user's requested sweep windows, with the ELRS focus sub-band inside each.
BAND_24 = ELRSBand("2.4G ELRS", 2100, 2500, 2400, 2483)
BAND_900 = ELRSBand("900M ELRS", 700, 1200, 860, 930)


@dataclass
class ELRSResult:
    name: str
    present: bool = False            # a controller is keyed up in this band
    verdict: str = "quiet"           # "tx_active" | "weak" | "quiet"
    confidence: float = 0.0          # 0..1
    n_hops: int = 0                  # distinct narrow hop channels seen
    hop_spread_mhz: float = 0.0      # frequency span the hops cover
    intermittency_db: float = 0.0    # median max-hold minus time-average at hops
    peak_dbm: Optional[float] = None
    peak_margin_db: float = 0.0      # peak above the noise floor
    floor_dbm: Optional[float] = None
    hop_freqs_mhz: list = field(default_factory=list)
    sweeps: int = 0
    above_ambient_db: Optional[float] = None   # peak above recorded ambient peak
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "present": self.present,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 2),
            "n_hops": self.n_hops,
            "hop_spread_mhz": round(self.hop_spread_mhz, 1),
            "intermittency_db": round(self.intermittency_db, 1),
            "peak_dbm": None if self.peak_dbm is None else round(self.peak_dbm, 1),
            "peak_margin_db": round(self.peak_margin_db, 1),
            "floor_dbm": None if self.floor_dbm is None else round(self.floor_dbm, 1),
            "hop_freqs_mhz": [round(x, 1) for x in self.hop_freqs_mhz],
            "sweeps": self.sweeps,
            "above_ambient_db": None if self.above_ambient_db is None else round(self.above_ambient_db, 1),
            "note": self.note,
        }


def load_ambient(band: ELRSBand, calib_dir: str = "calib") -> Optional[dict]:
    """Load a recorded ambient (no-gear) baseline for this band, if present.

    Looks for calib/ambient__<safe>.json (written by elrs_calibrate.py ambient).
    Returns the summary dict (with at least 'peak_dbm') or None.
    """
    import json
    import os
    path = os.path.join(calib_dir, f"ambient__{band.safe_name()}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


@dataclass
class ELRSConfig:
    min_margin_db: float = 9.0       # a hop peak must clear floor+this in max-hold
    max_hop_bw_mhz: float = 2.6      # peaks wider than this are not ELRS (e.g. Wi-Fi)
    min_intermittency_db: float = 5.0  # to COUNT a bin as a hop (max-hold vs time-avg)
    min_hops: int = 4                # need at least this many hop channels
    min_spread_mhz: float = 8.0      # spread across at least this much band
    target_hops: int = 14            # confidence saturates around here
    target_intermittency_db: float = 35.0
    # --- "is a transmitter actually keyed up here" gate, calibrated against
    #     bound / tx-only / rx-only captures. A lone receiver (no controller)
    #     collapses to ~18 dB intermittency and a weak peak, while a keyed
    #     controller sits at 32-50 dB and a strong peak. ---
    present_min_intermittency_db: float = 25.0
    present_min_peak_margin_db: float = 18.0
    # A recorded ambient (no-gear) baseline lets us reject WiFi/BT: real TX
    # activity must rise this many dB above the ambient peak to count. The 2.4
    # ISM band is full of WiFi/BT that otherwise looks like FHSS.
    ambient_delta_db: float = 10.0


class ELRSDetector:
    """Stateless-ish detector: feed it an accumulated (rows x freqs) block."""

    def __init__(self, band: ELRSBand, cfg: Optional[ELRSConfig] = None,
                 ambient: Optional[dict] = None):
        self.band = band
        self.cfg = cfg or ELRSConfig()
        # recorded no-gear baseline; ambient["peak_dbm"] is the reference
        self.ambient = ambient

    def detect(self, freqs_hz: np.ndarray, rows_dbm: np.ndarray) -> ELRSResult:
        """rows_dbm: shape (n_sweeps, n_freqs) for this band's dwell window."""
        cfg = self.cfg
        res = ELRSResult(name=self.band.name)
        if rows_dbm.ndim != 2 or rows_dbm.shape[0] == 0 or freqs_hz.size == 0:
            res.note = "no data"
            return res
        res.sweeps = int(rows_dbm.shape[0])

        maxhold = rows_dbm.max(axis=0)
        mean = rows_dbm.mean(axis=0)

        # restrict to the ELRS focus sub-band
        fm = freqs_hz / 1e6
        sel = (fm >= self.band.focus_lo_mhz) & (fm <= self.band.focus_hi_mhz)
        if sel.sum() < 5:
            res.note = "focus sub-band not covered by sweep"
            return res
        f = fm[sel]
        mh = maxhold[sel]
        mn = mean[sel]
        bin_mhz = float(np.median(np.diff(f))) if f.size > 1 else 1.0

        # noise floor = median of the time-average (robust to hopping bursts)
        floor = float(np.median(mn))
        res.floor_dbm = floor
        res.peak_dbm = float(mh.max())

        # candidate hop channels: narrow local maxima in the max-hold trace
        thresh = floor + cfg.min_margin_db
        max_bw_bins = max(1, int(round(cfg.max_hop_bw_mhz / bin_mhz)))
        hop_freqs = []
        intermittencies = []
        n = mh.size
        for i in range(1, n - 1):
            if mh[i] < thresh or mh[i] < mh[i - 1] or mh[i] < mh[i + 1]:
                continue
            # width at -6 dB from this peak; reject if too wide (not a hop)
            lvl = mh[i] - 6.0
            l = i
            while l > 0 and mh[l] >= lvl:
                l -= 1
            r = i
            while r < n - 1 and mh[r] >= lvl:
                r += 1
            width_bins = r - l
            if width_bins > max_bw_bins + 2:
                continue
            # intermittency: hop channels are only occasionally occupied
            interm = mh[i] - mn[i]
            if interm < cfg.min_intermittency_db:
                continue
            hop_freqs.append(float(f[i]))
            intermittencies.append(interm)

        # collapse hops that are within one channel width of each other
        hop_freqs.sort()
        merged = []
        for hf in hop_freqs:
            if merged and (hf - merged[-1]) < cfg.max_hop_bw_mhz:
                continue
            merged.append(hf)
        res.hop_freqs_mhz = merged
        res.n_hops = len(merged)
        res.hop_spread_mhz = (merged[-1] - merged[0]) if len(merged) >= 2 else 0.0
        res.intermittency_db = float(np.median(intermittencies)) if intermittencies else 0.0
        res.peak_margin_db = res.peak_dbm - floor

        # --- gates (calibrated: a lone receiver fails the intermittency/peak
        #     gate; a keyed controller passes) ---
        enough = (res.n_hops >= cfg.min_hops and res.hop_spread_mhz >= cfg.min_spread_mhz)
        strong = (res.intermittency_db >= cfg.present_min_intermittency_db
                  and res.peak_margin_db >= cfg.present_min_peak_margin_db)
        # --- ambient rejection: must rise clearly above the recorded WiFi/BT
        #     baseline (otherwise 2.4 GHz ambient masquerades as ELRS) ---
        above_ambient = True
        if self.ambient and self.ambient.get("peak_dbm") is not None:
            res.above_ambient_db = res.peak_dbm - float(self.ambient["peak_dbm"])
            above_ambient = res.above_ambient_db >= cfg.ambient_delta_db

        # --- confidence ---
        if enough:
            hop_score = min(1.0, res.n_hops / cfg.target_hops)
            interm_score = max(0.0, min(1.0, (res.intermittency_db - 12.0) /
                                        (cfg.target_intermittency_db - 12.0)))
            margin_score = max(0.0, min(1.0, (res.peak_margin_db - 15.0) / 25.0))
            res.confidence = round(float(0.4 * interm_score + 0.3 * hop_score
                                         + 0.3 * margin_score), 2)
        else:
            res.confidence = 0.0

        res.present = bool(enough and strong and above_ambient and res.confidence >= 0.5)
        if res.present:
            res.verdict = "tx_active"
            res.note = ("controller transmitting (bound OR searching — a bind "
                        "can't be confirmed from RF; receiver-only reads as quiet)")
        elif enough and strong and not above_ambient:
            res.verdict = "ambient"
            res.note = (f"FHSS present but only ~{res.above_ambient_db:.0f} dB over the "
                        f"recorded ambient — WiFi/BT, not a keyed controller")
        elif enough and res.n_hops > 0:
            res.verdict = "weak"
            res.note = ("faint hopping — receiver-only telemetry or distant TX, "
                        "no keyed controller uplink")
        else:
            res.verdict = "quiet"
            res.note = "no controller uplink detected"
        return res
