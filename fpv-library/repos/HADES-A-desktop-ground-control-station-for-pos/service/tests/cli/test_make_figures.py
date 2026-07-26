"""Task 7.2 - the Python documentation figures (routine charts from the 7.1 data files).

Every figure must (1) be produced and non-empty and (2) read from a real exported data
file - no figure invents its own numbers. matplotlib lives only in the `docs` dependency
group, so these tests skip cleanly on lean CI that does not install it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("matplotlib", reason="figures need the `docs` dependency group")

from hades.cli.export_doc_data import export_all  # noqa: E402
from hades.cli.make_figures import EXPECTED_FIGURES, make_all  # noqa: E402


@pytest.fixture(scope="module")
def figures_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("fig_run")
    data = root / "data"
    figs = root / "figures"
    export_all(data, coverage_trials=60)  # small/fast; figures only need the shape
    make_all(data, figs)
    return figs


def test_every_expected_figure_is_listed() -> None:
    # The figure manifest is the contract from OUTLINE.md; lock the count so a dropped
    # figure is caught here, not discovered missing in the README.
    # Eight strong charts; the weak 3-point loc-error CDF was dropped (OUTLINE.md) in favor
    # of the by-geometry chart, which carries the localization-accuracy story honestly.
    assert len(EXPECTED_FIGURES) == 8
    for fid in [
        "fig-detection-conf-sweep",
        "fig-resolution-tradeoff",
        "fig-quant-delta",
        "fig-loc-error-by-geometry",
        "fig-coverage-calibration",
        "fig-fps-by-resolution",
        "fig-ane-speedup",
        "fig-latency-budget",
    ]:
        assert fid in EXPECTED_FIGURES


@pytest.mark.parametrize("fid", list(EXPECTED_FIGURES))
def test_figure_is_produced_and_non_empty(figures_dir: Path, fid: str) -> None:
    f = figures_dir / f"{fid}.png"
    assert f.exists(), f"{fid}.png not rendered"
    # A real PNG has the 8-byte signature and meaningful size (not a blank stub).
    assert f.stat().st_size > 1000, f"{fid}.png looks empty ({f.stat().st_size} bytes)"
    assert f.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"{fid}.png is not a PNG"
