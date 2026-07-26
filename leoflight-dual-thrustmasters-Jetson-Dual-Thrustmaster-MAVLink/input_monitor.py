#!/usr/bin/env python3
"""
Leoflight Input Monitor + Bridge — sends joystick inputs to the FC via
MANUAL_CONTROL and visualizes the commanded drone state.

Usage:
    DISPLAY=:0 python3 input_monitor.py
    DISPLAY=:0 python3 input_monitor.py --port /dev/ttyACM0
"""

import argparse
import glob
import math
import os
import sys
import time

os.environ.setdefault("DBUS_FATAL_WARNINGS", "0")

import pygame
from pymavlink import mavutil

import config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WIN_W, WIN_H = 1024, 600
BG_COLOR = (25, 25, 30)
TEXT_COLOR = (220, 220, 220)
DIM_COLOR = (120, 120, 120)
GREEN = (0, 200, 80)
RED = (220, 50, 50)
YELLOW = (220, 200, 40)
CYAN = (60, 200, 220)
WHITE = (255, 255, 255)
STICK_BG = (55, 55, 60)
STICK_RING = (90, 90, 100)
ORANGE = (255, 140, 40)

DRONE_ARM_COLOR = (160, 160, 170)
DRONE_BODY_COLOR = (80, 80, 90)
MOTOR_OFF = (60, 60, 65)
MOTOR_CW = (60, 180, 220)
MOTOR_CCW = (220, 140, 40)

# Max tilt angle for visualization (degrees)
MAX_TILT_DEG = 45.0


def auto_detect_serial_port():
    if sys.platform == "darwin":
        patterns = ["/dev/cu.usbmodem*"]
    else:
        patterns = ["/dev/ttyACM*", "/dev/ttyUSB*"]
    for pattern in patterns:
        candidates = sorted(glob.glob(pattern))
        if candidates:
            return candidates[0]
    return None


# ---------------------------------------------------------------------------
# Control helpers
# ---------------------------------------------------------------------------

def apply_deadband(value, deadband):
    if abs(value) < deadband:
        return 0.0
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) - deadband) / (1.0 - deadband)


def apply_expo(value, factor):
    if factor == 1.0:
        return value
    return math.copysign(abs(value) ** factor, value)


def axis_to_mavlink(value, invert, low, high):
    if invert:
        value = -value
    value = apply_deadband(value, config.DEADBAND)
    value = apply_expo(value, config.EXPO_FACTOR)
    return int(value * (high - low) / 2.0 + (high + low) / 2.0)


