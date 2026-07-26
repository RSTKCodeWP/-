import json
from eval_harness.cases import Case
from eval_harness.runner import CaseResult
from eval_harness.scoring import score_case
from eval_harness.report import build_report
from eval_harness.__main__ import resolve_models, write_artifacts, main


class _Settings:
    def __init__(self, key="", model="m/default"):
        self.openrouter_api_key = key
        self.model = model
        self.base_url = "https://x"


def test_resolve_models_default_to_settings():
    assert resolve_models(None, _Settings(model="foo/bar")) == ["foo/bar"]


def test_resolve_models_parses_csv():
    assert resolve_models("a/b, c/d ,", _Settings()) == ["a/b", "c/d"]


def test_write_artifacts_creates_md_and_json(tmp_path):
    case = Case(id="h1", category="happy_path", prompt="p",
                expect={"action": "command", "verb": "loiter"})
    res = CaseResult("h1", "command", command={"verb": "loiter"}, attempts=1, latency_s=0.1)
    rep = build_report("m/x", [case], [res], [score_case(case, res)])
    md, js = write_artifacts([rep], tmp_path, "20260609T120000Z-m_x")
    assert md.exists() and js.exists()
    assert "m/x" in md.read_text()
    assert json.loads(js.read_text())[0]["model"] == "m/x"


def test_main_no_key_exits_2(monkeypatch):
    monkeypatch.setattr("eval_harness.__main__.AssistantSettings", lambda: _Settings(key=""))
    assert main(["--models", "a/b"]) == 2


def test_main_empty_models_exits_2(monkeypatch):
    monkeypatch.setattr("eval_harness.__main__.AssistantSettings",
                        lambda: _Settings(key="sk-test", model=""))
    assert main(["--models", ",,"]) == 2
