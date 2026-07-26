#!/usr/bin/env python3
"""
Leoflight — Thrustmaster T.16000M FCS → ARK FPV (ArduPilot) MAVLink bridge.

Reads joystick input via pygame, maps it to MAVLink MANUAL_CONTROL messages,
and sends them over USB serial to an ArduPilot flight controller.

Usage:
    python3 leoflight.py              # Normal operation (connects to FC)
    python3 leoflight.py --diag       # Diagnostic mode (joystick only, no FC)
    python3 leoflight.py --port /dev/ttyACM0   # Specify serial port
"""

import argparse
import glob
import math
import os
import sys
import time

# Allow headless operation (no display) — must be set before pygame import
if not os.environ.get("DISPLAY") and sys.platform == "linux":
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
from pymavlink import mavutil

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def auto_detect_serial_port():
    """Find the first serial device for the flight controller."""
    if sys.platform == "darwin":
        patterns = ["/dev/cu.usbmodem*"]
    else:
        patterns = ["/dev/ttyACM*", "/dev/ttyUSB*"]
    for pattern in patterns:
        candidates = sorted(glob.glob(pattern))
        if candidates:
            return candidates[0]
    return None


def apply_deadband(value, deadband):
    """Zero out values within the deadband, rescale the rest to full range."""
    if abs(value) < deadband:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) - deadband) / (1.0 - deadband)


def apply_expo(value, factor):
    """Apply exponential curve: preserves sign, softens response near center."""
    if factor == 1.0:
        return value
    return math.copysign(abs(value) ** factor, value)


def axis_to_mavlink(value, invert, low, high):
    """Scale a [-1, 1] axis value to a MAVLink integer range [low, high]."""
    if invert:
        value = -value
    value = apply_deadband(value, config.DEADBAND)
    value = apply_expo(value, config.EXPO_FACTOR)
    return int(value * (high - low) / 2.0 + (high + low) / 2.0)


def throttle_to_mavlink(value, invert):
    """Scale a [-1, 1] throttle axis to MAVLink [0, 1000].

    The T.16000M throttle slider typically reports -1 at full forward and
    +1 at full back, so inversion is usually needed.
    """
    if invert:
        value = -value
    value = apply_deadband(value, config.DEADBAND)
    value = apply_expo(value, config.EXPO_FACTOR)
    # Map from [-1, 1] to [0, 1000]
    return int((value + 1.0) / 2.0 * 1000.0)


# ---------------------------------------------------------------------------
# Diagnostic mode
# ---------------------------------------------------------------------------

def run_diagnostic(joystick):
    """Print live joystick values without connecting to the FC."""
    print("\n--- DIAGNOSTIC MODE (Ctrl+C to quit) ---\n")
    print(f"Joystick: {joystick.get_name()}")
    print(f"  Axes:    {joystick.get_numaxes()}")
    print(f"  Buttons: {joystick.get_numbuttons()}")
    print(f"  Hats:    {joystick.get_numhats()}")
    print()

    try:
        while True:
            pygame.event.pump()

            axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]
            buttons = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
            hats = [joystick.get_hat(i) for i in range(joystick.get_numhats())]

            # Build display line
            axis_str = "  ".join(f"A{i}:{v:+.3f}" for i, v in enumerate(axes))
            btn_str = "".join(str(b) for b in buttons)
            hat_str = "  ".join(f"H{i}:{h}" for i, h in enumerate(hats))

            # Show mapped MAVLink values too
            roll = axis_to_mavlink(
                joystick.get_axis(config.AXIS_ROLL), config.INVERT_ROLL, -1000, 1000
            )
            pitch = axis_to_mavlink(
                joystick.get_axis(config.AXIS_PITCH), config.INVERT_PITCH, -1000, 1000
            )
            yaw = axis_to_mavlink(
                joystick.get_axis(config.AXIS_YAW), config.INVERT_YAW, -1000, 1000
            )
            throttle = throttle_to_mavlink(
                joystick.get_axis(config.AXIS_THROTTLE), config.INVERT_THROTTLE
            )

            mapped_str = f"R:{roll:+5d}  P:{pitch:+5d}  Y:{yaw:+5d}  T:{throttle:4d}"

            print(
                f"\r{axis_str}  | Btn:{btn_str}  {hat_str}  | MAV  {mapped_str}",
                end="",
                flush=True,
            )
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\n\nDiagnostic mode ended.")


# ---------------------------------------------------------------------------
# Main bridge
# ---------------------------------------------------------------------------

