"""Unit tests: file import/export functionality.

Tests KML export/import, JSON mission files, parameter file export/import,
CSV log export format, and firmware file upload validation.
"""

import json
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.param_manager import ParamManager

# --- Helpers ---


def _make_link():
    link = MagicMock()
    link.sysid = 1
    link.sq = 0
    link.locale = "zh"
    link.add_event = MagicMock()
    link.send = MagicMock()
    link.vehicle = MagicMock()
    link.vehicle.sysid = 1
    return link


def _param_value_payload(name: str, value: float, index: int, total: int, ptype: int = 9) -> bytes:
    name_bytes = name.encode("ascii")[:16].ljust(16, b"\x00")
    return struct.pack("<f", value) + struct.pack("<HH", total, index) + name_bytes + struct.pack("<B", ptype)


KML_NAMESPACE = "http://www.opengis.net/kml/2.2"


# ============================================================
# KML Export Tests
# ============================================================


class TestKmlExport:
    """Test KML export format matching MissionPanel.svelte export logic."""

    def _generate_kml(self, waypoints: list[dict]) -> str:
        """Reproduce the KML export logic from MissionPanel.svelte."""
        coords = "\n".join(f"{w['lon']},{w['lat']},{w['alt']}" for w in waypoints)
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<kml xmlns="{KML_NAMESPACE}"><Document><name>Argus Mission</name>\n'
            f"<Placemark><name>Route</name><LineString><coordinates>{coords}</coordinates></LineString></Placemark>\n"
            "</Document></kml>"
        )
        return kml

    def test_kml_is_valid_xml(self):
        wps = [{"lat": 30.0, "lon": 120.0, "alt": 50}]
        kml = self._generate_kml(wps)
        root = ET.fromstring(kml)
        assert root is not None

    def test_kml_has_correct_namespace(self):
        wps = [{"lat": 30.0, "lon": 120.0, "alt": 50}]
        kml = self._generate_kml(wps)
        root = ET.fromstring(kml)
        assert root.tag == f"{{{KML_NAMESPACE}}}kml"

    def test_kml_contains_document(self):
        wps = [{"lat": 30.0, "lon": 120.0, "alt": 50}]
        kml = self._generate_kml(wps)
        root = ET.fromstring(kml)
        doc = root.find(f"{{{KML_NAMESPACE}}}Document")
        assert doc is not None

    def test_kml_placemark_with_coordinates(self):
        wps = [
            {"lat": 30.0, "lon": 120.0, "alt": 50},
            {"lat": 30.1, "lon": 120.1, "alt": 60},
        ]
        kml = self._generate_kml(wps)
        root = ET.fromstring(kml)
        ns = {"kml": KML_NAMESPACE}
        placemarks = root.findall(".//kml:Placemark", ns)
        assert len(placemarks) == 1
        coords_el = root.find(".//kml:coordinates", ns)
        assert coords_el is not None
        text = coords_el.text.strip()
        parts = text.split("\n")
        assert len(parts) == 2
        assert "120.0,30.0,50" in parts[0]
        assert "120.1,30.1,60" in parts[1]

    def test_kml_coordinate_order_is_lon_lat_alt(self):
        wps = [{"lat": 45.678, "lon": 123.456, "alt": 100}]
        kml = self._generate_kml(wps)
        root = ET.fromstring(kml)
        ns = {"kml": KML_NAMESPACE}
        coords_el = root.find(".//kml:coordinates", ns)
        coord_str = coords_el.text.strip()
        parts = coord_str.split(",")
        assert float(parts[0]) == 123.456  # lon first
        assert float(parts[1]) == 45.678  # lat second
        assert float(parts[2]) == 100  # alt third

    def test_kml_empty_waypoints_produces_valid_xml(self):
        kml = self._generate_kml([])
        root = ET.fromstring(kml)
        assert root is not None


# ============================================================
# KML Import Tests
# ============================================================


