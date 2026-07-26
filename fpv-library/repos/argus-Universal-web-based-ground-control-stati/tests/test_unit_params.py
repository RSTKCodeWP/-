"""Unit tests: parameter management."""

import json
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.param_manager import ParamManager


def _make_link():
    link = MagicMock()
    link.sysid = 1
    link.sq = 0
    link.add_event = MagicMock()
    link.send = MagicMock()
    return link


def _param_value_payload(name: str, value: float, index: int, total: int, ptype: int = 9) -> bytes:
    name_bytes = name.encode("ascii")[:16].ljust(16, b"\x00")
    return struct.pack("<f", value) + struct.pack("<HH", total, index) + name_bytes + struct.pack("<B", ptype)


class TestParamManager:
    def test_request_all_sends_message(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.request_all()
        assert mgr.fetching is True
        link.send.assert_called_once()
        link.add_event.assert_called_with("参数: 正在读取...", "param_reading")

    def test_handle_single_param(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        p = _param_value_payload("BATT_CAPACITY", 5000.0, 0, 3)
        mgr.handle_param_value(p, len(p))
        assert "BATT_CAPACITY" in mgr.params
        assert mgr.params["BATT_CAPACITY"]["value"] == 5000.0
        assert mgr.received_count == 1
        assert mgr.total_count == 3

    def test_handle_all_params_completes(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.fetching = True
        names = ["A_PARAM", "B_PARAM", "C_PARAM"]
        for i, name in enumerate(names):
            p = _param_value_payload(name, float(i), i, 3)
            mgr.handle_param_value(p, len(p))
        assert mgr.fetching is False
        assert mgr.received_count == 3
        assert len(mgr.params) == 3
        complete_msgs = [m for m in mgr._messages if m["type"] == "params_complete"]
        assert len(complete_msgs) == 1
        assert complete_msgs[0]["count"] == 3

    def test_duplicate_param_not_double_counted(self):
        link = _make_link()
        mgr = ParamManager(link)
        p = _param_value_payload("TEST", 1.0, 0, 5)
        mgr.handle_param_value(p, len(p))
        mgr.handle_param_value(p, len(p))
        assert mgr.received_count == 1

    def test_set_param_sends_message(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params["BATT_CAPACITY"] = {"name": "BATT_CAPACITY", "value": 5000, "type": 9, "index": 0}
        mgr.set_param("BATT_CAPACITY", 6000.0)
        link.send.assert_called_once()
        link.add_event.assert_called()
        assert "6000" in link.add_event.call_args[0][0]

    def test_set_param_unknown_uses_default_type(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.set_param("NEW_PARAM", 42.0)
        link.send.assert_called_once()

    def test_save_to_file(self, tmp_path):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {
            "A": {"name": "A", "value": 1.0, "type": 9, "index": 0},
            "B": {"name": "B", "value": 2.0, "type": 9, "index": 1},
        }
        path = str(tmp_path / "params.json")
        result = mgr.save_to_file(path)
        assert result == path
        data = json.loads(Path(path).read_text())
        assert data == {"A": 1.0, "B": 2.0}

    def test_load_from_file(self, tmp_path):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.params = {
            "A": {"name": "A", "value": 1.0, "type": 9, "index": 0},
            "B": {"name": "B", "value": 2.0, "type": 9, "index": 1},
        }
        path = tmp_path / "params.json"
        path.write_text(json.dumps({"A": 1.0, "B": 5.0}))
        changed = mgr.load_from_file(str(path))
        assert changed == ["B"]

    def test_get_status(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.received_count = 10
        mgr.total_count = 38
        mgr.fetching = True
        status = mgr.get_status()
        assert status == {"param_count": 10, "param_total": 38, "param_fetching": True}

    def test_messages_accumulate_for_ws(self):
        link = _make_link()
        mgr = ParamManager(link)
        for i in range(5):
            p = _param_value_payload("P%d" % i, float(i), i, 10)
            mgr.handle_param_value(p, len(p))
        pv_msgs = [m for m in mgr._messages if m["type"] == "param_value"]
        assert len(pv_msgs) == 5
        assert pv_msgs[0]["name"] == "P0"
        assert pv_msgs[4]["received"] == 5

    def test_short_payload_ignored(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.handle_param_value(b"\x00" * 10, 10)
        assert len(mgr.params) == 0

    def test_messages_trimmed_on_overflow(self):
        link = _make_link()
        mgr = ParamManager(link)
        mgr.total_count = 2500
        for i in range(2500):
            name = "P%04d" % i
            p = _param_value_payload(name, float(i), i, 2500)
            mgr.handle_param_value(p, len(p))
        assert len(mgr._messages) <= 1500


class TestParamMeta:
    def test_parse_xml(self):
        from backend.param_meta import _parse_xml

        xml = b"""<paramfile>
        <parameters name="ARMING">
          <param humanName="Arming Check" name="ARMING_CHECK"
                 documentation="Checks to perform before arming">
            <field name="Range">0 65535</field>
            <field name="Units">bitmask</field>
            <field name="Default">1</field>
            <values>
              <value code="0">Disabled</value>
              <value code="1">Enabled</value>
            </values>
          </param>
        </parameters>
        </paramfile>"""
        meta = _parse_xml(xml)
        assert "ARMING_CHECK" in meta
        m = meta["ARMING_CHECK"]
        assert m["human"] == "Arming Check"
        assert m["group"] == "ARMING"
        assert m["range"] == [0, 65535]
        assert m["units"] == "bitmask"
        assert m["default"] == 1.0
        assert "0" in m["values"]
        assert m["values"]["1"] == "Enabled"

    def test_empty_xml(self):
        from backend.param_meta import _parse_xml

        meta = _parse_xml(b"<paramfile></paramfile>")
        assert meta == {}

    def test_get_metadata_invalid_vehicle(self):
        from backend.param_meta import get_metadata

        assert get_metadata("helicopter") == {}
