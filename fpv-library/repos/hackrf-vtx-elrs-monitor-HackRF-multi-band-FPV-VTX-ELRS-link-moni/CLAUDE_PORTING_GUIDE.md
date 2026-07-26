# Porting Guide — HackRF VTX + ELRS Detection

**Audience: an AI coding agent (Claude) integrating this functionality into a
different application.** This document is self-contained: it explains *what* the
system detects, the *non-obvious RF domain knowledge* (most of which was learned
experimentally with real hardware and is expensive to rediscover), the
*algorithms* in enough detail to reimplement in any language, the *data
contracts*, and the *calibrated constants* with how they were derived.

The reference implementation is ~1500 lines of dependency-light Python
(`numpy` only for the core; stdlib `http.server` for the dashboard). Treat it as
a spec, not a library to vendor.

---

## 1. What it does

Drives a **HackRF One** SDR to monitor three RF bands and report, in real time:

1. **FPV VTX (analog 5.8 GHz video) channel activity** — which of the standard
   40-channel plan (bands L/A/B/E/F/R) is transmitting, analog vs digital, with
   a single clean label per transmitter.
2. **ELRS (ExpressLRS) control-link activity** on 2.4 GHz and 900 MHz — whether a
   control transmitter is keyed up, distinguished from ambient WiFi/BT.

A single radio can only look at one band at a time, so a **scheduler time-shares
it** across the three bands. A browser dashboard shows three live waterfalls +
status cards; everything is also exposed as JSON for programmatic use.

---

## 2. Critical RF domain knowledge (read this first)

These are the facts that make or break the detectors. They were established with
a real HackRF + a real ELRS radio/receiver and a bench calibration.

### 2.1 `hackrf_sweep` output is NOT frequency-ordered within a sweep
The tool tunes in ~20 MHz steps and emits two half-band rows per step, and the
rows of one sweep do **not** arrive in increasing-frequency order. Therefore:
- You **cannot** detect a new sweep by "frequency went backwards."
- Detect sweep boundaries by **the minimum `hz_low` value** repeating (each
  sweep starts at the lowest tune), or by a **bin frequency repeating** (each bin
  is emitted once per sweep).

### 2.2 VTX channels overlap in frequency
The 40-channel plan has many near-coincident channels (e.g. R8/F8 both 5880;
A1/B8 ≈ 5865/5866; R5/F4/A4/B5 all ≈ 5805–5809). One transmitter therefore lights
up 4+ channel labels. **You must collapse to one label per physical
transmitter**, or the output is unusable.

### 2.3 Analog vs digital VTX shape
- **Analog**: a sharp narrow carrier peak; high peak-to-mean (peakiness ≈ 15–20 dB),
  occupied width ≲ 17 MHz.
- **Digital** (DJI/HDZero/Walksnail): a wide (~20–28 MHz) flat-topped block; low
  peakiness (≈ 4–6 dB).
- Classify on a **time-smoothed** spectrum — per-sweep noise inflates peakiness
  and flips digital → analog.

### 2.4 ELRS is LoRa FHSS — detectable but not "bound"-verifiable
- An ELRS transmitter emits short **narrow (~0.8–1.6 MHz)** bursts that **hop**
  across the band hundreds of times/sec.
- On an accumulated **max-hold** trace this is a **comb of many narrow peaks**;
  on any single sweep only 1–2 are lit. So each visited channel's max-hold sits
  far above its time-average — call this **intermittency** (max-hold − mean).
- **You cannot confirm a "bound" link from RF.** A controller that is merely
  powered on transmits the *same* uplink as a bound one (ELRS TX hops whether or
  not it's connected). Only the receiver's weak downlink telemetry differs, and
  it's too faint/aliased to isolate. **Honest verdict = "TX active (bound OR
  searching)", never "bound."**

### 2.5 Calibration results (measured; the discriminators)
Captured in 4 conditions (controller=TX, receiver=RX):

| condition | 900 MHz peak | 900 MHz intermittency | verdict |
|---|---|---|---|
| bound (TX+RX) | −4 dBm | 33 dB | TX active |
| tx-only (no RX) | −4 dBm | 42 dB | TX active |
| rx-only (no TX) | −23 dBm | 18 dB | **quiet** |
| all off (ambient) | −18 dBm | ~20 dB | quiet |

Findings:
- **Receiver-only is distinguishable** (collapses to low peak/intermittency).
- **TX-only vs bound is NOT** (both strong) — hence the honesty caveat.
- **2.4 GHz is dominated by WiFi/BT** that looks like FHSS (narrow BT hops +
  busy channels). On this bench, 2.4 read "ELRS-like 100%" *in all conditions
  including everything-off* → **2.4 GHz alone is unreliable; use 900 MHz as the
  trustworthy ELRS indicator, and gate 2.4 against a recorded ambient baseline.**