class TestKmlImport:
    """Test KML import parsing matching MissionPanel.svelte importKml logic."""

    def _parse_kml(self, kml_text: str) -> list[dict]:
        """Reproduce the KML import logic from MissionPanel.svelte."""
        root = ET.fromstring(kml_text)
        coords = []
        for el in root.iter(f"{{{KML_NAMESPACE}}}coordinates"):
            text = el.text.strip() if el.text else ""
            for c in text.split():
                p = c.split(",")
                if len(p) >= 2:
                    lon = float(p[0])
                    lat = float(p[1])
                    alt = float(p[2]) if len(p) >= 3 else 30.0
                    if abs(lat) > 0.001 and abs(lon) > 0.001:
                        coords.append({"lat": lat, "lon": lon, "alt": alt, "drop": False, "delay": 0})
        # Remove duplicate closing point
        if len(coords) > 1 and abs(coords[0]["lat"] - coords[-1]["lat"]) < 0.00001:
            coords.pop()
        return coords

    def test_import_linestring_waypoints(self):
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<kml xmlns="{KML_NAMESPACE}"><Document>'
            "<Placemark><LineString><coordinates>"
            "120.0,30.0,50 120.1,30.1,60 120.2,30.2,70"
            "</coordinates></LineString></Placemark>"
            "</Document></kml>"
        )
        wps = self._parse_kml(kml)
        assert len(wps) == 3
        assert wps[0] == {"lat": 30.0, "lon": 120.0, "alt": 50.0, "drop": False, "delay": 0}
        assert wps[2]["alt"] == 70.0

    def test_import_point_coordinates(self):
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<kml xmlns="{KML_NAMESPACE}"><Document>'
            "<Placemark><Point><coordinates>121.5,31.2,100</coordinates></Point></Placemark>"
            "</Document></kml>"
        )
        wps = self._parse_kml(kml)
        assert len(wps) == 1
        assert wps[0]["lat"] == 31.2
        assert wps[0]["lon"] == 121.5

    def test_import_removes_duplicate_closing_point(self):
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<kml xmlns="{KML_NAMESPACE}"><Document>'
            "<Placemark><LinearRing><coordinates>"
            "120.0,30.0,50 120.1,30.1,60 120.2,30.2,70 120.0,30.0,50"
            "</coordinates></LinearRing></Placemark>"
            "</Document></kml>"
        )
        wps = self._parse_kml(kml)
        assert len(wps) == 3  # Closing duplicate removed

    def test_import_skips_near_zero_coordinates(self):
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<kml xmlns="{KML_NAMESPACE}"><Document>'
            "<Placemark><LineString><coordinates>"
            "0.0001,0.0001,0 120.1,30.1,60"
            "</coordinates></LineString></Placemark>"
            "</Document></kml>"
        )
        wps = self._parse_kml(kml)
        assert len(wps) == 1
        assert wps[0]["lat"] == 30.1

    def test_import_defaults_alt_when_missing(self):
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<kml xmlns="{KML_NAMESPACE}"><Document>'
            "<Placemark><LineString><coordinates>"
            "120.0,30.0"
            "</coordinates></LineString></Placemark>"
            "</Document></kml>"
        )
        wps = self._parse_kml(kml)
        assert len(wps) == 1
        assert wps[0]["alt"] == 30.0  # default alt


# ============================================================
# JSON Mission File Tests
# ============================================================


