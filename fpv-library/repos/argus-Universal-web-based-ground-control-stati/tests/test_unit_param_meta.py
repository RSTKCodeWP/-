"""Tests for backend/param_meta.py — XML parsing and metadata structure."""

import json
import time
from unittest.mock import MagicMock, patch

from backend.param_meta import _parse_xml, get_metadata

SAMPLE_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<paramfile>
  <parameters name="COPTER">
    <param name="ANGLE_MAX" humanName="Maximum Lean Angle" documentation="Maximum lean angle in all flight modes">
      <field name="Range">0 8000</field>
      <field name="Units">cdeg</field>
      <field name="Increment">10</field>
      <field name="Default">3000</field>
      <value code="0">Disabled</value>
      <value code="3000">30 degrees</value>
    </param>
    <param name="BATT_ARM_VOLT" humanName="Battery Arming Voltage" documentation="Minimum voltage to arm">
      <field name="Range">0 100</field>
      <field name="Units">V</field>
    </param>
    <param name="LOG_BITMASK" humanName="Log Bitmask" documentation="Controls which log types are enabled">
      <field name="Bitmask">0:Attitude,1:GPS,2:PM</field>
    </param>
  </parameters>
</paramfile>
"""


class TestParseXml:
    def test_parses_params(self):
        meta = _parse_xml(SAMPLE_XML)
        assert "ANGLE_MAX" in meta
        assert "BATT_ARM_VOLT" in meta
        assert "LOG_BITMASK" in meta

    def test_range_field(self):
        meta = _parse_xml(SAMPLE_XML)
        assert meta["ANGLE_MAX"]["range"] == [0.0, 8000.0]
        assert meta["BATT_ARM_VOLT"]["range"] == [0.0, 100.0]

    def test_units_field(self):
        meta = _parse_xml(SAMPLE_XML)
        assert meta["ANGLE_MAX"]["units"] == "cdeg"
        assert meta["BATT_ARM_VOLT"]["units"] == "V"

    def test_increment_field(self):
        meta = _parse_xml(SAMPLE_XML)
        assert meta["ANGLE_MAX"]["step"] == 10.0

    def test_default_field(self):
        meta = _parse_xml(SAMPLE_XML)
        assert meta["ANGLE_MAX"]["default"] == 3000.0

    def test_values(self):
        meta = _parse_xml(SAMPLE_XML)
        assert meta["ANGLE_MAX"]["values"]["0"] == "Disabled"
        assert meta["ANGLE_MAX"]["values"]["3000"] == "30 degrees"

    def test_bitmask(self):
        meta = _parse_xml(SAMPLE_XML)
        bm = meta["LOG_BITMASK"]["bitmask"]
        assert bm["0"] == "Attitude"
        assert bm["1"] == "GPS"
        assert bm["2"] == "PM"

    def test_human_name(self):
        meta = _parse_xml(SAMPLE_XML)
        assert meta["ANGLE_MAX"]["human"] == "Maximum Lean Angle"

    def test_description(self):
        meta = _parse_xml(SAMPLE_XML)
        assert "lean angle" in meta["ANGLE_MAX"]["desc"].lower()

    def test_group(self):
        meta = _parse_xml(SAMPLE_XML)
        assert meta["ANGLE_MAX"]["group"] == "COPTER"

    def test_empty_xml(self):
        meta = _parse_xml(b"<paramfile></paramfile>")
        assert meta == {}

    def test_param_without_name_skipped(self):
        xml = b'<paramfile><parameters name="X"><param documentation="no name"></param></parameters></paramfile>'
        meta = _parse_xml(xml)
        assert meta == {}

    def test_range_non_numeric_skipped(self):
        """Range field with non-numeric values should be silently skipped (line 84-85)."""
        xml = b"""<paramfile><parameters name="G">
          <param name="P1" humanName="P" documentation="D">
            <field name="Range">abc xyz</field>
          </param>
        </parameters></paramfile>"""
        meta = _parse_xml(xml)
        assert "P1" in meta
        assert "range" not in meta["P1"]

    def test_increment_non_numeric_skipped(self):
        """Increment field with non-numeric value should be silently skipped (line 91-92)."""
        xml = b"""<paramfile><parameters name="G">
          <param name="P2" humanName="P" documentation="D">
            <field name="Increment">not_a_number</field>
          </param>
        </parameters></paramfile>"""
        meta = _parse_xml(xml)
        assert "P2" in meta
        assert "step" not in meta["P2"]

    def test_default_non_numeric_skipped(self):
        """Default field with non-numeric value should be silently skipped (line 96-97)."""
        xml = b"""<paramfile><parameters name="G">
          <param name="P3" humanName="P" documentation="D">
            <field name="Default">NaN_text</field>
          </param>
        </parameters></paramfile>"""
        meta = _parse_xml(xml)
        assert "P3" in meta
        assert "default" not in meta["P3"]


class TestGetMetadata:
    """Test get_metadata() — cache, network download, and fallback paths."""

    def setup_method(self):
        """Clear the module-level in-memory cache before each test."""
        import backend.param_meta as pm

        pm._cache.clear()

    def test_unknown_vehicle_returns_empty(self):
        """Vehicle name not in _URLS returns {} immediately (line 30-31)."""
        assert get_metadata("helicopter") == {}

    def test_in_memory_cache_hit(self):
        """Second call for same vehicle returns from _cache without disk/network (line 32-33)."""
        import backend.param_meta as pm

        pm._cache["copter"] = {"CACHED": True}
        result = get_metadata("copter")
        assert result == {"CACHED": True}

    def test_disk_cache_fresh(self, tmp_path):
        """Fresh disk cache file is loaded and returned (lines 36-42)."""
        import backend.param_meta as pm

        cache_file = tmp_path / "copter.json"
        cache_data = {"FROM_DISK": True}
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(pm, "CACHE_DIR", tmp_path), patch.object(pm, "CACHE_TTL", 99999):
            result = get_metadata("copter")
        assert result == cache_data
        assert pm._cache["copter"] == cache_data

    def test_disk_cache_stale_triggers_download(self, tmp_path):
        """Stale disk cache triggers network download (lines 37-38 → 44+)."""
        import backend.param_meta as pm

        cache_file = tmp_path / "copter.json"
        cache_file.write_text(json.dumps({"OLD": True}))
        # Make file appear old
        old_time = time.time() - 999999
        import os

        os.utime(cache_file, (old_time, old_time))

        mock_resp = MagicMock()
        mock_resp.read.return_value = SAMPLE_XML

        with (
            patch.object(pm, "CACHE_DIR", tmp_path),
            patch.object(pm, "CACHE_TTL", 1),
            patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            result = get_metadata("copter")
        assert "ANGLE_MAX" in result
        # Should have written to disk cache
        disk = json.loads(cache_file.read_text())
        assert "ANGLE_MAX" in disk

    def test_network_success_writes_cache(self, tmp_path):
        """Successful network download creates cache dir and file (lines 44-52)."""
        import backend.param_meta as pm

        cache_dir = tmp_path / "fresh_cache"
        mock_resp = MagicMock()
        mock_resp.read.return_value = SAMPLE_XML

        with patch.object(pm, "CACHE_DIR", cache_dir), patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_metadata("copter")
        assert "ANGLE_MAX" in result
        assert (cache_dir / "copter.json").exists()

    def test_network_failure_falls_back_to_stale_cache(self, tmp_path):
        """Network error with existing stale cache returns stale data (lines 53-58)."""
        import backend.param_meta as pm

        cache_file = tmp_path / "copter.json"
        stale_data = {"STALE": True}
        cache_file.write_text(json.dumps(stale_data))
        # Make file old so it doesn't hit the fresh-cache path
        old_time = time.time() - 999999
        import os

        os.utime(cache_file, (old_time, old_time))

        with (
            patch.object(pm, "CACHE_DIR", tmp_path),
            patch.object(pm, "CACHE_TTL", 1),
            patch("urllib.request.urlopen", side_effect=OSError("no network")),
        ):
            result = get_metadata("copter")
        assert result == stale_data

    def test_network_failure_no_cache_returns_empty(self, tmp_path):
        """Network error with no disk cache returns {} (line 59)."""
        import backend.param_meta as pm

        with (
            patch.object(pm, "CACHE_DIR", tmp_path),
            patch.object(pm, "CACHE_TTL", 1),
            patch("urllib.request.urlopen", side_effect=OSError("no network")),
        ):
            result = get_metadata("copter")
        assert result == {}

    def test_fresh_cache_corrupted_falls_through_to_network(self, tmp_path):
        """Corrupted fresh cache must not raise — falls through to network fetch."""
        import backend.param_meta as pm

        cache_file = tmp_path / "copter.json"
        cache_file.write_text("{NOT VALID JSON{{")  # corrupted

        mock_resp = MagicMock()
        mock_resp.read.return_value = SAMPLE_XML

        with (
            patch.object(pm, "CACHE_DIR", tmp_path),
            patch.object(pm, "CACHE_TTL", 99999),
            patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            result = get_metadata("copter")
        assert "ANGLE_MAX" in result  # got fresh data from network, no exception

    def test_stale_fallback_cache_corrupted_returns_empty(self, tmp_path):
        """Corrupted stale fallback cache must not raise — returns {} gracefully."""
        import backend.param_meta as pm

        cache_file = tmp_path / "copter.json"
        cache_file.write_text("{NOT VALID JSON{{")  # corrupted
        old_time = time.time() - 999999
        import os

        os.utime(cache_file, (old_time, old_time))

        with (
            patch.object(pm, "CACHE_DIR", tmp_path),
            patch.object(pm, "CACHE_TTL", 1),
            patch("urllib.request.urlopen", side_effect=OSError("no network")),
        ):
            result = get_metadata("copter")
        assert result == {}  # both network and stale cache failed — empty dict, no exception

    def test_case_insensitive_vehicle(self):
        """Vehicle name is lowercased (line 29)."""
        import backend.param_meta as pm

        pm._cache["rover"] = {"ROVER": True}
        assert get_metadata("ROVER") == {"ROVER": True}
        assert get_metadata("Rover") == {"ROVER": True}