def run_bridge(joystick, port):
    """Main loop: read joystick → send MANUAL_CONTROL to FC."""
    # --- MAVLink connection ---
    print(f"\nConnecting to flight controller on {port} @ {config.BAUD_RATE} …")
    mav = mavutil.mavlink_connection(port, baud=config.BAUD_RATE)

    print("Waiting for heartbeat …")
    mav.wait_heartbeat(timeout=10)
    print(
        f"Heartbeat received  (system {mav.target_system}, "
        f"component {mav.target_component})"
    )

    armed = False
    arm_button_prev = False   # for edge-detect debounce
    mode_buttons_prev = {b: False for b in config.BUTTON_MODE_MAP}

    tick_interval = 1.0 / config.SEND_RATE_HZ

    print("\n--- BRIDGE ACTIVE (Ctrl+C to quit) ---\n")

    try:
        while True:
            tick_start = time.monotonic()
            pygame.event.pump()

            # ---- Read & map axes ----
            roll = axis_to_mavlink(
                joystick.get_axis(config.AXIS_ROLL), config.INVERT_ROLL, -1000, 1000
            )
            pitch = axis_to_mavlink(
                joystick.get_axis(config.AXIS_PITCH), config.INVERT_PITCH, -1000, 1000
            )
            yaw = axis_to_mavlink(
                joystick.get_axis(config.AXIS_YAW), config.INVERT_YAW, -1000, 1000
            )
            throttle = throttle_to_mavlink(
                joystick.get_axis(config.AXIS_THROTTLE), config.INVERT_THROTTLE
            )

            # ---- Arm / disarm toggle (trigger) ----
            arm_button_now = bool(joystick.get_button(config.BUTTON_ARM_DISARM))
            if arm_button_now and not arm_button_prev:
                # Rising edge — toggle
                if armed:
                    print("\n>> DISARM command sent")
                    mav.mav.command_long_send(
                        mav.target_system,
                        mav.target_component,
                        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                        0,       # confirmation
                        0,       # param1: 0 = disarm
                        0, 0, 0, 0, 0, 0,
                    )
                    armed = False
                else:
                    print("\n>> ARM command sent")
                    mav.mav.command_long_send(
                        mav.target_system,
                        mav.target_component,
                        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                        0,       # confirmation
                        1,       # param1: 1 = arm
                        0, 0, 0, 0, 0, 0,
                    )
                    armed = True
            arm_button_prev = arm_button_now

            # ---- Flight mode buttons ----
            for btn_idx, mode_num in config.BUTTON_MODE_MAP.items():
                btn_now = bool(joystick.get_button(btn_idx))
                if btn_now and not mode_buttons_prev[btn_idx]:
                    print(f"\n>> Set flight mode {mode_num}")
                    mav.mav.command_long_send(
                        mav.target_system,
                        mav.target_component,
                        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                        0,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        mode_num,
                        0, 0, 0, 0, 0,
                    )
                mode_buttons_prev[btn_idx] = btn_now

            # ---- Send MANUAL_CONTROL ----
            mav.mav.manual_control_send(
                mav.target_system,
                pitch,      # x = pitch
                roll,       # y = roll
                throttle,   # z = throttle
                yaw,        # r = yaw
                0,          # buttons bitmask (unused)
            )

            # ---- Check for incoming messages (update armed state from FC) ----
            msg = mav.recv_match(type="HEARTBEAT", blocking=False)
            if msg and msg.get_srcSystem() == mav.target_system:
                armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

            # ---- Telemetry display ----
            status = "ARMED" if armed else "DISARMED"
            print(
                f"\r[{status:>8s}]  R:{roll:+5d}  P:{pitch:+5d}  "
                f"T:{throttle:4d}  Y:{yaw:+5d}",
                end="",
                flush=True,
            )

            # ---- Pace the loop ----
            elapsed = time.monotonic() - tick_start
            sleep_time = tick_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\nShutting down — sending disarm + throttle zero …")
        # Safety: disarm and zero throttle
        mav.mav.manual_control_send(mav.target_system, 0, 0, 0, 0, 0)
        mav.mav.command_long_send(
            mav.target_system,
            mav.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,   # disarm
            0, 0, 0, 0, 0, 0,
        )
        time.sleep(0.1)
        print("Disarmed. Goodbye.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Leoflight — joystick-to-ArduPilot MAVLink bridge"
    )
    parser.add_argument(
        "--diag",
        action="store_true",
        help="Diagnostic mode: print joystick values without connecting to the FC",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help="Serial port for the flight controller (e.g. /dev/cu.usbmodem14201)",
    )
    args = parser.parse_args()

    # --- Init pygame & joystick ---
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("ERROR: No joystick detected. Is the T.16000M plugged in?")
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Joystick found: {joystick.get_name()}")
    print(f"  Axes: {joystick.get_numaxes()}  Buttons: {joystick.get_numbuttons()}")

    if args.diag:
        run_diagnostic(joystick)
        return

    # --- Determine serial port ---
    port = args.port or config.SERIAL_PORT or auto_detect_serial_port()
    if port is None:
        print(
            "ERROR: No serial port specified and auto-detect found nothing.\n"
            "       Plug in the FC via USB-C, then retry, or use --port."
        )
        sys.exit(1)

    run_bridge(joystick, port)


if __name__ == "__main__":
    main()