class TestJsonMission:
    """Test JSON mission file format matching MissionPanel.svelte save/load logic."""

    def test_export_contains_required_fields(self):
        waypoints = [
            {
                "lat": 30.0,
                "lon": 120.0,
                "alt": 50,
                "drop": False,
                "delay": 0,
                "speed": 0,
                "type": "wp",
                "loiter_param": 0,
            },
            {
                "lat": 30.1,
                "lon": 120.1,
                "alt": 60,
                "drop": True,
                "delay": 5,
                "speed": 3,
                "type": "spline",
                "loiter_param": 0,
            },
        ]
        data = json.dumps({"waypoints": waypoints, "alt": 50}, indent=2)
        parsed = json.loads(data)
        assert "waypoints" in parsed
        assert "alt" in parsed
        for wp in parsed["waypoints"]:
            assert "lat" in wp
            assert "lon" in wp
            assert "alt" in wp
            assert "type" in wp

    def test_export_preserves_all_waypoint_fields(self):
        wp = {
            "lat": 30.5,
            "lon": 120.5,
            "alt": 75,
            "drop": True,
            "delay": 3,
            "speed": 5,
            "type": "spline",
            "loiter_param": 2,
        }
        data = json.dumps({"waypoints": [wp], "alt": 75}, indent=2)
        parsed = json.loads(data)
        out_wp = parsed["waypoints"][0]
        assert out_wp["lat"] == 30.5
        assert out_wp["lon"] == 120.5
        assert out_wp["alt"] == 75
        assert out_wp["drop"] is True
        assert out_wp["delay"] == 3
        assert out_wp["speed"] == 5
        assert out_wp["type"] == "spline"
        assert out_wp["loiter_param"] == 2

    def test_import_parses_standard_format(self):
        mission = {
            "waypoints": [
                {
                    "lat": 30.0,
                    "lon": 120.0,
                    "alt": 50,
                    "drop": False,
                    "delay": 0,
                    "speed": 0,
                    "type": "wp",
                    "loiter_param": 0,
                },
            ],
            "alt": 50,
        }
        text = json.dumps(mission)
        d = json.loads(text)
        assert d["waypoints"][0]["lat"] == 30.0
        assert d["alt"] == 50

    def test_import_handles_missing_alt_field(self):
        mission = {
            "waypoints": [
                {
                    "lat": 30.0,
                    "lon": 120.0,
                    "alt": 50,
                    "drop": False,
                    "delay": 0,
                    "speed": 0,
                    "type": "wp",
                    "loiter_param": 0,
                },
            ],
        }
        text = json.dumps(mission)
        d = json.loads(text)
        assert "waypoints" in d
        assert d.get("alt") is None  # Frontend uses d.alt || default


# ============================================================
# Parameter File Export Tests
# ============================================================


class TestParamFileExport:
    """Test parameter file export matching ParamPanel.svelte exportParams logic.

    Frontend format: "PARAM_NAME\\tvalue" per line (tab-separated).
    Backend format (save_to_file): JSON dict of name:value pairs.
    """

    def test_frontend_format_tab_separated(self):
        """Frontend exports as 'NAME\\tVALUE' per line."""
        params = [
            {"name": "BATT_CAPACITY", "value": 5000.0},
            {"name": "ARMING_CHECK", "value": 1.0},
            {"name": "ACRO_YAW_P", "value": 4.5},
        ]
        lines = [f"{p['name']}\t{p['value']}" for p in params]
        text = "\n".join(lines)
        assert "BATT_CAPACITY\t5000.0" in text
        assert "ARMING_CHECK\t1.0" in text
        for line in text.split("\n"):
            parts = line.split("\t")
            assert len(parts) == 2
            assert parts[0].isupper() or "_" in parts[0]
            float(parts[1])  # must be parseable as float

    def test_backend_save_to_file_json_format(self):
        link = _make_link()
        mgr = ParamManager(link)
        # Populate some params
        names = ["BATT_CAPACITY", "ARMING_CHECK", "ACRO_YAW_P"]
        values = [5000.0, 1.0, 4.5]
        for i, (name, val) in enumerate(zip(names, values, strict=True)):
            p = _param_value_payload(name, val, i, 3)
            mgr.handle_param_value(p, len(p))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        mgr.save_to_file(path)
        with open(path) as f:
            data = json.load(f)

        assert "BATT_CAPACITY" in data
        assert abs(data["BATT_CAPACITY"] - 5000.0) < 0.1
        assert "ARMING_CHECK" in data
        assert "ACRO_YAW_P" in data
        Path(path).unlink()

    def test_backend_save_sorted_alphabetically(self):
        link = _make_link()
        mgr = ParamManager(link)
        names = ["Z_PARAM", "A_PARAM", "M_PARAM"]
        for i, name in enumerate(names):
            p = _param_value_payload(name, float(i), i, 3)
            mgr.handle_param_value(p, len(p))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        mgr.save_to_file(path)
        with open(path) as f:
            data = json.load(f)

        keys = list(data.keys())
        assert keys == sorted(keys)
        Path(path).unlink()


