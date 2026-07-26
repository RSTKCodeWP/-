<!-- Code-grounded go/no-go for the first field trial. Supersedes the REMAINING_WORK line-items where they are stale. Update when reality changes. -->

# BLOCK-03 — FIELD-TRIAL READINESS (go/no-go), 2026-07-21

> **What this is.** A single, code-grounded checklist for a **first field trial**, measured against the tree
> at HEAD `49db86b` (`block3-realdata-safety`) on 2026-07-21. It supersedes stale line-items in
> `REMAINING_WORK.md` (2026-07-19) where the code has since moved. Governing rule unchanged:
> **Наука во главе — a claim is worth exactly its evidence.** Where this file and an older doc disagree,
> trust the code; every green box below names what was run.

## One-line status

**The software and firmware for the chosen build are ready and were exercised end-to-end at the desk today.
Nothing blocks a field trial except the physical build (GAP 1) and the bench-HIL closure (GAP 2) — both of
which are hands-on-hardware, not code.** The one desk-reachable risk to field *success* — perception on real
thermal — was baselined today and has three concrete, fixable failure modes (below).

---

## Verified today (evidence, this tree)

| # | check | result | how |
|---|---|---|---|
| 1 | Component gate green | **675 passed, 71 deselected, 3 xfailed** (2:08) | `pytest -m "not slow"` |
| 2 | Integrated closed loop runs (synthetic) | reaches `AI_ACTIVE` @frame 8; commands 32/60; no false arm | `sil_runtime --scene approach --goal KINETIC` |
| 3 | Sticky-abort on link loss (negative control) | link-loss@15 → `ABORTED(link_loss_timeout)` → `KILLED`, `eff_pwr=False`; **stays killed even when the track re-locks @39** | `sil_runtime … --link-loss-at 15` |
| 4 | All flight/bench tooling imports w/o hardware | **12/12 OK** (`flight_gimbal`, `flight_head`, `msp_override_flight`, `sil_runtime`, `real_ingest`, `bench_hil`, `bench_runner`, `gimbal_bench_io`, `pi5_io`, `hwkill`, `arming`, `failsafe`) | import probe |
| 5 | FC flash config sound | `mask=15` (Pi cannot arm), MSP override AUX2, stray-ARM on AUX3 removed, payload GPIO removed, `failsafe DROP` | review `INTERCEPTOR_CLI.md` |
| 6 | Kill-MCU firmware = spec | `hwkill_mcu.ino` faithfully ports `hwkill.py` (4 invariants, default-deny at boot, latched kill, wrap-safe beacon) **plus** a stuck-clock detector the host spec can't model | review `.ino` vs `hwkill.py` |
| 7 | Perception on REAL thermal baselined | runs on Halmstad IR clips; per-target metrics captured (below) | `real_ingest` on `demo/real/*.mp4` |

The kill-MCU stub that `REMAINING_WORK.md` still lists (`clock_is_valid()`) is **no longer a stub** — it has
a real stuck-timer detector. That line in `REMAINING_WORK.md` is stale.

---

## The three gaps to a field trial (owner-tagged)

### GAP 1 — Build & flash the real airframe · **owner: hands + parts** · code side DONE
Everything code/firmware is ready (checks 5–6). Remaining is physical and procurement-gated:
- [ ] Re-flash SpeedyBee F405 V4 with `INTERCEPTOR_CLI.md`; verify `diff` shows MSP override + mask 15, no stray ARM, no payload GPIO.
- [ ] Flash RP2040 kill-MCU (`hwkill_mcu.ino`); **bench the safety contract props-OFF** (no beacon→CUT, beacon→power, beacon-stop→CUT ≤500 ms, KILL→latched).
- [ ] Mount FT640 on the 2-axis gimbal + Pi 5 + kill-MCU; wire the **three independent domains** per `firmware/WIRING.md` (flight power / kill / radio — never cross-power; gimbal servos on I2C only, never motors).
- [ ] Calibrate head-IMU axes/signs and servo rad→pulse (`seeker_core/calibrate_gimbal.py`). A wrong sign drives the target OUT of frame.

> ⚠️ Hardware note from the ops memory: the I2C bus **hard-locks under servo power** (grounding/BEC/cap) —
> resolve this on the bench before trusting the gimbal in the air.

### GAP 2 — First hardware-in-the-loop closure · **owner: hands on bench** · harness DONE, never closed live
- [ ] **Step 4 dry run (props OFF):** `msp_override_flight no-camera`, then `flight_gimbal --dry` — gimbal centres a warm object, logged FC channels stay neutral until the toggle is held, throttle never exceeds `--throttle-max-us`.
- [ ] **Step 5 static-stand HIL (props OFF):** head on `bench_runner`, warm target moved by hand; confirm the gimbal holds it and the guidance command tracks in the right direction. **This is the first real-seeker loop closure — the biggest unknown in the repo.**