### 2.6 Ambient baseline (the WiFi-rejection trick)
Record a no-gear "ambient" capture (peak dBm per band). A band only counts as a
keyed transmitter if its peak rises **≥ ~10 dB above the recorded ambient peak**.
Measured separation: WiFi sits ~8 dB over ambient; real 900 MHz ELRS sits ~14 dB
over. (2.4 WiFi swings ~14 dB though, so keep 900 as the primary signal.)

---

## 3. Data acquisition layer

### 3.1 Invoking the sweep
`hackrf_sweep -f <lo_mhz>:<hi_mhz> -w <bin_hz> -l <lna> -g <vga> [-a 1] [-p 1] -N <n_sweeps>`
- `-w` bin width 2445 Hz … 5 MHz. Use **1 MHz** for VTX (fast, enough), **500 kHz**
  for ELRS (resolve ~1 MHz hops).
- `-N n` does *n* complete sweeps then exits (use this for time-sharing dwells).
  No `-N` = sweep forever (use for a single-band live view).
- Gains: VTX 5–6 GHz is lossy → `lna 32, vga 30, amp on`. ELRS bands are strong →
  `amp off` (avoid saturation).
- On Windows the tool needs its own DLLs beside the exe; running by full path
  resolves them. (See `bootstrap_vendor.py` — it fetches the binaries +
  `hackrf-0.dll`, `fftw3f.dll`, `libusb-1.0.dll`, MSVC runtime, `libwinpthread`
  from conda-forge with zero system install.)

### 3.2 CSV line format
```
date, time, hz_low, hz_high, hz_bin_width, num_samples, dB, dB, dB, ...
```
The trailing dB values map to bin centers `hz_low + hz_bin_width*(i+0.5)`.

### 3.3 Parse to a (sweeps × freqs) matrix
- Collect all `(hz_low, bw, [dB...])` rows.
- Split into sweeps at each line where `hz_low == min(hz_low over all rows)`.
- Build a union frequency grid; for each sweep, `np.interp` its (freq→dB) onto
  the grid so every row has identical length. Result: `rows_dbm` shape
  `(n_sweeps, n_bins)`, `freqs_hz` length `n_bins`.

A single averaged **Spectrum** is `10*log10(mean(10**(rows/10), axis=0))` (average
in the linear/power domain, not dB).

---

## 4. VTX detection algorithm

Goal: from a stream of per-sweep spectra, report a stable, de-duplicated list of
active VTX transmitters with analog/digital labels. Input one `Spectrum` per
sweep with `dt` since last update.

### 4.1 Channel table (center MHz, index 1–8)
```
L: 5333 5373 5413 5453 5493 5533 5573 5613   (Betaflight Lowband)
A: 5865 5845 5825 5805 5785 5765 5745 5725   (Boscam A)
B: 5733 5752 5771 5790 5809 5828 5847 5866   (Boscam B)
E: 5705 5685 5665 5645 5885 5905 5925 5945   (Boscam E)
F: 5740 5760 5780 5800 5820 5840 5860 5880   (FatShark/IRC)
R: 5658 5695 5732 5769 5806 5843 5880 5917   (Raceband)
```
Default monitor span = L1−45 … R8+45 MHz = **5288–5962 MHz**.

### 4.2 Per-sweep pipeline
1. **floor** = median of the spectrum (robust noise floor).
2. **Find prominent regions** (not bare peaks): contiguous bins above a *grow*
   threshold `floor+8 dB`; keep a region only if its peak ≥ `floor+14 dB` AND its
   topographic prominence (peak − max(left,right flank)) ≥ 8 dB. The two-level
   grow/keep bridges the internal dips of a wide digital block into ONE region.
   Record each region's frequency span `[f_lo, f_hi]` and power-weighted centroid.
3. **Region-span hit assignment**: every channel whose center falls within a
   region's span (±2 MHz pad) gets a "hit" this sweep. (Assigning a single
   nearest-channel to a jittery centroid flickers; span assignment is stable.)