# ============================================================
# Parameter File Import Tests
# ============================================================


class TestParamFileImport:
    """Test parameter file import matching ParamPanel.svelte importParams and
    ParamDiffPanel.svelte parseParamFile logic."""

    def _parse_param_file(self, text: str) -> dict[str, float]:
        """Reproduce the frontend param file parsing logic."""
        result = {}
        for line in text.split("\n"):
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("#"):
                continue
            # Split by tab, comma, or whitespace
            import re

            parts = re.split(r"[\t,\s]+", trimmed)
            if len(parts) < 2:
                continue
            name = parts[0]
            try:
                val = float(parts[1])
            except ValueError:
                continue
            result[name] = val
        return result

    def test_import_valid_tab_separated(self):
        text = "BATT_CAPACITY\t5000\nARMING_CHECK\t1\nACRO_YAW_P\t4.5"
        params = self._parse_param_file(text)
        assert params["BATT_CAPACITY"] == 5000.0
        assert params["ARMING_CHECK"] == 1.0
        assert params["ACRO_YAW_P"] == 4.5

    def test_import_valid_comma_separated(self):
        text = "BATT_CAPACITY,5000\nARMING_CHECK,1"
        params = self._parse_param_file(text)
        assert params["BATT_CAPACITY"] == 5000.0
        assert params["ARMING_CHECK"] == 1.0

    def test_import_skips_comments(self):
        text = "# This is a comment\nBATT_CAPACITY\t5000\n# Another comment\nARMING_CHECK\t1"
        params = self._parse_param_file(text)
        assert len(params) == 2
        assert "#" not in "".join(params.keys())

    def test_import_skips_empty_lines(self):
        text = "\nBATT_CAPACITY\t5000\n\n\nARMING_CHECK\t1\n"
        params = self._parse_param_file(text)
        assert len(params) == 2

    def test_import_rejects_malformed_single_column(self):
        text = "BATT_CAPACITY\nARMING_CHECK\t1"
        params = self._parse_param_file(text)
        assert "BATT_CAPACITY" not in params
        assert "ARMING_CHECK" in params

    def test_import_rejects_non_numeric_value(self):
        text = "BATT_CAPACITY\tabc\nARMING_CHECK\t1"
        params = self._parse_param_file(text)
        assert "BATT_CAPACITY" not in params
        assert "ARMING_CHECK" in params

    def test_backend_load_from_file(self):
        link = _make_link()
        mgr = ParamManager(link)
        # Pre-populate with existing params
        names = ["BATT_CAPACITY", "ARMING_CHECK"]
        values = [5000.0, 1.0]
        for i, (name, val) in enumerate(zip(names, values, strict=True)):
            p = _param_value_payload(name, val, i, 2)
            mgr.handle_param_value(p, len(p))

        # Write a file with one changed value
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"BATT_CAPACITY": 6000.0, "ARMING_CHECK": 1.0}, f)
            path = f.name

        changed = mgr.load_from_file(path)
        assert "BATT_CAPACITY" in changed
        assert "ARMING_CHECK" not in changed  # value unchanged
        Path(path).unlink()

    def test_import_handles_inline_comments(self):
        """Param diff export includes '# default=X' suffix."""
        text = "BATT_CAPACITY\t5000\t# default=4000\nARMING_CHECK\t1\t# default=1"
        params = self._parse_param_file(text)
        # The parser uses parts[1] only, so inline comment after tab is a third field
        assert params["BATT_CAPACITY"] == 5000.0
        assert params["ARMING_CHECK"] == 1.0


