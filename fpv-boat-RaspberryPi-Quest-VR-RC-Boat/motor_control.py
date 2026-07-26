"""Differential-thrust motor control for the FPV boat (L298N dual H-bridge).

Steering is differential (no rudder / no steering servo):

    left_motor  = throttle + steer
    right_motor = throttle - steer      # each clamped to -1.0 .. 1.0

A negative value drives that motor in reverse (the L298N is a full H-bridge), so
the viewer's "reverse" toggle just sends a negative throttle -- there is no
special reverse case to handle here.

This module is deliberately decoupled from the web server so it can be
bench-tested on its own (see the __main__ block, or import MotorController from a
REPL). If gpiozero / a usable pin factory isn't available it runs in a no-op
software mode, so importing it never breaks the server on a dev machine.

For smooth, jitter-free PWM run with the pigpio pin factory:

    sudo pigpiod
    GPIOZERO_PIN_FACTORY=pigpio python3 webrtc_stream.py
"""

import threading

# L298N control pins (BCM numbering). ENA/ENB are the PWM speed pins -- put them
# on the Pi's hardware-PWM channels (GPIO12/GPIO13) for smooth speed control.
# IN1..IN4 set each motor's direction. See HARDWARE.md for the full wiring table.
LEFT_EN, LEFT_IN1, LEFT_IN2 = 12, 5, 6        # physical pins 32, 29, 31
RIGHT_EN, RIGHT_IN1, RIGHT_IN2 = 13, 20, 21   # physical pins 33, 38, 40

WATCHDOG_S = 0.5   # cut motors if no fresh command arrives within this window


def _clamp(v, lo=-1.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def differential_mix(throttle, steer):
    """Differential-thrust mix: (left, right) each clamped to [-1, 1].

    left = throttle + steer, right = throttle - steer. Pure function so it can
    be unit-tested without any GPIO (see test_motor_control.py).
    """
    return _clamp(throttle + steer), _clamp(throttle - steer)


class MotorController:
    """Differential-thrust driver: set_drive(throttle, steer) -> two L298N channels.

    A background watchdog zeroes both motors if set_drive() isn't called within
    WATCHDOG_S seconds, so a dropped control link (or a stalled client) can't
    leave the boat running away -- there is no radio fallback when the Pi drives.
    """

    def __init__(self, watchdog_s=WATCHDOG_S):
        self._watchdog_s = watchdog_s
        self._timer = None
        self._lock = threading.Lock()
        # armed = a set_drive arrived within the watchdog window (control link
        # live). Goes False when the watchdog trips or we stop() -> FAILSAFE.
        self.armed = False
        try:
            from gpiozero import Motor
            self._left = Motor(forward=LEFT_IN1, backward=LEFT_IN2, enable=LEFT_EN, pwm=True)
            self._right = Motor(forward=RIGHT_IN1, backward=RIGHT_IN2, enable=RIGHT_EN, pwm=True)
            self.hardware = True
        except Exception as e:
            self._left = self._right = None
            self.hardware = False
            print(f"[motor] hardware disabled ({e}); running in software-only mode")

    def set_drive(self, throttle, steer):
        """Apply differential thrust from a throttle/steer pair (-1..1 each)."""
        left, right = differential_mix(throttle, steer)
        with self._lock:
            self._apply(left, right)
            self._kick_watchdog()
            self.armed = True

    def stop(self):
        """Immediately zero both motors and disarm the watchdog."""
        with self._lock:
            self._cancel_watchdog()
            self._apply(0.0, 0.0)
            self.armed = False

    # ---- internals ----
    def _apply(self, left, right):
        if not self.hardware:
            return
        try:
            self._left.value = _clamp(left)
            self._right.value = _clamp(right)
        except Exception:
            pass

    def _kick_watchdog(self):
        self._cancel_watchdog()
        self._timer = threading.Timer(self._watchdog_s, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_watchdog(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _on_timeout(self):
        with self._lock:
            self._apply(0.0, 0.0)
            self._timer = None
            self.armed = False   # watchdog tripped -> FAILSAFE


if __name__ == "__main__":
    # Bench test: run this with the motors OFF the boat. Confirms direction,
    # speed response, and that both channels are independent. Feeds set_drive at
    # ~20 Hz (the real control rate) so the watchdog stays satisfied.
    import time

    m = MotorController()
    print("hardware:", m.hardware)

    def hold(throttle, steer, secs, label):
        print(f"{label}: throttle={throttle} steer={steer}")
        for _ in range(int(secs * 20)):
            m.set_drive(throttle, steer)
            time.sleep(0.05)

    try:
        hold(0.3, 0.0, 1.5, "both ahead slow")
        hold(0.6, 0.0, 1.5, "both ahead faster")
        hold(0.0, 0.6, 1.5, "spin right (left ahead, right astern)")
        hold(0.0, -0.6, 1.5, "spin left")
        hold(-0.4, 0.0, 1.5, "both astern")
    finally:
        m.stop()
        print("stopped")
