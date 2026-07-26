"""Unit tests: statustext filter — all ArduPilot terms must be hidden."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.statustext_filter import filter_statustext


class TestLeakPrevention:
    def test_ardupilot_replaced(self):
        assert "ArduPilot" not in filter_statustext("ArduPilot v4.5.0")

    def test_arducopter_replaced(self):
        assert "ArduCopter" not in filter_statustext("ArduCopter v4.5.0")

    def test_arduplane_replaced(self):
        assert "ArduPlane" not in filter_statustext("ArduPlane v4.5.0")

    def test_chibios_replaced(self):
        assert "ChibiOS" not in filter_statustext("ChibiOS v21.11")

    def test_mavlink_replaced(self):
        assert "MAVLink" not in filter_statustext("MAVLink version mismatch")

    def test_ekf_replaced(self):
        assert "EKF3" not in filter_statustext("EKF3 IMU0 is using GPS")
        assert "EKF2" not in filter_statustext("EKF2 started")

    def test_prearm_replaced(self):
        assert "PreArm" not in filter_statustext("PreArm: Need 3D Fix")

    def test_ahrs_replaced(self):
        assert "AHRS" not in filter_statustext("Bad AHRS")

    def test_compass_replaced(self):
        assert "Compass" not in filter_statustext("Compass not calibrated")


class TestFullMessage:
    def test_need_3d_fix(self):
        assert filter_statustext("Need 3D Fix") == "需要3D定位"

    def test_ready_to_fly(self):
        assert filter_statustext("Ready to FLY") == "准备就绪"

    def test_low_battery(self):
        assert filter_statustext("Low Battery") == "低电量"

    def test_critical_battery(self):
        assert filter_statustext("Critical Battery") == "电量极低"

    def test_crash_disarming(self):
        assert "Crash" not in filter_statustext("Crash: Disarming")

    def test_gps_glitch(self):
        assert filter_statustext("GPS Glitch") == "GPS异常"

    def test_radio_failsafe(self):
        r = filter_statustext("Radio failsafe")
        assert "failsafe" not in r.lower()

    def test_battery_failsafe(self):
        r = filter_statustext("Battery failsafe")
        assert "failsafe" not in r.lower()


class TestTrailing:
    def test_cleared(self):
        assert filter_statustext("围栏 cleared") == "围栏 已解除"

    def test_triggered(self):
        assert filter_statustext("警报 triggered") == "警报 已触发"

    def test_enabled(self):
        assert filter_statustext("功能 enabled") == "功能 已启用"

    def test_disabled(self):
        assert filter_statustext("功能 disabled") == "功能 已禁用"

    def test_complete(self):
        assert filter_statustext("校准 complete") == "校准 完成"

    def test_failed(self):
        assert filter_statustext("检查 failed") == "检查 失败"


class TestTrailingOnOff:
    def test_on(self):
        assert filter_statustext("功能 on") == "功能 开启"

    def test_off(self):
        assert filter_statustext("功能 off") == "功能 关闭"

    def test_only_first_trailing_applied(self):
        r = filter_statustext("test enabled")
        assert r == "test 已启用"


class TestEnglishLocale:
    def test_brand_only_in_english(self):
        r = filter_statustext("ArduCopter v4.5.0", locale="en")
        assert "ArduCopter" not in r
        assert "FC" in r

    def test_no_chinese_in_english(self):
        r = filter_statustext("Need 3D Fix", locale="en")
        assert r == "Need 3D Fix"

    def test_trailing_not_translated_in_english(self):
        r = filter_statustext("Fence enabled", locale="en")
        assert r == "Fence enabled"

    def test_chibios_replaced_in_english(self):
        r = filter_statustext("ChibiOS v21.11", locale="en")
        assert "ChibiOS" not in r
        assert "RTOS" in r


class TestPassthrough:
    def test_plain_chinese(self):
        assert filter_statustext("准备就绪") == "准备就绪"

    def test_imu_prefix(self):
        assert "IMU0" in filter_statustext("IMU0 accel ok")

    def test_empty_string(self):
        assert filter_statustext("") == ""

    def test_unknown_message(self):
        assert filter_statustext("something random") == "something random"

    def test_substring_replacement(self):
        r = filter_statustext("NotPreArm")
        assert "PreArm" not in r
