# Phase 4 Localization - Research Gate / Decision Record

Status: DECIDED. This is the gate. No Phase 4 code lands until this is reviewed.
Source: five independent expert-lens stress-tests (mc-propagation, fusion,
coverage-anticircular, sim-design, scope-simplicity), folded by the lead engineer.
Every conflict between lenses is resolved explicitly below ("which lens won, why").

Codebase facts this record is anchored to (verified, not assumed):
- `service/src/hades/locate/geometry.py` - `ray_to_ground` is the single source of
  truth. It REFUSES (raises `ValueError`) on: no GPS fix, any None attitude, None alt,
  non-finite lat/alt/attitude/ground_elev/pixel, datum mismatch. It enforces
  `ray.Up < 0` (no phantom pin behind the drone). `R_world_body(roll,pitch,yaw)` is
  the shared rotation-convention builder.
- `service/src/hades/locate/frame_gate.py` - `OBLIQUE_PITCH_CUTOFF_DEG = 65.0`
  (degrees from nadir). Gate owns fusion-eligibility, never visibility.
- `service/src/hades/locate/projector.py` - `GroundPoint.fusable` is True only when
  the gate passed AND a coordinate exists. Fuse consumes `GroundPoint`s.
- `service/src/hades/detect/detector.py:64` - `StubDetector(Detector)` exists (CPU,
  deterministic).
- `service/src/hades/cli/replay_dump.py` - already wires
  `FileFrameSource` + `SrtFileSource` -> `align()` -> Detector -> ByteTracker ->
  Confirmation on CPU. Task 4.7 is NOT a first assembly.
- `service/src/hades/ingest/telemetry_source.py` - `Pose(t, lat, lon, alt, alt_datum,
  roll, pitch, yaw, seq, gps_valid, abs_alt)`. The `.srt` replay path is
  position-only (roll/pitch/yaw = None).

---

## 1. METHOD CONFIRMATION

### 1.1 Fusion algorithm - full-2x2-information weighted mean in ENU meters

DECISION. Fuse N per-frame ground points with a **full 2x2 inverse-covariance
weighted mean** (the linear-Gaussian BLUE / MAP for N independent estimates of one
fixed 2-vector). Computed in the **local ENU tangent plane in meters** about a fixed
mission origin. Never average lat/lon degrees (lon scale varies with cos(lat)).

```
xi      in R^2          # per-frame ground point (ENU east,north, meters)
Sigma_i in R^2x2        # per-frame ground covariance (see 1.3)
Lambda  = sum_i Sigma_i^-1                       # total information (2x2)
x_hat   = Lambda^-1 . sum_i ( Sigma_i^-1 . xi )  # fused ENU point
Sigma_fuse = Lambda^-1                           # BEFORE the bias floor of section 2
```

Per-frame weight is the **full information matrix `Wi = Sigma_i^-1`**, NOT a scalar
`1/trace(Sigma_i)` or `1/R95_i^2`.

WHY full-2x2, not scalar. The dominant error (heading) makes `Sigma_i` strongly
anisotropic and rotated; its long axis points along the camera-to-target azimuth,
which changes as the drone flies past. The entire (modest) fusion gain on a
heading-limited system is azimuthal diversity collapsing the cross-range axis. A
scalar weight discards orientation and throws away exactly that signal. Full
`Sigma_i^-1` also AUTOMATICALLY down-weights oblique/long-range frames (their
`Sigma_i` is huge along down-range), so the design's "oblique/long-range
down-weighted" is an emergent consequence, not a separate hand-tuned heuristic. Do
not state it twice in code or it gets double-counted.

WHY batch weighted-mean FORM, not a streaming information filter / Kalman recursion.
For a STATIONARY target the constant-state info filter, RLS-with-forgetting-1, and
the batch weighted mean are the SAME estimator written three ways. The batch form is
chosen because it (a) recomputes cleanly when the tracker re-associates or drops a
frame, (b) runs the moving-target residual test (section 6) over the same buffer,
(c) is re-entrant for operator-promote-on-demand. N is tens-to-low-hundreds of frames
per contact; 2x2 math; rebatching is free. A streaming IF buys a covariance recursion
we would have to test for zero benefit.

CONFLICT RESOLVED. fusion lens and scope-simplicity lens AGREE (weighted average, not
IF/Kalman) and the math identity makes "which algorithm" a non-question. fusion lens
WON on the precise form: it must be **full-information weighted**, not the
scalar/`np.mean` reading that "geometry-weighted average" invites. Committed phrase
for code + doc: "full-information (`Sigma_i^-1`) weighted mean."

### 1.2 Uncertainty propagation - Monte Carlo, N=1000 (2000 for the validation report)

DECISION. Propagate input sigmas to the reported 2x2 ground covariance / ellipse /
R95 by **Monte Carlo**. Reject Unscented Transform and linearized-Jacobian as the
PRIMARY reported propagator.

- **N = 1000 draws** default, exposed as a config knob (do not auto-tune). **N = 2000
  for the offline coverage-validation report** (where the coverage number itself must
  be stable to < 1%). Backed numerically by the mc-propagation lens: R95 has MC
  standard error ~2.3% at N=1000 (3.3% at 500, 1.6% at 2000); ellipse semi-axes
  ~2.2% at N=1000. Diminishing returns past 2000.
- **Fixed seed per contact** for reproducibility. Use **antithetic / quasi-random**
  sampling so N=1000 behaves like ~N=2000 (cheap variance reduction, no bias). Use
  **common random numbers across contacts** so frame-to-frame ellipse jitter comes
  from geometry, not RNG churn.
- MC runs **only on confirmed/promoted contacts in Fuse (cold path)**, never
  per-detection at 30 fps. One contact's N=1000 MC is order tens of microseconds. The
  Projector hot path stays single-ray with no MC, exactly as designed.