### GAP 3 — First flight · **owner: hands in field** · gated on GAP 1 + GAP 2
- [ ] Per `FLIGHT_TEST_OVERRIDE.md`: fly manually; hold the toggle to hand the seeker a **bounded envelope** (slow, overhead, well-cued target, up-camera cone); release or Pi-loss returns the sticks; kill-MCU is the last-resort power cut. Cleared/surveyed keep-out footprint, spotters, pilot on the backup.

---

## Perception on real thermal — measured, then CORRECTED (honesty ledger)

> **Doctrine correction (owner, 2026-07-21) — load-bearing.** The target is **not a uniform hot point.** It is
> a **winged UAV** whose thermal signature is non-uniform (hot engine/exhaust, cooler airframe) and
> **aspect-varying** (head-on compact; side/beam an elongated resolved wingspan; rear exhaust-dominated), and
> the launch can be **from any angle into any aspect, against any background** (cold sky, hot ground, horizon,
> sun). This **voids the earlier "cold-sky, compact-target, from-below" scoping.** Hot-background and resolved/
> elongated cases are **IN-envelope**, not out of it. The honest state below is re-scored against this.

**Envelope map** — detect/lock across the winged-UAV (airplane) aspect/background clips (`real_ingest`, bare +
auto-polarity; 8-bit lossy source — **indicative, definitive test is raw Y16**):

| result | clips | reading |
|---|---|---|
| **holds** (100% detect, 5–10 s lock, 0–1 hop) | 001, 009, 010, 011, 013, 014, 015, 016 (**8/10**) | most aspects/backgrounds are tracked |
| **DETECT FAIL — in-envelope** | **002** (0%) | hot textured background raises the adaptive CFAR threshold above the target → 0 detections. NOT top-hat size suppression (refuted: 002's target is small 16×4 px; the 216 px resolved target is 009, which detects). region-CFAR / MPCM did not recover it. |
| **marginal** | **003** (1.1 s lock, 53 px jump) | hard aspect/clutter case |

So perception is **neither "3 gross failures" (my first pass) nor "mostly fine" (my over-correction)**: **8/10
aspect/background clips hold, with a real in-envelope detection hole (002, background-clutter CFAR
desensitisation) and a marginal case (003).**

**The 8-bit desk ceiling — measured, not assumed.** Three separate pieces of the perception stack cannot
function or be validated on the 8-bit colormapped clips, and **all three trace to one root: the colormap/AGC
destroys the radiometric dynamic range they depend on.**
1. **Detection (002):** background clutter lifts the adaptive CFAR threshold above the compressed target → 0.
2. **Resolved-target aimpoint:** the migration machinery exists (`aimpoint.py silhouette_centroid`, default-OFF)
   and targets exactly the doctrine problem — the motor-glow hotspot **walking across the airframe as aspect
   rotates head-on→beam**. But on 8-bit it is **dead**: the silhouette threshold (`base + 5σ` ≈ 11102) overshoots
   the compressed target peak (≈ 8800) → always falls back to the hotspot centroid → **0 migration** — and the
   walk it fixes is itself a radiometric effect the colormap flattens (measured offset hotspot↔silhouette ≈ 0 on
   every resolved clip).
3. **Silhouette / subtense range:** same 5σ overshoot → no footprint.

**Conclusion: 8-bit desk perception is exhausted.** It confirmed the tracker holds most aspects, found the
in-envelope clutter hole, and *proved* the resolved-target machinery needs Y16 to even run. **The definitive
perception work — detection under clutter, aimpoint on a resolved aspect-varying airframe, subtense — requires
raw Y16 from the QD115TB. Do not tune on the lossy proxy.**

The two sub-claims below still stand as recorded (they concern the *metric* and the *config*, not the envelope).

### Retracted: "association hopping on ~half the clips"
The metric was wrong. `centroid σ` over a multi-second lock conflates a target **legitimately traversing the
frame** (a crossing aircraft moves tens of px, all tracked correctly) with tracking error. Re-measured with a
**per-frame centroid-jump** metric (a hop = a sudden large single-frame displacement):

| clip | detect | lock | median jump | max jump | **hops >15 px** | net travel |
|---|---|---|---|---|---|---|
| AIRPLANE_009 | 100% | 8.5 s | 0.00 | 3.2 | **0** | 3 px |
| AIRPLANE_001 | 100% | 5.3 s | 2.04 | 12.3 | **0** | 29 px |
| DRONE_002 | 100% | 9.9 s | 1.19 | 2.0 | **0** | 64 px |
| BIRD_001 | 100% | 6.7 s | 0.00 | 0.4 | **0** | 0 px |
| AIRPLANE_010 | 100% | 9.9 s | 0.00 | 19.8 | 1 | 19 px |
| HELICOPTER_001 | 100% | 6.8 s | 1.21 | 38.9 | **3** | 114 px |

The tracker is **solid** on the doctrine-relevant cases (compact target, cold-ish sky): 0 hops while smoothly
following tens of px of traversal. Occasional real hops survive only on the hardest / non-doctrine clips
(helicopter rotor + 114 px traversal: 3 hops; one on AIRPLANE_010). Not a systemic defect — no code fix
warranted on 8-bit data.

### Retracted: "region-CFAR + sky basket is the validated real-data config"
A config sweep (2026-07-21) showed region-CFAR + sky-basket **did not help and often hurt** (DRONE_001 jump
0.07 → 83 px; AIRPLANE_009 lock 248 → 68), while **~doubling per-frame cost**. `real_ingest`'s headless path now
defaults to the **bare** pipeline (which measured best) and `--region-cfar` is opt-in. Correlation / JPDA /
trajectory-continuity added nothing to stability on these clips.

### Stands: one real detector gap + one polarity footgun (both fixed/characterised)
- **`AIRPLANE_002` — 0% detection under every config.** Root cause found: a **hot, structured background**
  (counts mean 9520; threshold ~13000 below the frame peak, yet 0 blobs) — the small-target top-hat suppresses
  a large/low-contrast target on a warm background. It is **out of the doctrine geometry** (camera-up vs cold
  sky), but a real limitation for low-elevation / hot-ground engagements. Left for **real Y16** rather than
  tuned on a lossy proxy.
- **Auto-polarity (shipped).** `real_ingest --auto-polarity` now decides white-hot/black-hot from the peak
  white-top-hat vs black-hat response (matches what the detector keys on; robust to a hot background).
  Validated: **0 false flips on every real clip**, recovers clean black-hot; conservative (defaults white-hot)
  on cluttered black-hot. Removes the operator footgun where a wrong manual `--invert` silently breaks lock.

### The real desk-reachable lever turned out to be latency, not accuracy (Pi)
Profiling the bare pipeline on real frames: most clips run **16–22 ms/frame on a Mac**, but the large-blob clip
(`AIRPLANE_009`) hits **126 ms (8 fps)** — and a large blob is exactly the **terminal phase** (target close →
blob big). On a Pi 5 (~3–5×) that is ~400–600 ms/frame right when the loop matters most. `cProfile` pins it on
`detect_frame`'s **per-blob statistics loop** (~1650 tiny numpy reductions/frame = pure Python-call overhead,
not heavy math). Two levers measured:
- **ROI-gating** (built-in, WAVE 2): 4× median on normal clips at **no accuracy cost** (DRONE lock/hops
  unchanged); 14× on 009 **but** with a large-blob accuracy cost (lock 248→154, +8 hops). Enable for normal
  operation; needs blob-aware ROI sizing before trusting on a large terminal blob.
