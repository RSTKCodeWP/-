"""Task 7.1 - the doc-data export behind every documentation graph.

The export writes the four metric families to flat files the figure code (Python AND
Wolfram) reads. Detection + real-time numbers are curated transcriptions of committed
result docs (each constant carries its `# source:` provenance); localization + coverage
are produced by running the REAL code at seed=0, so they can never drift from the system.

These tests are the content-gate teeth: every exported number must match its source
artifact, and every file must be non-empty. A wrong transcription fails here.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from hades.cli.export_doc_data import (
    DETECTION_CONF_SWEEP,
    DETECTION_RESOLUTION,
    FPS_BY_RESOLUTION,
    LATENCY_BUDGET,
    export_all,
)


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # Module-scoped: the export (whose coverage matrix is the slow part) runs ONCE for the
    # whole file. A smaller coverage-trial count keeps the directional assertions valid
    # (matched ~95%, time-sync-200ms collapse) while staying fast; the CLI default is 200.
    d = tmp_path_factory.mktemp("doc_data")
    export_all(d, coverage_trials=80)
    return d


# --- the four families each land as a non-empty file ----------------------------------

EXPECTED_FILES = [
    "detection_conf_sweep.csv",
    "detection_resolution.csv",
    "detection_quant_delta.json",
    "localization_strata.csv",
    "localization_moving.json",
    "coverage_matrix.csv",
    "fps_by_resolution.csv",
    "ane_speedup.csv",
    "latency_budget.json",
    "qualitative_refs.json",
    "manifest.json",
]


@pytest.mark.parametrize("name", EXPECTED_FILES)
def test_each_file_exists_and_is_non_empty(out_dir: Path, name: str) -> None:
    f = out_dir / name
    assert f.exists(), f"{name} not written"
    assert f.stat().st_size > 0, f"{name} is empty"


# --- detection: exported rows match the committed p2.5 docs ----------------------------


def test_conf_sweep_matches_acceptance_doc(out_dir: Path) -> None:
    rows = list(csv.DictReader((out_dir / "detection_conf_sweep.csv").open()))
    by_conf = {r["conf"]: r for r in rows}
    # p2.5-acceptance.md: conf 0.25 -> 0.51/0.62, 0.10 -> 0.63/0.46, 0.05 -> 0.69/0.37
    assert float(by_conf["0.25"]["recall"]) == 0.51
    assert float(by_conf["0.25"]["precision"]) == 0.62
    assert float(by_conf["0.05"]["recall"]) == 0.69


def test_resolution_table_matches_training_doc(out_dir: Path) -> None:
    rows = {r["resolution"]: r for r in csv.DictReader((out_dir / "detection_resolution.csv").open())}
    # p2.5-training-results.md: 960 -> 0.510 recall, chosen (compare as numbers)
    assert float(rows["960"]["recall"]) == 0.510
    assert rows["960"]["chosen"] == "true"
    assert float(rows["640"]["recall"]) == 0.417
    assert float(rows["1280"]["recall"]) == 0.511


def test_quant_delta_shows_fp16_did_not_degrade(out_dir: Path) -> None:
    d = json.loads((out_dir / "detection_quant_delta.json").read_text())
    # shipped FP16 recall 0.551 > .pt 0.509; gain positive
    assert d["fp16"]["recall"] == 0.551
    assert d["pt"]["recall"] == 0.509
    assert d["recall_gain"] == pytest.approx(0.042, abs=1e-3)


# --- localization: produced live by the real report (seed=0, deterministic) ------------


def test_localization_strata_are_real_and_sim_tagged(out_dir: Path) -> None:
    rows = list(csv.DictReader((out_dir / "localization_strata.csv").open()))
    assert rows, "no strata exported"
    # near-nadir [30-80) x [0-15) is the PINPOINT stratum: ~1.2 m median (sim, seed=0)
    near = next(r for r in rows if r["range_bin"] == "[30-80)" and r["pitch_bin"] == "[0-15)")
    assert float(near["median_m"]) == pytest.approx(1.2, abs=0.3)
    # every meter row must declare it is a sim number
    assert all(r["kind"] == "sim" for r in rows)
    # near-nadir error must be smaller than the oblique gated stratum (the honest story)
    oblique = next(r for r in rows if r["pitch_bin"] == "[65+)")
    assert float(near["median_m"]) < float(oblique["median_m"])


def test_moving_target_does_not_converge(out_dir: Path) -> None:
    d = json.loads((out_dir / "localization_moving.json").read_text())
    assert d["actionability_class"] in {"AREA", "CUE_ONLY"}
    assert d["median_r95_m"] > 10.0  # never a PINPOINT
    assert d["kind"] == "sim"


# --- coverage: the flagship honesty proof, produced live (seed=0) ----------------------


def test_coverage_matrix_has_matched_and_collapse_rows(out_dir: Path) -> None:
    rows = {r["name"]: r for r in csv.DictReader((out_dir / "coverage_matrix.csv").open())}
    # matched control proves the arithmetic (coverage near the 95% target)
    assert float(rows["matched_control"]["coverage"]) >= 0.90
    # the out-of-schema time-sync 200ms row is the non-tautology signature: it collapses
    assert float(rows["time_sync_200ms"]["coverage"]) < 0.50
    assert float(rows["time_sync_200ms"]["mean_nees"]) > 5.0


# --- real-time: exported rows match the committed spike + latency docs ------------------


def test_fps_by_resolution_matches_spike_doc(out_dir: Path) -> None:
    rows = {r["resolution"]: r for r in csv.DictReader((out_dir / "fps_by_resolution.csv").open())}
    # spike-latency-results.md: 640->292.8, 960->63.1, 1280->56.7, all >= 10 fps
    assert float(rows["960"]["fps"]) == pytest.approx(63.1, abs=0.2)
    assert all(float(r["fps"]) >= 10.0 for r in rows.values())


def test_latency_budget_is_a_disclosed_floor(out_dir: Path) -> None:
    d = json.loads((out_dir / "latency_budget.json").read_text())
    # p5-latency-budget.md: p95 22.4 ms vs 120 ms budget
    assert d["p95_ms"] == pytest.approx(22.4, abs=0.1)
    assert d["budget_ms"] == 120
    assert d["measurement"] == "floor"  # honest: dev/CI software-GL, not field


# --- the in-module constants are themselves the source-of-truth (catch typos early) -----


def test_module_constants_are_self_consistent() -> None:
    assert DETECTION_CONF_SWEEP[0]["conf"] == 0.05  # sweep ordered low-conf first
    assert any(r["resolution"] == 960 and r["chosen"] for r in DETECTION_RESOLUTION)
    assert FPS_BY_RESOLUTION[0]["resolution"] == 640
    assert LATENCY_BUDGET["p95_ms"] == 22.4


# --- the manifest ties every figure to its data file (the traceability contract) -------


def test_manifest_lists_every_data_file_with_a_source(out_dir: Path) -> None:
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["families"]  # non-empty
    for entry in manifest["families"]:
        assert entry["file"]
        assert entry["source"]  # every family names where it came from
        assert (out_dir / entry["file"]).exists()
