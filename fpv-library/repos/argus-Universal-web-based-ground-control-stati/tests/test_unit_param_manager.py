"""Tests for backend/param_manager.py — MAVLink PARAM protocol."""

import json
import struct
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.param_manager import ParamManager


def _make_link() -> MagicMock:
    link = MagicMock()
    link.locale = "en"
    link.vehicle.sysid = 1
    link.sq = 0
    return link


def _param_payload(name: str, value: float, index: int, total: int, ptype: int = 9) -> bytes:
    p = struct.pack("<f", value)
    p += struct.pack("<HH", total, index)
    p += name.encode("ascii")[:16].ljust(16, b"\x00")
    p += struct.pack("<B", ptype)
    return p


class TestParamManagerInit:
    def test_initial_state(self):
        link = _make_link()
        mgr = ParamManager(link)
        assert mgr.total_count == -1
        assert mgr.received_count == 0
        assert mgr.fetching is False
        assert len(mgr.params) == 0


class TestRequestAll:
    def test_clears_and_fetches(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {"old": {"value": 1}}
        mgr.request_all()
        assert len(mgr.params) == 0
        assert mgr.fetching is True
        assert mgr.total_count == -1
        link.send.assert_called_once()
        link.add_event.assert_called_once()


class TestHandleParamValue:
    def test_parses_single_param(self):
        link = _make_link()
        mgr = ParamManager(link)
        p = _param_payload("BATT_CAPACITY", 5000.0, 0, 3)
        mgr.handle_param_value(p, len(p))
        assert "BATT_CAPACITY" in mgr.params
        assert mgr.params["BATT_CAPACITY"]["value"] == 5000.0
        assert mgr.received_count == 1
        assert mgr.total_count == 3

    def test_duplicate_param_not_double_counted(self):
        link = _make_link()
        mgr = ParamManager(link)
        p = _param_payload("BATT_CAPACITY", 5000.0, 0, 3)
        mgr.handle_param_value(p, len(p))
        mgr.handle_param_value(p, len(p))
        assert mgr.received_count == 1

    def test_all_params_completes_fetch(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        names = ["PARAM_A", "PARAM_B", "PARAM_C"]
        for i, name in enumerate(names):
            p = _param_payload(name, float(i), i, 3)
            mgr.handle_param_value(p, len(p))
        assert mgr.fetching is False
        assert mgr.received_count == 3

    def test_short_payload_ignored(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.handle_param_value(b"\x00" * 10, 10)
        assert len(mgr.params) == 0

    def test_messages_capped(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        for i in range(2100):
            name = f"P{i:04d}"[:16]
            p = _param_payload(name, float(i), i, 2100)
            mgr.handle_param_value(p, len(p))
        assert len(mgr._messages) <= 2000


class TestSetParam:
    def test_sends_param_set(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {"THR_MAX": {"name": "THR_MAX", "value": 80.0, "type": 9, "index": 0}}
        mgr.set_param("THR_MAX", 90.0)
        link.send.assert_called_once()
        link.add_event.assert_called_once()

    def test_unknown_param_uses_default_type(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.set_param("NEW_PARAM", 42.0)
        link.send.assert_called_once()


class TestSaveToFile:
    def test_saves_json(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {
            "A": {"name": "A", "value": 1.0, "type": 9, "index": 0},
            "B": {"name": "B", "value": 2.0, "type": 9, "index": 1},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        result = mgr.save_to_file(path)
        assert result == path
        with open(path) as f:
            data = json.load(f)
        assert data == {"A": 1.0, "B": 2.0}
        Path(path).unlink()

    def test_auto_path(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {"X": {"name": "X", "value": 1.0, "type": 9, "index": 0}}
        path = mgr.save_to_file()
        assert Path(path).exists()
        Path(path).unlink()


class TestLoadFromFile:
    def test_loads_and_sets_changed(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {
            "A": {"name": "A", "value": 1.0, "type": 9, "index": 0},
            "B": {"name": "B", "value": 2.0, "type": 9, "index": 1},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"A": 1.0, "B": 5.0}, f)
            path = f.name
        changed = mgr.load_from_file(path)
        assert "B" in changed
        assert "A" not in changed
        Path(path).unlink()

    def test_invalid_json_returns_empty(self):
        link = _make_link()
        mgr = ParamManager(link)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            path = f.name
        changed = mgr.load_from_file(path)
        assert changed == []
        Path(path).unlink()

    def test_missing_file_returns_empty(self):
        link = _make_link()
        mgr = ParamManager(link)
        changed = mgr.load_from_file("/nonexistent/path.json")
        assert changed == []

    def test_json_array_at_root_returns_empty_with_event(self):
        """JSON list at root must not raise AttributeError — emits an error event."""
        link = _make_link()
        mgr = ParamManager(link)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([1, 2, 3], f)
            path = f.name
        changed = mgr.load_from_file(path)
        Path(path).unlink()
        assert changed == []
        event_types = [call.args[1] for call in link.add_event.call_args_list]
        assert "param_load_err" in event_types

    def test_non_numeric_values_skipped(self):
        """String values in param file must be skipped, not raise TypeError."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {"A": {"name": "A", "value": 1.0, "type": 9, "index": 0}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"A": "bad_value", "B": 5.0}, f)
            path = f.name
        changed = mgr.load_from_file(path)
        Path(path).unlink()
        assert "A" not in changed  # skipped (bad type)
        assert "B" not in changed  # skipped (not in current params)

    def test_bool_values_skipped(self):
        """JSON booleans must be skipped — bool is subclass of int in Python."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.set_param = MagicMock()
        mgr.params = {"A": {"name": "A", "value": 0.0, "type": 9, "index": 0}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"A": True}, f)  # would become 1.0 without the bool guard
            path = f.name
        changed = mgr.load_from_file(path)
        Path(path).unlink()
        assert changed == []
        mgr.set_param.assert_not_called()

    def test_inf_values_skipped_so_changed_count_stays_honest(self):
        """JSON Infinity must be filtered before the count_appender. set_param would reject
        Inf but `changed.append` + `time.sleep` still execute, inflating the load summary."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.set_param = MagicMock()
        mgr.params = {"A": {"name": "A", "value": 50.0, "type": 9, "index": 0}}
        # Python json.load accepts the non-standard `Infinity` literal by default.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"A": Infinity}')
            path = f.name
        changed = mgr.load_from_file(path)
        Path(path).unlink()
        assert changed == []
        mgr.set_param.assert_not_called()


class TestHandleParamValueEdgeCases:
    def test_zero_length_payload_ignored(self):
        """Line 71: pl < 1 early return."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.handle_param_value(b"", 0)
        assert len(mgr.params) == 0
        assert mgr.received_count == 0

    def test_empty_name_payload_rejected(self):
        """All-zero payload produces empty name and must be discarded."""
        link = _make_link()
        mgr = ParamManager(link)
        payload = b"\x00" * 25
        mgr.handle_param_value(payload, 25)
        assert "" not in mgr.params
        assert mgr.received_count == 0

    def test_index_0xFFFF_not_added_to_received_indices(self):
        """AP replies with index=0xFFFF for PARAM_REQUEST_READ by name."""
        link = _make_link()
        mgr = ParamManager(link)
        p = _param_payload("THR_MAX", 80.0, 0xFFFF, 10)
        mgr.handle_param_value(p, len(p))
        assert "THR_MAX" in mgr.params
        assert mgr.received_count == 1
        assert 0xFFFF not in mgr._received_indices


class TestSetParamValidation:
    def test_nan_rejected(self):
        """Lines 125-126: NaN value rejected."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.set_param("THR_MAX", float("nan"))
        link.send.assert_not_called()
        link.add_event.assert_called_once()
        assert "NaN" in link.add_event.call_args[0][0]

    def test_positive_inf_rejected(self):
        """Lines 125-126: +Inf value rejected."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.set_param("THR_MAX", float("inf"))
        link.send.assert_not_called()
        link.add_event.assert_called_once()

    def test_negative_inf_rejected(self):
        """Lines 125-126: -Inf value rejected."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.set_param("THR_MAX", float("-inf"))
        link.send.assert_not_called()


class TestCheckTimeout:
    def test_not_fetching_is_noop(self):
        """Line 168: early return when not fetching."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = False
        mgr.check_timeout()
        link.send.assert_not_called()

    def test_gap_fill_requests_missing_indices(self):
        """Lines 169-186: after gap delay, missing indices are re-requested."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        mgr.total_count = 5
        mgr._received_indices = {0, 1, 3, 4}  # index 2 missing
        # Set last_value_time far enough in the past to trigger gap fill
        mgr._last_value_time = time.time() - 10.0
        mgr._fetch_start = time.time()

        mgr.check_timeout()

        # _request_one sends via link.send
        link.send.assert_called_once()
        assert mgr._gap_fill_attempts[2] == 1

    def test_gap_fill_respects_max_retries(self):
        """Lines 182-183: index with >= max_retries is skipped."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        mgr.total_count = 3
        mgr._received_indices = {0, 2}  # index 1 missing
        mgr._last_value_time = time.time() - 10.0
        mgr._fetch_start = time.time()
        mgr._gap_fill_attempts = {1: 3}  # already at max

        mgr.check_timeout()

        link.send.assert_not_called()

    def test_gap_fill_throttled_to_10(self):
        """Line 180: only up to 10 missing indices per cycle."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        mgr.total_count = 20
        mgr._received_indices = set()  # all 20 missing
        mgr._last_value_time = time.time() - 10.0
        mgr._fetch_start = time.time()

        mgr.check_timeout()

        assert link.send.call_count == 10

    def test_relists_when_initial_request_dropped(self):
        """total_count still unknown (no PARAM_VALUE ever arrived) → re-send
        PARAM_REQUEST_LIST. Without this, a single dropped msg 21 stalls the
        whole fetch: gap-fill needs total_count and can never engage."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        mgr.total_count = -1
        mgr._list_attempts = 1  # the initial request_all() send
        mgr._last_value_time = time.time() - 10.0
        mgr._fetch_start = time.time()

        mgr.check_timeout()

        # Re-sent PARAM_REQUEST_LIST (msg 21), not a gap-fill READ.
        link.send.assert_called_once()
        sent = link.send.call_args[0][0]
        mid = sent[7] | (sent[8] << 8) | (sent[9] << 16)
        assert mid == 21
        assert mgr._list_attempts == 2

    def test_relist_respects_max_retries(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        mgr.total_count = -1
        mgr._list_attempts = 4  # already past max (3)
        mgr._last_value_time = time.time() - 10.0
        mgr._fetch_start = time.time()

        mgr.check_timeout()

        link.send.assert_not_called()

    def test_timeout_stops_fetching(self):
        """Lines 188-192: after PARAM_FETCH_TIMEOUT, fetching stops."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        mgr.total_count = 10
        mgr._received_indices = {0, 1, 2}  # 7 missing
        # Set fetch_start far in the past
        mgr._fetch_start = time.time() - 120.0
        mgr._last_value_time = time.time()

        mgr.check_timeout()

        assert mgr.fetching is False
        link.add_event.assert_called_once()
        # Check timeout message was appended
        timeout_msgs = [m for m in mgr._messages if m.get("type") == "param_timeout"]
        assert len(timeout_msgs) == 1
        assert timeout_msgs[0]["missing"] == 7

    def test_gap_fill_then_timeout(self):
        """Both gap fill and timeout fire when both conditions met."""
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        mgr.total_count = 3
        mgr._received_indices = {0}  # indices 1, 2 missing
        mgr._fetch_start = time.time() - 120.0
        mgr._last_value_time = time.time() - 10.0

        mgr.check_timeout()

        # Gap fill sent requests for missing indices
        assert link.send.call_count == 2
        # Then timeout fired
        assert mgr.fetching is False


class TestGetStatus:
    def test_returns_status_dict(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.received_count = 50
        mgr.total_count = 100
        mgr.fetching = True
        status = mgr.get_status()
        assert status == {"param_count": 50, "param_total": 100, "param_fetching": True}
