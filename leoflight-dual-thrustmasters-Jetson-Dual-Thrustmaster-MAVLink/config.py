"""
Leoflight configuration — axis mapping, deadband, serial port, and button assignments
for the Thrustmaster T.16000M FCS joystick to ArduPilot MAVLink bridge.
"""

# ---------------------------------------------------------------------------
# Serial / MAVLink
# ---------------------------------------------------------------------------
# Set to None to auto-detect, or specify a full path.
# macOS: "/dev/cu.usbmodem14201"  Linux/Jetson: "/dev/ttyACM0"
SERIAL_PORT = None
BAUD_RATE = 115200

# MAVLink MANUAL_CONTROL send rate in Hz. ArduPilot triggers GCS failsafe
# if it stops receiving messages, so keep this >= 50.
SEND_RATE_HZ = 50

# ---------------------------------------------------------------------------
# Joystick axis mapping
# ---------------------------------------------------------------------------
# T.16000M default axis indices (verify with --diag):
#   0 = stick X (roll)
#   1 = stick Y (pitch)
#   2 = twist Z (yaw)
#   3 = throttle slider
AXIS_ROLL = 0
AXIS_PITCH = 1
AXIS_YAW = 2
AXIS_THROTTLE = 3

# Invert flags — set True if an axis reports the opposite direction.
# The T.16000M typically reports pitch/throttle inverted from what
# ArduPilot expects.
INVERT_ROLL = False
INVERT_PITCH = False
INVERT_YAW = False
INVERT_THROTTLE = True

# ---------------------------------------------------------------------------
# Deadband & expo
# ---------------------------------------------------------------------------
# Values within ±DEADBAND of center are treated as zero.
DEADBAND = 0.05

# Expo curve: output = input^EXPO_FACTOR (applied after deadband).
# 1.0 = linear, 2.0 = quadratic (softer near center), 3.0 = cubic.
# Set to 1.0 to disable.
EXPO_FACTOR = 1.5

# ---------------------------------------------------------------------------
# Button assignments
# ---------------------------------------------------------------------------
# T.16000M button indices (verify with --diag):
BUTTON_ARM_DISARM = 0   # Trigger — toggle arm/disarm
BUTTON_MODE_STABILIZE = 1
BUTTON_MODE_ALTHOLD = 2
BUTTON_MODE_LOITER = 3

# ArduPilot flight mode numbers (for MAV_CMD_DO_SET_MODE)
MODE_STABILIZE = 0
MODE_ALT_HOLD = 2
MODE_LOITER = 5

# Button-to-mode mapping
BUTTON_MODE_MAP = {
    BUTTON_MODE_STABILIZE: MODE_STABILIZE,
    BUTTON_MODE_ALTHOLD: MODE_ALT_HOLD,
    BUTTON_MODE_LOITER: MODE_LOITER,
}
