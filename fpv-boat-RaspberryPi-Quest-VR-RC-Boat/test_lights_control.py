"""Unit tests for the light controller state machine (Track I.6).

Pure-logic coverage of LightController: the running-lights on/off/toggle and the
separate reverse ("backup") light channel. Runs in CI with no GPIO — importing
lights_control never touches hardware, and LightController falls back to a no-op
when gpiozero is absent, so every method here exercises the software path.

Run: python -m unittest test_lights_control
"""

import unittest

from lights_control import LightController, FRONT_PIN, REAR_PIN, REVERSE_PIN


class TestSoftwareMode(unittest.TestCase):
    """Without gpiozero (CI) the controller no-ops but must track state and never raise."""

    def test_construct_no_hardware(self):
        lights = LightController()
        self.assertFalse(lights.hardware)   # gpiozero absent in CI
        self.assertFalse(lights.state)      # running lights start off
        self.assertFalse(lights.reverse_state)

    def test_on_off_track_state(self):
        lights = LightController()
        lights.on()
        self.assertTrue(lights.state)
        lights.off()
        self.assertFalse(lights.state)

    def test_on_off_idempotent(self):
        lights = LightController()
        lights.on()
        lights.on()
        self.assertTrue(lights.state)
        lights.off()
        lights.off()
        self.assertFalse(lights.state)


class TestToggle(unittest.TestCase):
    def test_toggle_flips_and_returns_new_state(self):
        lights = LightController()
        self.assertTrue(lights.toggle())    # off -> on
        self.assertTrue(lights.state)
        self.assertFalse(lights.toggle())   # on -> off
        self.assertFalse(lights.state)

    def test_toggle_round_trips(self):
        lights = LightController()
        for _ in range(5):
            before = lights.state
            self.assertEqual(lights.toggle(), not before)

    def test_toggle_after_explicit_on(self):
        lights = LightController()
        lights.on()
        self.assertFalse(lights.toggle())   # on -> off


class TestReverseChannel(unittest.TestCase):
    def test_reverse_tracks_state(self):
        lights = LightController()
        lights.reverse(True)
        self.assertTrue(lights.reverse_state)
        lights.reverse(False)
        self.assertFalse(lights.reverse_state)

    def test_reverse_idempotent(self):
        lights = LightController()
        lights.reverse(True)
        lights.reverse(True)
        self.assertTrue(lights.reverse_state)
        lights.reverse(False)
        lights.reverse(False)
        self.assertFalse(lights.reverse_state)

    def test_reverse_coerces_truthiness(self):
        lights = LightController()
        lights.reverse(1)
        self.assertIs(lights.reverse_state, True)
        lights.reverse(0)
        self.assertIs(lights.reverse_state, False)
        lights.reverse("on")            # non-empty string is truthy
        self.assertIs(lights.reverse_state, True)
        lights.reverse("")              # empty string is falsy
        self.assertIs(lights.reverse_state, False)


class TestChannelIndependence(unittest.TestCase):
    """The running lights and the reverse channel must not interfere."""

    def test_reverse_does_not_touch_running_lights(self):
        lights = LightController()
        lights.on()
        lights.reverse(True)
        self.assertTrue(lights.state)          # still on
        lights.reverse(False)
        self.assertTrue(lights.state)

    def test_running_lights_do_not_touch_reverse(self):
        lights = LightController()
        lights.reverse(True)
        lights.toggle()                        # off -> on
        self.assertTrue(lights.reverse_state)  # unaffected
        lights.off()
        self.assertTrue(lights.reverse_state)


class TestPinAssignments(unittest.TestCase):
    """Guard against accidental pin collisions between the three channels."""

    def test_pins_are_distinct(self):
        pins = {FRONT_PIN, REAR_PIN, REVERSE_PIN}
        self.assertEqual(len(pins), 3)

    def test_pins_avoid_motor_pins(self):
        # L298N uses GPIO 12/13 (PWM) and 5/6/20/21 (direction) per HARDWARE.md;
        # the light channels must not land on any of them.
        motor_pins = {12, 13, 5, 6, 20, 21}
        for pin in (FRONT_PIN, REAR_PIN, REVERSE_PIN):
            self.assertNotIn(pin, motor_pins)


if __name__ == "__main__":
    unittest.main()
