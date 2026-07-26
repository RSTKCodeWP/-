"""`hades-make-figures` - render the routine documentation charts (Task 7.2).

Reads the flat data files written by `hades-export-doc-data` and renders one PNG per
figure into `docs/documentation/figures/`. Every chart draws from a real exported file -
no figure invents numbers - and is styled to the HADES design system (the cool-charcoal
canvas + the rationed status hues from docs/DESIGN-SYSTEM.md), so the set reads as one
deliberate family rather than default matplotlib.

The Wolfram hero visuals (Task 7.3) and the qualitative showcase frames (Task 7.4) are
rendered elsewhere; this module owns the bar/line/calibration charts only.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless render; no display needed
import matplotlib.pyplot as plt  # noqa: E402

# --- design-system palette (docs/DESIGN-SYSTEM.md) --------------------------------------
# Chroma lives in data, not chrome: a near-achromatic charcoal canvas, one structural blue,
# and the rationed status hues used for their real meanings (orange = world-urgency only,
# magenta = system-integrity failure only).
BG_BASE = "#0B0E14"
SURFACE_1 = "#141821"
SURFACE_3 = "#28303E"
HAIRLINE = "#33456A"
TEXT_HI = "#E6EDF3"
TEXT_MID = "#AAB4C0"
TEXT_LO = "#8593AD"
BLUE_CORE = "#3B7BC8"
BLUE_BRIGHT = "#5E9BD6"
ST_NOMINAL = "#2FB67C"  # green: healthy / pass
ST_INFO = "#33C5E0"  # cyan: informational / converging
ST_CAUTION = "#E6A23C"  # amber: caution / SWEEP-grade
ST_WARNING = "#E8531F"  # hazard orange: world-urgency (the chosen / headline accent)
ST_CRITICAL = "#F5326B"  # magenta-red: system-integrity failure (the collapse)
ST_STALE = "#7E78A8"  # violet-slate: unknown / off the severity ramp

EXPECTED_FIGURES = [
    "fig-detection-conf-sweep",
    "fig-resolution-tradeoff",
    "fig-quant-delta",
    "fig-loc-error-by-geometry",
    "fig-coverage-calibration",
    "fig-fps-by-resolution",
    "fig-ane-speedup",
    "fig-latency-budget",
]


def _style_axes(ax: plt.Axes) -> None:
    """Apply the charcoal canvas + hairline grid to a single axes."""
    ax.set_facecolor(SURFACE_1)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(HAIRLINE)
    ax.tick_params(colors=TEXT_MID, labelsize=9)
    ax.yaxis.label.set_color(TEXT_MID)
    ax.xaxis.label.set_color(TEXT_MID)
    ax.title.set_color(TEXT_HI)
    ax.grid(True, axis="y", color=HAIRLINE, alpha=0.35, linewidth=0.6)
    ax.set_axisbelow(True)


def _new_fig(w: float = 7.2, h: float = 4.2) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(w, h), dpi=160)
    fig.patch.set_facecolor(BG_BASE)
    _style_axes(ax)
    return fig, ax


def _save(fig: plt.Figure, out_dir: Path, fid: str) -> None:
    fig.tight_layout()
    fig.savefig(out_dir / f"{fid}.png", facecolor=fig.get_facecolor())
    plt.close(fig)


def _read_csv(data: Path, name: str) -> list[dict[str, str]]:
    with (data / name).open() as f:
        return list(csv.DictReader(f))


def _read_json(data: Path, name: str) -> Any:
    return json.loads((data / name).read_text())


# --- detection figures ------------------------------------------------------------------


def _fig_conf_sweep(data: Path, out: Path) -> None:
    rows = sorted(_read_csv(data, "detection_conf_sweep.csv"), key=lambda r: float(r["conf"]))
    recall = [float(r["recall"]) for r in rows]
    precision = [float(r["precision"]) for r in rows]
    confs = [float(r["conf"]) for r in rows]
    fig, ax = _new_fig()
    ax.plot(recall, precision, "-o", color=BLUE_BRIGHT, markerfacecolor=ST_WARNING,
            markeredgecolor=ST_WARNING, linewidth=1.8, markersize=8)
    for rc, pr, cf in zip(recall, precision, confs):
        ax.annotate(f"conf {cf:g}", (rc, pr), textcoords="offset points", xytext=(8, 6),
                    color=TEXT_LO, fontsize=8)
    ax.set_xlabel("recall")
    ax.set_ylabel("precision")
    ax.set_title("Detection operating points (confidence sweep, HERIDAL held-out)")
    ax.set_xlim(0.3, 0.8)
    ax.set_ylim(0.3, 0.75)
    _save(fig, out, "fig-detection-conf-sweep")


def _fig_resolution(data: Path, out: Path) -> None:
    rows = sorted(_read_csv(data, "detection_resolution.csv"), key=lambda r: int(r["resolution"]))
    res = [r["resolution"] for r in rows]
    recall = [float(r["recall"]) for r in rows]
    precision = [float(r["precision"]) for r in rows]
    chosen = [r["chosen"] == "true" for r in rows]
    x = range(len(res))
    fig, ax = _new_fig()
    bars = ax.bar([i - 0.18 for i in x], recall, width=0.36, label="recall", color=BLUE_CORE)
    ax.bar([i + 0.18 for i in x], precision, width=0.36, label="precision", color=ST_STALE)
    # Mark the shipped resolution with the world-urgency accent halo.
    for i, ch in enumerate(chosen):
        if ch:
            bars[i].set_color(ST_WARNING)
            ax.annotate("shipped", (i - 0.18, recall[i] + 0.02), color=ST_WARNING,
                        fontsize=8, ha="center")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{r}px" for r in res])
    ax.set_ylabel("score")
    ax.set_ylim(0, 0.8)
    ax.set_title("Recall and precision by inference resolution")
    leg = ax.legend(facecolor=SURFACE_3, edgecolor=HAIRLINE, labelcolor=TEXT_MID, fontsize=8)
    leg.get_frame().set_alpha(0.9)
    _save(fig, out, "fig-resolution-tradeoff")


def _fig_quant_delta(data: Path, out: Path) -> None:
    d = _read_json(data, "detection_quant_delta.json")
    cats = ["recall", "precision"]
    pt = [d["pt"]["recall"], d["pt"]["precision"]]
    fp16 = [d["fp16"]["recall"], d["fp16"]["precision"]]
    x = range(len(cats))
    fig, ax = _new_fig(6.2, 4.2)
    ax.bar([i - 0.18 for i in x], pt, width=0.36, label="float32 (.pt)", color=ST_STALE)
    ax.bar([i + 0.18 for i in x], fp16, width=0.36, label="shipped FP16 Core ML", color=ST_NOMINAL)
    ax.set_xticks(list(x))
    ax.set_xticklabels(cats)
    ax.set_ylim(0, 0.8)
    ax.set_ylabel("score")
    ax.set_title("FP16 quantization did not degrade accuracy")
    leg = ax.legend(facecolor=SURFACE_3, edgecolor=HAIRLINE, labelcolor=TEXT_MID, fontsize=8)
    leg.get_frame().set_alpha(0.9)
    _save(fig, out, "fig-quant-delta")


# --- localization figures ---------------------------------------------------------------


def _fig_loc_error_by_geometry(data: Path, out: Path) -> None:
    rows = _read_csv(data, "localization_strata.csv")
    labels = [f"{r['range_bin']}\n{r['pitch_bin']}deg" for r in rows]
    median = [float(r["median_m"]) for r in rows]
    p90 = [float(r["p90_m"]) for r in rows]
    x = range(len(rows))
    fig, ax = _new_fig(7.4, 4.4)
    ax.bar([i - 0.18 for i in x], median, width=0.36, label="median (sim)", color=ST_INFO)
    ax.bar([i + 0.18 for i in x], p90, width=0.36, label="p90 (sim)", color=ST_CAUTION)
    for i, m in enumerate(median):
        ax.annotate(f"{m:.1f} m", (i - 0.18, m + 0.4), color=TEXT_LO, fontsize=8, ha="center")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("localization error (m)")
    ax.set_title("Localization error by geometry (sim) - near-nadir is PINPOINT, oblique is AREA")
    leg = ax.legend(facecolor=SURFACE_3, edgecolor=HAIRLINE, labelcolor=TEXT_MID, fontsize=8)
    leg.get_frame().set_alpha(0.9)
    fig.text(0.5, 0.01, "(sim) calibrated synthetic simulator; real-flight numbers pending",
             color=TEXT_LO, fontsize=7, ha="center")
    _save(fig, out, "fig-loc-error-by-geometry")


def _fig_coverage(data: Path, out: Path) -> None:
    rows = _read_csv(data, "coverage_matrix.csv")
    names = [r["name"] for r in rows]
    cov = [float(r["coverage"]) for r in rows]
    fig, ax = _new_fig(8.0, 4.4)
    # Color each bar by how it relates to the 95% target: matched/near-target = blue,
    # the out-of-schema time-sync collapse = magenta (a system-integrity-style failure).
    colors = []
    for n, c in zip(names, cov):
        if "time_sync_200" in n:
            colors.append(ST_CRITICAL)
        elif c < 0.90:
            colors.append(ST_CAUTION)
        else:
            colors.append(BLUE_CORE)
    ax.bar(range(len(names)), cov, color=colors)
    ax.axhline(0.95, color=ST_WARNING, linestyle="--", linewidth=1.2)
    ax.annotate("95% target", (len(names) - 1, 0.95), color=ST_WARNING, fontsize=8,
                va="bottom", ha="right")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=35, ha="right", fontsize=7.5)
    ax.set_ylabel("empirical coverage")
    ax.set_ylim(0, 1.05)
    ax.set_title("Uncertainty calibration: honest under model error (sim)")
    fig.text(0.5, 0.005, "matched control proves the arithmetic; the time-sync collapse is the "
             "non-tautology proof the metric measures the world", color=TEXT_LO, fontsize=7,
             ha="center")
    _save(fig, out, "fig-coverage-calibration")


# --- real-time figures ------------------------------------------------------------------


def _fig_fps(data: Path, out: Path) -> None:
    rows = sorted(_read_csv(data, "fps_by_resolution.csv"), key=lambda r: int(r["resolution"]))
    res = [f"{r['resolution']}px" for r in rows]
    fps = [float(r["fps"]) for r in rows]
    gate = float(rows[0]["gate_fps"])
    fig, ax = _new_fig()
    ax.bar(res, fps, color=BLUE_CORE)
    for i, v in enumerate(fps):
        ax.annotate(f"{v:.0f} fps", (i, v + 4), color=TEXT_LO, fontsize=8, ha="center")
    ax.axhline(gate, color=ST_WARNING, linestyle="--", linewidth=1.2)
    ax.annotate(f"{gate:.0f} fps detection gate", (len(res) - 1, gate + 6), color=ST_WARNING,
                fontsize=8, va="bottom", ha="right")
    ax.set_ylabel("detector throughput (fps, ANE)")
    ax.set_title("Detection throughput per resolution (MacBook Air M4, FP16)")
    _save(fig, out, "fig-fps-by-resolution")


def _fig_ane_speedup(data: Path, out: Path) -> None:
    rows = _read_csv(data, "ane_speedup.csv")
    units = [r["compute_unit"] for r in rows]
    ms = [float(r["latency_ms"]) for r in rows]
    fig, ax = _new_fig(6.4, 4.2)
    # CPU_ONLY is the slow baseline (stale/amber); the ANE paths are the fast nominal.
    colors = [ST_STALE if u == "CPU_ONLY" else ST_NOMINAL for u in units]
    ax.bar(units, ms, color=colors)
    for i, v in enumerate(ms):
        ax.annotate(f"{v:.1f} ms", (i, v + 0.4), color=TEXT_LO, fontsize=8, ha="center")
    ax.set_ylabel("forward-pass latency (ms, 640px)")
    ax.set_title("ANE placement check: ALL tracks CPU_AND_NE, not CPU_ONLY")
    _save(fig, out, "fig-ane-speedup")


def _fig_latency_budget(data: Path, out: Path) -> None:
    d = _read_json(data, "latency_budget.json")
    cats = ["p50", "p95", "max"]
    vals = [d["p50_ms"], d["p95_ms"], d["max_ms"]]
    budget = d["budget_ms"]
    fig, ax = _new_fig(6.6, 4.2)
    ax.bar(cats, vals, color=BLUE_BRIGHT)
    for i, v in enumerate(vals):
        ax.annotate(f"{v:.1f} ms", (i, v + 1.2), color=TEXT_LO, fontsize=8, ha="center")
    ax.axhline(budget, color=ST_WARNING, linestyle="--", linewidth=1.2)
    ax.annotate(f"{budget} ms budget", (2, budget - 8), color=ST_WARNING, fontsize=8,
                va="top", ha="right")
    ax.set_ylim(0, budget * 1.1)
    ax.set_ylabel("in-app glass-to-glass (ms)")
    ax.set_title("In-app latency clears the 120 ms budget (dev floor)")
    fig.text(0.5, 0.005, "floor: dev/CI software GL; on-device field measurement pending",
             color=TEXT_LO, fontsize=7, ha="center")
    _save(fig, out, "fig-latency-budget")


_RENDERERS = {
    "fig-detection-conf-sweep": _fig_conf_sweep,
    "fig-resolution-tradeoff": _fig_resolution,
    "fig-quant-delta": _fig_quant_delta,
    "fig-loc-error-by-geometry": _fig_loc_error_by_geometry,
    "fig-coverage-calibration": _fig_coverage,
    "fig-fps-by-resolution": _fig_fps,
    "fig-ane-speedup": _fig_ane_speedup,
    "fig-latency-budget": _fig_latency_budget,
}


def make_all(data_dir: Path, out_dir: Path) -> list[Path]:
    """Render every expected figure from the data files; return the written paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fid in EXPECTED_FIGURES:
        _RENDERERS[fid](data_dir, out_dir)
        written.append(out_dir / f"{fid}.png")
    return written


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[4]
    docs = repo / "docs" / "documentation"
    parser = argparse.ArgumentParser(prog="hades-make-figures", description=__doc__)
    parser.add_argument("--data", type=Path, default=docs / "data")
    parser.add_argument("--out", type=Path, default=docs / "figures")
    args = parser.parse_args(argv)

    written = make_all(args.data, args.out)
    print(f"rendered {len(written)} figures to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
