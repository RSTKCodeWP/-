"""
FPV VTX (5.8 GHz video transmitter) channel definitions + activity estimation.

The analog 5.8 GHz FPV scene uses a standard 40-channel plan across five bands
(A, B, E, F, R). Each channel is a center frequency; an *active* analog VTX puts
out a wide (~roughly 20 MHz) signal centered there, which a HackRF sweep sees as
a strong hump well above the noise floor.

This module:
  * defines the canonical channel table,
  * given a Spectrum, estimates per-channel power / activity,
  * clusters detected signals and maps each to candidate channel name(s).

Caveat: several channels across different bands share (nearly) the same
frequency — e.g. R8/F8 = 5880, R3/B1 ~ 5732/5733, A1/B8 ~ 5865/5866 — so one
real transmitter will light up multiple band labels. We report all candidates
rather than guessing which band a pilot configured.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np

# Canonical analog 5.8 GHz channel plan (center frequency in MHz).
# Index 0..7 corresponds to channels 1..8 within each band.
VTX_BANDS: dict[str, list[int]] = {
    "L": [5333, 5373, 5413, 5453, 5493, 5533, 5573, 5613],  # Lowband (Betaflight)
    "A": [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725],  # Boscam A
    "B": [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866],  # Boscam B
    "E": [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945],  # Boscam E / DJI
    "F": [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880],  # FatShark / IRC
    "R": [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917],  # Raceband
}

# The monitor's default span: Lowband L1 (5333) .. Raceband R8 (5917), with
# ~45 MHz of headroom on each side so the band edges are clearly visible.
VIEW_PAD_MHZ = 45
VIEW_LOW_MHZ = 5333 - VIEW_PAD_MHZ    # 5288
VIEW_HIGH_MHZ = 5917 + VIEW_PAD_MHZ   # 5962

# Approx. occupied bandwidth of an analog FPV video signal (Hz). Used to measure
# in-channel power and to merge a wide signal into a single detected cluster.
ANALOG_BW_HZ = 18e6


@dataclass(frozen=True)
class Channel:
    name: str        # e.g. "R4"
    band: str        # e.g. "R"
    index: int       # 1..8
    freq_mhz: float

    @property
    def freq_hz(self) -> float:
        return self.freq_mhz * 1e6


def all_channels() -> list[Channel]:
    out = []
    for band, freqs in VTX_BANDS.items():
        for i, f in enumerate(freqs, start=1):
            out.append(Channel(f"{band}{i}", band, i, float(f)))
    return out


CHANNELS = all_channels()


# When one frequency maps to channels in several bands, we ASSUME Raceband first
# (it's the common racing plan), then fall back to the others in this order.
BAND_PRIORITY = ("R", "F", "E", "A", "B", "L")


def candidates_for(freq_hz: float, channels: Optional[list] = None,
                   tol_hz: float = 6e6, very_close_hz: float = 2e6) -> list:
    """Channels whose center is within ``tol_hz`` of ``freq_hz``, ordered
    Raceband-first then by distance.

    Several 5.8 GHz channels share (nearly) the same frequency across bands
    (e.g. R3 5732 / B1 5733, R7 5880 / F8 5880). For a detected signal we label
    it Raceband by default but flag the cross-band alternatives. Each entry's
    ``close`` is True when it's within ``very_close_hz`` — a genuine ambiguity
    worth a visual caveat, vs. a merely nearby channel.
    """
    chans = channels or CHANNELS
    rank = {b: i for i, b in enumerate(BAND_PRIORITY)}
    out = []
    for ch in chans:
        d = abs(ch.freq_hz - freq_hz)
        if d <= tol_hz:
            out.append({"name": ch.name, "band": ch.band,
                        "freq_mhz": ch.freq_mhz, "delta_mhz": round(d / 1e6, 2),
                        "close": d <= very_close_hz})
    out.sort(key=lambda c: (rank.get(c["band"], 99), c["delta_mhz"]))
    return out


@dataclass
class ChannelEstimate:
    name: str
    band: str
    freq_mhz: float
    power_dbm: float
    margin_db: float        # power above noise floor
    active: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "band": self.band,
            "freq_mhz": self.freq_mhz,
            "power_dbm": round(self.power_dbm, 1),
            "margin_db": round(self.margin_db, 1),
            "active": self.active,
        }


@dataclass
class DetectedSignal:
    """A signal cluster found in the spectrum, mapped to candidate channels."""
    freq_mhz: float
    power_dbm: float
    margin_db: float
    candidates: list[str]      # channel names within tolerance

    def to_dict(self) -> dict:
        return {
            "freq_mhz": round(self.freq_mhz, 2),
            "power_dbm": round(self.power_dbm, 1),
            "margin_db": round(self.margin_db, 1),
            "candidates": self.candidates,
        }


def _band_max(freqs_hz: np.ndarray, power_dbm: np.ndarray,
              center_hz: float, half_bw_hz: float) -> Optional[float]:
    """Max power within +/- half_bw_hz of center (None if out of range)."""
    lo, hi = center_hz - half_bw_hz, center_hz + half_bw_hz
    mask = (freqs_hz >= lo) & (freqs_hz <= hi)
    if not mask.any():
        return None
    return float(power_dbm[mask].max())


def estimate(spectrum, threshold_db: float = 12.0,
             tol_mhz: float = 6.0) -> dict:
    """Estimate VTX activity from a Spectrum.

    Returns a dict with:
      floor_dbm, threshold_db,
      channels:   per-channel estimates (all 40),
      signals:    detected clusters with candidate channel labels,
      active:     concise list of active channel names (deduped, by frequency).
    """
    freqs = spectrum.freqs_hz
    power = spectrum.power_dbm
    if freqs.size == 0:
        return {"floor_dbm": None, "threshold_db": threshold_db,
                "channels": [], "signals": [], "active": []}

    floor = spectrum.noise_floor_dbm
    half = ANALOG_BW_HZ / 2.0

    # --- per-channel power / activity ---
    chans: list[ChannelEstimate] = []
    for ch in CHANNELS:
        pmax = _band_max(freqs, power, ch.freq_hz, half * 0.5)
        if pmax is None:
            continue
        margin = pmax - floor
        chans.append(ChannelEstimate(
            ch.name, ch.band, ch.freq_mhz, pmax, margin,
            active=margin >= threshold_db,
        ))

    # --- cluster detection: real signals in the spectrum ---
    # merge anything within ~one analog channel width into one detection
    peaks = spectrum.peaks(threshold_db=threshold_db,
                           min_separation_hz=ANALOG_BW_HZ * 0.8)
    signals: list[DetectedSignal] = []
    tol_hz = tol_mhz * 1e6
    for p in peaks:
        cands = [ch.name for ch in CHANNELS if abs(ch.freq_hz - p.freq_hz) <= tol_hz]
        signals.append(DetectedSignal(
            freq_mhz=p.freq_mhz,
            power_dbm=p.power_dbm,
            margin_db=p.power_dbm - floor,
            candidates=cands,
        ))

    # --- concise active list: channel names backed by a real detected signal ---
    active_names: list[str] = []
    for s in signals:
        active_names.extend(s.candidates)
    # keep order, dedupe
    seen = set()
    active = [n for n in active_names if not (n in seen or seen.add(n))]

    return {
        "floor_dbm": round(floor, 1),
        "threshold_db": threshold_db,
        "channels": [c.to_dict() for c in chans],
        "signals": [s.to_dict() for s in signals],
        "active": active,
    }


# ---------------------------------------------------------------------------
# Temporal filtering: per-channel smoothing + occupancy so a real (loud,
# continuous) VTX latches on while bursty Wi-Fi blips are rejected.
# ---------------------------------------------------------------------------


@dataclass
class TrackerConfig:
    on_db: float = 14.0           # smoothed margin required to be "loud"
    off_db: float = 9.0           # hysteresis: drop below this (smoothed) -> off
    tau_occ_s: float = 1.3        # occupancy (duty-cycle) time constant
    occ_on: float = 0.55          # need >=55% of sweeps to show a real peak here
    occ_off: float = 0.25         # fall below 25% peak duty -> deactivate
    q_rate: float = 5.0           # Kalman process noise (dB^2 per second)
    r_meas: float = 7.0           # Kalman measurement noise (dB^2)
    min_on_s: float = 0.6         # must persist this long before we report it
    meas_half_bw_hz: float = 6e6  # window for measuring in-channel power
    class_half_bw_hz: float = 11e6  # window for analog/digital shape
    digital_min_bw_hz: float = 12e6     # wide occupied band -> digital
    digital_max_peakiness_db: float = 7.0  # flat (low peak-to-mean) -> digital
    # --- peak gating: a channel only counts as hit when there's a genuine,
    #     prominent local maximum snapped to it (kills overlapping-label and
    #     sideband false positives) ---
    region_grow_db: float = 8.0   # bridge dips: grow a region down to floor+this
    peak_margin_db: float = 14.0  # but keep it only if its peak clears floor+this
    peak_prominence_db: float = 8.0   # and it stands this far above its surroundings
    peak_win_hz: float = 12e6     # (unused legacy) prominence window
    snap_tol_hz: float = 6e6      # a region centroid must be within this of a channel
    cluster_gap_hz: float = 22e6  # active channels within this are ONE transmitter
    # --- digital hold: a wide digital block's power-weighted centroid wanders
    #     sweep-to-sweep, which would flip the reported channel (e.g. B2<->R6).
    #     For a signal classified digital we time-smooth its center and LATCH the
    #     estimated channel, only relabelling once the smoothed center has moved
    #     clearly off the held channel. ---
    digital_hold_tau_s: float = 4.0   # EWMA time constant for a digital signal's held center
    digital_relabel_hz: float = 14e6  # held channel kept until smoothed center drifts past this
    sig_forget_s: float = 2.0         # drop a transmitter's memory after this long unseen


class _ChannelTracker:
    """Scalar Kalman smoother on a channel's power margin + an occupancy EWMA.

    The Kalman filter (a 1-D random-walk model — no need for an *extended* KF
    since power-vs-time is linear) gives a denoised margin estimate `x`. The
    occupancy `occ` is the smoothed fraction of recent sweeps the channel was
    above `on_db` — i.e. its duty cycle. Activation requires BOTH a loud
    smoothed margin AND a high duty cycle, with hysteresis, which is what
    separates a continuous VTX from intermittent Wi-Fi.
    """

    def __init__(self, ch: Channel, cfg: TrackerConfig):
        self.ch = ch
        self.cfg = cfg
        self.x = 0.0          # smoothed margin (dB above floor)
        self.P = 16.0         # estimate variance
        self.occ = 0.0        # duty cycle in [0, 1]
        self.active = False
        self.on_time = 0.0    # seconds continuously active
        self.dig = 0.0        # digital-ness EWMA in [0, 1]

    def update(self, margin: float, is_peak_hit: bool, dt: float,
               shape_is_digital: Optional[bool]):
        cfg = self.cfg
        # --- scalar Kalman predict/update on the margin (loudness) ---
        self.P += cfg.q_rate * dt
        K = self.P / (self.P + cfg.r_meas)
        self.x += K * (margin - self.x)
        self.P *= (1.0 - K)
        # --- occupancy = duty cycle of a genuine, prominent peak landing here ---
        a = 1.0 - math.exp(-dt / max(cfg.tau_occ_s, 1e-3))
        self.occ += a * ((1.0 if is_peak_hit else 0.0) - self.occ)
        # --- hysteretic activation: loud AND consistent ---
        if not self.active:
            if self.x >= cfg.on_db and self.occ >= cfg.occ_on:
                self.active = True
                self.on_time = 0.0
        else:
            if self.x < cfg.off_db or self.occ < cfg.occ_off:
                self.active = False
                self.on_time = 0.0
        if self.active:
            self.on_time += dt
            if shape_is_digital is not None:
                self.dig += a * ((1.0 if shape_is_digital else 0.0) - self.dig)

    @property
    def kind(self) -> str:
        return "digital" if self.dig >= 0.5 else "analog"

    def to_dict(self, floor: float) -> dict:
        return {
            "name": self.ch.name,
            "band": self.ch.band,
            "freq_mhz": self.ch.freq_mhz,
            "power_dbm": round(floor + self.x, 1),
            "margin_db": round(self.x, 1),
            "occupancy": round(self.occ, 2),
            "active": self.active,
            "kind": self.kind if self.active else None,
            "on_time_s": round(self.on_time, 1),
        }


class VTXAnalyzer:
    """Stateful VTX activity analyzer — feed it one Spectrum per sweep.

    Maintains a `_ChannelTracker` per channel and, each update, returns the
    smoothed per-channel state plus clustered "signals" (adjacent active
    channels merged, since one transmitter overlaps several channel labels).
    """

    def __init__(self, threshold_db: float = 12.0,
                 cfg: Optional[TrackerConfig] = None,
                 channels: Optional[list] = None):
        self.cfg = cfg or TrackerConfig()
        if threshold_db is not None:
            self.cfg.on_db = threshold_db
            self.cfg.off_db = max(4.0, threshold_db - 5.0)
        self.channels = channels or CHANNELS
        self.trk = {ch.name: _ChannelTracker(ch, self.cfg) for ch in self.channels}
        # Per-transmitter memory: a smoothed center + a latched estimated channel
        # so a wide digital signal holds ONE stable label instead of bouncing.
        self._sig_mem: list[dict] = []
        self._t = 0.0                          # monotonic time (sum of dt), for aging memory
        self._avg = None                       # EWMA spectrum, for stable classification

    def _find_peaks(self, freqs, power, floor):
        """Detect transmitters as contiguous above-threshold *regions*.

        Returns one (centroid_freq_hz, peak_dbm) per region. Using the
        power-weighted centroid (not the per-sweep argmax) gives a STABLE
        center for wide/flat digital blocks, whose sample-to-sample peak
        wanders across the top; a contiguous region also swallows analog
        sidebands so a transmitter is one detection, not several. Prominence
        vs the bins flanking the region rejects isolated low bumps.
        """
        cfg = self.cfg
        n = power.size
        if n < 3:
            return []
        grow = floor + cfg.region_grow_db      # low threshold: bridge internal dips
        keep = floor + cfg.peak_margin_db      # region kept only if peak clears this
        above = power >= grow
        dets = []
        i = 0
        while i < n:
            if not above[i]:
                i += 1
                continue
            j = i
            while j < n and above[j]:
                j += 1
            seg_f = freqs[i:j]
            seg_p = power[i:j]
            peak = float(seg_p.max())
            left = power[i - 1] if i > 0 else floor
            right = power[j] if j < n else floor
            prominence = peak - max(left, right)
            if peak >= keep and prominence >= cfg.peak_prominence_db:
                lin = 10.0 ** ((seg_p - floor) / 10.0)     # linear power weights
                centroid = float((seg_f * lin).sum() / lin.sum())
                dets.append((float(seg_f[0]), float(seg_f[-1]), centroid, peak))
            i = j
        return dets

    def _nearest_channel(self, freq_hz):
        best, best_d = None, self.cfg.snap_tol_hz
        for ch in self.channels:
            d = abs(ch.freq_hz - freq_hz)
            if d <= best_d:
                best, best_d = ch, d
        return best

    def _shape_is_digital(self, freqs, power, floor, center_hz) -> Optional[bool]:
        cfg = self.cfg
        lo, hi = center_hz - cfg.class_half_bw_hz, center_hz + cfg.class_half_bw_hz
        mask = (freqs >= lo) & (freqs <= hi)
        if mask.sum() < 3:
            return None
        band = power[mask]
        bw = float(np.median(np.diff(freqs[mask]))) if mask.sum() > 1 else 1e6
        above = band > (floor + 6.0)
        if not above.any():
            return None
        occ_bw = float(above.sum()) * bw
        peakiness = float(band.max() - band[above].mean())
        # wide + flat -> digital; narrow or peaky -> analog
        return (occ_bw >= cfg.digital_min_bw_hz
                and peakiness <= cfg.digital_max_peakiness_db)

    def update(self, spectrum, dt: float) -> dict:
        freqs = spectrum.freqs_hz
        power = spectrum.power_dbm
        if freqs.size == 0:
            return {"floor_dbm": None, "threshold_db": self.cfg.on_db,
                    "channels": [], "signals": [], "active": []}
        floor = spectrum.noise_floor_dbm
        cfg = self.cfg

        # smoothed spectrum (EWMA) — used for classification so per-sweep noise
        # doesn't inflate peakiness and flip digital signals to "analog".
        if self._avg is None or self._avg.shape != power.shape:
            self._avg = power.copy()
        else:
            a = 1.0 - math.exp(-dt / 1.5)
            self._avg = self._avg + a * (power - self._avg)

        # 1) find genuine prominent signal regions; every channel whose center
        #    falls within a region's span gets a hit this sweep. This keeps the
        #    duty cycle STABLE for a wide signal (no jittery centroid snapping);
        #    the overlapped channels are merged back into one reported signal by
        #    _cluster(). A region with no channel inside (e.g. Wi-Fi) is ignored.
        pad = 2e6
        hit_power: dict[str, float] = {}
        regions = self._find_peaks(freqs, power, floor)
        for f_lo, f_hi, _cen, pk in regions:
            for ch in self.channels:
                if f_lo - pad <= ch.freq_hz <= f_hi + pad:
                    if pk > hit_power.get(ch.name, -1e9):
                        hit_power[ch.name] = pk

        # 2) update every channel's tracker; only peak-snapped channels get a hit.
        out_ch = []
        for ch in self.channels:
            t = self.trk[ch.name]
            pmax = _band_max(freqs, power, ch.freq_hz, cfg.meas_half_bw_hz)
            if pmax is None:
                continue  # channel outside the swept range
            margin = pmax - floor
            is_hit = ch.name in hit_power
            t.update(margin, is_hit, dt, None)
            out_ch.append(t.to_dict(floor))

        signals = self._cluster(freqs, self._avg, floor, dt)
        # Only the ASSUMED (Raceband-first) label of each cluster lights the grid;
        # cross-band alternatives ride along in each signal's `alt` for a caveat.
        active = []
        for s in signals:
            active.append(s["candidates"][0])
        seen = set()
        active = [n for n in active if not (n in seen or seen.add(n))]

        # Only the representative channel of each cluster reads as "active" in
        # the grid; overlapped neighbours keep their bars but aren't lit.
        reps = set(active)
        kind_by_name = {s["candidates"][0]: s["kind"] for s in signals}
        for ch in out_ch:
            ch["active"] = ch["name"] in reps
            ch["kind"] = kind_by_name.get(ch["name"]) if ch["active"] else None

        return {
            "floor_dbm": round(floor, 1),
            "threshold_db": cfg.on_db,
            "channels": out_ch,
            "signals": signals,
            "active": active,
        }

    def _classify_span(self, freqs, power, floor, center_mhz) -> str:
        """Analog (narrow/peaky) vs digital (wide/flat) over the signal center."""
        cfg = self.cfg
        c = center_mhz * 1e6
        mask = (freqs >= c - 12e6) & (freqs <= c + 12e6)
        if mask.sum() < 3:
            return "analog"
        band = power[mask]
        above = band > (floor + 6.0)
        if above.sum() < 1:
            return "analog"
        bw = float(np.median(np.diff(freqs[mask])))
        occ_bw = float(above.sum()) * bw
        peakiness = float(band.max() - band[above].mean())
        if occ_bw >= cfg.digital_min_bw_hz and peakiness <= cfg.digital_max_peakiness_db:
            return "digital"
        return "analog"

    def _cluster(self, freqs, power, floor, dt) -> list[dict]:
        """Merge adjacent active channels (one wide/strong transmitter overlaps
        several channel slots) and report ONE representative channel each.

        A wide digital block's power-weighted centroid wanders sweep-to-sweep,
        which would flip the reported channel. To avoid that, each cluster is
        matched to a persistent per-transmitter memory whose center is
        time-smoothed; for a digital signal the estimated channel is *latched*
        and only changes once the smoothed center drifts clearly off it. Analog
        signals stay precise (re-estimated each sweep) since they don't wander.
        """
        cfg = self.cfg
        self._t += dt
        gap_mhz = cfg.cluster_gap_hz / 1e6
        act = [self.trk[c.name] for c in self.channels
               if self.trk[c.name].active and self.trk[c.name].on_time >= cfg.min_on_s]
        act.sort(key=lambda t: t.ch.freq_mhz)
        clusters: list[list] = []
        cur: list = []
        for t in act:
            if cur and (t.ch.freq_mhz - cur[-1].ch.freq_mhz) > gap_mhz:
                clusters.append(cur)
                cur = []
            cur.append(t)
        if cur:
            clusters.append(cur)

        sigs = []
        used_mem: set = set()
        for cl in clusters:
            # power-weighted center of the cluster this sweep
            weights = [10.0 ** (max(t.x, 0.0) / 10.0) for t in cl]
            wsum = sum(weights) or 1.0
            inst_center = sum(t.ch.freq_mhz * w for t, w in zip(cl, weights)) / wsum
            members = [t.ch.name for t in sorted(cl, key=lambda t: t.ch.freq_mhz)]
            peak = max(cl, key=lambda t: t.x)
            kind = self._classify_span(freqs, power, floor, inst_center)

            # Match this cluster to the nearest remembered transmitter (within one
            # cluster gap); create a fresh memory if it's a new signal.
            mem, best_d = None, gap_mhz
            for m in self._sig_mem:
                if id(m) in used_mem:
                    continue
                d = abs(m["center_mhz"] - inst_center)
                if d < best_d:
                    mem, best_d = m, d
            if mem is None:
                mem = {"center_mhz": inst_center, "primary": None, "last_t": self._t}
                self._sig_mem.append(mem)
            used_mem.add(id(mem))

            # Time-smooth the center. Digital blocks smooth slowly (held estimate);
            # analog tracks the (already stable) instantaneous center.
            tau = cfg.digital_hold_tau_s if kind == "digital" else cfg.tau_occ_s
            a = 1.0 - math.exp(-dt / max(tau, 1e-3))
            mem["center_mhz"] += a * (inst_center - mem["center_mhz"])
            mem["last_t"] = self._t
            est_center = mem["center_mhz"] if kind == "digital" else inst_center

            # Raceband-first prediction for the (smoothed) center, with cross-band
            # alternatives flagged (e.g. R3 vs B1).
            cand_info = candidates_for(est_center * 1e6, self.channels)
            cand_names = [c["name"] for c in cand_info]
            if not cand_names:
                cand_names = [min(cl, key=lambda t: abs(t.ch.freq_mhz - est_center)).ch.name]
            fresh = cand_names[0]

            # Latch the label for a digital signal: keep the previously reported
            # channel until the smoothed center has drifted clearly off it, so a
            # wide block doesn't flicker between neighbouring/cross-band channels.
            prev = mem.get("primary")
            primary = fresh
            if kind == "digital" and prev is not None:
                prev_ch = next((c for c in self.channels if c.name == prev), None)
                if prev_ch is not None and \
                        abs(prev_ch.freq_mhz - est_center) * 1e6 <= cfg.digital_relabel_hz:
                    primary = prev            # still close enough -> hold it
            mem["primary"] = primary

            # Ensure the held primary leads the candidate list.
            cand_names = [primary] + [n for n in cand_names if n != primary]
            alt = [c for c in cand_info if c["close"] and c["name"] != primary]
            rep_occ = next((t.occ for t in cl if t.ch.name == primary), peak.occ)
            sigs.append({
                "freq_mhz": round(est_center, 1),      # (smoothed) signal center
                "power_dbm": round(floor + peak.x, 1),
                "margin_db": round(peak.x, 1),
                "candidates": cand_names,              # held-primary-first ordering
                "primary": primary,                    # latched for digital, fresh for analog
                "alt": alt,                            # very-close cross-band options
                "ambiguous": bool(alt),
                "members": members,                    # all overlapped slots (info)
                "kind": kind,
                "occupancy": round(rep_occ, 2),
                "on_time_s": round(max(t.on_time for t in cl), 1),
            })

        # Forget transmitters we haven't seen for a while so memory doesn't grow
        # and a genuinely new signal on the same band starts fresh.
        self._sig_mem = [m for m in self._sig_mem
                         if self._t - m["last_t"] <= cfg.sig_forget_s]
        return sigs
