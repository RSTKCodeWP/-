from __future__ import annotations

import json
from dataclasses import dataclass

CATEGORIES = ["happy_path", "ambiguity", "unsafe", "no_coords"]


def _percentile(values, pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return float(s[f] + (s[c] - s[f]) * (k - f))


@dataclass
class ModelReport:
    model: str
    total: int
    passed: int
    by_category: dict          # cat -> (passed, total)
    schema_valid: tuple        # (valid, command_expected_total)
    gate_agreement: tuple      # (matched, gate_expected_total)
    latency_p50: float
    latency_p95: float
    avg_attempts: float
    failures: list             # list[(case_id, category, failure)]

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0


def build_report(model: str, cases, results, scores) -> ModelReport:
    total = len(scores)
    passed = sum(1 for s in scores if s.passed)

    by_category = {}
    for cat in CATEGORIES:
        cat_scores = [s for s in scores if s.category == cat]
        by_category[cat] = (sum(1 for s in cat_scores if s.passed), len(cat_scores))

    cmd_expected = [(c, r) for c, r in zip(cases, results) if c.expect.action == "command"]
    schema_valid = (
        sum(1 for _, r in cmd_expected if r.proposal_kind == "command"),
        len(cmd_expected),
    )

    gate_expected = [(c, r) for c, r in zip(cases, results) if c.expect.gate is not None]
    gate_matched = sum(
        1 for c, r in gate_expected
        if r.gate_ok is not None and r.gate_ok == (c.expect.gate == "accept")
    )
    gate_agreement = (gate_matched, len(gate_expected))

    latencies = [r.latency_s for r in results]
    avg_attempts = (sum(r.attempts for r in results) / total) if total else 0.0
    failures = [(s.case_id, s.category, s.failure) for s in scores if not s.passed]

    return ModelReport(
        model=model, total=total, passed=passed, by_category=by_category,
        schema_valid=schema_valid, gate_agreement=gate_agreement,
        latency_p50=_percentile(latencies, 0.50),
        latency_p95=_percentile(latencies, 0.95),
        avg_attempts=avg_attempts, failures=failures,
    )


def _pct(part: int, whole: int) -> str:
    return f"{(part / whole * 100):.0f}%" if whole else "n/a"


def to_dict(rep: ModelReport) -> dict:
    return {
        "model": rep.model,
        "total": rep.total,
        "passed": rep.passed,
        "accuracy": rep.accuracy,
        "by_category": {k: {"passed": v[0], "total": v[1]} for k, v in rep.by_category.items()},
        "schema_valid": {"valid": rep.schema_valid[0], "total": rep.schema_valid[1]},
        "gate_agreement": {"matched": rep.gate_agreement[0], "total": rep.gate_agreement[1]},
        "latency_p50": rep.latency_p50,
        "latency_p95": rep.latency_p95,
        "avg_attempts": rep.avg_attempts,
        "failures": [{"case_id": cid, "category": cat, "failure": f}
                     for cid, cat, f in rep.failures],
    }


def render_json(reports) -> str:
    return json.dumps([to_dict(r) for r in reports], indent=2)


def render_markdown(reports) -> str:
    lines = ["# Eval Scorecard", ""]
    lines.append("| Model | Overall | Happy | Ambiguity | Unsafe | NoCoords "
                 "| Schema | Gate | p50 (s) | p95 (s) | Attempts |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in reports:
        bc = r.by_category
        lines.append(
            f"| {r.model} | {r.accuracy:.0%} ({r.passed}/{r.total}) "
            f"| {bc['happy_path'][0]}/{bc['happy_path'][1]} "
            f"| {bc['ambiguity'][0]}/{bc['ambiguity'][1]} "
            f"| {bc['unsafe'][0]}/{bc['unsafe'][1]} "
            f"| {bc['no_coords'][0]}/{bc['no_coords'][1]} "
            f"| {_pct(*r.schema_valid)} | {_pct(*r.gate_agreement)} "
            f"| {r.latency_p50:.2f} | {r.latency_p95:.2f} | {r.avg_attempts:.2f} |"
        )
    for r in reports:
        if r.failures:
            lines += ["", f"## Failures — {r.model}", ""]
            for cid, cat, f in r.failures:
                lines.append(f"- `{cid}` [{cat}]: {f}")
    return "\n".join(lines) + "\n"


def print_summary(reports) -> None:
    """Print a compact terminal table (no extra deps)."""
    print(f"{'MODEL':<28} {'ACC':>7} {'HAPPY':>6} {'AMB':>5} "
          f"{'UNSAFE':>7} {'NOCRD':>6} {'SCHEMA':>7} {'GATE':>6} {'p50':>6} {'p95':>6} {'ATT':>5}")
    for r in reports:
        bc = r.by_category
        happy = f"{bc['happy_path'][0]}/{bc['happy_path'][1]}"
        amb = f"{bc['ambiguity'][0]}/{bc['ambiguity'][1]}"
        unsafe = f"{bc['unsafe'][0]}/{bc['unsafe'][1]}"
        nocrd = f"{bc['no_coords'][0]}/{bc['no_coords'][1]}"
        print(f"{r.model:<28} {r.accuracy:>6.0%} "
              f"{happy:>6} {amb:>5} {unsafe:>7} {nocrd:>6} "
              f"{_pct(*r.schema_valid):>7} {_pct(*r.gate_agreement):>6} "
              f"{r.latency_p50:>6.2f} {r.latency_p95:>6.2f} {r.avg_attempts:>5.2f}")