WHY MC over linearized. At a heading-limited oblique operating point (AGL 80 m, 12 deg
depression -> 376 m ground range, sigma_yaw=25 deg) the linearized 95% ellipse covered
only **87.2%** of truth (target 95%) AND its naive R95 (major semi-axis * 2.4477 =
402 m) OVER-states the true 95% radius (313 m) by ~28%. It is wrong in both directions
at once. Unusable for an honesty claim.

WHY MC over UT. UT covered well on that run (95.4%) and recovered the nonlinear mean
bias with 7 points, genuinely better than linearization. It is rejected as primary
anyway because: (a) UT matches only the first two moments; it cannot give the
empirical R95 quantile the contact record is built on without ASSUMING Gaussian, and
the banana is exactly where Gaussian-from-covariance breaks (the MC's own Gaussian fit
gives 93.7%, not 95%); (b) UT covariance is fragile near the AGL=H/cos blowup, where a
single sigma point at high pitch can shoot a near-horizon ray and detonate the weighted
covariance, and UT has no spare point to reject it (MC can reject draws individually);
(c) UT (alpha,beta,kappa) is another knob set to defend at a research gate; MC has none.

CONFLICT RESOLVED. mc-propagation, fusion, and scope-simplicity lenses ALL chose MC.
No conflict. The cross-lens nuance: the CHEAP linearized Jacobian is still used, but
only for the per-frame WEIGHT `Sigma_i` (section 1.3), never for the final reported
ellipse. fusion lens WON that split.

### 1.3 Per-frame `Sigma_i` for the weight - cheap linearized Jacobian (NOT per-frame MC)

DECISION. Do NOT run MC per frame. Per fusable frame get `Sigma_i` by first-order
linearized propagation through `ray_to_ground`:

```
Sigma_i = Ji . Sigma_inputs . Ji^T
Ji = d(east,north)/d(roll,pitch,yaw,lat,lon,alt,ground_elev)   # 2x7 Jacobian
```

`Sigma_inputs` is the diagonal of input variances from the shared `error_model`
schema. `Ji` is computed by central finite-difference on `ray_to_ground` (7 extra
calls per frame, negligible) or analytically later. This gives a correctly-rotated,
correctly-scaled per-frame covariance at near-zero cost for the weight.

REQUIRED RECONCILIATION UNIT TEST. Near nadir, linearized `Sigma_i` and full MC
`Sigma_fuse` MUST agree within tolerance (they describe the same thing where the
geometry is near-linear). Divergence at high obliquity is EXPECTED and is precisely
why the REPORTED ellipse uses MC. Assert agreement near nadir; assert MC tail >=
linearized tail oblique. Forbid the implementer from using the cheap Jacobian for the
final reported ellipse (it under-reports the oblique tail).

---

## 2. THE BIAS FLOOR (the headline honesty point)

YES. R95 gets an explicit, non-shrinking bias floor. This is the single most important
correction the lenses make and it is the flagship's honesty claim.

> **IMPLEMENTATION NOTE (Phase 4, superseded form).** The additive analytic floor
> `Sigma_report = Lambda^-1 + Sigma_bias` specified below as "non-negotiable" was SUPERSEDED in
> the implementation by the §1.2 Monte-Carlo-over-fusion approach, which delivers the same
> non-shrinking behavior more honestly. The reason is empirical: the linearized additive form
> UNDER-COVERED (matched coverage 0.46, mean NEES ~11) because at the 20 deg heading scale the
> ray map is non-linear and the per-frame errors correlate, so `Lambda^-1` itself was wrong.
> MC-over-fusion (`fuse._mc_fused_cov`) resamples inputs, draws the heading bias ONCE per
> realization (the common-mode rule), re-fuses, and reports the cloud spread - matched coverage
> 0.99, NEES ~1. Because the bias is shared across a realization's frames it does not average
> out, so R95 still asymptotes to a floor that grows with the heading lever arm (ground range),
> never to zero (verified seed-robust: short-standoff ~10 m vs long-standoff ~59 m). The
> reported R95 is the EMPIRICAL 95th-percentile cloud radius about x_hat (§4), not the additive
> covariance. The §2 intent (a non-shrinking, range-scaled, honest floor) holds; the mechanism
> is MC, not the additive term. The math below documents the original reasoning.

THE PROBLEM. Inverse-variance averaging assumes N independent zero-mean errors. The
heading error is neither. On one straight pass the yaw for every frame is the SAME
COG-derived value with the SAME wind-crab offset `b` (5-40 deg). Decompose:

```
xi = x_true + b_common + eps_i      eps_i ~ N(0,Sigma_i) independent
                                    b_common = correlated heading-bias displacement
```

Averaging drives `eps_i` down as ~1/sqrt(N_eff), but `b_common` is OUTSIDE the average
and passes straight through: `E[x_hat] = x_true + b_common`. As N -> infinity,
`Lambda^-1 -> 0` but the estimate converges to a CONFIDENTLY WRONG point. A naive
`Sigma_fuse = Lambda^-1` therefore LIES MORE as it sees more frames - the canonical
"smug filter," the worst failure a SAR localizer can have.

THE FIX - three required representations:

1. **Bias floor on the reported covariance (non-negotiable).** The reported
   uncertainty is NOT `Lambda^-1`:

   ```
   Sigma_report = Lambda^-1 + Sigma_bias
   Sigma_bias  ~= J_yaw . sigma_b^2 . J_yaw^T   (evaluated at the representative
                                                 median-range/median-azimuth frame)
   ```

   `Sigma_bias` is the systematic heading-bias contribution that does NOT average
   down. It is added AFTER fusion and is INDEPENDENT of N. `J_yaw` is the
   down-range/cross-range sensitivity ~= 1.75 m / 100 m range / degree. Consequence:
   **R95 asymptotes to a floor `R95_min ~= k * range * sigma_b` (k ~= 1.75 m/100m/deg,
   2-sigma), NOT to zero.**

