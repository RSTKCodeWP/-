"""
PS5 DualSense -> Arduino ESP-NOW Drone Controller + Telemetry GUI
=================================================================
Full GCS (Ground Control Station) with:
  - Live telemetry parsing from Arduino serial output
  - PS5 gamepad input -> serial command bridge
  - Dark avionics-style GUI dashboard

REQUIREMENTS:
  pip install pygame pyserial

USAGE:
  python ps5_drone_controller.py --port COM3              # Windows
  python ps5_drone_controller.py --port /dev/ttyUSB0      # Linux
  python ps5_drone_controller.py --list-ports
  python ps5_drone_controller.py --list-axes

CONTROL MAPPING:
  Left Stick  Y  -> Throttle (w/s)
  Left Stick  X  -> Yaw      (a/d)
  Right Stick X  -> Roll     (j/l)
  Right Stick Y  -> Pitch    (i/k)
  Cross [X]      -> Arm      (t)
  Square [sq]    -> Disarm   (g)
  Circle [O]     -> Reset RPY(r)
  Triangle [tri] -> GPIO     (x)
  PS Button      -> Emergency stop
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
import threading
import time
import re
import sys
import argparse
import queue
import math

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("[WARN] pyserial not installed. Running in demo mode.")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[WARN] pygame not installed. Gamepad disabled.")

# ──────────────────────────────────────────────────────────────────────────────
# TUNING
# ──────────────────────────────────────────────────────────────────────────────
DEADZONE           = 0.1
MAX_STEPS_PER_TICK = 1
LOOP_HZ            = 15
LOOP_PERIOD        = 1.0 / LOOP_HZ
AXIS_LX, AXIS_LY   = 0, 1
AXIS_RX, AXIS_RY   = 2, 3
BTN_CROSS, BTN_CIRCLE, BTN_SQUARE, BTN_TRIANGLE, BTN_PS = 0, 1, 2, 3, 10

# ──────────────────────────────────────────────────────────────────────────────
# THEME — Dark Avionics
# ──────────────────────────────────────────────────────────────────────────────
T = {
    "bg":         "#0a0d12",
    "panel":      "#0f1520",
    "border":     "#1a2540",
    "border2":    "#243050",
    "cyan":       "#00d4ff",
    "cyan_dim":   "#006080",
    "green":      "#00ff88",
    "green_dim":  "#005530",
    "yellow":     "#ffd060",
    "red":        "#ff4060",
    "orange":     "#ff8c42",
    "white":      "#e8f0ff",
    "muted":      "#4a5570",
    "text":       "#b0bcd4",
    "label":      "#5a6a8a",
}

# ──────────────────────────────────────────────────────────────────────────────
# TELEMETRY PARSER
# ──────────────────────────────────────────────────────────────────────────────
class Telemetry:
    def __init__(self):
        self.battery_v  = 0.0
        self.battery_a  = 0.0
        self.battery_pct= 0
        self.roll       = 0.0
        self.pitch      = 0.0
        self.yaw        = 0.0
        self.gps_sats   = 0
        self.gps_fix    = "No Fix"
        self.altitude   = 0.0
        self.speed      = 0.0
        self.mode       = 0
        self.armed      = False
        self.rssi       = 0
        self.last_update= 0.0
        self.connected  = False

    def parse_line(self, line: str):
        line = line.strip()
        # Strip emoji and unicode noise for regex reliability
        clean = line.encode("ascii", "ignore").decode("ascii").strip()

        # Battery: 14.18V | 0.25A | 10%
        m = re.search(r'Battery.*?([\d.]+)V.*?([\d.]+)A.*?(\d+)%', line)
        if m:
            self.battery_v   = float(m.group(1))
            self.battery_a   = float(m.group(2))
            self.battery_pct = int(m.group(3))
            self.last_update = time.time()
            return

        # Attitude: Roll=1.3° Pitch=1.5° Yaw=1.4°
        m = re.search(r'Roll\s*=\s*([-\d.]+).*?Pitch\s*=\s*([-\d.]+).*?Yaw\s*=\s*([-\d.]+)', line)
        if m:
            self.roll  = float(m.group(1))
            self.pitch = float(m.group(2))
            self.yaw   = float(m.group(3))
            return

        # GPS: 0 sats | Fix: No Fix
        m = re.search(r'GPS.*?(\d+)\s*sat.*?Fix:\s*(.+)', line)
        if m:
            self.gps_sats = int(m.group(1))
            self.gps_fix  = m.group(2).strip()
            return

        # Alt: 0.0m | Speed: 0.0m/s
        m = re.search(r'Alt:\s*([-\d.]+)m.*?Speed:\s*([\d.]+)', line)
        if m:
            self.altitude = float(m.group(1))
            self.speed    = float(m.group(2))
            return

        # Mode: 0 | Armed: YES/NO | RSSI: 0
        m = re.search(r'Mode:\s*(\d+).*?Armed:.*?(YES|NO).*?RSSI:\s*(-?\d+)', line)
        if m:
            self.mode   = int(m.group(1))
            self.armed  = m.group(2) == "YES"
            self.rssi   = int(m.group(3))
            return

    def age(self) -> float:
        if self.last_update == 0:
            return 999.0
        return time.time() - self.last_update

# ──────────────────────────────────────────────────────────────────────────────
# SERIAL WORKER
# ──────────────────────────────────────────────────────────────────────────────
class SerialWorker(threading.Thread):
    def __init__(self, port, baud, telemetry: Telemetry, cmd_queue: queue.Queue):
        super().__init__(daemon=True)
        self.port      = port
        self.baud      = baud
        self.telem     = telemetry
        self.cmd_queue = cmd_queue
        self.running   = True
        self.ser       = None
        self.status    = "Connecting..."

    def run(self):
        if not SERIAL_AVAILABLE:
            self.status = "pyserial missing"
            return
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.status = "Connected"
            self.telem.connected = True
        except Exception as e:
            self.status = f"Error: {e}"
            return

        buf = ""
        while self.running:
            # Write pending commands
            while not self.cmd_queue.empty():
                try:
                    cmd = self.cmd_queue.get_nowait()
                    self.ser.write(cmd.encode())
                    time.sleep(0.002)
                except Exception:
                    pass

            # Read telemetry lines
            try:
                raw = self.ser.read(256)
                if raw:
                    buf += raw.decode("utf-8", errors="ignore")
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        self.telem.parse_line(line)
            except Exception as e:
                self.status = f"Read error: {e}"
                break

            time.sleep(0.005)

        if self.ser and self.ser.is_open:
            self.ser.close()
        self.telem.connected = False
        self.status = "Disconnected"

    def stop(self):
        self.running = False

# ──────────────────────────────────────────────────────────────────────────────
# GAMEPAD WORKER
# ──────────────────────────────────────────────────────────────────────────────
class GamepadWorker(threading.Thread):
    def __init__(self, cmd_queue: queue.Queue, state_cb):
        super().__init__(daemon=True)
        self.cmd_queue = cmd_queue
        self.state_cb  = state_cb   # callback(throttle, roll, pitch, yaw, armed)
        self.running   = True
        self.status    = "No gamepad"
        self.js        = None
        # Local shadow of control state for display
        self.throttle  = 172
        self.roll      = 992
        self.pitch     = 992
        self.yaw       = 992
        self.armed     = False

    def _deadzone(self, v):
        if abs(v) < DEADZONE:
            return 0.0
        s = 1 if v > 0 else -1
        return s * (abs(v) - DEADZONE) / (1.0 - DEADZONE)

    def _steps(self, axis_val):
        return round(self._deadzone(axis_val) * MAX_STEPS_PER_TICK)

    def _clamp(self, v):
        return max(172, min(1811, v))

    def run(self):
        if not PYGAME_AVAILABLE:
            self.status = "pygame missing"
            return
        pygame.init()
        pygame.joystick.init()

        # Find controller
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            name = js.get_name().lower()
            if any(k in name for k in ["dualsense","playstation","wireless controller","ps5"]):
                self.js = js
                break
        if not self.js and pygame.joystick.get_count() > 0:
            self.js = pygame.joystick.Joystick(0)

        if not self.js:
            self.status = "No gamepad"
            return

        self.js.init()
        self.status = f"OK: {self.js.get_name()[:24]}"
        n_axes = self.js.get_numaxes()
        n_btns = self.js.get_numbuttons()
        prev_btns = [False] * n_btns

        while self.running:
            t0 = time.time()
            pygame.event.pump()
            cmds = []
            cur_btns = [self.js.get_button(i) for i in range(n_btns)]

            def pressed(idx):
                return idx < n_btns and cur_btns[idx] and not prev_btns[idx]

            if pressed(BTN_CROSS):
                cmds.append('t'); self.armed = True
            if pressed(BTN_SQUARE):
                cmds.append('g'); self.armed = False
            if pressed(BTN_CIRCLE):
                cmds.append('r')
                self.roll = self.pitch = self.yaw = 992
            if pressed(BTN_TRIANGLE):
                cmds.append('x')
            if BTN_PS < n_btns and pressed(BTN_PS):
                for _ in range(20): cmds.append('s')
                cmds.append('g')
                self.armed = False; self.throttle = 172

            prev_btns = cur_btns

            # Throttle (LY inverted)
            if n_axes > AXIS_LY:
                steps = -self._steps(self.js.get_axis(AXIS_LY))
                for _ in range(abs(steps)):
                    c = 'w' if steps > 0 else 's'
                    cmds.append(c)
                    self.throttle = self._clamp(self.throttle + (50 if steps > 0 else -50))

            # Yaw (LX)
            if n_axes > AXIS_LX:
                steps = self._steps(self.js.get_axis(AXIS_LX))
                for _ in range(abs(steps)):
                    c = 'd' if steps > 0 else 'a'
                    cmds.append(c)
                    self.yaw = self._clamp(self.yaw + (50 if steps > 0 else -50))

            # Roll (RX)
            rx = AXIS_RX if AXIS_RX < n_axes else min(2, n_axes-1)
            if rx < n_axes:
                steps = self._steps(self.js.get_axis(rx))
                for _ in range(abs(steps)):
                    c = 'l' if steps > 0 else 'j'
                    cmds.append(c)
                    self.roll = self._clamp(self.roll + (50 if steps > 0 else -50))

            # Pitch (RY inverted)
            ry = AXIS_RY if AXIS_RY < n_axes else min(3, n_axes-1)
            if ry < n_axes:
                steps = -self._steps(self.js.get_axis(ry))
                for _ in range(abs(steps)):
                    c = 'i' if steps > 0 else 'k'
                    cmds.append(c)
                    self.pitch = self._clamp(self.pitch + (50 if steps > 0 else -50))

            for c in cmds:
                self.cmd_queue.put(c)

            self.state_cb(self.throttle, self.roll, self.pitch, self.yaw, self.armed)

            elapsed = time.time() - t0
            rem = LOOP_PERIOD - elapsed
            if rem > 0:
                time.sleep(rem)

    def stop(self):
        self.running = False

# ──────────────────────────────────────────────────────────────────────────────
# ATTITUDE INDICATOR (canvas-drawn artificial horizon)
# ──────────────────────────────────────────────────────────────────────────────
class AttitudeIndicator(tk.Canvas):
    def __init__(self, parent, size=160, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=T["panel"], highlightthickness=0, **kw)
        self.size = size
        self.cx   = size // 2
        self.cy   = size // 2
        self.r    = size // 2 - 4
        self.roll_deg  = 0.0
        self.pitch_deg = 0.0
        self._draw()

    def set(self, roll, pitch):
        self.roll_deg  = roll
        self.pitch_deg = pitch
        self._draw()

    def _draw(self):
        self.delete("all")
        cx, cy, r = self.cx, self.cy, self.r

        # Clip circle
        self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=T["bg"], outline=T["border2"], width=2)

        # Pitch offset in pixels (1deg ~ 2px)
        pitch_px = self.pitch_deg * 2.0
        roll_rad = math.radians(self.roll_deg)

        # Sky / ground split line
        # Horizon line rotated by roll, shifted by pitch
        dx = math.sin(roll_rad) * (r + 20)
        dy = -math.cos(roll_rad) * (r + 20)
        # Perpendicular pitch offset
        pdx = math.cos(roll_rad) * pitch_px
        pdy = math.sin(roll_rad) * pitch_px

        # Fill sky (top half relative to horizon)
        horizon_cx = cx + pdx
        horizon_cy = cy + pdy

        # Draw sky polygon clipped to circle
        # Simple approach: draw rotated rectangle for sky / ground
        import math as m
        angle = math.radians(self.roll_deg)
        pts_sky = []
        pts_gnd = []
        for deg in range(0, 370, 10):
            rad = math.radians(deg)
            px = cx + r * math.cos(rad)
            py = cy + r * math.sin(rad)
            # Determine if above or below horizon
            # Horizon normal: (-sin(roll), cos(roll))
            nx = -math.sin(angle)
            ny = math.cos(angle)
            dot = (px - horizon_cx) * nx + (py - horizon_cy) * ny
            if dot >= 0:
                pts_sky.append((px, py))
            else:
                pts_gnd.append((px, py))

        # Intersection points of horizon with circle
        # horizon line direction: (cos(roll), sin(roll))
        lx = math.cos(angle)
        ly = math.sin(angle)
        # Solve for t where (horizon_cx + t*lx)^2 + offset^2 = r^2
        a = 1
        b_coef = 2 * ((horizon_cx - cx) * lx + (horizon_cy - cy) * ly)
        c_coef = (horizon_cx - cx)**2 + (horizon_cy - cy)**2 - r**2
        disc = b_coef**2 - 4*a*c_coef
        if disc >= 0:
            t1 = (-b_coef + math.sqrt(disc)) / 2
            t2 = (-b_coef - math.sqrt(disc)) / 2
            p1 = (horizon_cx + t1*lx, horizon_cy + t1*ly)
            p2 = (horizon_cx + t2*lx, horizon_cy + t2*ly)
        else:
            p1 = p2 = (cx, cy)

        # Sky fill
        sky_pts = pts_sky + [p1, p2]
        if len(sky_pts) >= 3:
            flat = [v for pt in sky_pts for v in pt]
            self.create_polygon(flat, fill="#0d2a4a", outline="", smooth=False)
        # Ground fill
        gnd_pts = pts_gnd + [p1, p2]
        if len(gnd_pts) >= 3:
            flat = [v for pt in gnd_pts for v in pt]
            self.create_polygon(flat, fill="#3d1a08", outline="", smooth=False)

        # Horizon line
        self.create_line(p1[0], p1[1], p2[0], p2[1], fill=T["yellow"], width=2)

        # Pitch ladder lines
        for deg in [-20, -10, 10, 20]:
            offset_px = -deg * 2.0 + pitch_px
            lx2 = math.cos(angle) * 20
            ly2 = math.sin(angle) * 20
            ox = -math.sin(angle) * offset_px
            oy = math.cos(angle) * offset_px
            x0, y0 = cx + ox - lx2, cy + oy - ly2
            x1, y1 = cx + ox + lx2, cy + oy + ly2
            # Only draw if within circle
            dist = math.sqrt(ox**2 + oy**2)
            if dist < r - 5:
                self.create_line(x0, y0, x1, y1, fill=T["white"], width=1)

        # Roll arc tick marks
        self.create_arc(cx-r, cy-r, cx+r, cy+r,
                        start=0, extent=360, style="arc",
                        outline=T["border2"], width=1)
        for tick_deg in [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]:
            tr = math.radians(tick_deg - 90)
            x0 = cx + (r-1) * math.cos(tr)
            y0 = cy + (r-1) * math.sin(tr)
            x1 = cx + (r-8) * math.cos(tr)
            y1 = cy + (r-8) * math.sin(tr)
            col = T["yellow"] if tick_deg % 90 == 0 else T["muted"]
            self.create_line(x0, y0, x1, y1, fill=col, width=1)

        # Roll pointer (fixed triangle at top)
        self.create_polygon(
            cx, cy-r+2,
            cx-6, cy-r+14,
            cx+6, cy-r+14,
            fill=T["yellow"], outline=""
        )

        # Fixed aircraft symbol
        # Center dot
        self.create_oval(cx-4, cy-4, cx+4, cy+4, fill=T["yellow"], outline="")
        # Wings
        self.create_line(cx-30, cy, cx-6, cy, fill=T["yellow"], width=3)
        self.create_line(cx+6, cy, cx+30, cy, fill=T["yellow"], width=3)
        # Tail
        self.create_line(cx, cy, cx, cy+12, fill=T["yellow"], width=3)

        # Border ring
        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                         outline=T["border2"], width=2)

# ──────────────────────────────────────────────────────────────────────────────
# STICK VISUALIZER
# ──────────────────────────────────────────────────────────────────────────────
class StickDisplay(tk.Canvas):
    """Shows a joystick position as a dot in a square gate."""
    def __init__(self, parent, label="", size=80, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=T["panel"], highlightthickness=0, **kw)
        self.size  = size
        self.label = label
        self.x_val = 0.0   # -1..1
        self.y_val = 0.0
        self._draw()

    def set(self, x_norm, y_norm):
        self.x_val = max(-1.0, min(1.0, x_norm))
        self.y_val = max(-1.0, min(1.0, y_norm))
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self.size
        pad = 10
        area = s - 2*pad

        # Gate square
        self.create_rectangle(pad, pad, s-pad, s-pad,
                               outline=T["border2"], fill=T["bg"], width=1)
        # Crosshair
        cx = s//2
        self.create_line(cx, pad+2, cx, s-pad-2, fill=T["border2"], width=1)
        self.create_line(pad+2, cx, s-pad-2, cx, fill=T["border2"], width=1)

        # Dot position
        px = pad + (self.x_val + 1.0) / 2.0 * area
        py = pad + (self.y_val + 1.0) / 2.0 * area
        r = 5
        self.create_oval(px-r, py-r, px+r, py+r,
                          fill=T["cyan"], outline=T["white"], width=1)

        # Label
        self.create_text(s//2, s-4, text=self.label,
                          fill=T["label"], font=("Courier", 7))

# ──────────────────────────────────────────────────────────────────────────────
# CHANNEL BAR
# ──────────────────────────────────────────────────────────────────────────────
class ChannelBar(tk.Canvas):
    def __init__(self, parent, label, min_v=172, max_v=1811, **kw):
        super().__init__(parent, width=180, height=22,
                         bg=T["panel"], highlightthickness=0, **kw)
        self.label = label
        self.min_v = min_v
        self.max_v = max_v
        self.value = min_v
        self._draw()

    def set(self, v):
        self.value = v
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = 180, 22
        label_w = 52
        bar_x   = label_w + 4
        bar_w   = w - bar_x - 44

        self.create_text(label_w, h//2, text=self.label,
                          anchor="e", fill=T["label"], font=("Courier", 9))

        # Track
        self.create_rectangle(bar_x, 6, bar_x+bar_w, h-6,
                               fill=T["bg"], outline=T["border2"])

        # Fill
        pct  = (self.value - self.min_v) / (self.max_v - self.min_v)
        fill_w = int(bar_w * pct)
        color = T["cyan"] if self.label != "THR" else T["green"]
        if fill_w > 0:
            self.create_rectangle(bar_x, 6, bar_x+fill_w, h-6,
                                   fill=color, outline="")

        # Value
        self.create_text(bar_x+bar_w+4, h//2, text=str(self.value),
                          anchor="w", fill=T["white"], font=("Courier", 9, "bold"))

# ──────────────────────────────────────────────────────────────────────────────
# BATTERY GAUGE
# ──────────────────────────────────────────────────────────────────────────────
class BatteryGauge(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, width=200, height=28,
                         bg=T["panel"], highlightthickness=0, **kw)
        self.pct = 0
        self._draw()

    def set(self, pct):
        self.pct = max(0, min(100, pct))
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = 200, 28
        # Battery outline
        bx, by = 2, 4
        bw, bh = 170, h-8
        # Terminal
        self.create_rectangle(bx+bw, by+4, bx+bw+6, by+bh-4,
                               fill=T["border2"], outline="")
        self.create_rectangle(bx, by, bx+bw, by+bh,
                               outline=T["border2"], fill=T["bg"], width=2)

        pct = self.pct / 100.0
        fill_w = int((bw-4) * pct)
        color = (T["green"] if pct > 0.5 else
                 T["yellow"] if pct > 0.25 else T["red"])
        if fill_w > 0:
            self.create_rectangle(bx+2, by+2, bx+2+fill_w, by+bh-2,
                                   fill=color, outline="")

        # Percentage text centered
        self.create_text(bx+bw//2, h//2, text=f"{self.pct}%",
                          fill=T["white"], font=("Courier", 10, "bold"))

# ──────────────────────────────────────────────────────────────────────────────
# COMPASS
# ──────────────────────────────────────────────────────────────────────────────
class Compass(tk.Canvas):
    def __init__(self, parent, size=80, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=T["panel"], highlightthickness=0, **kw)
        self.size = size
        self.yaw  = 0.0
        self._draw()

    def set(self, yaw):
        self.yaw = yaw
        self._draw()

    def _draw(self):
        self.delete("all")
        cx = cy = self.size // 2
        r = self.size // 2 - 4

        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                          fill=T["bg"], outline=T["border2"], width=2)

        # Cardinal marks
        for deg, lbl in [(0,"N"),(90,"E"),(180,"S"),(270,"W")]:
            rad = math.radians(deg - self.yaw - 90)
            tx = cx + (r-10) * math.cos(rad)
            ty = cy + (r-10) * math.sin(rad)
            col = T["red"] if lbl == "N" else T["label"]
            self.create_text(tx, ty, text=lbl, fill=col,
                              font=("Courier", 8, "bold"))

        # Needle (always points "up" = current yaw)
        self.create_line(cx, cy, cx, cy-r+16,
                          fill=T["cyan"], width=2, arrow=tk.LAST,
                          arrowshape=(8,10,4))
        # Center dot
        self.create_oval(cx-3, cy-3, cx+3, cy+3, fill=T["white"])

# ──────────────────────────────────────────────────────────────────────────────
# LOG BOX
# ──────────────────────────────────────────────────────────────────────────────
class LogBox(tk.Text):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=T["bg"], fg=T["text"],
                         font=("Courier", 8), relief="flat",
                         insertbackground=T["cyan"], state="disabled",
                         height=6, **kw)
        self.tag_config("err",   foreground=T["red"])
        self.tag_config("ok",    foreground=T["green"])
        self.tag_config("info",  foreground=T["cyan"])
        self.tag_config("warn",  foreground=T["yellow"])

    def log(self, msg, tag=""):
        self.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        self.insert("end", f"[{ts}] {msg}\n", tag)
        self.see("end")
        if int(self.index("end-1c").split(".")[0]) > 200:
            self.delete("1.0", "50.0")
        self.configure(state="disabled")

# ──────────────────────────────────────────────────────────────────────────────
# MAIN GCS GUI
# ──────────────────────────────────────────────────────────────────────────────
class GCSApp:
    def __init__(self, root, port=None, baud=115200):
        self.root     = root
        self.port     = port
        self.baud     = baud
        self.telem    = Telemetry()
        self.cmd_q    = queue.Queue()
        self.serial_w = None
        self.gamepad_w= None

        # Gamepad shadow state for display
        self.gp_thr = 172; self.gp_roll = 992
        self.gp_pit = 992; self.gp_yaw  = 992
        self.gp_arm = False

        self._build_ui()
        self._start_workers()
        self._tick()

    # ── UI BUILD ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        r = self.root
        r.title("DRONE GCS — Avionics Dashboard")
        r.configure(bg=T["bg"])
        r.resizable(False, False)

        # Import tkinter font here for use
        try:
            mono  = tkfont.Font(family="Courier New", size=10, weight="bold")
            small = tkfont.Font(family="Courier New", size=8)
            big   = tkfont.Font(family="Courier New", size=14, weight="bold")
        except Exception:
            mono = small = big = None

        def lbl(parent, text, color=None, size=9, bold=False, **kw):
            weight = "bold" if bold else "normal"
            fg = color or T["text"]
            return tk.Label(parent, text=text, bg=T["panel"],
                            fg=fg, font=("Courier New", size, weight), **kw)

        def panel(parent, title="", **kw):
            f = tk.Frame(parent, bg=T["panel"],
                         highlightbackground=T["border"],
                         highlightthickness=1, **kw)
            if title:
                tk.Label(f, text=f" {title} ", bg=T["border"],
                         fg=T["cyan"], font=("Courier New", 8, "bold"),
                         padx=4).pack(fill="x")
            return f

        def sep(parent):
            tk.Frame(parent, bg=T["border"], height=1).pack(fill="x", pady=2)

        # ── HEADER BAR ────────────────────────────────────────────────────────
        hdr = tk.Frame(r, bg="#060a0f", height=40)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="◈  DRONE GCS  ◈", bg="#060a0f",
                 fg=T["cyan"], font=("Courier New", 14, "bold")).pack(side="left", padx=16)
        self.lbl_conn = tk.Label(hdr, text="● OFFLINE", bg="#060a0f",
                                  fg=T["red"], font=("Courier New", 10, "bold"))
        self.lbl_conn.pack(side="right", padx=16)
        self.lbl_clock = tk.Label(hdr, text="00:00:00", bg="#060a0f",
                                   fg=T["muted"], font=("Courier New", 10))
        self.lbl_clock.pack(side="right", padx=8)

        # ── MAIN LAYOUT ───────────────────────────────────────────────────────
        main = tk.Frame(r, bg=T["bg"])
        main.pack(fill="both", expand=True, padx=6, pady=4)

        left  = tk.Frame(main, bg=T["bg"])
        left.pack(side="left", fill="y", padx=(0,4))

        center = tk.Frame(main, bg=T["bg"])
        center.pack(side="left", fill="both", expand=True, padx=4)

        right = tk.Frame(main, bg=T["bg"])
        right.pack(side="left", fill="y", padx=(4,0))

        # ╔══ LEFT COLUMN ══════════════════════════════════════════════════════╗
        # BATTERY
        bat_p = panel(left, "BATTERY")
        bat_p.pack(fill="x", pady=(0,4))
        self.bat_gauge = BatteryGauge(bat_p)
        self.bat_gauge.pack(padx=8, pady=4)
        bf = tk.Frame(bat_p, bg=T["panel"])
        bf.pack(fill="x", padx=8, pady=(0,6))
        self.lbl_volts = lbl(bf, "00.00V", T["yellow"], 11, True)
        self.lbl_volts.pack(side="left")
        self.lbl_amps  = lbl(bf, "0.00A", T["cyan"], 10)
        self.lbl_amps.pack(side="right")

        # ARM STATUS
        arm_p = panel(left, "STATUS")
        arm_p.pack(fill="x", pady=(0,4))
        self.lbl_armed = tk.Label(arm_p, text="DISARMED",
                                   bg=T["panel"], fg=T["green"],
                                   font=("Courier New", 16, "bold"))
        self.lbl_armed.pack(pady=6)
        sf = tk.Frame(arm_p, bg=T["panel"])
        sf.pack(fill="x", padx=8, pady=(0,6))
        lbl(sf, "MODE:", T["label"]).pack(side="left")
        self.lbl_mode = lbl(sf, "0", T["white"], bold=True)
        self.lbl_mode.pack(side="left", padx=4)
        self.lbl_rssi = lbl(sf, "RSSI:---", T["muted"])
        self.lbl_rssi.pack(side="right")

        # GPS
        gps_p = panel(left, "GPS")
        gps_p.pack(fill="x", pady=(0,4))
        self.lbl_fix  = lbl(gps_p, "NO FIX", T["red"], 11, True)
        self.lbl_fix.pack(pady=(4,0))
        self.lbl_sats = lbl(gps_p, "0 SATS", T["muted"])
        self.lbl_sats.pack(pady=(0,4))
        gf = tk.Frame(gps_p, bg=T["panel"])
        gf.pack(fill="x", padx=8, pady=(0,6))
        lbl(gf, "ALT:", T["label"]).pack(side="left")
        self.lbl_alt = lbl(gf, "0.0m", T["white"], bold=True)
        self.lbl_alt.pack(side="left", padx=4)
        lbl(gf, "SPD:", T["label"]).pack(side="left", padx=(8,0))
        self.lbl_spd = lbl(gf, "0.0m/s", T["white"], bold=True)
        self.lbl_spd.pack(side="left", padx=4)

        # ╔══ CENTER COLUMN ════════════════════════════════════════════════════╗
        # ATTITUDE INDICATOR
        att_p = panel(center, "ATTITUDE")
        att_p.pack(fill="x", pady=(0,4))
        att_inner = tk.Frame(att_p, bg=T["panel"])
        att_inner.pack(pady=6)

        self.ai = AttitudeIndicator(att_inner, size=160)
        self.ai.pack(side="left", padx=8)

        att_vals = tk.Frame(att_inner, bg=T["panel"])
        att_vals.pack(side="left", padx=8)
        for name, attr in [("ROLL", "lbl_roll"), ("PITCH","lbl_pitch"),("YAW","lbl_yaw")]:
            row = tk.Frame(att_vals, bg=T["panel"])
            row.pack(fill="x", pady=3)
            lbl(row, f"{name}", T["label"], 8).pack(side="left")
            v = lbl(row, "+000.0°", T["cyan"], 12, True)
            v.pack(side="right")
            setattr(self, attr, v)

        self.compass = Compass(att_inner, size=80)
        self.compass.pack(side="left", padx=8)

        # CHANNELS
        ch_p = panel(center, "CHANNELS")
        ch_p.pack(fill="x", pady=(0,4))
        ch_inner = tk.Frame(ch_p, bg=T["panel"])
        ch_inner.pack(pady=6, padx=8)
        self.bar_thr  = ChannelBar(ch_inner, "THR")
        self.bar_thr.pack(pady=2)
        self.bar_roll = ChannelBar(ch_inner, "ROLL")
        self.bar_roll.pack(pady=2)
        self.bar_pit  = ChannelBar(ch_inner, "PITCH")
        self.bar_pit.pack(pady=2)
        self.bar_yaw  = ChannelBar(ch_inner, "YAW")
        self.bar_yaw.pack(pady=2)

        # STICKS
        stk_p = panel(center, "STICKS")
        stk_p.pack(fill="x", pady=(0,4))
        stk_inner = tk.Frame(stk_p, bg=T["panel"])
        stk_inner.pack(pady=6)
        self.stick_l = StickDisplay(stk_inner, "L: THR/YAW", size=90)
        self.stick_l.pack(side="left", padx=16)
        self.stick_r = StickDisplay(stk_inner, "R: PITCH/ROLL", size=90)
        self.stick_r.pack(side="left", padx=16)

        # ╔══ RIGHT COLUMN ═════════════════════════════════════════════════════╗
        # Gamepad status
        gp_p = panel(right, "GAMEPAD")
        gp_p.pack(fill="x", pady=(0,4))
        self.lbl_gp = lbl(gp_p, "Detecting...", T["muted"], 8)
        self.lbl_gp.pack(padx=8, pady=4, anchor="w")

        # Connection info
        ci_p = panel(right, "SERIAL")
        ci_p.pack(fill="x", pady=(0,4))
        self.lbl_port = lbl(ci_p, self.port or "None", T["text"], 8)
        self.lbl_port.pack(padx=8, pady=(4,0), anchor="w")
        self.lbl_serial_st = lbl(ci_p, "Connecting...", T["muted"], 8)
        self.lbl_serial_st.pack(padx=8, pady=(0,4), anchor="w")

        # RSSI signal bar
        sig_p = panel(right, "LINK QUALITY")
        sig_p.pack(fill="x", pady=(0,4))
        self.sig_canvas = tk.Canvas(sig_p, width=160, height=40,
                                     bg=T["panel"], highlightthickness=0)
        self.sig_canvas.pack(padx=8, pady=4)
        self._draw_signal(0)

        # LOG
        log_p = panel(right, "LOG")
        log_p.pack(fill="both", expand=True, pady=(0,4))
        self.logbox = LogBox(log_p, width=28)
        self.logbox.pack(padx=2, pady=2, fill="both", expand=True)

        # ── STATUS BAR ────────────────────────────────────────────────────────
        sbar = tk.Frame(r, bg="#060a0f", height=22)
        sbar.pack(fill="x")
        sbar.pack_propagate(False)
        self.lbl_status = tk.Label(sbar, text="Initializing...",
                                    bg="#060a0f", fg=T["muted"],
                                    font=("Courier New", 8))
        self.lbl_status.pack(side="left", padx=8)

    def _draw_signal(self, rssi: int):
        c = self.sig_canvas
        c.delete("all")
        # Normalize RSSI: typical range -100 (bad) to 0 (best)
        # clamp to 0..100 scale
        pct = max(0.0, min(1.0, (rssi + 100) / 100.0))
        bars = 5
        for i in range(bars):
            threshold = (i + 1) / bars
            color = T["green"] if pct >= threshold else T["border2"]
            bh = 10 + i * 6
            bx = 8 + i * 30
            by = 38 - bh
            c.create_rectangle(bx, by, bx+22, 38, fill=color, outline="")

        rssi_str = f"RSSI: {rssi} dBm" if rssi != 0 else "RSSI: ---"
        c.create_text(80, 18, text=rssi_str, fill=T["label"],
                       font=("Courier New", 8))

    # ── WORKERS ───────────────────────────────────────────────────────────────
    def _start_workers(self):
        if self.port and SERIAL_AVAILABLE:
            self.serial_w = SerialWorker(self.port, self.baud, self.telem, self.cmd_q)
            self.serial_w.start()

        if PYGAME_AVAILABLE:
            self.gamepad_w = GamepadWorker(self.cmd_q, self._on_gamepad_state)
            self.gamepad_w.start()

    def _on_gamepad_state(self, thr, roll, pit, yaw, armed):
        self.gp_thr  = thr
        self.gp_roll = roll
        self.gp_pit  = pit
        self.gp_yaw  = yaw
        self.gp_arm  = armed

    # ── TICK (UI UPDATE LOOP) ─────────────────────────────────────────────────
    def _tick(self):
        t = self.telem

        # Clock
        self.lbl_clock.config(text=time.strftime("%H:%M:%S"))

        # Connection status
        age = t.age()
        if t.connected and age < 3.0:
            self.lbl_conn.config(text="● ONLINE", fg=T["green"])
        elif t.connected:
            self.lbl_conn.config(text="● STALE", fg=T["yellow"])
        else:
            self.lbl_conn.config(text="● OFFLINE", fg=T["red"])

        # Battery
        self.bat_gauge.set(t.battery_pct)
        self.lbl_volts.config(text=f"{t.battery_v:.2f}V")
        self.lbl_amps.config(text=f"{t.battery_a:.2f}A")

        # Armed status
        if t.armed or self.gp_arm:
            self.lbl_armed.config(text="ARMED", fg=T["red"])
        else:
            self.lbl_armed.config(text="DISARMED", fg=T["green"])

        self.lbl_mode.config(text=str(t.mode))
        self.lbl_rssi.config(text=f"RSSI:{t.rssi}")

        # GPS
        fix_color = T["green"] if "3D" in t.gps_fix or "Fix" not in t.gps_fix.lower() else T["red"]
        if t.gps_fix == "No Fix":
            fix_color = T["red"]
        elif t.gps_sats > 0:
            fix_color = T["yellow"] if t.gps_sats < 6 else T["green"]
        self.lbl_fix.config(text=t.gps_fix.upper(), fg=fix_color)
        self.lbl_sats.config(text=f"{t.gps_sats} SATS")
        self.lbl_alt.config(text=f"{t.altitude:.1f}m")
        self.lbl_spd.config(text=f"{t.speed:.1f}m/s")

        # Attitude
        self.ai.set(t.roll, t.pitch)
        self.compass.set(t.yaw)

        def fmt_angle(v):
            return f"{v:+.1f}°"

        self.lbl_roll.config(text=fmt_angle(t.roll))
        self.lbl_pitch.config(text=fmt_angle(t.pitch))
        self.lbl_yaw.config(text=fmt_angle(t.yaw))

        # Channels from gamepad
        self.bar_thr.set(self.gp_thr)
        self.bar_roll.set(self.gp_roll)
        self.bar_pit.set(self.gp_pit)
        self.bar_yaw.set(self.gp_yaw)

        # Stick visualizers
        # Left stick: X=yaw, Y=throttle (normalize to -1..1)
        def norm(v): return (v - 992) / (1811 - 992) * 2  # approximate
        def norm_thr(v): return (v - 172) / (1811 - 172) * 2 - 1
        self.stick_l.set(norm(self.gp_yaw), -norm_thr(self.gp_thr))
        self.stick_r.set(norm(self.gp_roll), -norm(self.gp_pit))

        # Signal
        self._draw_signal(t.rssi)

        # Serial/gamepad status
        if self.serial_w:
            self.lbl_serial_st.config(text=self.serial_w.status)
        if self.gamepad_w:
            self.lbl_gp.config(text=self.gamepad_w.status)

        self.lbl_status.config(
            text=f"Port: {self.port or 'none'} | "
                 f"Telem age: {age:.1f}s | "
                 f"{'GAMEPAD OK' if self.gamepad_w and self.gamepad_w.status.startswith('OK') else 'NO GAMEPAD'}"
        )

        self.root.after(100, self._tick)  # 10Hz UI refresh

    def on_close(self):
        if self.serial_w:
            self.serial_w.stop()
        if self.gamepad_w:
            self.gamepad_w.stop()
        self.root.destroy()

# ──────────────────────────────────────────────────────────────────────────────
# ENTRY
# ──────────────────────────────────────────────────────────────────────────────
def list_serial_ports():
    if not SERIAL_AVAILABLE:
        print("pyserial not installed.")
        return
    ports = serial.tools.list_ports.comports()
    print("Available ports:")
    for p in ports:
        print(f"  {p.device}  --  {p.description}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drone GCS with PS5 Controller")
    parser.add_argument("--port",       type=str, default=None)
    parser.add_argument("--baud",       type=int, default=115200)
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--list-axes",  action="store_true")
    args = parser.parse_args()

    if args.list_ports:
        list_serial_ports()
        sys.exit(0)

    if args.list_axes:
        if not PYGAME_AVAILABLE:
            print("pygame not installed.")
            sys.exit(1)
        pygame.init(); pygame.joystick.init()
        count = pygame.joystick.get_count()
        if count == 0:
            print("No controller found.")
            sys.exit(1)
        js = pygame.joystick.Joystick(0); js.init()
        print(f"Controller: {js.get_name()}")
        print("Move sticks. Ctrl+C to quit.")
        try:
            while True:
                pygame.event.pump()
                vals = [f"A{i}:{js.get_axis(i):+.2f}" for i in range(js.get_numaxes())]
                btns = [str(i) for i in range(js.get_numbuttons()) if js.get_button(i)]
                print(f"\r  {' | '.join(vals)}  Btns:{btns}    ", end="", flush=True)
                time.sleep(0.05)
        except KeyboardInterrupt:
            pygame.quit()
        sys.exit(0)

    if args.port is None and SERIAL_AVAILABLE:
        print("No port specified. Available ports:\n")
        list_serial_ports()
        args.port = input("\nEnter port (or press Enter to run without serial): ").strip() or None

    root = tk.Tk()
    app  = GCSApp(root, port=args.port, baud=args.baud)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()