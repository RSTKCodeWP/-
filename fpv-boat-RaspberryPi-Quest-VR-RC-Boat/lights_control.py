"""Front/rear running lights, switched via GPIO through an NPN transistor per group.

Two LED groups (per the ShareGoo 8-LED kit): 4 white front, 4 red rear, each
group wired through its own transistor so the Pi's GPIO pins (which can't
safely source the LEDs' combined current directly) just switch the transistor's
base on/off. See HARDWARE.md for the wiring table.

    GPIO pin --[1k resistor]--> transistor base
    transistor collector <----- LED group negative
    transistor emitter --------> GND (shared with Pi / buck converter)
    LED group positive ---------> 5V rail (buck converter output)

Currently wired to auto-trigger with recording (see webrtc_stream.py) rather
than a controller button -- lights on when record_start fires, off on
record_stop. Both groups switch together.

Same self-contained, no-op-if-missing pattern as motor_control.py: importing
this never breaks the server if gpiozero or the hardware isn't present.
"""

FRONT_PIN = 17    # 4x white LEDs, physical pin 11
REAR_PIN = 27     # 4x red LEDs, physical pin 13
REVERSE_PIN = 22  # reverse ("backup") lights, physical pin 15 -- future install,
                  # come on automatically while the boat is in reverse


class LightController:
    """Running lights (front+rear together) plus a separate reverse-light channel.

    - on() / off() / toggle(): the main running lights (both groups together),
      driven manually (single-tap Y) or auto-on with recording.
    - reverse(on): the rear backup lights, switched by the server whenever the
      boat enters/leaves reverse. The LEDs aren't installed yet, but the pin is
      claimed here so wiring is drop-in; it stays a no-op without gpiozero.
    """

    def __init__(self):
        try:
            from gpiozero import OutputDevice
            self._front = OutputDevice(FRONT_PIN)
            self._rear = OutputDevice(REAR_PIN)
            self._reverse = OutputDevice(REVERSE_PIN)
            self.hardware = True
        except Exception as e:
            self._front = self._rear = self._reverse = None
            self.hardware = False
            print(f"[lights] hardware disabled ({e}); running in software-only mode")
        self.state = False
        self.reverse_state = False

    def on(self):
        self.state = True
        if not self.hardware:
            return
        try:
            self._front.on()
            self._rear.on()
        except Exception:
            pass

    def off(self):
        self.state = False
        if not self.hardware:
            return
        try:
            self._front.off()
            self._rear.off()
        except Exception:
            pass

    def toggle(self):
        """Flip the running lights; returns the new state."""
        self.off() if self.state else self.on()
        return self.state

    def reverse(self, on):
        """Switch the rear backup lights (idempotent; only acts on a change)."""
        on = bool(on)
        if on == self.reverse_state:
            return
        self.reverse_state = on
        if not self.hardware:
            return
        try:
            self._reverse.on() if on else self._reverse.off()
        except Exception:
            pass


if __name__ == "__main__":
    # Bench test: blinks both groups a few times so you can confirm wiring
    # before wiring this into the server's record start/stop.
    import time

    lights = LightController()
    print("hardware:", lights.hardware)

    for i in range(3):
        print(f"  running on  ({i + 1}/3)")
        lights.on()
        time.sleep(1)
        print(f"  running off ({i + 1}/3)")
        lights.off()
        time.sleep(1)

    print("  reverse lights on")
    lights.reverse(True)
    time.sleep(1)
    print("  reverse lights off")
    lights.reverse(False)

    print("Done.")