4. **Per-channel tracker update** (one scalar Kalman + occupancy per channel):
   - measured margin = (max power within ±6 MHz of the channel center) − floor.
   - Kalman (1-D random walk) smooths the margin: `P+=Q*dt; K=P/(P+R); x+=K*(z−x); P*=1−K` with `Q≈5 dB²/s, R≈7 dB²`.
   - occupancy EWMA of the hit boolean: `a=1−exp(−dt/τ)` with `τ≈1.3 s`;
     `occ += a*(hit − occ)`.
   - **Activate with hysteresis**: become active when `x ≥ 14 dB` AND `occ ≥ 0.55`;
     deactivate when `x < 9 dB` OR `occ < 0.25`. (This duty-cycle gate is what
     rejects bursty WiFi — it's loud but not *continuously* present.)
5. **Cluster active channels** within 22 MHz into one signal (one transmitter
   overlaps several slots). Per cluster:
   - power-weighted center frequency;
   - **representative channel** = the member nearest that center, but held stable
     by a *label-hysteresis* map keyed on `round(center/20 MHz)` (keeps the same
     name across small wobble — stops F6/R6/A2 flicker);
   - **kind** = classify on the SMOOTHED spectrum over center±12 MHz:
     `digital` if occupied-width ≥ 12 MHz AND peakiness ≤ 7 dB, else `analog`.
6. Only the representative channels read as "active" in the per-channel grid.

Maintain an EWMA-smoothed spectrum (`a=1−exp(−dt/1.5)`) and classify on it.

---

## 5. ELRS detection algorithm

Input: an accumulated `(n_sweeps × n_freqs)` block for one band's dwell (≈30
sweeps). Output: a verdict per band.

1. `maxhold = max over sweeps`, `mean = mean over sweeps`, `floor = median(mean)`
   over the **focus sub-band** (2.4 GHz: 2400–2483; 900 MHz: 860–930).
2. **Find narrow hop channels** in `maxhold`: local maxima above `floor+9 dB`
   whose −6 dB width ≤ ~2.6 MHz (rejects 20 MHz WiFi humps) and whose
   intermittency `maxhold[i]−mean[i] ≥ 5 dB`. Merge hops within one channel width.
3. Metrics: `n_hops`, `hop_spread`, **median intermittency**, `peak`, `peak_margin = peak − floor`.
4. **Gates** (calibrated):
   - `enough` = `n_hops ≥ 4` AND `hop_spread ≥ 8 MHz`
   - `strong` = `intermittency ≥ 25 dB` AND `peak_margin ≥ 18 dB`  ← rejects rx-only
   - `above_ambient` = `peak ≥ ambient_peak + 10 dB`  ← rejects WiFi/BT (needs a
     recorded ambient baseline; if none, skip this gate)
