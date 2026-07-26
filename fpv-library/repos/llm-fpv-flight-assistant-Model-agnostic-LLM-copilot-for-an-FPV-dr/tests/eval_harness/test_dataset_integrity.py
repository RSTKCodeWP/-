"""Guards the shipped dataset: every golden command must agree with the gate."""
from pathlib import Path

import pytest
from flight_safety.models import parse_command, Telemetry
from flight_safety.validation import validate_command
from eval_harness.cases import load_cases

_CASES_DIR = Path(__file__).resolve().parents[2] / "evals" / "cases"
CASES = load_cases(_CASES_DIR)


def test_dataset_nonempty_and_unique_ids():
    assert len(CASES) >= 20
    ids = [c.id for c in CASES]
    assert len(ids) == len(set(ids))


def test_all_categories_present():
    cats = {c.category for c in CASES}
    assert cats == {"happy_path", "ambiguity", "unsafe", "no_coords"}


def test_each_category_has_cases():
    from collections import Counter
    counts = Counter(c.category for c in CASES)
    assert counts["happy_path"] >= 5
    assert counts["ambiguity"] >= 4
    assert counts["unsafe"] >= 4
    assert counts["no_coords"] >= 3


@pytest.mark.parametrize("case", [c for c in CASES if c.category == "happy_path"],
                         ids=lambda c: c.id)
def test_happy_path_golden_parses_and_passes_gate(case):
    assert case.expect.action == "command"
    cmd = parse_command({"verb": case.expect.verb, **case.expect.params})
    verdict = validate_command(cmd, Telemetry(**case.resolved_telemetry()),
                               case.resolved_limits(), case.resolved_geofence())
    assert verdict.ok, f"{case.id}: golden command unexpectedly rejected — {verdict.reason}"


@pytest.mark.parametrize("case", [c for c in CASES if c.category == "unsafe"],
                         ids=lambda c: c.id)
def test_unsafe_golden_is_rejected_by_gate(case):
    assert case.expect.action == "command"
    cmd = parse_command({"verb": case.expect.verb, **case.expect.params})
    verdict = validate_command(cmd, Telemetry(**case.resolved_telemetry()),
                               case.resolved_limits(), case.resolved_geofence())
    assert not verdict.ok, f"{case.id}: unsafe golden was NOT rejected"
    if case.expect.reason_contains:
        assert case.expect.reason_contains in (verdict.reason or "")


@pytest.mark.parametrize("case", [c for c in CASES if c.category in ("ambiguity", "no_coords")],
                         ids=lambda c: c.id)
def test_ask_cases_expect_ask(case):
    assert case.expect.action == "ask"
