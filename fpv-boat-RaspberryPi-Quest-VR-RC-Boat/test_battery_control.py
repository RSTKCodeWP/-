"""Unit tests for the battery state-of-charge estimation (Track D / I.3).

Covers the pure voltage->percent mapping and the no-sensor fallback of
BatteryMonitor. Runs in CI with no hardware — importing battery_control never
touches I2C, and without the `ina219` library the monitor reports all-None.

Run: python -m unittest test_battery_control
"""

import unittest

from battery_control import percent_from_voltage, BatteryMonitor


class TestPercentFromVoltage(unittest.TestCase):
    def test_full_and_empty_clamp(self):
        # 3S pack: 3 * 4.2 = 12.6 full, 3 * 3.27 = 9.81 empty
        self.assertEqual(percent_from_voltage(12.6, cells=3), 100)
        self.assertEqual(percent_from_voltage(9.81, cells=3), 0)

    def test_above_full_and_below_empty_saturate(self):
        self.assertEqual(percent_from_voltage(13.5, cells=3), 100)
        self.assertEqual(percent_from_voltage(6.0, cells=3), 0)

    def test_midpoint_is_reasonable(self):
        # 3.84 V/cell is the 50% point in the curve -> 11.52 V on 3S
        self.assertEqual(percent_from_voltage(3.84 * 3, cells=3), 50)

    def test_monotonic_non_decreasing_with_voltage(self):
        last = -1
        v = 9.6
        while v <= 12.6:
            p = percent_from_voltage(round(v, 3), cells=3)
            self.assertIsNotNone(p)
            self.assertGreaterEqual(p, last)   # never drops as voltage rises
            last = p
            v += 0.05

    def test_always_in_0_100(self):
        v = 8.0
        while v <= 13.0:
            p = percent_from_voltage(round(v, 3), cells=3)
            self.assertGreaterEqual(p, 0)
            self.assertLessEqual(p, 100)
            v += 0.1

    def test_cell_count_scales(self):
        # same per-cell voltage -> same percent regardless of pack size
        self.assertEqual(percent_from_voltage(3.80 * 2, cells=2),
                         percent_from_voltage(3.80 * 4, cells=4))

    def test_bad_input_returns_none(self):
        self.assertIsNone(percent_from_voltage(None, cells=3))
        self.assertIsNone(percent_from_voltage(11.1, cells=0))
        self.assertIsNone(percent_from_voltage(11.1, cells=None))


class TestBatteryMonitorSoftwareMode(unittest.TestCase):
    """Without the ina219 lib (CI), reads must be all-None and never raise."""

    def test_no_sensor_reads_none(self):
        batt = BatteryMonitor(cells=3)
        self.assertFalse(batt.hardware)
        r = batt.read()
        self.assertIsNone(r["voltage"])
        self.assertIsNone(r["current_ma"])
        self.assertIsNone(r["percent"])
        self.assertEqual(r["cells"], 3)

    def test_warn_pct_exposed(self):
        batt = BatteryMonitor()
        self.assertIsInstance(batt.warn_pct, int)


if __name__ == "__main__":
    unittest.main()