- **Vectorise the per-blob loop** (`scipy.ndimage` labeled stats — one C call for all labels): the clean,
  no-accuracy-cost fix, but it is **core `detect.py` surgery** requiring strict before/after blob-equivalence.
  **Not yet done — recommended next, gated on the owner accepting core-file risk vs. deferring to the bench.**

**Gate:** fast gate **675 passed, 3 xfailed** after the `real_ingest` changes — no regression.

---

## Recommended next work, in order

1. **The real perception work is aspect/background invariance, and its definitive home is Y16.** The any-angle/
   any-aspect/any-background doctrine makes perception genuinely **under-validated**, with a measured in-envelope
   hole (002, background-clutter CFAR desensitisation) and the resolved-target aimpoint question open (009). On
   8-bit colormapped clips I can only find gross holes; setting the fix needs **labeled raw Y16 from the
   QD115TB** — which is GAP 2 and needs the hardware online. **Do not tune the detector on 8-bit — it overfits.**
2. **Pi latency (parallel, safe desk work):** vectorise `detect_frame`'s per-blob loop (`scipy.ndimage` labeled
   stats) — real Pi win, core-file risk under strict before/after blob-equivalence. Independent of the envelope
   question.
3. **Hands + parts (yours):** GAP 1 build & flash; bench the kill-MCU safety contract.
4. **Hands on bench (yours), me co-driving:** GAP 2 dry run → **record raw Y16 from the QD115TB across aspects
   and backgrounds**, then static-stand HIL — where the 002-class background-clutter hole and the resolved-target
   aimpoint get their definitive test and tuning.
5. **Field (yours):** GAP 3 first flight, bounded envelope, manual backup live.

## Bottom line

The system is **not** a safety-guaranteeing device and this trial does not make it one. On the corrected
doctrine (a resolved, aspect-varying winged UAV engaged from any angle against any background), perception is
**neither as broken as my first pass nor as fine as my second**: **8/10 aspect/background clips hold, with a
real in-envelope detection hole (002) and a marginal case (003)**, and the resolved-target aimpoint is open.
The honest measurement tools are now in place (per-frame jitter, auto-polarity, envelope map) and the fast gate
is green — but the **definitive perception work needs labeled Y16**, so the critical path is still **record on
the real seeker → bench HIL → fly**, with detector tuning done there, not on a lossy proxy.