2. **The error_model heading sigma MUST split into two fields**:
   - `heading_jitter_sigma_deg` - zero-mean, frame-independent, AVERAGES DOWN.
   - `heading_bias_sigma_deg` - crab/COG offset, common across a pass, does NOT
     average down, drives the floor.
   This is a required schema change before Task 4.1 freezes (see section 3). The MC
   draws the heading bias ONCE PER CONTACT (shared latent across all frames of a
   pass), and the GPS/attitude jitter PER FRAME. Drawing the bias i.i.d. per frame
   would fake an error reduction fusion cannot achieve on a single straight pass - the
   "smug filter" again, inside the MC this time. This is the single most important
   correlation to model and the original plan did not state it.

3. **Aspect diversity is the only real cure, and it is MEASURABLE in v1.** A heading
   bias displaces the ground point roughly perpendicular to the camera-to-target
   azimuth. Observed from a SPREAD of azimuths the common bias projects to different
   ground directions and partially cancels; from one azimuth it does not cancel at
   all. Compute per contact:

   ```
   az_i          = atan2(target_ENU - drone_nadir_ENU)   per fused frame
   aspect_spread = circular spread of {az_i}             (circular std or max-min)
   ```

   - `aspect_spread < ~20 deg` (one straight pass): apply the FULL `Sigma_bias` floor,
     set `heading_limited = True`, and **cap actionability at SWEEP** (never PINPOINT)
     no matter how small `Lambda^-1` got.
   - `aspect_spread > ~70 deg` (orbit / multiple passes): bias is partially
     observable; reduce the floor by the cancellation factor.
   v1 only RELAXES the floor based on measured geometry. It does NOT estimate the bias
   as a free state (Schmidt-consider stays v1.x). This makes "attack heading or
   nothing" a quantitative gate, not a slogan, and is the honest use of the
   `HeadingSource` seam.

4. **`localization_confidence` binds to `R95(Sigma_report)`** (floor-inclusive), not
   to `Lambda`. So a long single straight pass shows HIGH detection confidence,
   CAPPED localization confidence. That separation stops the smug-filter lie from
   reaching the operator.

REQUIRED UNIT TEST. `R95(N -> infinity)` converges to `R95_floor > 0`, and the floor
SCALES WITH SLANT RANGE. This is also a clean non-tautological coverage check: with one
pass and a real bias, coverage of `Lambda^-1` alone collapses; coverage of
`Sigma_report` holds.

CONFLICT RESOLVED. fusion lens OWNS this section (it is the one that derived the floor
math and the schema split). mc-propagation lens INDEPENDENTLY arrived at the same
once-per-contact common-mode bias draw from the MC side - they reinforce, no conflict.
scope-simplicity lens defers the *estimation* of the bias (Schmidt) to v1.x and is
satisfied by the floor + measured aspect-spread; that boundary is adopted.

---

## 3. SENSOR-ERROR SCHEMA (`error_model.py`)

DECISION. One frozen dataclass, the SHARED SCHEMA consumed by both the sim (to inject
noise) and the MC (to propagate assumed sigmas). Each receives its OWN INSTANCE
(values may differ - see section 4). The conversion of fields into distributions /
perturbations lives at each CONSUMER; the schema is pure declarative params. Defaults
grounded in the SOTA findings (M10-class GPS, no magnetometer, O4 mount).

```
@dataclass(frozen=True)
class SensorErrorModel:
    # --- GPS position (drone), per-axis, METERS ---
    gps_horiz_sigma_m: float        = 2.5      # 1-sigma horizontal; M10 SBAS-class. Per E,N indep.
    gps_vert_sigma_m: float         = 5.0      # 1-sigma vertical; GPS vert ~1.5-2x horiz.
    gps_dist: str                   = "gauss"  # "gauss" | "studentt" (heavy-tail mismatch knob)
    gps_studentt_dof: float         = 4.0      # used only when gps_dist="studentt"

    # --- Attitude, DEGREES, roll/pitch/yaw SEPARATE (they are NOT equal: the headline) ---
    roll_sigma_deg: float           = 1.5      # FC AHRS w/ accel leveling: good.
    pitch_sigma_deg: float          = 1.5      # same; + O4 mount-angle error folds in here.
    yaw_jitter_sigma_deg: float     = 20.0     # zero-mean heading jitter; AVERAGES DOWN. (15-30 range)

    # --- Heading SYSTEMATIC error (does NOT average down; drives the bias floor, sec 2) ---
    heading_bias_sigma_deg: float   = 12.0     # 1-sigma of the crab/COG-vs-heading offset. Floor driver.
    crab_angle_deg: float           = 8.0      # nominal mean wind-crab offset (5-40). A BIAS, per pass.
    crab_sign_random: bool          = True     # crab sign varies with wind/leg; sampled per run.

    # --- Boresight (camera<->body mount alignment), DEGREES ---
    boresight_sigma_deg: float      = 0.1      # cheap/calibratable; small on purpose.

    # --- Time sync (video frame <-> pose), MILLISECONDS ---
    t_sync_offset_ms: float         = 0.0      # CONSTANT lag pose-behind-video. THE named MC-blind term.
    t_sync_jitter_ms: float         = 15.0     # zero-mean per-frame jitter in the pairing.

    # --- Ground-plane elevation uncertainty, METERS ---
    sigma_h_m: float                = 3.0      # operator flat-earth elevation error -> down-range error.

    # --- Pixel / detector footedness, PIXELS ---
    pixel_sigma_px: float           = 3.0      # box bottom-center jitter (detector localization noise).
    foot_bias_px: float             = 0.0      # systematic feet-vs-box-bottom offset (prone bias knob).
```

Load-bearing defaults, tied to findings:
- `yaw_jitter_sigma_deg = 20` (mid of 15-30) is the HEADLINE: heading-limited, no
  usable magnetometer (COG + gyro). Roll/pitch at 1.5 deg are an order of magnitude
  tighter. The schema FORCES roll/pitch/yaw to be separate fields so no one can
  collapse them to one "attitude sigma."
