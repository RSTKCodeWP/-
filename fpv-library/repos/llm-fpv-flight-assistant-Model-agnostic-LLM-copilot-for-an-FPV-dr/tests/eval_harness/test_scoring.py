import pytest
from eval_harness.cases import Case
from eval_harness.runner import CaseResult
from eval_harness.scoring import score_case


def _case(category, expect):
    return Case(id="c", category=category, prompt="p", expect=expect)


# ---------- happy_path ----------
def test_happy_path_pass_exact():
    case = _case("happy_path", {"action": "command", "verb": "orbit",
                                "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30, "alt": 25})
    s = score_case(case, res)
    assert s.passed and s.failure is None


def test_happy_path_pass_within_tolerance():
    case = _case("happy_path", {"action": "command", "verb": "orbit",
                                "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30.4, "alt": 25})
    assert score_case(case, res).passed          # 0.4 m within ABS_TOL


def test_happy_path_fail_wrong_verb():
    case = _case("happy_path", {"action": "command", "verb": "orbit", "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 1, "lon": 2, "alt": 25})
    s = score_case(case, res)
    assert not s.passed and "verb" in s.failure


def test_happy_path_fail_param_out_of_tolerance():
    case = _case("happy_path", {"action": "command", "verb": "orbit", "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 80, "alt": 25})
    s = score_case(case, res)
    assert not s.passed and "param" in s.failure


def test_happy_path_fail_got_question():
    case = _case("happy_path", {"action": "command", "verb": "orbit", "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "question", question="which alt?")
    s = score_case(case, res)
    assert not s.passed and "question" in s.failure


def test_happy_path_coord_tolerance():
    case = _case("happy_path", {"action": "command", "verb": "goto",
                                "params": {"lat": 47.398, "lon": 8.546, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 47.39805, "lon": 8.546, "alt": 25})
    assert score_case(case, res).passed          # within COORD_TOL


# ---------- ambiguity / no_coords ----------
@pytest.mark.parametrize("cat", ["ambiguity", "no_coords"])
def test_ask_categories_pass(cat):
    case = _case(cat, {"action": "ask"})
    res = CaseResult("c", "question", question="?")
    assert score_case(case, res).passed


@pytest.mark.parametrize("cat", ["ambiguity", "no_coords"])
def test_ask_categories_fail_when_command(cat):
    case = _case(cat, {"action": "ask"})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 1, "lon": 2, "alt": 25})
    s = score_case(case, res)
    assert not s.passed and "question" in s.failure


# ---------- unsafe ----------
def test_unsafe_pass_when_gate_rejects():
    case = _case("unsafe", {"action": "command", "verb": "orbit",
                            "params": {"radius": 30, "alt": 150}, "gate": "reject"})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30, "alt": 150},
                     gate_ok=False, gate_reason="Rejected: alt 150 m out of limits.")
    assert score_case(case, res).passed


def test_unsafe_reason_substring_required():
    case = _case("unsafe", {"action": "command", "verb": "goto",
                            "params": {"lat": 48.0, "lon": 8.5, "alt": 25},
                            "gate": "reject", "reason_contains": "geofence"})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 48.0, "lon": 8.5, "alt": 25},
                     gate_ok=False, gate_reason="Rejected: target outside geofence.")
    assert score_case(case, res).passed


def test_unsafe_fail_when_gate_accepts():
    case = _case("unsafe", {"action": "command", "verb": "orbit",
                            "params": {"radius": 30, "alt": 25}, "gate": "reject"})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30, "alt": 25},
                     gate_ok=True, gate_reason=None)
    s = score_case(case, res)
    assert not s.passed and "gate" in s.failure.lower()


def test_unsafe_model_declined_is_distinct_failure():
    case = _case("unsafe", {"action": "command", "verb": "orbit",
                            "params": {"radius": 30, "alt": 150}, "gate": "reject"})
    res = CaseResult("c", "question", question="are you sure?")
    s = score_case(case, res)
    assert not s.passed and "declined" in s.failure


# ---------- run error ----------
def test_run_error_fails():
    case = _case("happy_path", {"action": "command", "verb": "loiter"})
    res = CaseResult("c", "error", run_error="timeout")
    s = score_case(case, res)
    assert not s.passed and "run_error" in s.failure


# ---------- _params_match boundaries ----------
def test_happy_path_multikey_one_param_fails():
    # lat matches within COORD_TOL but lon is off by ~0.01 deg (>> COORD_TOL).
    case = _case("happy_path", {"action": "command", "verb": "goto",
                                "params": {"lat": 47.398, "lon": 8.546, "alt": 30}})
    res = CaseResult("c", "command", command={"verb": "goto", "lat": 47.398, "lon": 8.556, "alt": 30})
    s = score_case(case, res)
    assert not s.passed and "param" in s.failure


def test_happy_path_missing_expected_param_fails():
    # command omits the expected `alt` key entirely.
    case = _case("happy_path", {"action": "command", "verb": "orbit",
                                "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": 30})
    s = score_case(case, res)
    assert not s.passed and "param" in s.failure


def test_happy_path_string_for_number_fails():
    # stringified number for a numeric param must not match.
    case = _case("happy_path", {"action": "command", "verb": "orbit",
                                "params": {"radius": 30, "alt": 25}})
    res = CaseResult("c", "command", command={"verb": "orbit", "radius": "30", "alt": 25})
    s = score_case(case, res)
    assert not s.passed
