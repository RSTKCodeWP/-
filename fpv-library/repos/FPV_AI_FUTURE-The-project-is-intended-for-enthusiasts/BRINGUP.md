# Block-3 seeker on Zynq-7020 — bench bring-up guide

The verifiable-here work is done: the whole seeker is built and co-sim-verified against the Python
golden (`../fpv/`). This doc turns those 15 blocks into an ordered bench procedure on the Zynq Mini
(XC7Z020) + Vivado. Everything below the "bench-only" line needs the hardware/toolchain; everything
above it is already green here and re-run with one command.

**Verified here (re-runnable):** `cd 03-fpv && python3 -m pytest fpga -q`  → 47 pass
(6 PL RTL blocks via iverilog co-sim, 9 PS C blocks via clang++, + the reference models, + a
front-end INTEGRATION co-sim `rtl/test_frontend_integration.py`: two entry points —
`bt656_rx→morph_tophat→hist→[PS C threshold_stats]→ccl→centroid` on one frame — that assert the
composed RTL+PS chain reproduces the Python detect chain bit-exact (a uint16 path and an 8-bit
BT.656-ingest path, the FT640 CVBS reality). This is the PL analog of `ps/seeker_backend`. NB: it
proves the blocks COMPOSE; the synthesizable *streaming* top-level (line buffers around the windowed
stages, AXI-Stream) is still the Vivado-bench task in §3. Sizing scaffolds: `fpga/vivado/`.
**Streaming form STARTED (fielded, synthesis-oriented):** `rtl/win_reduce.v` — a line-buffered
sliding-window min/max primitive (co-sim vs numpy erode/dilate, `test_win_reduce.py`) — and
`rtl/morph_tophat_stream.v` — two cascaded win_reduce (erode→dilate) + an f frame buffer for the
subtract, **byte-exact vs `_white_tophat`** (`test_morph_tophat_stream.py`). This replaces the
frame-addressed footprint sweep with true line-buffer streaming. `rtl/ccl_stream.v` — a **single-pass
streaming union-find** labeller (1-row label line buffer + parent table + one resolve pass) — replaces
the iterative Gauss-Seidel sweeps of `ccl.v`, same grouping as `_connected_components`
(`test_ccl_stream.py`). **All four windowed stages now have a fielded streaming form** (top-hat, hist,
CCL, centroid). **Wired into an RTL top (CAPSTONE):** `rtl/detect_frontend_top.v` chains the whole detect front-end,
**frame → morph_tophat_stream → th_mem buffer → (PS-injected threshold) → mask → ccl_stream → dominant
component → centroid_dp → (cx,cy,den)**, in ONE module with hardware handshakes (two-pass, since the
adaptive threshold needs the full-frame histogram). Co-sim == the Python tophat→threshold→CCL→centroid
chain, dominant centroid bit-exact (`test_detect_frontend_top.py`). What remains for the *synthesizable*
top: an AXI-Stream skin, a divider IP for the centroid, and a bounded/pipelined union-find engine (the
co-sim uses a behavioural pointer-chase); then Vivado synth/P&R. NB across the streaming blocks: output
regs must be NON-BLOCKING so downstream @(posedge) readers/stages sample race-free; the top carries a
sim-time watchdog so a bug can't hang vvp.

---

## 0. What exists (the inventory you're integrating)

**PL (fabric) — RTL, co-sim-verified vs the SW detector:**

| Stage | File | Co-sim |
|-------|------|--------|
| BT.656 ingest (Y frame + SOF/SOL) | `rtl/bt656_rx.v` | `rtl/test_bt656_rx.py` |
| White top-hat morphology (11×11 SE) | `rtl/morph_tophat.v` | `rtl/test_morph_tophat.py` |
| Threshold histogram (per-pixel) | `rtl/hist.v` | `rtl/test_hist_rtl.py` |
| Connected components (4-conn) | `rtl/ccl.v` | `rtl/test_ccl_rtl.py` |
| Weighted-centroid datapath | `rtl/centroid_dp.v` | `rtl/test_centroid_dp_rtl.py` |

**PS (ARM) — C, verified vs the Python modules:**

| Function | File | Verified vs |
|----------|------|-------------|
| Threshold stats (percentile+MAD+sigma-clip) | `ps/threshold_stats.cpp` | `msp_codec`… `_compute_threshold` |
| LOS computer (centroid→bearing+rate) | `ps/los.{h,cpp}` | `seeker.los.LOSComputer` |
| IMM filter (2-mode, 4×4) | `ps/imm.{h,cpp}` | `seeker.imm.IMMFilter` |
| Bearing-rate guidance | `ps/guidance.{h,cpp}` | `guidance.bearing_rate` |
| Assembled main loop + engage gate | `ps/seeker_backend.cpp` | composed Python chain |
| MSP command encoder | `ps/msp.cpp` | `betaflight_link.msp_codec` |
| Commit-based F&F engage FSM | `ps/engage.cpp` | `betaflight_link.engage_fsm` |
| Arming FSM (arm/kill) | `ps/arming.cpp` | `betaflight_link.arming` |
| Independent HW-kill | `ps/hwkill.cpp` | `betaflight_link.hwkill` |

**The PL/PS split:** per-pixel work in fabric (ingest, top-hat, histogram, CCL, centroid); once-per-frame
control-flow on the ARM (threshold stats, LOS/IMM/guidance, safety shell). See
`../docs/FPGA_MIGRATION_ZYNQ7020_FT640LM.md` for the architecture rationale.

---

## 1. Hardware BOM (seeker side)

- **Zynq Mini** board (XC7Z020-CLG400, 512 MB DDR3, HDMI-out, GigE, 34 GPIO).
- **CVBS→BT.656 video decoder** (ADV7280-M or TVP5150 breakout) — the FT640LM is analog CVBS; this
  chip is the one new part that turns it into the 8-bit BT.656 parallel stream `bt656_rx.v` ingests.
  ~9–10 GPIO (8 data + PCLK; sync embedded). Confirm 3.3 V LVCMOS levels; add a level shifter if 1.8 V.
- **FT640LM thermal camera** (or camera #2 behind the same decoder — one BT.656 RX serves both).
- HDMI monitor for the overlay / bring-up.

Flight side (FC, airframe, kill-MCU) is a separate integration; the seeker outputs an MSP RC stream
to a **MockFcChannel** until the whole chain is validated (never wire a live FC before §7).

---

## 2. Toolchain + golden vectors

- **Vivado** (2022.2+ recommended) for the PL; **Vitis / PetaLinux** for the PS.
- PS runtime option: **PetaLinux** (easiest bring-up; the C blocks build as a normal Vitis app;
  you may even run the Python `fpv/` seeker for non-realtime checks) — or bare-metal for determinism.
- **Regenerate the golden vectors** (the bench co-sim inputs) on this machine:
  ```
  cd 03-fpv
  PYTHONPATH=fpv python3 -m fpga.ref_model.golden_vectors --out fpga/ref_model/vectors --frames 120
  ```
  Each scene dir gets `frame_XXXX.bin` (LE uint16) + `manifest.json` (expected detect output +
  ground truth). This is exactly what an HDL/Vitis testbench replays.

---

## 3. Vivado block design (PL dataflow)

Wire the RTL stages into one AXI-Stream pipeline. Border/line-buffer handling is the integration work
(the co-sims verify the interior/numerics; the fielded top-level adds line buffers around each windowed
stage):

```
 [decoder] --BT.656 8b @27MHz--> bt656_rx --Y AXIS (+sof/sol)-->
   morph_tophat --tophat AXIS--> ( hist ==histogram==> PS via AXI-Lite/BRAM )
                                  ( threshold from PS --> compare )
              --binary mask AXIS--> ccl --labels+stats--> centroid_dp --centroid--> PS
 [PL also] --VDMA--> DDR frame buffer --> HDMI overlay compositor
```

Notes:
- `bt656_rx` runs in the **decoder pixel-clock domain** (~27 MHz); cross into the processing clock via
  an AXIS FIFO. Everything downstream is one frame at 60 Hz — a comfortable budget.
- `hist.v` streams the per-pixel histogram; the PS reads the bins (AXI-Lite/BRAM), computes the
  threshold (`threshold_stats.cpp`), writes it back to the mask-compare register. Once-per-frame.
- `morph_tophat.v`/`ccl.v` are written frame-addressed (BRAM in/out) for verification clarity; for
  throughput, replace the frame-BRAM sweep with **line buffers + a sliding window** (same min/max
  numerics — the fixed-point study proved them integer-exact, so no re-verification of the arithmetic).
- **ROI-gate the heavy operators** (audit finding): once locked, run top-hat/MTI/correlation on a
  ~64×64 window around the track gate, not full-frame — the difference between real-time and not.

---

## 4. PL↔PS interface (register/stream map to define)

- **PL→PS (per frame):** blob list — `centroid (Q_x/Q_y fixed-point)`, `bbox (l,t,w,h)`, `area`,
  `snr`, and the `threshold histogram` bins. (These are the outputs `detect_frame` produces in SW.)
- **PS→PL (per frame):** the computed `threshold` (for the mask compare) and, on the actuator side,
  nothing to the PL — the RC goes out over UART as an MSP frame from the PS.
- Use AXI-Lite for the low-rate scalars (threshold, control/status) and AXI-Stream/VDMA for the frame
  + blob stream. **Hardware-timestamp the frame-valid and the IMU sample** in the PL (kills the
  cam↔IMU sync error the audit flagged as the dominant λ̇ term).

---

## 5. PS software (assemble the C into the runtime)

The C blocks already compose (`seeker_backend.cpp` chains LOS→IMM→guidance + the engage gate). The PS
app is: read the PL blob → `los::step` → `imm::step` → `guid::step` → `engage_fsm` (commit authority)
→ `arming` (arm/kill on the committed authorization) → `msp` encode → UART to the FC; `hwkill` gates
motor power independently. Build each `.cpp` in the Vitis app; the `.h` cores (`los/imm/guidance`) are
already namespaced to link together.

Fire-and-forget: `engage_fsm` releases BOTH tethers post-commit (software link-abort AND the HW-kill
beacon latch) — see `../fpv/fpv_ai/sil_runtime.py` (`fire_and_forget=True`) for the wired reference.

---

## 6. Bench bring-up ladder (the ORDER)

Bring it up incrementally; each rung has an objective check. Do NOT skip to a live FC.

- **B0 — HDMI passthrough.** Decoder → `bt656_rx` → HDMI. Objective: see the FT640LM thermal image on
  the monitor. Confirms the decoder, the BT.656 RX, and the pixel-clock crossing. (Recover the exact
  active grid here — it feeds §7 of the migration doc: recompute `ft640_intrinsics` for the real grid.)
- **B1 — detect front-end on target.** Full PL chain → PS reads the blob. Objective: on a hot target,
  the PL centroid matches the SW `detect_frame` on the SAME captured frame (dump a frame, run it
  through Python, compare). This is the on-hardware version of the co-sim.
- **B2 — post-synthesis co-sim.** Replay `fpga/ref_model/vectors/*` through the synthesized netlist
  (Vivado post-synth/post-impl simulation) and diff against the manifests — proves synthesis preserved
  the numerics the behavioural co-sim verified here.
- **B3 — PS chain.** Feed the blob to `seeker_backend` on the ARM; confirm LOS/IMM/guidance produce a
  command (or ROE abort) matching the Python on the same blob stream.
- **B4 — safety shell to MockFC.** Arming FSM + engage FSM + hwkill + MSP → a mock FC channel.
  Objective: reproduce the SIL contract — reaches AI_ACTIVE only on a committed auth; link loss aborts
  pre-commit and is ignored post-commit; HW-kill cuts on beacon loss.
- **B5 — real FC, props OFF, GATED.** Only after B0–B4 and a signed dual-operator authorization. Bench
  the RC on a real FC with **props removed**; verify arm/kill/failsafe on the wire before any flight.

---

## 7. Synthesis / sizing checklist (XC7Z020)

- **Clocks/timing:** 27 MHz decoder domain; ~100–150 MHz processing domain; 60 Hz frame. Constrain the
  BT.656 PCLK input and the AXIS FIFO crossing.
- **Datapath widths (measured here — no re-derivation needed):**
  - Centroid divide: **≤4 fractional bits** (14-bit) / 2 (8-bit CVBS); accumulators **≤23 bits**
    (`Σx·w`) / ≤15 (`Σw`) → a small divider + 32-bit accumulators.
  - Top-hat / CC: **integer-exact** (min/max, labelling) — no error budget, just SE line buffers.
  - Threshold histogram: 2048×20-bit bins (≈40 Kb BRAM); stats on the PS.
- **Resource pressure (7020 is small):** the tight fits are MOSSE/MTI (not in the M0 spine) and
  full-frame morphology — use ROI-gating (§3). The M0 spine (ingest→top-hat→threshold→CCL→centroid)
  fits comfortably; if you later want the full look-down stack full-frame at 60 Hz, step up to a
  larger Zynq (7045 / UltraScale+), which you have.
- **8-bit reality:** the CVBS path is 8-bit AGC, not radiometric Y16 — good enough for the deterministic
  loop now, but the NETD/Pd-vs-range win needs a native-digital Y16 camera later.

---

## 8. Non-negotiable safety gates before any powered flight

- Kinetic action is **default-blocked**; only a valid `operator_authorization.v1` (two Ed25519
  signatures + committed physical keypress + ROE pass + civcas estimate + expiry) can enable it.
  Synthetic authorizations can NEVER arm a live engagement (`arming` invariant 2).
- The engage-FSM keep-out box must be surveyed to a **cleared ground footprint** before enabling F&F.
- HW-kill is the independent backstop — verify its beacon-loss cut and latched operator kill on the
  bench (B4) before trusting the software failsafe.

The kinetic effector cue itself is downstream of all of the above and is deliberately NOT built.
