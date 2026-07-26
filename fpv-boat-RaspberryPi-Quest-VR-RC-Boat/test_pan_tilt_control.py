"""Unit tests for the head-tracking servo mapping (Track H — pan/tilt).

Covers the pure head-orientation -> servo-angle mapping and the no-hardware
fallback of PanTiltController. Runs in CI with no I2C — importing
pan_tilt_control never touches the bus, and without adafruit_servokit the
controller just tracks the last commanded angle.

Run: python -m unittest test_pan_tilt_control
"""

import unittest

import pan_tilt_control as pt
from pan_tilt_control import (
    head_to_servo, PanTiltController,
    PAN_CENTER, PAN_MIN, PAN_MAX, TILT_CENTER, TILT_MIN, TILT_MAX,
    PAN_RANGE_DEG, TILT_RANGE_DEG,
)


class TestHeadToServo(unittest.TestCase):
    def test_neutral_is_centered(self):
        self.assertEqual(head_to_servo(0, 0), (PAN_CENTER, TILT_CENTER))

    def test_full_yaw_hits_pan_limits(self):
        # +PAN_RANGE_DEG -> PAN_MAX, -PAN_RANGE_DEG -> PAN_MIN (with default sign +1)
        pan_pos, _ = head_to_servo(PAN_RANGE_DEG, 0)
        pan_neg, _ = head_to_servo(-PAN_RANGE_DEG, 0)
        self.assertEqual(pan_pos, PAN_MAX)
        self.assertEqual(pan_neg, PAN_MIN)

    def test_beyond_range_clamps(self):
        pan, tilt = head_to_servo(10 * PAN_RANGE_DEG, 10 * TILT_RANGE_DEG)
        self.assertEqual(pan, PAN_MAX)
        self.assertEqual(tilt, TILT_MAX)
        pan, tilt = head_to_servo(-10 * PAN_RANGE_DEG, -10 * TILT_RANGE_DEG)
        self.assertEqual(pan, PAN_MIN)
        self.assertEqual(tilt, TILT_MIN)

    def test_half_yaw_is_halfway(self):
        pan, _ = head_to_servo(PAN_RANGE_DEG / 2, 0)
        self.assertAlmostEqual(pan, PAN_CENTER + (PAN_MAX - PAN_CENTER) / 2)

    def test_tilt_maps_independently_of_pan(self):
        _, tilt = head_to_servo(PAN_RANGE_DEG, TILT_RANGE_DEG)
        self.assertEqual(tilt, TILT_MAX)      # pan at limit doesn't disturb tilt

    def test_output_always_within_servo_limits(self):
        for yaw in (-200, -90, -30, 0, 30, 90, 200):
            for pitch in (-200, -45, 0, 45, 200):
                pan, tilt = head_to_servo(yaw, pitch)
                self.assertGreaterEqual(pan, PAN_MIN)
                self.assertLessEqual(pan, PAN_MAX)
                self.assertGreaterEqual(tilt, TILT_MIN)
                self.assertLessEqual(tilt, TILT_MAX)

    def test_tilt_never_exceeds_safe_cone(self):
        # tilt is intentionally narrower than a full 0..180 so the camera can't
        # crank into the hull or straight up
        self.assertGreater(TILT_MIN, 0)
        self.assertLess(TILT_MAX, 180)


class TestSoftwareMode(unittest.TestCase):
    """Without adafruit_servokit (CI), commands track angle state but never raise."""

    def test_construct_no_hardware(self):
        c = PanTiltController()
        self.assertFalse(c.hardware)
        self.assertEqual((c.pan, c.tilt), (PAN_CENTER, TILT_CENTER))

    def test_set_head_updates_tracked_angles(self):
        c = PanTiltController()
        c.set_head(PAN_RANGE_DEG, 0)
        self.assertEqual(c.pan, PAN_MAX)
        c.set_head(-PAN_RANGE_DEG, 0)
        self.assertEqual(c.pan, PAN_MIN)

    def test_center_resets(self):
        c = PanTiltController()
        c.set_head(PAN_RANGE_DEG, TILT_RANGE_DEG)
        c.center()
        self.assertEqual((c.pan, c.tilt), (PAN_CENTER, TILT_CENTER))

    def test_tiny_changes_still_tracked(self):
        # The hardware deadband must never affect the *tracked* angles — telemetry
        # and recenter() rely on them being exact.
        c = PanTiltController()
        c.set_head(0.1, 0.05)
        pan1, tilt1 = c.pan, c.tilt
        c.set_head(0.2, 0.1)
        self.assertNotEqual((c.pan, c.tilt), (pan1, tilt1))

    def test_recenter_adopts_current_aim(self):
        c = PanTiltController()
        c.set_head(PAN_RANGE_DEG / 2, TILT_RANGE_DEG / 2)   # aim off the default center
        pan_before, tilt_before = c.pan, c.tilt
        c.recenter()
        # the current aim becomes the new neutral...
        self.assertEqual((c.pan_center, c.tilt_center), (pan_before, tilt_before))
        # ...and looking straight ahead now holds that aim instead of snapping back
        c.set_head(0, 0)
        self.assertEqual((c.pan, c.tilt), (pan_before, tilt_before))


if __name__ == "__main__":
    unittest.main()