5. **Verdict**:
   - `tx_active` if `enough AND strong AND above_ambient AND confidence ≥ 0.5`
   - `ambient` if `enough AND strong AND NOT above_ambient` (FHSS, but it's WiFi)
   - `weak` if `enough` but not strong (rx-only telemetry / distant TX)
   - `quiet` otherwise
6. **confidence** (0–1), used as the FHSS-strength headline (NOT presence):
   `0.4*interm_score + 0.3*hop_score + 0.3*margin_score`, each a clamped ramp
   (`interm`: 12→target 35 dB; `hops`: /14; `margin`: 15→40 dB).
7. Smooth the **gated presence** boolean across dwells with an EWMA (present if
   ewma ≥ 0.5) so the indicator is steady; smooth confidence separately for
   display.

> Display rule learned from the user: show **confidence** as the headline number
> (strong 2.4 WiFi still reads "100%"), but let the **verdict** drive the color
> (green tx_active / yellow ambient). Showing presence as the headline hid the
> real activity and confused them.

---

## 6. Multi-band scheduler

One thread owns the radio and loops a **visit schedule**. VTX changes fastest, so
it's pinged before each ELRS band:
```
schedule = [vtx, elrs24, vtx, elrs900]   # VTX twice per rotation
```
For each visit: run `hackrf_sweep -N <dwell>` (VTX 18, ELRS 30), parse to a
matrix, feed VTX rows to the VTX analyzer (stateful) or the ELRS block to the
ELRS detector, store latest result + a rolling waterfall ring buffer. Each band
updates in bursts while the radio dwells on it. Keep rotating even if one band
throws.

**Only one OS process can own the HackRF.** Stop any other sweeper first.

---

## 7. Data contracts (for the UI / integration)

`GET /api/meta` → per-band `{id, name, kind, lo_mhz, hi_mhz, bin_hz, num_bins,
freqs_mhz[], (vtx: bands{}), (elrs: focus_lo_mhz, focus_hi_mhz)}`.

`GET /api/band?id=<vtx|elrs24|elrs900>&since=<n>` →
`{count, rows[][] (new dBm rows since n), maxhold[], avg[], analysis, age_s}`.

VTX `analysis`:
```jsonc
{ "floor_dbm": -54, "threshold_db": 14,
  "channels": [ {"name":"R1","band":"R","freq_mhz":5658,"power_dbm":-13,
                 "margin_db":41,"occupancy":1.0,"active":true,"kind":"analog"} ],
  "signals":  [ {"freq_mhz":5658.0,"power_dbm":-13,"margin_db":41,
                 "candidates":["R1"],"members":["R1","E3"],"kind":"analog",
                 "occupancy":1.0,"on_time_s":12.4} ],
  "active": ["R1"] }
```

ELRS `analysis`:
```jsonc
{ "name":"900M ELRS", "verdict":"tx_active", "present":true,
  "confidence":0.94, "confidence_smoothed":0.91, "presence":1.0,
  "n_hops":9, "hop_spread_mhz":43, "intermittency_db":40, "peak_dbm":-4.3,
  "peak_margin_db":45, "above_ambient_db":14.4, "hop_freqs_mhz":[...],
  "note":"controller transmitting (bound OR searching — ...)" }
```

`GET /api/channels` → concise VTX `{active[], signals[], floor_dbm}`.
`GET /api/elrs` → `{elrs:{elrs24:{...}, elrs900:{...}}}`.

---

## 8. Calibrated constants (and provenance)

| constant | value | why |
|---|---|---|
| VTX region grow / keep | floor+8 / floor+14 dB | bridge digital dips; keep only real signals |
| VTX peak prominence | 8 dB | reject shoulders/sidebands |
| VTX activate | x≥14 dB AND occ≥0.55 | loud AND continuous (rejects WiFi blips) |
| VTX deactivate | x<9 dB OR occ<0.25 | hysteresis |
| VTX cluster gap | 22 MHz | merge overlapping channel slots of one TX |
| VTX digital | width≥12 MHz AND peakiness≤7 dB | wide+flat = digital |
| ELRS hop width max | 2.6 MHz | reject 20 MHz WiFi |
| ELRS present intermittency | ≥25 dB | rx-only=18, tx=32–50 (measured) |
| ELRS present peak margin | ≥18 dB | rx-only weak |
| ELRS ambient delta | ≥10 dB over recorded ambient | WiFi≈+8, ELRS≈+14 (measured) |
| Kalman Q,R / occ τ | 5 dB²/s, 7 dB², 1.3 s | smoothing vs responsiveness |

Re-derive `ambient_peak` per site by capturing with all gear off
(`elrs_calibrate.py ambient`); the rest transfer across setups.

---

## 9. Porting checklist & gotchas

- [ ] **One process owns the radio.** Serialize device access.
- [ ] **Sweep rows aren't frequency-ordered** — split sweeps by min `hz_low`.
- [ ] **Average power in linear domain**, not dB.
- [ ] **Collapse overlapping VTX channels** to one label per transmitter.
- [ ] **Classify analog/digital on a smoothed spectrum**, not one sweep.
- [ ] **Don't claim ELRS "bound"** — only "TX active". Receiver-only is the only
      thing you can rule out.
- [ ] **Gate 2.4 GHz against a recorded ambient baseline** or WiFi/BT false-positives.
- [ ] **Headline = confidence, color = verdict** for ELRS UI.
- [ ] Windows console is cp1252 — keep CLI output ASCII (UTF-8 only in the HTML).
- [ ] Time-share dwells with `-N`; expect ~0.5–1 s restart latency per visit.

---

## 10. Reference implementation map

```
hackrf_api/core.py   HackRF wrapper, sweep CSV parsing, Spectrum/Waterfall,
                     VTX-independent helpers (scan, record, peak detection)
hackrf_api/vtx.py    VTX channel table + VTXAnalyzer (regions, Kalman+occupancy
                     trackers, clustering, label hysteresis, analog/digital)
hackrf_api/elrs.py   ELRSDetector (FHSS comb, gates, ambient baseline) + load_ambient
hackrf_api/webapp.py MultiBandMonitor scheduler + stdlib HTTP server + data API
hackrf_api/webui.py  embedded dashboard (3 waterfalls + status cards), pure JS
hackrf_api/live.py   single-band matplotlib live window (_SweepStreamer = the
                     continuous-sweep reader; reusable for streaming)
bootstrap_vendor.py  fetch HackRF binaries from conda-forge (no system install)
elrs_calibrate.py    capture labeled ambient/bound/no_tx/no_rx data to calib/
```

Start by reading `vtx.py` and `elrs.py` — that's where the signal-processing IP
lives. `core._parse_waterfall` shows the sweep-boundary handling. Everything else
is plumbing you can replace to fit the target application.
