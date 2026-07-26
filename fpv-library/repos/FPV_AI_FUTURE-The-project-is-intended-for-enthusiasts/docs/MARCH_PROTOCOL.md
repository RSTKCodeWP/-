# MARCH protocol — inertial trajectory estimation + slew-to-cue reacquisition

**Problem.** A thermal seeker has a narrow instantaneous field of view (FT640 ≈ 48° full, **half-FOV ≈ 24°**).
When the target briefly disappears — a cloud occludes it, or it jinks out of frame — it keeps moving and ends
up at a bearing **outside the current FOV**. Expanding a pixel gate cannot recover it: it is off-frame. The
sensor must be physically **pointed to where the target should now be**. That is MARCH.

Reference implementation: `fpv/fpv_ai/bench/march_sim.py` (+ tests). Demonstrated: hold-the-gimbal loses the
target to **~99° off-frame**; MARCH slews on the prediction, stays within **~2°**, and re-locks the instant
the target reappears.

---

## 1. Inertial line-of-sight (decouple our own motion)

The target pixel is a bearing in the **camera** frame. To reason about the target's *own* motion we rotate it
into the **world/inertial** frame using what we know about our own attitude:

```
R_cam→world = R_body→world(FC gyro / attitude)  ·  R_gimbal→body(gimbal encoders + gimbal gyro)
u_world = R_cam→world · u_pixel
```

`u_world` is the target's true line-of-sight direction, **free of our own rotation**. On a strapdown mount the
gimbal term is identity and only the body attitude rotates the bearing; on a gimbal the encoders/gyro add the
head angles. This fusion is why the body gyro (FC `MSP_RAW_IMU`) AND the gimbal gyro both matter.

We parameterise `u_world` on the sky dome by `(az, el)` — `el` = angle off vertical (0 = overhead), `az` = azimuth.

## 2. Trajectory estimate (α–β filter → position AND velocity)

An α–β filter on the inertial bearing gives not just where the target is but **where it is going**:

```
predict:   âz ← âz + v̂az·Δt ,   êl ← êl + v̂el·Δt
update:    r = z − prediction
           âz ← âz + α·r_az ,   v̂az ← v̂az + (β/Δt)·r_az     (same for el)
```

`(v̂az, v̂el)` is the target's inertial **angular velocity** — the seed of the dead-reckon. (A full build uses
the same IMM CV/turn models as the tracker; α–β is the minimal honest core.)

## 3. Dead-reckon prediction (while blind)

With no measurement we propagate the estimate forward at the last velocity:

```
û(t) = last bearing + v̂ · (t − t_lost)
```

This is **constant-velocity** dead reckoning. A maneuver *during* the blind window is unobservable and degrades
it — the honest limit that sets the recovery window.

## 4. Uncertainty cone (grows with time-unseen)

The prediction's 1σ angular radius grows monotonically while blind:

```
σ(Δt) = σ0 + q · Δt
```

The gimbal search **sweep widens with σ** — narrow right after loss, broad later.

## 5. Slew-to-cue (point the sensor at the prediction)

Command the gimbal boresight to the predicted bearing, rate- and envelope-limited (Rodrigues rotation of the
boresight vector toward the target vector, ≤ `gimbal_rate·Δt` per step, `el ≤ el_max`). Sweep the σ-cone.

- **Gimbal**: slews independently — the airframe keeps flying its intercept. Clean.
- **Strapdown**: "slewing" = **tilting the whole quad** (roll/pitch) toward the bearing — which also translates
  it (coupled), bounded by 0.84 g and the viewable cone `θ_max + FOV/2 ≈ 64°` off vertical. Yaw only rotates the
  image; it does **not** re-point an up-looking camera.

## 6. Re-ID (LOBL) — grab the SAME target, not clutter

When a blob re-enters the swept FOV, accept it only if it matches the frozen **LOBL study reference**
(aspect / thermal signature / silhouette) AND lands within the predicted σ-cone. Otherwise keep marching. This
is what stops MARCH from re-locking the sun or a decoy.

## 7. Budget / give-up

MARCH runs until either re-ID succeeds (→ back to `LOCKED`), or the dead-reckon window exceeds `march_budget_s`
/ the σ-cone outgrows the reachable sweep → `HARD_LOST`. No infinite hunt on a diverging estimate.

---

### State machine
```
LOCKED ──lose measurement──▶ COAST(brief hold) ──gap>coast──▶ MARCH(slew to prediction, sweep σ)
   ▲                                                              │
   └────────────── re-ID within σ-cone ◀──────────────────────────┤
                                                                   └──gap>budget──▶ HARD_LOST
```

### Honest scope
Angular-domain core (the domain MARCH lives in): true bearing on the sky dome, gimbal pointing, FOV circle,
rate-limited slew, growing uncertainty, constant-velocity dead reckon, re-ID gate. Not yet wired to the live
seeker pipeline or the FC — that needs S0 gyro calibration (clean inertial LOS) and the gimbal control seam.
