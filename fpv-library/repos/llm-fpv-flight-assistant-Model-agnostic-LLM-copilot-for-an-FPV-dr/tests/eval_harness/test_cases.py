import textwrap
import pytest
from eval_harness.cases import Case, load_cases, DEFAULT_TELEMETRY, DEFAULT_GEOFENCE


def _write(tmp_path, name, text):
    f = tmp_path / name
    f.write_text(textwrap.dedent(text))
    return f


def test_loads_valid_case(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: takeoff_20
          category: happy_path
          prompt: take off to 20 meters
          telemetry: {armed: false, alt_m: 0.0}
          expect: {action: command, verb: arm_takeoff, params: {alt: 20}}
    """)
    cases = load_cases(tmp_path)
    assert len(cases) == 1
    c = cases[0]
    assert c.id == "takeoff_20"
    assert c.category == "happy_path"
    assert c.expect.action == "command"
    assert c.expect.verb == "arm_takeoff"
    assert c.expect.params == {"alt": 20}


def test_telemetry_defaults_merge(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: low_batt
          category: unsafe
          prompt: orbit here
          telemetry: {battery_pct: 0.1}
          expect: {action: command, verb: orbit, params: {radius: 30, alt: 25}, gate: reject}
    """)
    c = load_cases(tmp_path)[0]
    tlm = c.resolved_telemetry()
    assert tlm["battery_pct"] == 0.1          # override
    assert tlm["gps_ok"] is True              # from default
    assert tlm["lat"] == DEFAULT_TELEMETRY["lat"]


def test_geofence_and_limits_defaults(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: g
          category: ambiguity
          prompt: fly up
          expect: {action: ask}
    """)
    c = load_cases(tmp_path)[0]
    assert c.resolved_geofence() == DEFAULT_GEOFENCE
    assert c.resolved_limits().max_alt_m == 120.0


def test_limits_override(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: g
          category: happy_path
          prompt: x
          limits: {max_alt_m: 50}
          expect: {action: command, verb: loiter}
    """)
    c = load_cases(tmp_path)[0]
    assert c.resolved_limits().max_alt_m == 50.0
    assert c.resolved_limits().min_battery_pct == 0.20   # untouched default


def test_invalid_category_raises(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: bad
          category: nonsense
          prompt: x
          expect: {action: ask}
    """)
    with pytest.raises(ValueError):
        load_cases(tmp_path)


def test_command_without_verb_raises(tmp_path):
    _write(tmp_path, "a.yaml", """
        - id: bad
          category: happy_path
          prompt: x
          expect: {action: command}
    """)
    with pytest.raises(ValueError):
        load_cases(tmp_path)


def test_duplicate_id_raises(tmp_path):
    _write(tmp_path, "a.yaml", """
        - {id: dup, category: ambiguity, prompt: x, expect: {action: ask}}
        - {id: dup, category: ambiguity, prompt: y, expect: {action: ask}}
    """)
    with pytest.raises(ValueError):
        load_cases(tmp_path)


def test_single_document_mapping(tmp_path):
    # Top-level is a single mapping (no leading `-`), not a list.
    _write(tmp_path, "a.yaml", """
        id: solo
        category: ambiguity
        prompt: fly up
        expect: {action: ask}
    """)
    cases = load_cases(tmp_path)
    assert len(cases) == 1
    assert cases[0].id == "solo"


def test_cross_file_duplicate_id_raises(tmp_path):
    _write(tmp_path, "a.yaml", """
        - {id: dup, category: ambiguity, prompt: x, expect: {action: ask}}
    """)
    _write(tmp_path, "b.yaml", """
        - {id: dup, category: ambiguity, prompt: y, expect: {action: ask}}
    """)
    with pytest.raises(ValueError):
        load_cases(tmp_path)


def test_malformed_yaml_raises_with_filename(tmp_path):
    _write(tmp_path, "broken.yaml", """
        - id: x
          category: ambiguity
          prompt: "unterminated
    """)
    with pytest.raises(ValueError, match="broken.yaml"):
        load_cases(tmp_path)
