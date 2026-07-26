import json
from eval_harness.cases import Case
from eval_harness.runner import CaseResult
from eval_harness.scoring import score_case
from eval_harness.report import (
    build_report, render_markdown, render_json, to_dict, print_summary, ModelReport,
)


def _c(cid, cat, expect):
    return Case(id=cid, category=cat, prompt="p", expect=expect)


def _build():
    cases = [
        _c("h1", "happy_path", {"action": "command", "verb": "loiter"}),
        _c("a1", "ambiguity", {"action": "ask"}),
        _c("u1", "unsafe", {"action": "command", "verb": "orbit",
                            "params": {"radius": 30, "alt": 150}, "gate": "reject"}),
    ]
    results = [
        CaseResult("h1", "command", command={"verb": "loiter"}, attempts=1, latency_s=0.2),
        CaseResult("a1", "question", question="?", attempts=1, latency_s=0.4),
        CaseResult("u1", "command", command={"verb": "orbit", "radius": 30, "alt": 150},
                   gate_ok=False, gate_reason="Rejected: alt 150 m out of limits.",
                   attempts=2, latency_s=0.6),
    ]
    scores = [score_case(c, r) for c, r in zip(cases, results)]
    return build_report("modelX", cases, results, scores), cases, results, scores


def test_build_report_aggregates():
    rep, *_ = _build()
    assert rep.model == "modelX"
    assert rep.total == 3 and rep.passed == 3
    assert rep.accuracy == 1.0
    assert rep.by_category["happy_path"] == (1, 1)
    assert rep.by_category["unsafe"] == (1, 1)
    # command-expected cases: h1 + u1 = 2, both produced commands.
    assert rep.schema_valid == (2, 2)
    # gate-expected cases: u1 only.
    assert rep.gate_agreement == (1, 1)
    assert rep.avg_attempts == (1 + 1 + 2) / 3
    assert rep.latency_p50 == 0.4         # median of 0.2/0.4/0.6


def test_build_report_counts_failures():
    cases = [_c("h1", "happy_path", {"action": "command", "verb": "loiter"})]
    results = [CaseResult("h1", "question", question="?")]
    scores = [score_case(cases[0], results[0])]
    rep = build_report("m", cases, results, scores)
    assert rep.passed == 0
    assert len(rep.failures) == 1
    assert rep.failures[0][0] == "h1"


def test_render_markdown_has_model_and_table():
    rep, *_ = _build()
    md = render_markdown([rep])
    assert "modelX" in md
    assert "| Model |" in md
    assert "Failures" not in md or "modelX" in md   # no failures section needed here


def test_render_json_roundtrips():
    rep, *_ = _build()
    data = json.loads(render_json([rep]))
    assert data[0]["model"] == "modelX"
    assert data[0]["accuracy"] == 1.0
    assert data[0]["by_category"]["happy_path"] == {"passed": 1, "total": 1}


def test_to_dict_shape():
    rep, *_ = _build()
    d = to_dict(rep)
    for key in ("model", "total", "passed", "accuracy", "by_category",
                "schema_valid", "gate_agreement", "latency_p50", "latency_p95",
                "avg_attempts", "failures"):
        assert key in d


def test_render_markdown_failures_section():
    # A happy_path case expecting a command but answered with a question -> failed.
    cases = [_c("h_fail", "happy_path", {"action": "command", "verb": "loiter"})]
    results = [CaseResult("h_fail", "question", question="?", attempts=1, latency_s=0.1)]
    scores = [score_case(cases[0], results[0])]
    rep = build_report("modelF", cases, results, scores)
    md = render_markdown([rep])
    assert "## Failures" in md
    assert "h_fail" in md


def test_print_summary_aligns_multi_digit_counts(capsys):
    rep_a = ModelReport(
        model="org/model-a", total=27, passed=23,
        by_category={"happy_path": (12, 14), "ambiguity": (3, 3),
                     "unsafe": (6, 6), "no_coords": (2, 4)},
        schema_valid=(18, 20), gate_agreement=(6, 6),
        latency_p50=0.4, latency_p95=0.6, avg_attempts=1.5, failures=[],
    )
    rep_b, *_ = _build()  # model "modelX", single-digit counts
    print_summary([rep_a, rep_b])
    out = capsys.readouterr().out
    assert "org/model-a" in out
    assert "modelX" in out
    assert "12/14" in out
