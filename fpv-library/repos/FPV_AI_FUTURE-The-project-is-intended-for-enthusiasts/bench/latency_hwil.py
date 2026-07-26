"""D1 / R3 HWIL latency harness -- measure REAL closed-loop pipeline latency on-target.

Feeds synthetic thermal frames through the actual ``SeekerGuidancePipeline`` and times each
``pipe.step()`` -- the per-frame compute latency the R1 sim *assumes* and Gate D1 *checks*
(p99 closed-loop latency < one frame; measured <= the R1 sensor-delay assumption).  No camera,
no dataset: pure compute on real silicon.  Toggle the Phase-B perception stages to measure
what they cost on-target (can we afford look-down CFAR / MPCM / MTI / continuity at frame rate?).

    PYTHONPATH=fpv python -u -m fpv_ai.bench.latency_hwil --frames 600 --hz 60
    PYTHONPATH=fpv python -u -m fpv_ai.bench.latency_hwil --frames 600 --region-bands 4 --mpcm \
        --directional-median --motion-gate --trajectory-continuity
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator
from fpv.guidance.pipeline import SeekerGuidancePipeline


def main() -> None:  # pragma: no cover - hardware/timing bench
    ap = argparse.ArgumentParser(description="HWIL closed-loop latency (D1/R3)")
    ap.add_argument("--frames", type=int, default=600, help="measured frames (after warmup)")
    ap.add_argument("--warmup", type=int, default=40, help="warmup frames excluded from stats")
    ap.add_argument("--hz", type=float, default=60.0, help="frame rate the budget is checked against")
    ap.add_argument("--r1-assumption-ms", type=float, default=30.0, help="R1 sensor-delay budget")
    ap.add_argument("--region-bands", type=int, default=0)
    ap.add_argument("--graduated-k", action="store_true")
    ap.add_argument("--mpcm", action="store_true")
    ap.add_argument("--directional-median", action="store_true")
    ap.add_argument("--motion-gate", action="store_true")
    ap.add_argument("--trajectory-continuity", action="store_true")
    # Stage-1/2/3 campaign flags (for per-feature latency profiling on-target):
    ap.add_argument("--use-imm-coast", action="store_true")
    ap.add_argument("--use-peak-relative-deletion", action="store_true")
    ap.add_argument("--use-tau-terminal", action="store_true")
    ap.add_argument("--regime-enabled", action="store_true")
    ap.add_argument("--aimpoint-migration", action="store_true")
    ap.add_argument("--event-channel", action="store_true")
    ap.add_argument("--require-consensus", action="store_true")
    ap.add_argument("--correlation", action="store_true")
    args = ap.parse_args()

    dt = 1.0 / args.hz
    n_total = args.frames + args.warmup
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=0))
    frames = [f for f, _gt in sim.generate(n_total)]

    pipe = SeekerGuidancePipeline(
        region_bands=args.region_bands, graduated_k=args.graduated_k, use_mpcm=args.mpcm,
        directional_median=args.directional_median, motion_gate=args.motion_gate,
        trajectory_continuity=args.trajectory_continuity,
        use_imm_coast=args.use_imm_coast, use_peak_relative_deletion=args.use_peak_relative_deletion,
        use_tau_terminal=args.use_tau_terminal, regime_enabled=args.regime_enabled,
        aimpoint_migration=args.aimpoint_migration, event_channel=args.event_channel,
        require_consensus_for_lock=args.require_consensus, correlation=args.correlation,
    )

    lat_ms: list[float] = []
    n_locked = 0
    for i, frame in enumerate(frames):
        t0 = time.perf_counter()
        out = pipe.step(now=i * dt, frame_u16=frame, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=dt)
        t1 = time.perf_counter()
        if i >= args.warmup:
            lat_ms.append((t1 - t0) * 1e3)
            n_locked += int(out.locked)

    a = np.asarray(lat_ms, dtype=np.float64)
    budget_ms = dt * 1e3

    def p(q: float) -> float:
        return float(np.percentile(a, q))

    feats = [n for n, on in (
        ("region_bands=%d" % args.region_bands, args.region_bands > 0),
        ("graduated_k", args.graduated_k), ("mpcm", args.mpcm),
        ("directional_median", args.directional_median), ("motion_gate", args.motion_gate),
        ("trajectory_continuity", args.trajectory_continuity)) if on]
    print("=== HWIL closed-loop latency (D1/R3) ===")
    print("features : %s" % (", ".join(feats) if feats else "baseline (Phase-A/S1-S3 only)"))
    print("frames   : %d measured (+%d warmup)   locked %d/%d" % (len(a), args.warmup, n_locked, len(a)))
    print("budget   : %.3f ms (one frame @ %.0f Hz)" % (budget_ms, args.hz))
    print("latency  : mean %.3f  p50 %.3f  p90 %.3f  p99 %.3f  max %.3f  (ms)"
          % (a.mean(), p(50), p(90), p(99), a.max()))
    over = int((a > budget_ms).sum())
    print("over-budget frames : %d/%d (%.2f%%)" % (over, len(a), 100.0 * over / len(a)))
    g1 = "PASS" if p(99) < budget_ms else "FAIL"
    g2 = "PASS" if p(99) <= args.r1_assumption_ms else "FAIL"
    print("GATE p99 < one frame (%.2f ms) : %s" % (budget_ms, g1))
    print("GATE p99 <= R1 assumption (%.1f ms) : %s" % (args.r1_assumption_ms, g2))


if __name__ == "__main__":
    main()