- `heading_bias_sigma_deg = 12` and `crab_angle_deg = 8` are the BIAS knobs. When the
  MC ignores `heading_bias_sigma_deg` / `crab_angle_deg`, coverage breaks (the
  non-tautology proof, section 5).
- `t_sync_offset_ms = 0.0` DEFAULT, but the mismatch fixtures set it to 50-200 ms
  (at 15 m/s that is 0.75-3.0 m pose-position error per frame in a consistent
  down-track direction) - the named dominant failure the MC does not model.
- `sigma_h_m = 3.0` flat-earth elevation guess error; couples to down-range error
  growing as 1/cos^2(nadir angle), so it dominates the oblique strata.

SCHEMA-CHANGE NOTE vs the original CLAUDE.md/DESIGN wording. The design listed a single
"heading sigma + crab/bias." This record SPLITS it into `yaw_jitter_sigma_deg`
(averages down) and `heading_bias_sigma_deg` + `crab_angle_deg` (do not). This split
is mandatory and must land before Task 4.1 freezes the schema.

AUDITABILITY. The dataclass docstring must name which fields the MC reads vs which the
sim reads, so the "shared schema, not shared values" rule is auditable (scope-simplicity
lens requirement).

CONFLICT RESOLVED. sim-design lens authored the 16-field schema. fusion lens demanded
the heading split (one field -> jitter + bias). The split WON and is folded in
(sim-design's single `yaw_sigma_deg` is replaced by `yaw_jitter_sigma_deg` +
`heading_bias_sigma_deg`). All other sim-design fields adopted verbatim.

---

## 4. ANTI-CIRCULARITY

There are TWO distinct circularity risks with DIFFERENT mitigations. Conflating them is
the trap.

### Risk A - "forward == inverse" makes the METER-ERROR metric circular

THE QUESTION the prompt asks: if the sim forward-projects with the same shared function
the MC inverts, is meter-error circular? ANSWER: it WOULD be if the sim inverted
`ray_to_ground`. The mitigation is a HARD architectural rule that it does not.

RULE.
- The sim's forward projector `geom_sim.world_to_pixel` (world -> pixel) MUST NOT call,
  import, or invert `ray_to_ground`. It is written from first principles as the
  FORWARD collinearity equation:
  ```
  p_enu = enu_offset(drone_latlon -> target_latlon, H)
  r_cam = (R_world_body @ R_body_cam).T @ p_enu     # transpose of the world rotation
  require r_cam[2] > 0                               # target in front of the lens
  u = fx * r_cam[0]/r_cam[2] + cx
  v = fy * r_cam[1]/r_cam[2] + cy
  then forward-distort (the inverse of geometry._undistort)
  ```
- SHARE ONLY the convention-loaded primitives that are too dangerous to duplicate:
  `CameraModel.K`, `R_body_cam`, and `geometry.R_world_body(roll,pitch,yaw)`
  (the ZYX + NED->ENU adapter). Re-deriving the rotation in the sim would create a
  SECOND place for a sign-flip bug to live, which is worse.
- NEVER share the projection SOLVER (`ray_to_ground` <-> `world_to_pixel`).

PROOF OBLIGATION (this is what makes it defensible, not asserted):
- A zero-noise round-trip test (`world_to_pixel` then `ray_to_ground` recovers the
  target to < 1e-6 m across the strata) is NECESSARY but EXPLICITLY NOT SUFFICIENT: a
  shared rotation-convention bug would cancel in the round-trip and still pass. So the
  round-trip is a sanity check, not the anti-circularity guarantee.
- The actual guarantee: each path is independently pinned to its OWN hand-derived
  analytic fixtures. `ray_to_ground` is anchored by `test_geometry.py` against
  hand-derived truth (the 173.2 m due-North case, the 10 m East case).
  `world_to_pixel` is anchored by its OWN fixtures in `test_geom_sim.py` (a target
  10 m East at H=100 under a nadir mount lands at exactly `(cx + fx*0.1, cy)`; a nadir
  target lands at `(cx, cy)`) - hand-computed from similar triangles with NO reference
  to `ray_to_ground` outputs. A shared-bug rotation would have to satisfy BOTH
  independent analytic anchors simultaneously, which a sign error cannot.

### Risk B - sim and MC sharing noise VALUES makes the COVERAGE metric circular

This is the one the project memory flags. The mitigation: the `SensorErrorModel` is a
SCHEMA; the sim and the MC each get their OWN INSTANCE.

THE PRECISE RULE (stop overloading the word "coverage" - split it into two claims):

| Claim | Proven by | Does NOT prove |
|---|---|---|
| C1 propagation is arithmetically correct | MATCHED case -> coverage in [93,97]% | that the assumed sigma values are right |
| C2 the uncertainty is HONEST under model error | MISMATCHED cases -> coverage degrades in the predicted direction and magnitude | (this is the whole ballgame) |

MAY be shared (and MUST be, or you are not testing one system): the geometry
(`ray_to_ground`, both paths call the identical function); the SCHEMA of `error_model`
(field names, units, frame conventions); the nominal trajectory + detection pixel
stream; the chi^2(2)=5.991 ellipse construction.

MUST differ for C2 to mean anything - and "value vs value" is the wrong axis. The real
axis is DISTRIBUTION MODEL, four degrees of freedom (each a real failure): magnitude
(sim sigma != MC sigma), shape (sim heavy-tailed vs MC Gaussian), mean (sim biased vs
MC zero-mean), and ERROR NOT IN THE SCHEMA AT ALL (time-sync offset). The honest
restatement of the rule:

> The anti-circularity guarantee is NOT "different values." It is: the MC must never
> see the sim's realized noise (only the shared config object), AND at least one
> mismatch case must inject an error mode the MC's schema cannot represent at all (the
> time-sync offset). If every mismatch is "same family, different number," a reviewer
> can argue you only tested mis-tuned-but-correctly-shaped Gaussians.

