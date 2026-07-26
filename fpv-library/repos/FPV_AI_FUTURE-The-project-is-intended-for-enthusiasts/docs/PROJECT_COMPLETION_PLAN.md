> **[HISTORICAL]** — status as of 2026-07-19. 2026-06-20 plan. Its central warning -- that a green test count is not the same as a verified system -- still stands and is worth reading.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Block-3 thermal seeker: completion roadmap synthesized from the 2026-06-20 8-agent code-grounded audit. -->

# BLOCK-3 THERMAL SEEKER — PROJECT COMPLETION PLAN

Synthesized from a full subsystem audit (8 code-grounded auditors: perception, estimation, guidance,
sim-fidelity, safety, hardware, verification, theory). Every item below is traced to a real gap the
audit found in the working tree.

## The headline finding (reframes everything)

The seeker is **algorithmically rich and doctrinally clean**, but a large part of the "330 green /
S3 acceptance" **tests the simulator's own assumptions, not the system**:

- **Mode-A closed loop is near-tautological** — it feeds the analytically-TRUE LOS-rate + white
  per-frame noise straight to guidance (`closed_loop.py:569-570`); the headline 0.02–0.04 m / 100 %-hit
  numbers are a property of the 3e-4 rad clean measurement, not guidance robustness (miss scales ~linearly
  with measurement error; hits collapse by 1e-2 rad).
- **Looming/τ is fed from the TRUE range** (`closed_loop.py:528-531`) — a closing-sign/τ-confidence
  signal a passive monocular channel **cannot** have.
- **The acceptance gates don't use the honest Monte-Carlo** — `test_s3_acceptance.py:209` runs a single
  fixed nominal plant, `latency_jitter_s=0`, no dispersion. The A5 honest-MC machinery (per-seed
  mass/drag/τ, latency jitter, step-jink) **exists but is UNUSED by the gates that produce the green count.**
- **S2 estimator gates inject ground-truth centroid + GT gyro**, not `detect_frame` output — the full
  detector→IMM→guidance chain is never graded end-to-end.
- **Camera-model 2.7× mismatch**: docs/Johnson budget assume FT640 @ 1.33 mrad IFOV; the code hard-codes
  Boson-640 24 mm @ ~0.5 mrad (`f_px=2130`). The quoted 115–190 m detect envelope does not correspond to
  the sim's optics.

None of this means the algorithms are wrong — the audit confirms the science (CFAR, MPCM, Deshpande
max-median, MOSSE/PSR, d(logI)/dt, modified-polar IMM, λ̇-nulling PN) is **correct**. It means the
**evidence is softer than the green count implies.** Wave 1 fixes that first, so every later number is real.

## Status by subsystem (audit verdict)

| Subsystem | Verdict | Biggest gap |
|---|---|---|
| Perception | correct, default-off clean | no ROI-gate → ~388 ms/frame on Pi5 (not real-time); thresholds unvalidated on real AGC |
| Estimation (IMM/JPDA) | filter math sound | rate-channel R double-counts bearing; no Tier-2 1/r observer; no NEES gate |
| Guidance (λ̇-PN/τ) | theory sound | no committed hit-rate vs sustained jink; terminal lead direction-only |
| Sim fidelity | **the weak link** | Mode-A tautological; τ from true range; gates skip honest-MC |
| Safety / Phase C | tether only | onboard abort authority (FSM/COMMIT_GATE/SELF_SAFE/box) NOT built |
| Hardware / lab | bench runs live | only recorder writes lossy annotated MP4 — no raw-uint16 dataset path |
| Verification | behavioral, real | end-to-end chain & real-data validation missing; a few tautological tests |
| Theory / docs | mostly consistent | camera-model drift; NEES gate promised-not-built; RGB-YOLO legacy cruft |

---

## Execution plan — software-completable waves (no lab/flight hardware)

### WAVE 1 — Honest foundation (make the green mean something) · HIGHEST PRIORITY
1. Re-point S3 acceptance gates at `run_monte_carlo(randomize=True, latency_jitter_max_s>0)` + per-seed
   mass/drag/τ dispersion (so the green count exercises the A5 stressors that already exist). [S]
2. Derive looming/τ from the rendered/noisy blob area, not ground-truth range. [S]
3. Replace Mode-A white-noise bearing injection with a noise model fitted to Mode-B pixel-pipeline output
   (centroid quantization + ego residual + SNR-vs-range). [M]
4. Add a correlated/biased LOS-rate error term (AR(1)/random-walk bias + gyro scale-factor) and re-baseline
   the S3 gates; report how miss distributions change. [M]
5. End-to-end acceptance: drive λ̇ from the REAL `detect_frame` centroid + KLT/gyro ego under sync error →
   one miss-distance / λ̇-RMSE gate for the full chain. [L]
6. Fix tautological tests (`test_ego_quality_one_is_a_noop` self-vs-self) and add real `array_equal`
   bit-identity tests for every default-off flag vs a frozen reference. [S]

### WAVE 2 — Real-time on target (ROI-gate + decimation)
1. Add `roi=(x,y,w,h)` to `detect_frame`: crop once, run all morphology/threshold/MPCM/median/CC on the
   crop, offset centroids/bboxes back to absolute coords; unit-test ROI==full-frame centroid. [M]
2. Plumb ROI into `SeekerGuidancePipeline.step()`: when tracking, ROI = tracker-predicted centroid +
   covariance search radius; full-frame only in ACQUIRE/reacquire. [M]