def throttle_to_mavlink(value, invert):
    if invert:
        value = -value
    value = apply_deadband(value, config.DEADBAND)
    value = apply_expo(value, config.EXPO_FACTOR)
    return int((value + 1.0) / 2.0 * 1000.0)


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def draw_stick(surface, cx, cy, radius, x_val, y_val, label, font):
    pygame.draw.circle(surface, STICK_BG, (cx, cy), radius)
    pygame.draw.circle(surface, STICK_RING, (cx, cy), radius, 2)
    pygame.draw.line(surface, STICK_RING, (cx - radius, cy), (cx + radius, cy), 1)
    pygame.draw.line(surface, STICK_RING, (cx, cy - radius), (cx, cy + radius), 1)
    dx = int(x_val * (radius - 8))
    dy = int(-y_val * (radius - 8))
    pygame.draw.circle(surface, GREEN, (cx + dx, cy + dy), 8)
    pygame.draw.circle(surface, WHITE, (cx + dx, cy + dy), 8, 2)
    lbl = font.render(label, True, TEXT_COLOR)
    surface.blit(lbl, (cx - lbl.get_width() // 2, cy + radius + 5))


def draw_throttle_bar(surface, x, y, w, h, value, label, font):
    pygame.draw.rect(surface, STICK_BG, (x, y, w, h))
    pygame.draw.rect(surface, STICK_RING, (x, y, w, h), 2)
    fill_h = int(max(0.0, min(1.0, value)) * (h - 4))
    if fill_h > 0:
        pygame.draw.rect(surface, CYAN, (x + 2, y + h - 2 - fill_h, w - 4, fill_h))
    lbl = font.render(label, True, TEXT_COLOR)
    surface.blit(lbl, (x + w // 2 - lbl.get_width() // 2, y + h + 5))
    pct_str = "{:.0f}%".format(value * 100)
    pct_surf = font.render(pct_str, True, DIM_COLOR)
    surface.blit(pct_surf, (x + w // 2 - pct_surf.get_width() // 2, y + h + 20))


def draw_gauge_bar(surface, x, y, w, h, value, label, val_str, font, color=CYAN):
    """Horizontal gauge bar. value in [-1, 1] for centered, [0, 1] for throttle."""
    pygame.draw.rect(surface, STICK_BG, (x, y, w, h))
    pygame.draw.rect(surface, STICK_RING, (x, y, w, h), 1)

    # Label on the left
    lbl = font.render(label, True, TEXT_COLOR)
    surface.blit(lbl, (x - lbl.get_width() - 8, y + (h - lbl.get_height()) // 2))

    # Value on the right
    vs = font.render(val_str, True, DIM_COLOR)
    surface.blit(vs, (x + w + 8, y + (h - vs.get_height()) // 2))

    # Fill from center for [-1,1] or from left for [0,1]
    inner_w = w - 4
    if value < -0.01:
        # Negative: fill left from center
        cx = x + 2 + inner_w // 2
        fill_w = int(abs(value) * inner_w / 2)
        pygame.draw.rect(surface, color, (cx - fill_w, y + 2, fill_w, h - 4))
    elif value > 0.01:
        # Positive: fill right from center
        cx = x + 2 + inner_w // 2
        fill_w = int(value * inner_w / 2)
        pygame.draw.rect(surface, color, (cx, y + 2, fill_w, h - 4))

    # Center line
    cx = x + w // 2
    pygame.draw.line(surface, STICK_RING, (cx, y), (cx, y + h), 1)


# ---------------------------------------------------------------------------
# 3D Drone visualization
# ---------------------------------------------------------------------------

def rotate_point(x, y, z, roll, pitch, yaw):
    # Yaw (Z axis)
    cr, sr = math.cos(yaw), math.sin(yaw)
    x1 = x * cr - y * sr
    y1 = x * sr + y * cr
    z1 = z
    # Pitch (Y axis — nose down is positive pitch input)
    cp, sp = math.cos(pitch), math.sin(pitch)
    x2 = x1 * cp + z1 * sp
    y2 = y1
    z2 = -x1 * sp + z1 * cp
    # Roll (X axis)
    crl, srl = math.cos(roll), math.sin(roll)
    x3 = x2
    y3 = y2 * crl - z2 * srl
    z3 = y2 * srl + z2 * crl
    return x3, y3, z3


def project(x, y, z, cx, cy, scale=1.0, perspective=600.0):
    d = perspective + z
    if d < 50:
        d = 50
    factor = perspective / d * scale
    sx = cx + int(x * factor)
    sy = cy + int(y * factor)
    return sx, sy, factor


def draw_drone_3d(surface, cx, cy, roll_rad, pitch_rad, yaw_rad,
                  throttle_pct, armed, font):
    """Draw a 3D quadcopter tilted by commanded roll/pitch/yaw."""
    arm_len = 90
    body_r = 20
    scale = 1.5

    # Slight top-down viewing angle (tilt the view ~30 deg)
    view_pitch = math.radians(-30)

    # Motor positions in body frame (X config)
    motor_angles = [math.radians(45), math.radians(135),
                    math.radians(225), math.radians(315)]
    motor_cw = [True, False, True, False]

    # Build points in body frame
    motor_pts = []
    for angle in motor_angles:
        mx = arm_len * math.cos(angle)
        my = arm_len * math.sin(angle)
        motor_pts.append((mx, my, 0))

    # Front indicator
    front_pt = (arm_len * 0.6, 0, -10)

    # Apply commanded attitude
    def transform(pt):
        x, y, z = pt
        # Apply body rotation (commanded)
        x, y, z = rotate_point(x, y, z, roll_rad, pitch_rad, yaw_rad)
        # Apply view angle
        x, y, z = rotate_point(x, y, z, 0, view_pitch, 0)
        return x, y, z

    body_3d = transform((0, 0, 0))
    motor_3d = [transform(p) for p in motor_pts]
    front_3d = transform(front_pt)

    # Project
    body_proj = project(*body_3d, cx, cy, scale)
    motor_projs = [project(*m, cx, cy, scale) for m in motor_3d]
    front_proj = project(*front_3d, cx, cy, scale)

    # Sort by depth
    indices = list(range(4))
    indices.sort(key=lambda i: motor_3d[i][2], reverse=True)

    bsx, bsy, _ = body_proj

    # Draw arms
    for i in indices:
        sx, sy, sf = motor_projs[i]
        arm_width = max(2, int(5 * sf / scale))
        pygame.draw.line(surface, DRONE_ARM_COLOR, (bsx, bsy), (sx, sy), arm_width)

    # Draw body
    _, _, bsf = body_proj
    body_screen_r = max(8, int(body_r * bsf / scale))
    pygame.draw.circle(surface, DRONE_BODY_COLOR, (bsx, bsy), body_screen_r)
    pygame.draw.circle(surface, STICK_RING, (bsx, bsy), body_screen_r, 2)

    # Front indicator line
    fsx, fsy, _ = front_proj
    pygame.draw.line(surface, RED, (bsx, bsy), (fsx, fsy), 3)
    pygame.draw.circle(surface, RED, (fsx, fsy), 4)

    # Draw motors
    for i in indices:
        sx, sy, sf = motor_projs[i]
        motor_r = max(6, int(18 * sf / scale))

        base_color = MOTOR_CW if motor_cw[i] else MOTOR_CCW
        if not armed:
            base_color = MOTOR_OFF

        # Prop disc scales with throttle
        if throttle_pct > 0.01 and armed:
            disc_r = int(motor_r + throttle_pct * motor_r * 1.8)
            disc_color = (base_color[0] // 3, base_color[1] // 3, base_color[2] // 3)
            pygame.draw.circle(surface, disc_color, (sx, sy), disc_r)
            pygame.draw.circle(surface, base_color, (sx, sy), disc_r, 1)

        pygame.draw.circle(surface, base_color, (sx, sy), motor_r)
        pygame.draw.circle(surface, WHITE, (sx, sy), motor_r, 1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Leoflight Input Monitor + Bridge")
    parser.add_argument("--port", type=str, default=None)
    args = parser.parse_args()

    port = args.port or config.SERIAL_PORT or auto_detect_serial_port()
    if port is None:
        print("ERROR: No serial port found.")
        sys.exit(1)

    # --- MAVLink ---
    print("Connecting to FC on {} ...".format(port))
    mav = mavutil.mavlink_connection(port, baud=config.BAUD_RATE)
    print("Waiting for heartbeat ...")
    mav.wait_heartbeat(timeout=10)
    print("Heartbeat OK (system {}, component {})".format(
        mav.target_system, mav.target_component))

    # Disable pre-arm checks and battery failsafe
    print("Disabling pre-arm checks ...")
    mav.mav.param_set_send(
        mav.target_system, mav.target_component,
        b'ARMING_CHECK', 0, mavutil.mavlink.MAV_PARAM_TYPE_INT32)
    time.sleep(0.3)
    mav.mav.param_set_send(
        mav.target_system, mav.target_component,
        b'BATT_FS_LOW_ACT', 0, mavutil.mavlink.MAV_PARAM_TYPE_INT32)
    time.sleep(0.3)

    # Request data streams
    mav.mav.request_data_stream_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    time.sleep(0.5)

    # Set ACRO mode before arming
    print("Setting ACRO mode ...")
    mav.mav.set_mode_send(
        mav.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        1)  # ACRO = 1
    time.sleep(0.5)

    # Drain pending
    while mav.recv_match(blocking=False):
        pass

    # Force arm
    print("Sending force ARM command ...")
    mav.mav.command_long_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 21196, 0, 0, 0, 0, 0)
    time.sleep(1.0)

    # --- Pygame ---
    pygame.display.init()
    pygame.font.init()
    pygame.joystick.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Leoflight Monitor + Bridge")
    clock = pygame.time.Clock()

    js_rp = None   # Roll/Pitch joystick (stick 1)
    js_ty = None   # Throttle/Yaw joystick (stick 0) — uses its roll/pitch axes
    js_count = pygame.joystick.get_count()
    if js_count >= 2:
        js_rp = pygame.joystick.Joystick(1)
        js_rp.init()
        print("Joystick 1 (Roll/Pitch): {}".format(js_rp.get_name()))
        js_ty = pygame.joystick.Joystick(0)
        js_ty.init()
        print("Joystick 0 (Throttle/Yaw): {}".format(js_ty.get_name()))
    elif js_count == 1:
        js_rp = pygame.joystick.Joystick(0)
        js_rp.init()
        print("WARNING: Only 1 joystick found — using it for all axes")

    font_title = pygame.font.SysFont("monospace", 22, bold=True)
    font_lg = pygame.font.SysFont("monospace", 18)
    font_md = pygame.font.SysFont("monospace", 15)
    font_sm = pygame.font.SysFont("monospace", 13)

    # State
    servo_outputs = [1000] * 8
    armed = False
    flight_mode = 0
    last_servo_time = 0
    last_nav_time = 0

    # FC desired angles (from NAV_CONTROLLER_OUTPUT)
    fc_roll = 0.0       # degrees
    fc_pitch = 0.0      # degrees
    fc_yaw_rate = 0.0   # commanded yaw rate (from stick)
    fc_throttle = 0.0   # 0-100 percent (from VFR_HUD)
    viz_yaw_heading = 0.0  # accumulated yaw for visualization

    # Joystick send values
    mav_roll = mav_pitch = mav_yaw = 0
    mav_throttle = 0

    # Smoothed viz angles
    viz_roll = 0.0
    viz_pitch = 0.0
    viz_yaw = 0.0
    viz_throttle = 0.0

    arm_retry_time = time.monotonic() + 3
    tick_interval = 1.0 / config.SEND_RATE_HZ

    running = True
    try:
        while running:
            tick_start = time.monotonic()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_a:
                        cmd = 0 if armed else 1
                        mav.mav.command_long_send(
                            mav.target_system, mav.target_component,
                            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                            0, cmd, 21196, 0, 0, 0, 0, 0)

            # --- Read joysticks ---
            pygame.event.pump()
            # Joystick 0: Roll (axis 0) and Pitch (axis 1)
            if js_rp:
                mav_roll = axis_to_mavlink(
                    js_rp.get_axis(config.AXIS_ROLL), config.INVERT_ROLL, -1000, 1000)
                mav_pitch = axis_to_mavlink(
                    js_rp.get_axis(config.AXIS_PITCH), config.INVERT_PITCH, -1000, 1000)
            # Roll/Pitch joystick also handles Yaw (twist axis)
            manual_yaw = 0
            if js_rp:
                manual_yaw = axis_to_mavlink(
                    js_rp.get_axis(config.AXIS_YAW), config.INVERT_YAW, -1000, 1000)
            # Joystick 2: its stick Y→Throttle
            if js_ty:
                mav_throttle = throttle_to_mavlink(
                    js_ty.get_axis(config.AXIS_PITCH), config.INVERT_THROTTLE)
            elif js_rp:
                # Fallback: single joystick handles everything
                mav_throttle = throttle_to_mavlink(
                    js_rp.get_axis(config.AXIS_THROTTLE), config.INVERT_THROTTLE)

            # Coordinated turn: mix roll into yaw
            # When banked, add proportional yaw to keep the turn coordinated
            COORD_TURN_FACTOR = 0.5  # 0.0 = no mixing, 1.0 = full roll→yaw
            coord_yaw = int(mav_roll * COORD_TURN_FACTOR)
            mav_yaw = max(-1000, min(1000, manual_yaw + coord_yaw))

            # --- Send MANUAL_CONTROL ---
            mav.mav.manual_control_send(
                mav.target_system,
                mav_pitch, mav_roll, mav_throttle, mav_yaw, 0)

            # Re-arm if needed
            if not armed and time.monotonic() > arm_retry_time:
                mav.mav.command_long_send(
                    mav.target_system, mav.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0, 1, 21196, 0, 0, 0, 0, 0)
                arm_retry_time = time.monotonic() + 5

            # --- Read MAVLink ---
            while True:
                msg = mav.recv_match(blocking=False)
                if msg is None:
                    break
                mtype = msg.get_type()
                if mtype == "SERVO_OUTPUT_RAW":
                    servo_outputs = [
                        msg.servo1_raw, msg.servo2_raw, msg.servo3_raw, msg.servo4_raw,
                        msg.servo5_raw, msg.servo6_raw, msg.servo7_raw, msg.servo8_raw,
                    ]
                    last_servo_time = time.monotonic()
                elif mtype == "NAV_CONTROLLER_OUTPUT":
                    fc_roll = msg.nav_roll    # desired roll in degrees
                    fc_pitch = msg.nav_pitch  # desired pitch in degrees
                    last_nav_time = time.monotonic()
                elif mtype == "VFR_HUD":
                    fc_throttle = msg.throttle  # 0-100 percent
                elif mtype == "HEARTBEAT" and msg.get_srcSystem() == mav.target_system:
                    armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                    flight_mode = msg.custom_mode

            # --- Smooth the visualization ---
            target_roll = math.radians(fc_roll)
            target_pitch = math.radians(-fc_pitch)  # invert pitch for viz
            target_thr = fc_throttle / 100.0

            # Yaw: accumulate commanded yaw rate into heading
            # mav_yaw is -1000 to 1000, map to deg/s (±180 deg/s max)
            yaw_rate_dps = (mav_yaw / 1000.0) * 180.0
            viz_yaw_heading += yaw_rate_dps * tick_interval
            target_yaw = math.radians(viz_yaw_heading)

            # Exponential smoothing
            alpha = 0.3
            viz_roll += alpha * (target_roll - viz_roll)
            viz_pitch += alpha * (target_pitch - viz_pitch)
            viz_yaw += alpha * (target_yaw - viz_yaw)
            viz_throttle += alpha * (target_thr - viz_throttle)

            # ===================== DRAW =====================
            screen.fill(BG_COLOR)

            # ---- Header ----
            title = font_title.render("LEOFLIGHT", True, WHITE)
            screen.blit(title, (15, 8))

            status_text = "ARMED" if armed else "DISARMED"
            status_color = RED if armed else GREEN
            status_surf = font_lg.render(status_text, True, status_color)
            screen.blit(status_surf, (WIN_W - status_surf.get_width() - 15, 8))

            MODE_NAMES = {0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO",
                          5: "LOITER", 6: "RTL", 9: "LAND", 16: "POSHOLD"}
            mode_name = MODE_NAMES.get(flight_mode, "MODE {}".format(flight_mode))
            mode_surf = font_sm.render(mode_name, True, YELLOW)
            screen.blit(mode_surf, (WIN_W - mode_surf.get_width() - 15, 30))

            # Connection indicator
            if last_servo_time > 0:
                s_age = time.monotonic() - last_servo_time
                s_color = GREEN if s_age < 0.5 else YELLOW if s_age < 2.0 else RED
            else:
                s_color = RED
            pygame.draw.circle(screen, s_color, (WIN_W - 8, 52), 5)

            hint_surf = font_sm.render("[A] arm/disarm   [ESC] quit", True, DIM_COLOR)
            screen.blit(hint_surf, (15, WIN_H - 18))

            # ---- Left: Joystick input ----
            panel_y = 55
            lbl = font_lg.render("Stick 1: R/P", True, TEXT_COLOR)
            screen.blit(lbl, (15, panel_y))
            if js_ty:
                lbl2 = font_sm.render("Stick 2: Y/T", True, DIM_COLOR)
                screen.blit(lbl2, (15, panel_y + 20))

            draw_stick(screen, 80, panel_y + 110, 60, mav_roll / 1000.0,
                       mav_pitch / 1000.0, "Roll/Pitch", font_sm)
            draw_stick(screen, 215, panel_y + 110, 60, mav_yaw / 1000.0,
                       0.0, "Yaw", font_sm)
            draw_throttle_bar(screen, 295, panel_y + 50, 28, 120,
                              mav_throttle / 1000.0, "Thr", font_sm)

            # ---- Center: 3D Drone ----
            drone_cx = WIN_W // 2
            drone_cy = panel_y + 160

            # Panel background
            panel_rect = (drone_cx - 170, panel_y, 340, 340)
            pygame.draw.rect(screen, (32, 32, 38), panel_rect, border_radius=8)
            pygame.draw.rect(screen, STICK_RING, panel_rect, 1, border_radius=8)

            viz_title = font_lg.render("FC Commanded", True, TEXT_COLOR)
            screen.blit(viz_title, (drone_cx - viz_title.get_width() // 2, panel_y + 6))

            draw_drone_3d(screen, drone_cx, drone_cy,
                          viz_roll, viz_pitch, viz_yaw,
                          viz_throttle, armed, font_sm)

            # Commanded values text under drone
            cmd_y = drone_cy + 145
            cmd_str = "R:{:+5.1f}  P:{:+5.1f}  Y:{:+5.1f}  T:{:.0f}%".format(
                math.degrees(viz_roll), math.degrees(viz_pitch),
                math.degrees(viz_yaw), viz_throttle * 100)
            cmd_surf = font_md.render(cmd_str, True, CYAN)
            screen.blit(cmd_surf, (drone_cx - cmd_surf.get_width() // 2, cmd_y))

            # ---- Right: FC Output gauges ----
            gauge_x = drone_cx + 190
            gauge_w = 180
            gauge_h = 18

            fc_lbl = font_lg.render("FC Output", True, TEXT_COLOR)
            screen.blit(fc_lbl, (gauge_x, panel_y))

            gy = panel_y + 35
            draw_gauge_bar(screen, gauge_x + 45, gy, gauge_w, gauge_h,
                           fc_roll / MAX_TILT_DEG, "Roll",
                           "{:+.1f}".format(fc_roll), font_md, CYAN)
            gy += 45
            draw_gauge_bar(screen, gauge_x + 45, gy, gauge_w, gauge_h,
                           fc_pitch / MAX_TILT_DEG, "Pitch",
                           "{:+.1f}".format(fc_pitch), font_md, GREEN)
            gy += 45
            draw_gauge_bar(screen, gauge_x + 45, gy, gauge_w, gauge_h,
                           mav_yaw / 1000.0, "Yaw",
                           "{:+.0f}/s".format(yaw_rate_dps), font_md, ORANGE)
            gy += 45
            # Throttle as a left-to-right bar
            thr_norm = fc_throttle / 100.0
            thr_x = gauge_x + 45
            thr_lbl = font_md.render("Thr", True, TEXT_COLOR)
            screen.blit(thr_lbl, (thr_x - thr_lbl.get_width() - 8,
                                  gy + (gauge_h - thr_lbl.get_height()) // 2))
            pygame.draw.rect(screen, STICK_BG, (thr_x, gy, gauge_w, gauge_h))
            pygame.draw.rect(screen, STICK_RING, (thr_x, gy, gauge_w, gauge_h), 1)
            fill_w = int(thr_norm * (gauge_w - 4))
            if fill_w > 0:
                pygame.draw.rect(screen, YELLOW, (thr_x + 2, gy + 2, fill_w, gauge_h - 4))
            thr_vs = font_md.render("{:.0f}%".format(thr_norm * 100), True, DIM_COLOR)
            screen.blit(thr_vs, (thr_x + gauge_w + 8,
                                 gy + (gauge_h - thr_vs.get_height()) // 2))

            # Servo raw values
            gy += 55
            srv_lbl = font_md.render("Servos", True, TEXT_COLOR)
            screen.blit(srv_lbl, (gauge_x, gy))
            gy += 22
            for i in range(4):
                val = servo_outputs[i]
                s_str = "M{}: {:4d}".format(i + 1, val)
                s_surf = font_sm.render(s_str, True, DIM_COLOR)
                screen.blit(s_surf, (gauge_x + (i % 2) * 100, gy + (i // 2) * 18))

            pygame.display.flip()

            elapsed = time.monotonic() - tick_start
            sleep_time = tick_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass

    # Safety: disarm on exit
    print("\nDisarming ...")
    mav.mav.manual_control_send(mav.target_system, 0, 0, 0, 0, 0)
    mav.mav.command_long_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 0, 0, 0, 0, 0, 0, 0)
    time.sleep(0.1)
    pygame.quit()
    print("Done.")


if __name__ == "__main__":
    main()
