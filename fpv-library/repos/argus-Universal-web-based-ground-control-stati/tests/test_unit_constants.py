"""Unit tests: constants — no English leaks in mode names/buttons."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.constants import (
    COPTER_BTNS,
    COPTER_BTNS_EN,
    COPTER_MODES,
    COPTER_MODES_EN,
    FIX_NAMES,
    FIX_NAMES_EN,
    PLANE_BTNS,
    PLANE_BTNS_EN,
    PLANE_MODES,
    PLANE_MODES_EN,
    ROVER_BTNS,
    ROVER_BTNS_EN,
    ROVER_MODES,
    ROVER_MODES_EN,
    SUB_BTNS,
    SUB_BTNS_EN,
    SUB_MODES,
    SUB_MODES_EN,
)


def _has_english(text):
    return any("a" <= c <= "z" or "A" <= c <= "Z" for c in text)


class TestModeNames:
    def test_copter_modes_chinese(self):
        for mid, name in COPTER_MODES.items():
            assert not _has_english(name), f"COPTER mode {mid} has English: {name}"

    def test_plane_modes_chinese(self):
        for mid, name in PLANE_MODES.items():
            clean = name.replace("A", "").replace("B", "")
            assert not _has_english(clean), f"PLANE mode {mid} has English: {name}"

    def test_fix_names_chinese(self):
        for fix, name in FIX_NAMES.items():
            english_only = all("a" <= c <= "z" or "A" <= c <= "Z" or c.isdigit() for c in name.replace(" ", ""))
            if english_only and name not in ("2D", "3D", "RTK"):
                assert False, f"FIX {fix} may leak: {name}"


class TestButtons:
    def test_copter_buttons_chinese(self):
        for mid, name in COPTER_BTNS:
            assert not _has_english(name), f"COPTER button {mid} has English: {name}"
            assert mid in COPTER_MODES, f"COPTER button {mid} not in COPTER_MODES"

    def test_plane_buttons_chinese(self):
        for mid, name in PLANE_BTNS:
            assert not _has_english(name), f"PLANE button {mid} has English: {name}"
            assert mid in PLANE_MODES, f"PLANE button {mid} not in PLANE_MODES"


class TestCompleteness:
    def test_copter_has_common_modes(self):
        assert 0 in COPTER_MODES  # Stabilize
        assert 5 in COPTER_MODES  # Loiter
        assert 6 in COPTER_MODES  # RTL
        assert 3 in COPTER_MODES  # Auto

    def test_plane_has_common_modes(self):
        assert 10 in PLANE_MODES  # Auto
        assert 11 in PLANE_MODES  # RTL
        assert 19 in PLANE_MODES  # QLoiter
        assert 21 in PLANE_MODES  # QRTL

    def test_rover_has_common_modes(self):
        assert 0 in ROVER_MODES  # Manual
        assert 10 in ROVER_MODES  # Auto
        assert 11 in ROVER_MODES  # RTL

    def test_sub_has_common_modes(self):
        assert 0 in SUB_MODES  # Stabilize
        assert 2 in SUB_MODES  # Depth Hold
        assert 3 in SUB_MODES  # Auto


class TestEnglishModes:
    def test_en_zh_mode_parity(self):
        assert set(COPTER_MODES.keys()) == set(COPTER_MODES_EN.keys())
        assert set(PLANE_MODES.keys()) == set(PLANE_MODES_EN.keys())
        assert set(ROVER_MODES.keys()) == set(ROVER_MODES_EN.keys())
        assert set(SUB_MODES.keys()) == set(SUB_MODES_EN.keys())

    def test_en_zh_btn_parity(self):
        assert len(COPTER_BTNS) == len(COPTER_BTNS_EN)
        assert len(PLANE_BTNS) == len(PLANE_BTNS_EN)
        assert len(ROVER_BTNS) == len(ROVER_BTNS_EN)
        assert len(SUB_BTNS) == len(SUB_BTNS_EN)

    def test_en_btn_ids_match_modes(self):
        for mid, _ in COPTER_BTNS_EN:
            assert mid in COPTER_MODES_EN
        for mid, _ in PLANE_BTNS_EN:
            assert mid in PLANE_MODES_EN
        for mid, _ in ROVER_BTNS_EN:
            assert mid in ROVER_MODES_EN
        for mid, _ in SUB_BTNS_EN:
            assert mid in SUB_MODES_EN

    def test_fix_names_en_parity(self):
        assert set(FIX_NAMES.keys()) == set(FIX_NAMES_EN.keys())


class TestIsPlane:
    def test_zh_copter(self):
        from backend.drone_link import DroneLink

        link = DroneLink()
        link.vehicle.vtype_raw = 2
        _, _, vn = link._get_vehicle_info()
        assert vn == "多旋翼"

    def test_en_copter(self):
        from backend.drone_link import DroneLink

        link = DroneLink()
        link.vehicle.vtype_raw = 2
        link.locale = "en"
        _, _, vn = link._get_vehicle_info()
        assert vn == "Multirotor"

    def test_en_plane(self):
        from backend.drone_link import DroneLink

        link = DroneLink()
        link.vehicle.vtype_raw = 1
        link.locale = "en"
        _, _, vn = link._get_vehicle_info()
        assert vn == "Fixed Wing"

    def test_en_rover(self):
        from backend.drone_link import DroneLink

        link = DroneLink()
        link.vehicle.vtype_raw = 10
        link.locale = "en"
        _, _, vn = link._get_vehicle_info()
        assert vn == "Rover"

    def test_en_sub(self):
        from backend.drone_link import DroneLink

        link = DroneLink()
        link.vehicle.vtype_raw = 12
        link.locale = "en"
        _, _, vn = link._get_vehicle_info()
        assert vn == "Sub"