3. Temporal decimation: run directional-median + MTI every Nth frame (reuse last mask); flag N. [M]
4. Re-profile on the RPi5 per flag-combo; tune ROI size + N to p99 < 16.6 ms. [HW — on the Pi]

### WAVE 3 — Estimation / theory correctness
1. Reconcile the camera model: real `ft640_intrinsics()` @ 1.33 mrad / 48.7×38.6°, switch pipeline +
   closed_loop off Boson; re-run closing-geometry acceptance. [M]
2. Fix the rate-channel measurement model (drop az/el-rate from H, or set R_rate=2σ²/dt² with the
   bearing↔rate cross-covariance); re-tune Q. [M]
3. NEES/NIS filter-consistency acceptance over the V3 library + A5 cases → wire into Gate G-A. [M]
4. Tier-2 observability-gated single-state 1/r observer (`seeker/range_observer.py`): looming-τ + own
   lateral accel + IMM rate behind a published observability index; feeds diagnostics/t_go/COMMIT only,
   NEVER the PN gain. [L]
5. Add Coordinated-Turn mode to the IMM bank (CV+Singer+CT); NEES-check the 3-model bank in budget. [M]
6. Feed per-frame detector centroid uncertainty (blob SNR/2nd-moments) into the IMM bearing R. [S]

### WAVE 4 — Lab/dataset infrastructure (software side; unblocks the lab phase)
1. Lossless raw-uint16 clip recorder: per-frame `.npy/.npz` of `frame_u16` BEFORE mask/annotation +
   JSON sidecar (`t_capture_ns`, frame_id, resolution, fourcc, hfov, crop, invert, mask-state). [M]
2. `RecordedClipSource` FrameSource to replay a raw recording through the `--source` seam (D1 HWIL). [S]
3. Stamp every frame `t_capture_ns` (+ `cam_imu_sync_us` placeholder) into telemetry + sidecar. [S]
4. Optional real-gyro reader thread (MSP_RAW_IMU) into `SeekerObserver` so the bench exercises ego. [M]
5. AGC 8-bit↔14-bit bridging/normalization stage + a re-characterization script (runs on recorded clips). [M]

### WAVE 5 — Phase C onboard abort authority (REQUIRES EXPLICIT GO — safety-critical)
1. C1: mission-profile flag `TETHERED_BENCH` vs `FIRE_AND_FORGET`; in F&F, link-loss ≠ ABORT, hwkill
   becomes timed onboard arming/box logic; keep an optional one-way abort beacon that only ADDS a path. [M]
2. C2: `safety/engage_fsm.py` — ACQUIRE→CONFIRM→COMMIT→TERMINAL→ABORT, ABORT reachable-from-any-state &
   latched; + hysteretic `COMMIT_GATE` (AND of track-ID continuity, lock-quality, class-plausible,
   geometry-in-ROE, inside geo/alt/time box, sensor+clock healthy). [L]
3. C2: wire the existing Ed25519/JSONL signed journal to emit a record at every COMMIT and ABORT. [M]
4. C3: extend `ArmingAuthorization` with target-profile + keep-in/no-engage polygon + min/max AGL +
   time-window; per-tick box-check → abort on breach. [M]
5. C3: `SELF_SAFE` state (break-lock, level, fly-to-ditch-waypoint, latch) as the ABORT target instead of
   a bare disarm. [L — design-sensitive]
6. Gate G-C V&V: kill-chain property/branch suite — "wrongly committed" = hard FAIL; "safely aborted a
   real target" = acceptable. Re-parameterize the 84 tether tests per mission profile. [L]

### WAVE 6 — Cleanup / hygiene
1. Quarantine/delete the v1 RGB-YOLO racing-gate lineage (`fpv_ai/gates`, `perception/yolo_offline`,
   `datasets/FpvRacingGateConfig`, `evaluation/gate_lock`, `tracking/reacquire`, `runtime/offline_pipeline`). [M]
2. `geometry.py` unit tests (pixel↔bearing round-trip, FOV-edge angles) + hypothesis property tests
   (round-trip identity, IMM P symmetric+PSD, RANSAC inlier recovery). [M]
3. Doc-vs-code drift: reword APN as gated-to-zero pending Phase-E ToF; realize/relabel the "ten-tau wall". [S]
4. Forward look-down flags through `detect_frame_to_observation` or document baseline-only. [S]

---

## Hardware / lab-blocked (the user's "laboratory" phase — cannot be done from software alone)

- Radiometric / NETD / FOV / intrinsics calibration on a thermal target board / blackbody.
- Cam↔IMU time offset (<1 ms) + gyro scale/bias on a turntable with the FC attached.
- Threshold tuning (MPCM 0.3, region k, MTI diff_k/min_inliers, event k_mad) against held-out real FT640
  look-down clips → pass Gate G-B (no lock-on-clutter, hoverer retained, FA under budget).
- Sim-vs-real validation of one bench/flight bearing-rate trace (NETD, real centroid noise, real latency).
- Strapdown full pitch/yaw ego-compensation validation on the hard-mounted camera.
- Phase-D discrimination ensemble (kinematic + appearance + INT8 CNN, calibrated abstain) trained on
  real imagery.
- Flight ladder (Phase F: R5→R6→R7).

Wave 4 builds the recorder/replay/timestamps so these become "press record in the lab," not new code.

## Recommended order

**Wave 1 → Wave 2 → Wave 3 → Wave 4**, then **Wave 6** cleanup, with **Wave 5 (Phase C)** slotted when the
user explicitly authorizes the safety re-architecture. Wave 1 is first because it makes every subsequent
number trustworthy; without it we would tune against a sim that grades itself.
