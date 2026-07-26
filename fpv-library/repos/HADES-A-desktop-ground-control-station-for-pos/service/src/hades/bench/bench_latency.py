"""Benchmark CoreML YOLO11s inference latency per resolution on the ANE.

Phase 1.5 Task 1.5.2. Goal: measure **sustained steady-state** ms/frame for each
exported resolution so we can record which resolutions hold the ≥10fps gate
(CLAUDE.md latency budget). The decision is judged on the **MacBook Air M4** — the
field-laptop floor (CLAUDE.md Hard Constraints). The Air is fanless and throttles
under sustained load, so a cold burst would lie; we warm up, then time a sustained
window, so the throttled steady-state shows up in the number.

This measures **latency only** (review note F5). The final resolution pick
(latency × recall) is deferred to P2.5 against fine-tuned recall.

Two layers, deliberately split so the *logic* is offline-testable:
  - `summarize()` / `Decision`: pure stats + the ≥10fps gate. No ML, no hardware.
  - `benchmark_resolution()` / `run_sweep()`: load a `.mlpackage`, drive frames
    through it, time the steady-state window. Needs CoreML + the artifacts; the
    pytest wrapper is marked `@pytest.mark.ane` (manual, excluded on CI).

Run (on the target Mac, after `hades-export-coreml`):
    uv run --group bench hades-bench-latency [--res 640 960 1280] [--models models]
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from hades.bench.export_coreml import DEFAULT_OUT_DIR, DEFAULT_RESOLUTIONS, artifact_path

# The ≥10fps gate: detection runs decoupled from video at ≥10fps (CLAUDE.md).
FPS_GATE = 10.0
# Measurement window defaults. Warm-up lets the ANE/thermals settle; the timed
# window must be long enough that throttling on the fanless Air shows up — a few
# seconds of sustained inference, not a 5-frame burst.
DEFAULT_WARMUP_FRAMES = 30
DEFAULT_MEASURE_FRAMES = 300


@dataclass(frozen=True)
class Decision:
    """Per-resolution latency result and the ≥10fps verdict.

    Attributes:
        resolution: square input side in pixels.
        latencies_ms: per-frame inference times over the measured window.
        median_ms / p90_ms / mean_ms: summary statistics (ms).
        fps_median: 1000 / median_ms — the sustained throughput estimate.
        meets_gate: whether fps_median >= FPS_GATE.
    """

    resolution: int
    latencies_ms: tuple[float, ...]
    median_ms: float
    p90_ms: float
    mean_ms: float
    fps_median: float
    meets_gate: bool


def summarize(resolution: int, latencies_ms: Sequence[float]) -> Decision:
    """Reduce raw per-frame latencies to summary stats + the ≥10fps verdict.

    Pure: no ML, no hardware. This is the unit-testable core of the benchmark —
    the gate decision is exercised offline so a bad threshold can't slip through
    only on a machine with an ANE.

    Throughput is judged on the **median** (not the mean): a single GC/thermal
    spike shouldn't flip the verdict, but a consistently-too-slow resolution
    must fail. p90 is reported so a long tail is visible even when the median passes.
    """
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    if not latencies_ms:
        raise ValueError("latencies_ms must be non-empty")
    if any(x <= 0 for x in latencies_ms):
        raise ValueError("latencies must be positive (ms)")

    ordered = sorted(latencies_ms)
    median = _percentile(ordered, 50.0)
    p90 = _percentile(ordered, 90.0)
    mean = sum(ordered) / len(ordered)
    fps_median = 1000.0 / median
    return Decision(
        resolution=resolution,
        latencies_ms=tuple(latencies_ms),
        median_ms=median,
        p90_ms=p90,
        mean_ms=mean,
        fps_median=fps_median,
        meets_gate=fps_median >= FPS_GATE,
    )


def _percentile(ordered: Sequence[float], pct: float) -> float:
    """Linear-interpolation percentile over an already-sorted sequence."""
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def time_inference(
    infer: Callable[[], object],
    *,
    warmup_frames: int = DEFAULT_WARMUP_FRAMES,
    measure_frames: int = DEFAULT_MEASURE_FRAMES,
) -> list[float]:
    """Drive `infer` repeatedly: warm up, then time each call over the window.

    `infer` is a zero-arg callable that runs one forward pass (its return value is
    ignored). Decoupling the timing loop from CoreML lets the loop itself be tested
    with a fake `infer` — no hardware needed to prove warm-up/window arithmetic.
    Returns per-frame latencies in **milliseconds** for the measured window only.
    """
    if warmup_frames < 0 or measure_frames <= 0:
        raise ValueError("warmup_frames >= 0 and measure_frames > 0 required")

    for _ in range(warmup_frames):
        infer()

    latencies_ms: list[float] = []
    for _ in range(measure_frames):
        t0 = time.perf_counter()
        infer()
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
    return latencies_ms


def benchmark_resolution(
    resolution: int,
    models_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    warmup_frames: int = DEFAULT_WARMUP_FRAMES,
    measure_frames: int = DEFAULT_MEASURE_FRAMES,
) -> Decision:
    """Load the `.mlpackage` for `resolution` and benchmark sustained inference.

    Lazy-imports CoreML + numpy so this module stays importable without the bench
    deps. Feeds a fixed random RGB frame at the model's input size (latency is
    content-independent for a fixed-shape CNN, so a synthetic frame is honest here).
    """
    import numpy as np
    from coremltools.models import MLModel  # noqa: F401  (import proves availability)

    path = artifact_path(models_dir, resolution)
    if not path.exists():
        raise FileNotFoundError(
            f"missing artifact {path} — run `hades-export-coreml --res {resolution}` first"
        )

    model = _load_mlmodel(path)
    input_name = _coreml_image_input_name(model)
    from PIL import Image

    rng = np.random.default_rng(0)
    frame = Image.fromarray(
        rng.integers(0, 256, size=(resolution, resolution, 3), dtype=np.uint8), mode="RGB"
    )

    def infer() -> object:
        return model.predict({input_name: frame})

    latencies = time_inference(
        infer, warmup_frames=warmup_frames, measure_frames=measure_frames
    )
    return summarize(resolution, latencies)


def run_sweep(
    resolutions: Sequence[int] = DEFAULT_RESOLUTIONS,
    models_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    warmup_frames: int = DEFAULT_WARMUP_FRAMES,
    measure_frames: int = DEFAULT_MEASURE_FRAMES,
) -> list[Decision]:
    """Benchmark each resolution in turn. Returns one Decision per resolution."""
    return [
        benchmark_resolution(
            r, models_dir, warmup_frames=warmup_frames, measure_frames=measure_frames
        )
        for r in resolutions
    ]


def _load_mlmodel(path: Path):
    """Load a `.mlpackage` with ComputeUnits.all (ANE/GPU/CPU placement)."""
    from coremltools import ComputeUnit
    from coremltools.models import MLModel

    return MLModel(str(path), compute_units=ComputeUnit.ALL)


def _coreml_image_input_name(model) -> str:
    """First input feature name from the CoreML spec (the image input)."""
    return model.get_spec().description.input[0].name


# A run on the ANE must be meaningfully faster than CPU_ONLY; below this speedup
# we can't claim the Neural Engine actually served the model (Core ML places
# per-op and silently falls back to GPU/CPU). 2× is a deliberately loose floor —
# observed speedup is ~5.6× — chosen to flag a real CPU fallback, not noise.
ANE_SPEEDUP_FLOOR = 2.0


@dataclass(frozen=True)
class AnePlacement:
    """Result of the ANE-placement check (does `ComputeUnits.all` use the ANE?)."""

    resolution: int
    cpu_only_ms: float
    all_ms: float
    speedup: float
    ane_served: bool


def assess_ane_placement(resolution: int, cpu_only_ms: float, all_ms: float) -> AnePlacement:
    """Decide whether `ComputeUnits.all` was ANE-served, from the two medians.

    Pure (no ML): `ALL` tracking `CPU_ONLY` means Core ML fell back to CPU; `ALL`
    being ≥`ANE_SPEEDUP_FLOOR`× faster means the ANE (or GPU) actually served it.
    Split out so the verdict logic is unit-tested without hardware.
    """
    if cpu_only_ms <= 0 or all_ms <= 0:
        raise ValueError("latencies must be positive (ms)")
    speedup = cpu_only_ms / all_ms
    return AnePlacement(
        resolution=resolution,
        cpu_only_ms=cpu_only_ms,
        all_ms=all_ms,
        speedup=speedup,
        ane_served=speedup >= ANE_SPEEDUP_FLOOR,
    )


def verify_ane_placement(
    resolution: int,
    models_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    warmup_frames: int = DEFAULT_WARMUP_FRAMES,
    measure_frames: int = 80,
) -> AnePlacement:
    """Benchmark the same model under `CPU_ONLY` then `ALL`; assess placement.

    This is the load-bearing check for the whole spike: a fast number is only a
    valid ANE number if the ANE actually served it. Lazy-imports CoreML.
    """
    import numpy as np
    from coremltools import ComputeUnit
    from coremltools.models import MLModel
    from PIL import Image

    path = artifact_path(models_dir, resolution)
    if not path.exists():
        raise FileNotFoundError(
            f"missing artifact {path} — run `hades-export-coreml --res {resolution}` first"
        )
    rng = np.random.default_rng(0)
    frame = Image.fromarray(
        rng.integers(0, 256, size=(resolution, resolution, 3), dtype=np.uint8), mode="RGB"
    )

    def _median_ms(compute_unit) -> float:
        model = MLModel(str(path), compute_units=compute_unit)
        name = model.get_spec().description.input[0].name
        lat = time_inference(
            lambda: model.predict({name: frame}),
            warmup_frames=warmup_frames,
            measure_frames=measure_frames,
        )
        return _percentile(sorted(lat), 50.0)

    cpu_only = _median_ms(ComputeUnit.CPU_ONLY)
    all_units = _median_ms(ComputeUnit.ALL)
    return assess_ane_placement(resolution, cpu_only, all_units)


def format_table(decisions: Sequence[Decision]) -> str:
    """Render results as a markdown table — pasted straight into the results doc."""
    header = (
        "| Resolution | median ms | p90 ms | mean ms | fps (median) | ≥10fps? |\n"
        "|---:|---:|---:|---:|---:|:---:|"
    )
    rows = [
        f"| {d.resolution} | {d.median_ms:.1f} | {d.p90_ms:.1f} | {d.mean_ms:.1f} "
        f"| {d.fps_median:.1f} | {'✅' if d.meets_gate else '❌'} |"
        for d in decisions
    ]
    return "\n".join([header, *rows])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hades-bench-latency",
        description="Benchmark CoreML YOLO11s ANE latency per resolution (Phase 1.5 spike).",
    )
    parser.add_argument(
        "--res", type=int, nargs="+", default=list(DEFAULT_RESOLUTIONS),
        help="resolutions to benchmark (default: 640 960 1280)",
    )
    parser.add_argument("--models", default=DEFAULT_OUT_DIR, help="dir holding .mlpackage artifacts")
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP_FRAMES, help="warm-up frames")
    parser.add_argument(
        "--frames", type=int, default=DEFAULT_MEASURE_FRAMES, help="timed frames per resolution"
    )
    parser.add_argument(
        "--verify-ane",
        action="store_true",
        help="also check the ANE actually serves ComputeUnits.all (CPU_ONLY vs ALL speedup)",
    )
    args = parser.parse_args(argv)

    decisions = run_sweep(
        args.res, args.models, warmup_frames=args.warmup, measure_frames=args.frames
    )
    feasible = [d.resolution for d in decisions if d.meets_gate]
    print(format_table(decisions))
    print()
    print(f"feasible (>= {FPS_GATE:.0f}fps) resolutions: {feasible or 'NONE'}")

    if args.verify_ane:
        # Verify at the smallest resolution — placement is per-graph, not per-size,
        # so one check confirms the model runs on the ANE rather than CPU.
        res = min(args.res)
        p = verify_ane_placement(res, args.models, warmup_frames=args.warmup)
        verdict = "ANE-served ✅" if p.ane_served else "CPU FALLBACK ⚠"
        print()
        print(
            f"ANE placement @ {res}: CPU_ONLY={p.cpu_only_ms:.1f}ms ALL={p.all_ms:.1f}ms "
            f"speedup={p.speedup:.1f}x -> {verdict}"
        )
        if not p.ane_served:
            return 1  # a fast latency number that's actually CPU is a failed spike
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
