"""Unit tests for the differential-thrust motor math (Track I.6).

Pure-logic coverage on the one deterministic piece of the drive system. Runs in
CI with no GPIO — importing motor_control never touches hardware, and
MotorController falls back to a no-op when gpiozero is absent.

Run: python -m unittest test_motor_control
"""

import unittest

from motor_control import _clamp, differential_mix, MotorController


class TestClamp(unittest.TestCase):
    def test_within_range_unchanged(self):
        self.assertEqual(_clamp(0.0), 0.0)
        self.assertEqual(_clamp(0.5), 0.5)
        self.assertEqual(_clamp(-0.5), -0.5)

    def test_clamps_to_bounds(self):
        self.assertEqual(_clamp(1.5), 1.0)
        self.assertEqual(_clamp(-1.5), -1.0)
        self.assertEqual(_clamp(2.0), 1.0)

    def test_exact_bounds(self):
        self.assertEqual(_clamp(1.0), 1.0)
        self.assertEqual(_clamp(-1.0), -1.0)


class TestDifferentialMix(unittest.TestCase):
    def test_straight_ahead(self):
        # throttle only, no steer -> both motors equal
        self.assertEqual(differential_mix(0.5, 0.0), (0.5, 0.5))
        self.assertEqual(differential_mix(1.0, 0.0), (1.0, 1.0))

    def test_reverse(self):
        # negative throttle -> both motors reverse together
        self.assertEqual(differential_mix(-0.5, 0.0), (-0.5, -0.5))

    def test_pivot_turn(self):
        # zero throttle + steer -> motors spin opposite (spin in place)
        self.assertEqual(differential_mix(0.0, 0.5), (0.5, -0.5))
        self.assertEqual(differential_mix(0.0, -0.5), (-0.5, 0.5))

    def test_full_throttle_full_steer_clamps(self):
        # 1.0 + 1.0 would be 2.0 -> clamp to 1.0; other side 1.0 - 1.0 = 0.0
        self.assertEqual(differential_mix(1.0, 1.0), (1.0, 0.0))
        self.assertEqual(differential_mix(1.0, -1.0), (0.0, 1.0))

    def test_reverse_with_steer_clamps(self):
        self.assertEqual(differential_mix(-1.0, -1.0), (-1.0, 0.0))
        self.assertEqual(differential_mix(-1.0, 1.0), (0.0, -1.0))

    def test_partial_mix(self):
        left, right = differential_mix(0.4, 0.2)
        self.assertAlmostEqual(left, 0.6)
        self.assertAlmostEqual(right, 0.2)

    def test_output_always_in_range(self):
        for t in (-1.5, -1.0, -0.3, 0.0, 0.3, 1.0, 1.5):
            for s in (-1.5, -1.0, -0.3, 0.0, 0.3, 1.0, 1.5):
                left, right = differential_mix(t, s)
                self.assertGreaterEqual(left, -1.0)
                self.assertLessEqual(left, 1.0)
                self.assertGreaterEqual(right, -1.0)
                self.assertLessEqual(right, 1.0)


class TestMotorControllerSoftwareMode(unittest.TestCase):
    """Without gpiozero (CI), the controller no-ops but must not raise."""

    def test_construct_and_drive_no_hardware(self):
        m = MotorController(watchdog_s=0.05)
        self.assertFalse(m.hardware)  # gpiozero absent in CI
        m.set_drive(0.5, 0.2)
        m.set_drive(-1.0, 1.0)
        m.stop()  # cancels the watchdog cleanly

    def test_armed_state(self):
        m = MotorController(watchdog_s=10)  # long window so it won't trip mid-test
        self.assertFalse(m.armed)      # nothing sent yet -> FAILSAFE/disarmed
        m.set_drive(0.3, 0.0)
        self.assertTrue(m.armed)       # control arrived -> ARMED
        m.stop()
        self.assertFalse(m.armed)      # explicit stop -> disarmed

    def test_watchdog_trips_disarms(self):
        import time
        m = MotorController(watchdog_s=0.05)
        m.set_drive(0.3, 0.0)
        self.assertTrue(m.armed)
        time.sleep(0.15)               # let the watchdog fire
        self.assertFalse(m.armed)      # watchdog trip -> FAILSAFE
        m.stop()


if __name__ == "__main__":
    unittest.main()