# ============================================================
# CSV Log Export Tests
# ============================================================


class TestCsvLogExport:
    """Test CSV log export format matching drone_link.py _start_log / _write_log_line."""

    EXPECTED_HEADERS = [
        "time",
        "roll",
        "pitch",
        "yaw",
        "lat",
        "lon",
        "alt_rel",
        "alt_msl",
        "gs",
        "vz",
        "voltage",
        "current",
        "remaining",
        "mode",
        "mode_name",
        "armed",
        "gps_fix",
        "sats",
        "wp",
        "hdg",
        "dist",
        "bat_time",
    ]

    def _generate_csv_header(self) -> str:
        return ",".join(self.EXPECTED_HEADERS)

    def _generate_csv_line(self) -> str:
        """Simulate a log line from drone_link.py."""
        return "%.2f,%.2f,%.2f,%.1f,%.7f,%.7f,%.1f,%.1f,%.1f,%.1f,%.2f,%.2f,%d,%d,%s,%d,%d,%d,%d,%.0f,%.0f,%d" % (
            10.5,
            5.2,
            -3.1,
            180.0,
            30.1234567,
            120.1234567,
            15.3,
            115.3,
            5.5,
            -0.3,
            12.45,
            8.32,
            75,
            4,
            "GUIDED",
            1,
            3,
            12,
            3,
            180,
            250,
            600,
        )

    def test_csv_header_has_correct_columns(self):
        header = self._generate_csv_header()
        cols = header.split(",")
        assert len(cols) == 22
        assert cols[0] == "time"
        assert cols[4] == "lat"
        assert cols[5] == "lon"
        assert cols[10] == "voltage"

    def test_csv_data_line_matches_column_count(self):
        header = self._generate_csv_header()
        line = self._generate_csv_line()
        header_count = len(header.split(","))
        line_count = len(line.split(","))
        assert header_count == line_count

    def test_csv_data_types_are_numeric(self):
        line = self._generate_csv_line()
        parts = line.split(",")
        # mode_name (index 14) is a string, all others are numeric
        for i, val in enumerate(parts):
            if i == 14:  # mode_name is string
                continue
            float(val)  # Should not raise


# ============================================================
# Firmware File Upload Validation Tests
# ============================================================


class TestFirmwareUploadValidation:
    """Test firmware upload validation matching app.py api_firmware_upload.

    Backend only accepts .apj files (ArduPilot firmware JSON format).
    """

    def test_reject_no_filename(self):
        # The endpoint checks: if not file.filename or not file.filename.endswith('.apj')
        assert not _validate_firmware_filename(None)

    def test_reject_empty_filename(self):
        assert not _validate_firmware_filename("")

    def test_reject_bin_extension(self):
        assert not _validate_firmware_filename("firmware.bin")

    def test_reject_hex_extension(self):
        assert not _validate_firmware_filename("firmware.hex")

    def test_reject_txt_extension(self):
        assert not _validate_firmware_filename("firmware.txt")

    def test_accept_apj_extension(self):
        assert _validate_firmware_filename("ArduCopter.apj")

    def test_accept_apj_with_version(self):
        assert _validate_firmware_filename("arducopter-v4.5.1.apj")

    def test_reject_apj_prefix_wrong_ext(self):
        assert not _validate_firmware_filename("apj_firmware.bin")


def _validate_firmware_filename(filename: str | None) -> bool:
    """Reproduce the firmware upload validation from app.py."""
    return bool(filename and filename.endswith(".apj"))