CODE TEETH (the test file MUST enforce):
1. ONE geometry - both sim and MC call the identical `ray_to_ground`.
2. NO LEAKAGE - assert the MC sampler is seeded independently and is NEVER handed the
   sim's realized error array, only the shared config object. A unit test fails if
   someone wires the sim's draws into the MC.
3. BANDS, NOT POINTS - predicted numbers are measure-then-lock; the committed asserts
   are the PASS CONDITION column (directions + thresholds), robust to the tuned sigma.
4. The suite FAILS if EVERY mismatch is downward-Gaussian - a meta-assertion requires
   the time-sync (out-of-schema) row AND the over-estimate (upward) row to be present.
5. FUSION-WORSENS SIGNATURE - for the two systematic rows (crab, time-sync), assert
   `cov(N=30) < cov(N=1)`. This is what distinguishes a BIAS (fusion amplifies it
   relative to the shrinking ellipse) from a variance underestimate (fusion leaves it
   roughly flat), and is the single most convincing demonstration the validation
   measures the world, not its own arithmetic.

CONFLICT RESOLVED. sim-design and coverage-anticircular lenses fully AGREE on the
two-risk split. coverage-anticircular WON on the sharpest framing ("must inject an
out-of-schema error mode; different values is insufficient"). sim-design WON on the
forward/inverse independent-anchor mechanism for Risk A. No conflict - they cover the
two halves.

---

## 5. COVERAGE TEST MATRIX (`eval/coverage.py`)

Config: error_model SCHEMA shared. Geometry = same `ray_to_ground`. MC NEVER sees the
sim's realized draws. Trajectory (all rows unless noted): straight transect,
v = 15 m/s, AGL = 60 m, ~30 deg off-nadir, stationary survivor (straight + constant-v
makes any bias maximally systematic = the adversarial worst case). Trials: >= 2000 MC
realizations per row (CI on 95% coverage ~ +/- 1% at N=2000). Report at fusion
N = {1, 30}. Metrics per row: empirical coverage (%), mean NEES (target ~2),
R95 median (m).

```
ROW                          SIM noise               MC noise          COV(N=1)  COV(N=30)  meanNEES  PASS CONDITION
matched_control              N(0,sigma) all          N(0,sigma) same    93-97%    93-97%    ~2        cov in [93,97] AND NEES in [1.7,2.3]
sigma_underestimate          heading N(0,1.5sig)     heading N(0,sig)   70-80%    lower     ~4-5      cov < 88% (strictly below control)
sigma_overestimate           heading N(0,0.6sig)     heading N(0,sig)   99-100%   99-100%   ~0.4      cov > 98% (two-sided detection)
heading_bias_crab            heading N(8deg,sig)     heading N(0,sig)   75-85%    50-65%    5-12      cov(N=30) < cov(N=1)  [fusion worsens]
gps_heavy_tail               GPS Student-t(3,sig)    GPS N(0,sig)       88-93%    88-93%    ~2.5      cov < control BUT > 85%  [small, by design]
TIME_SYNC_50ms               offset 50ms @15m/s      no time term       88-92%    70-80%    3-6       cov(N=30) < cov(N=1)
TIME_SYNC_100ms (HEADLINE)   offset 100ms @15m/s     no time term       75-85%    40-55%    8-20      cov(N=30) < 80% AND < cov(N=1)
TIME_SYNC_200ms              offset 200ms @15m/s     no time term       50-65%    10-25%    >20       cov(N=30) < 30%  [collapse]
```

Predicted numbers are predictions to MEASURE then LOCK to a regression band on first
real run; the COMMITTED asserts are the PASS CONDITION column (directions + thresholds).

Why the time-sync row is the headline. A video frame at true time t paired with pose at
t + delta gives position error v*delta in a consistent down-track direction. At
v=15 m/s a delta=100 ms offset = 1.5 m bias PER FRAME. Fusion of a stationary survivor
averages many frames that ALL share the same directional bias -> the ellipse SHRINKS
while the center stays WRONG. That is the worst SAR failure: FALSE PRECISION. No choice
of sigma in the MC can absorb it (it is out-of-schema), which is what makes the suite
non-tautological by construction. The load-bearing assertion is the MONOTONE one:
`cov(N=30) < cov(N=1)` for any delta>0, falling below ~80% by 100 ms. If fused coverage
does NOT drop relative to single-frame, the MC is secretly absorbing the bias and the
test is compromised.

Two deliberate non-downward rows. INCLUDE `sigma_overestimate` (coverage rises to
~100%): proves the metric is two-sided and can tell honest-but-useless (R95 huge,
coverage 100%) from honest-and-tight. STATE that the heavy-tail effect is SMALL and
WHY (heading dominates the ellipse, so GPS tails are a minor lever) - predicting a
small drop and measuring it is more credible than predicting drama everywhere. If t(3)
GPS DID tank coverage, that is a finding (GPS unexpectedly dominant), not a pass.

NEES DECISION: IN for v1, as a SCALAR diagnostic (mean NEES + % within chi^2 bounds),
NOT a full ANEES/Snedecor-F apparatus.

CONFLICT RESOLVED - this is the one real cross-lens disagreement. scope-simplicity lens
said CUT NEES to v1.x ("coverage covers it, half the code"). coverage-anticircular lens
said KEEP it ("~15 lines on top of coverage; you already compute Sigma and the error
vector for the ellipse; NEES is one quadratic form `r @ inv(Sigma) @ r`"). The
coverage-anticircular lens WINS, for a concrete reason scope-simplicity missed: coverage
is a single pass/fail (is truth inside the ellipse). Two opposite errors CANCEL in it -
an ellipse too big in range but too small in cross-range still scores ~95% while being
wrong about SHAPE, and shape drives the PINPOINT/SWEEP/AREA class and the searched-area
map layer. NEES weights the error by the full 2x2 (`(x_hat - x_true)^T Sigma^-1
(x_hat - x_true)`), so an over-tight axis inflates it even when the point is inside.
Mean NEES ~ 2 is the consistency target. NEES earns its keep on the time-sync and crab
rows specifically: under a systematic bias with fusion, mean NEES BLOWS UP well above 2
and RISES WITH N - a cleaner "this is a bias, not under-sized noise" fingerprint than
coverage alone, and that bias-vs-variance distinction is INVISIBLE to coverage. The
scope concern is answered by capping scope: scalar mean NEES + chi^2 bound %, reported
in the matrix; SKIP ANEES confidence intervals, NIS-over-time, per-axis decomposition
unless /codex flags a specific row.

One-line rule for the doc: coverage answers "is the radius honest on average?";
mean-NEES answers "is the whole ellipse honest, including shape and hidden bias?" -
report both, they cost the same.

---

## 6. MOVING-TARGET / CONVERGENCE

### 6.1 Convergence / divergence test - NIS-style residual consistency + drift-slope

Fusion assumes a static target, so a moving target produces per-frame points that MARCH
rather than SCATTER. Detect by checking residuals against the per-frame covariances:

```
ri       = xi - x_hat                 # each fused frame's residual (2-vector)
d2_i     = ri^T . Sigma_i^-1 . ri     # squared Mahalanobis, ~ chi^2(2) if static & noise correct
NIS_bar  = (1/N) sum_i d2_i           # mean normalized residual; E[d2]=2 under H0: static
```

Decision rules:
- STATIC / converging-normally: `NIS_bar <= 2*tau` (tau ~ 2-3, tuned on sim).
- MOVING (or unmodeled bias / association error): `NIS_bar` stays high and/or GROWS as
  the buffer extends. Do NOT collapse the radius. Freeze the contact in CONVERGING, set
  `Sigma_report` to the EMPIRICAL scatter `Sigma_emp = (1/(N-1)) sum_i ri ri^T`
  (inflated, since it reflects the spread the model cannot explain), and flag
  `moving_suspected = True`. This is exactly the design's "non-converging -> big radius,
  never PINPOINT" but as a TEST, not a hope.

Second, cheaper trend signal (use ALONGSIDE, not instead): fit a line to xi vs frame
time and test the slope against zero given `Sigma_i`. A significant net drift velocity
(`|v_hat| > 3*sigma_v`) is direct motion evidence. NIS catches scatter+drift; the slope
test catches steady drift even when NIS is borderline (a slowly drifting target in
water). Trigger non-convergence on EITHER.

Per-frame chi^2 outlier reject (robustness, prevents NIS misfire on a single bad box):
before declaring "moving," reject any frame with `d2_i > 13.8` (chi^2(2) 99.9%) from the
FUSED MEAN. Still show it as a detection (the gate owns fusion-eligibility, never
visibility - consistent with the existing `frame_gate` contract). Distinguish "one
outlier" (reject the frame, keep converging) from "systematic spread" (NIS_bar high
AFTER outlier rejection -> genuinely moving/biased).

LINKAGE WORTH RECORDING. The named time-sync anti-circularity failure (section 5) shows
up in THIS SAME `NIS_bar`: a video<->pose offset the MC does not model produces
residuals larger than `Sigma_i` predicts -> `NIS_bar > 2` and coverage drops. One
statistic detects motion AND model-mismatch (time-sync). The MC must stay blind to the
time offset (schema-shared, value-mismatched) or the coverage-drop test goes
tautological.

### 6.2 CONVERGING <-> STABLE state machine (Schmitt + dwell, instant demotion)

The state variable is the reported `R95 = R95(Sigma_report)` (FLOOR-INCLUSIVE, section 2),
NOT `Lambda^-1` - so a smug-filter shrink can never flip a contact to STABLE.

```
CONVERGING -> STABLE   (ALL must hold for >= N_dwell consecutive fused frames, e.g. 10):
  (a) R95 <= R_enter                       # tight enough (enter threshold)
  (b) |dR95| / R95 < eps_rate per frame    # radius stopped shrinking (converged, not still moving)
  (c) NIS_bar <= 2*tau                      # residuals consistent w/ static (6.1) -- HARD precondition
  (d) N_fused >= N_min                       # enough frames (e.g. >= 8); guards a 2-frame "lucky tight"

STABLE -> CONVERGING   (ANY triggers, IMMEDIATELY, no dwell -- degradation is instant & honest):
  (e) R95 >= R_exit                          # radius grew back past exit threshold (R_exit > R_enter)
  (f) NIS_bar > 2*tau_exit                   # consistency broke (target moving / new bias)
  (g) |x_hat - x_dispatched| > R95           # estimate jumped beyond its own circle after dispatch
```

Anti-flicker hysteresis (three mechanisms, all needed):
1. DUAL THRESHOLDS (Schmitt): `R_enter < R_exit` with a deliberate gap, e.g.
   `R_enter = 0.8 * R_class`, `R_exit = 1.25 * R_class`. A contact hovering near a class
   boundary cannot oscillate every frame.
2. MINIMUM DWELL: STABLE requires enter conditions for `N_dwell` consecutive frames
   (~0.3-1 s at 10 fps fused). One good frame can't promote.
3. ASYMMETRIC LATENCY: promotion (->STABLE) is slow (dwell-gated); demotion
   (->CONVERGING) is instant. Never linger in a falsely-confident STABLE state.

ORTHOGONALITY (prevents contradiction). `PINPOINT/SWEEP/AREA/CUE-ONLY` is the R95-band
classification (pure function of R95 + gate verdict + the `heading_limited` cap from
section 2). `CONVERGING/STABLE` is the temporal-stability axis. Both belong in the
record. RULE: a contact may be `PINPOINT` ONLY IF `STABLE` AND `aspect_spread`
sufficient - a single-pass heading-limited contact is capped at SWEEP EVEN WHEN STABLE,
because STABLE means "variance stopped shrinking," NOT "bias is gone." This is the clean
composition of sections 2 and 6.

CONFLICT RESOLVED. fusion lens authored both 6.1 and 6.2; sim-design lens independently
required a moving-target NON-CONVERGENCE row in the strata report (adopted in section
7). scope-simplicity lens's "running variance of incoming points exceeds fused
covariance -> don't converge" is the SAME test as 6.1, stated less formally; the formal
NIS version WON (it is what makes section 5's time-sync linkage work). No conflict.

---

## 7. SCOPE (4.1-4.9): minimal-but-honest, with deferrals and the 4.7 assembly order

### Per-task scope

- **4.0 RESEARCH GATE** - THIS DOC. No code. CUT the literature dump (the SOTA survey
  is already in memory). Lands exactly the decisions above with numbers. Done when it
  states them.

- **4.1 error_model + HeadingSource** - keep, minimal. One frozen dataclass (section 3,
  WITH the heading jitter/bias split) + one `HeadingSource` interface, v1 impl returns
  the configured large heading sigma; seam for future magnetometer/aspect-diversity.
  The schema MUST carry `t_sync_offset_ms` AND `sigma_h_m` explicitly or 4.5's mismatch
  test has nothing to perturb. Docstring names which fields the MC reads vs the sim
  reads (auditability).

- **4.2 geom_sim** - keep, minimal. Forward `world_to_pixel` (independent equation,
  section 4 Risk A) + zero-noise round-trip test. SCOPE CAP: a single configurable
  STRAIGHT pass at a target gives slant-range + pitch stratification for free. Orbit /
  lawnmower / figure-8 / wind-gust paths are v1.x. (sim-design lens proposed
  Orbit/Lawnmower/Hover/Straight; scope-simplicity capped v1 at the straight pass -
  the cap WINS for v1; the others land in v1.x when a stratum cell needs denser n.)

- **4.3 Fuse** - full-information weighted mean (section 1.1), NOT an information
  filter. Imports `geometry.ray_to_ground` (the SAME function as the Projector). Moving
  target stays CONVERGING via the residual test (section 6.1). Add per-frame chi^2
  outlier reject.

- **4.4 uncertainty** - Monte Carlo, N=1000 (section 1.2), NOT UT. MC samples poses
  from `error_model` (heading BIAS drawn ONCE per contact, jitter per frame) ->
  re-project each via the same `ray_to_ground` (per-sample `ray.Up < 0` reject + max
  ground-range cap; count rejects; >5% rejects -> force CUE-ONLY floor) -> 2x2 covariance
  -> 95% ellipse (scale = sqrt(5.991) = 2.4477) + R95 as the EMPIRICAL 95th-percentile
  sample radius (NOT the major semi-axis). Actionability class = 3 threshold
  comparisons on R95. Surface the MC-mean-vs-nominal-pin offset as honest bias.

- **4.5 coverage** - keep, the flagship's credibility. The matrix in section 5,
  matched->~95% / mismatched->drops, time-sync named. NEES IN as a scalar diagnostic.

- **4.6 contact record** - MINIMUM HONEST record the localizer can populate TODAY:
  `track_id, lat, lon, R95, actionability_class, convergence_state{CONVERGING|STABLE},
  heading_limited(bool), aspect_spread, detection_conf, localization_conf, frame_id,
  age, moving_suspected, reject_fraction`. ALSO emit ellipse (semi-axes + orientation)
  as the expert overlay, distinct from R95. DEFER to v1.x: `clearance_state` (a
  UI-mutated mission-log field, not a localizer output), `snapshot+delta` wire
  optimization (premature - emit full records until profiling says otherwise),
  `cluster` id (only meaningful once multi-survivor disambiguation exists, which v1
  does not claim). Adding JSON fields later is cheap and backward-compatible.

- **4.7 assemble + WS** - see order below.

- **4.8 detector->localizer glue** - keep, highest value-per-line. Focused unit test of
  the SEAM: does `box_xyxy` (top-left origin, +x right / +y down per `Detection`)
  arrive at `ray_to_ground`'s `pixel` arg in that exact convention, and is the
  FOOT/BOTTOM-CENTER (not box center) used as the ground-contact pixel? Silent-wrong-
  coordinate bug class. Not E2E.

- **4.9 meter-error report (flagship close)** - `hades-locsim` reports median / mean /
  p90 / max meter-error + empirical coverage, STRATIFIED by slant-range x pitch-from-
  nadir. Plus a separate MOVING-TARGET non-convergence row (must show CONVERGING + big
  radius, never PINPOINT). Honesty framing in section 8.

  Stratification bins (sim-design lens, adopted):
  - slant range (m): [0-30) [30-80) [80-150) [150-300) [300+)
  - pitch from nadir (deg): [0-15) near-nadir, [15-35) moderate, [35-55) oblique,
    [55-65) high-oblique, [65+) GATED (the last bin must show the gate firing and the
    frames surfacing as CUE-ONLY).

### Deferred to v1.x (none load-bearing for the flagship claim)
Information filter / Kalman recursion (4.3); Unscented Transform (4.4); ANEES /
NIS-over-time / per-axis NEES (4.5 keeps only scalar mean NEES); curved/orbit/lawnmower/
wind flight paths (4.2); `clearance_state` / snapshot+delta wire opt / `cluster` id
(4.6); aspect-diversity / multi-bearing heading TRIANGULATION impl (the `HeadingSource`
SEAM is the v1 deliverable; the impl is a whole estimation sub-project = the single
biggest scope-creep trap); Schmidt-consider bias ESTIMATION (v1 only floors + relaxes on
measured aspect-spread); real-flight meter validation (gated on the ~2026-07-01 dataset).

### Task 4.7 - safest assembly order + stub-detector CPU decision

REFRAME (verified): 4.7 is NOT the first assembly. `cli/replay_dump.py` already wires
FrameSource + SrtFileSource -> `align()` -> Detector -> ByteTracker -> Confirmation on
CPU, with a swappable `_make_detector(stub|onnx|coreml)`, and `StubDetector` exists at
`detector.py:64`. 4.7 adds exactly THREE deltas: (a) Fuse on confirmed tracks, (b) WS
emit on two channels, (c) a long-running loop instead of a batch dump. Scope 4.7 to
ONLY those deltas; do not re-wire what `replay_dump` proves.

STUB-DETECTOR DECISION: YES, CPU-only. `loop.py` takes a `Detector` by injection
(default resolved lazily, like the CLI). The 4.7 pytest passes `StubDetector()` ->
fully offline + deterministic. The ANE/CoreML path stays `@pytest.mark.ane` (manual on
the M4), matching the P1.5 pattern. DO NOT import CoreML at module top in `loop.py`.

Assembly order (each step independently runnable before the next):
1. LOOP over the proven chain, NO Fuse, NO WS - pull frame+pose via `align()`, run
   StubDetector -> Tracker -> Projector -> Confirmation, just count/log outputs. Proves
   the long-running loop + drop-to-latest does not deadlock or leak. (= `replay_dump`
   minus the dump, plus a loop.)
2. ADD WS emit, still NO Fuse - emit `DetectionMessage` (JSON) + JPEG (binary) on the
   two channels; a Python WS client asserts `frame_id` alignment across BOTH channels
   against a MULTI-FRAME fixture (a one-frame fixture hides ordering bugs).
3. ADD Fuse on confirmed tracks + emit `ContactRecord` - last; depends on nothing the
   WS client can't already see.

Seams that will actually break (ranked):
- (HIGHEST) frame_id JOIN across two WS channels - binary JPEG vs JSON arrive on
  separate sockets with separate buffering; a late/dropped frame must not desync the
  join. Test WITH DROPS in the fixture.
- POSE-NONE / gate-reject frames - `ray_to_ground` RAISES on position-only or
  non-finite poses (strict by design). The `.srt` replay path is position-only
  (roll/pitch/yaw = None) -> EVERY projection raises. The loop MUST catch this and emit
  a CUE-ONLY / no-fused-estimate contact, NOT crash and NOT drop the detection from
  view. Most likely 4.7 crash; a GUARANTEED hit on the validation path. Name it in the
  4.7 test.
- BACK-PRESSURE / drop-to-latest - if the WS consumer is slow, the loop drops frames,
  never blocks detection. Reuse the ingest drop-to-latest discipline; do not invent a
  new queue.
- AXIS CONVENTION - real, but OWNED by 4.8 and de-risked by `replay_dump` already
  running the same projector path. Do not double-test it in 4.7.

CONFLICT RESOLVED. scope-simplicity lens owns this section end to end; the other lenses
do not contest it. Its one cross-cut with fusion/mc-propagation (NEES, IF vs weighted
mean, MC vs UT) is resolved in their favor in sections 1 and 5 above, and the deferral
list reflects those resolutions.

---

## 8. OPEN RISKS (need the real dataset or a human call)

1. REAL-FLIGHT METER NUMBER IS NOT CLAIMABLE FROM SIM. The sim proves the method is
   correct and the uncertainty is CALIBRATED; it does NOT prove a field meter-accuracy
   number. 4.9 must label every meter number "(sim)" and read: "Localization accuracy in
   a calibrated synthetic simulator whose noise models are tuned to literature /
   test-flight sensor-error distributions - pending confirmation against the
   labeled-with-pose flight dataset (expected ~2026-07-01)." Lead with what the sim
   legitimately proves (unbiased geometry via zero-noise round-trip; error drops
   monotonically with observation count; coverage ~95% matched, drops mismatched).
   Frame heading-limited as a FEATURE: the reported error is dominated by heading sigma
   taken from `error_model`, not from ground truth, so real numbers WILL move when the
   magnetometer-less heading distribution is measured - and the R95/coverage machinery
   is what makes that honest TODAY.

2. HEADING-SIGMA AND CRAB-BIAS DISTRIBUTIONS ARE LITERATURE-ESTIMATED, not measured.
   `yaw_jitter_sigma_deg = 20`, `heading_bias_sigma_deg = 12`, `crab_angle_deg = 8` are
   SOTA-grounded defaults. The whole error budget is dominated by these. They must be
   RE-TUNED from the real test-flight sensor-error distributions when the ~2026-07-01
   dataset lands. Until then the sim's noise model and the headline "heading-limited"
   claim rest on these estimates. NEEDS THE DATASET.

3. ALT DATUM (HAE vs MSL) - already deferred to the ~2026-07-01 dataset (per memory and
   DESIGN.md 3.5). `alt_datum` tag + assert-on-mismatch already in code. The vertical
   error feeds `sigma_h`-coupled down-range error; if the real feed's datum is
   mis-tagged the oblique strata degrade. NEEDS THE DATASET to confirm the tag.

4. `.srt` POSITION-ONLY ATTITUDE-SYNTHESIS SEAM - NOT owned by the sim or this gate.
   The `.srt` path has roll/pitch/yaw = None and `ray_to_ground` refuses it. The
   validation path needs an attitude supplier (gyro-integrated roll/pitch +
   `HeadingSource` returning COG + crab-bias + the large yaw sigma). The sim injects a
   COG-derived heading-with-crab to feed it, but the actual attitude-synthesis impl is
   Phase 4 estimation code, a localizer-architect call. NAMED here as a dependency, not
   resolved. HUMAN/ARCHITECT CALL.

5. TUNABLE CONSTANTS PENDING SIM CALIBRATION (not blocking, but lock on first run, not
   by guess): `tau`/`tau_exit` (NIS thresholds), `N_dwell`/`N_min` (state-machine
   dwell), `R_enter`/`R_exit` (Schmitt gap), `aspect_spread` cutoffs (~20 deg / ~70
   deg), the MC near-horizon reject fraction trigger (~5%), and the per-class R95 band
   edges. Measure on the matched-control sim, then lock to regression bands. Do not
   invent absolute coverage numbers - lock them after first measurement.
