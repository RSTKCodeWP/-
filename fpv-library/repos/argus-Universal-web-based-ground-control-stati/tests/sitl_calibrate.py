#!/usr/bin/env python3
"""Record calibration-handshake fixtures against real ArduPilot SITL.

Boots the prebuilt SITL binary with the special 'calibration' vehicle model
(libraries/SITL/SIM_Calibration.cpp — attitude commanded through servo
outputs 5-8), connects the Argus backend to SERIAL0 (tcp:5760), and drives
the two interactive calibrations end-to-end THROUGH THE BACKEND'S OWN
command path:

  1. onboard compass cal   cal_compass -> rotation poses -> MAG_CAL_REPORT
                           -> cal_compass_accept
  2. 6-position accel cal  cal_accel -> 6x (attitude + cal_accel_next)
                           -> "Calibration successful"

Each backend connect auto-records logs/argus_*.tlog; the two session logs
are copied to tests/fixtures/{magcal,accelcal}_sitl.tlog for the replay
regression tests (tests/test_contract_calibration_replay.py).

SIM-side attitude driving mirrors ArduPilot's own autotest
(Tools/autotest/vehicle_test_suite.py: SITLCompassCalibration / AccelCal):
MAV_CMD_DO_SET_SERVO on outputs 5-8, sent over a SECOND direct pymavlink
connection on SERIAL1 (tcp:5762) so the link under test carries only the
GCS-side protocol. Servo semantics per SIM_Calibration.cpp:update():
  servo5 <1100 stop | 1100-1199 attitude mode (servo6/7/8 = roll/pitch/yaw)
         | 1200-1299 autonomous calibration poses | >=1300 angular-velocity
PWM encoding per Tools/mavproxy_modules/sitl_calibration.py set_attitute():
  pwm = 1500 + int(angle_normalized_to_[-pi,pi] * 500/pi)

Usage: python tests/sitl_calibrate.py   (self-contained: boots SITL + backend
on port 8199, tears both down on exit; needs curl + internet on first run to
fetch the prebuilt binary into ~/sitl/)
"""

import asyncio
import json
import math
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

os.environ.setdefault("MAVLINK20", "1")
from pymavlink import mavutil  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SITL_DIR = Path.home() / "sitl"
BIN_URL = "https://firmware.ardupilot.org/Copter/stable/SITL_x86_64_linux_gnu/arducopter"
PARM_URL = "https://raw.githubusercontent.com/ArduPilot/ardupilot/ArduCopter-stable/Tools/autotest/default_params/copter.parm"
HOME = "-35.363261,149.165230,584,353"
BACKEND_PORT = 8199
WS_URL = f"ws://127.0.0.1:{BACKEND_PORT}/ws"
RUN_DIR = REPO / "logs" / "sitl_cal_run"
FIXTURES = REPO / "tests" / "fixtures"

# Tools/mavproxy_modules/sitl_calibration.py AccelcalController.state_data,
# keyed by the words AP_AccelCal prints in "Place vehicle %s and press any
# key." ('level' must be matched last — it is a substring-style catch).
ACCEL_POSES = [
    ("LEFT", (-math.pi / 2, 0, 0)),
    ("RIGHT", (math.pi / 2, 0, 0)),
    ("DOWN", (0, -math.pi / 2, 0)),
    ("UP", (0, math.pi / 2, 0)),
    ("BACK", (math.pi, 0, 0)),
    ("level", (0, 0, 0)),
]


def log(msg: str) -> None:
    print(f"[cal] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"[cal] FATAL: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def _kill(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def ensure_sitl_assets() -> None:
    SITL_DIR.mkdir(exist_ok=True)
    binp = SITL_DIR / "arducopter"
    parm = SITL_DIR / "copter.parm"
    if not binp.exists():
        log(f"downloading SITL binary -> {binp}")
        urllib.request.urlretrieve(BIN_URL, binp)
        binp.chmod(0o755)
    if not parm.exists():
        log(f"downloading default params -> {parm}")
        urllib.request.urlretrieve(PARM_URL, parm)


def boot_sitl() -> subprocess.Popen:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    sitl_log = RUN_DIR / "sitl.log"
    # --serial0 tcp:0 (no :wait): boot must not gate on the first TCP client
    # (AP_HAL_SITL/UARTDriver.cpp:117), our backend connects later.
    cmd = [
        str(SITL_DIR / "arducopter"),
        "--model", "calibration",
        "--speedup", "8",
        "-w",
        "--serial0", "tcp:0",
        "--defaults", str(SITL_DIR / "copter.parm"),
        "--home", HOME,
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=RUN_DIR,
        stdin=subprocess.DEVNULL,
        stdout=open(sitl_log, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            die(f"SITL exited {proc.returncode} during boot:\n{sitl_log.read_text()[-2000:]}")
        if "SERIAL2 on TCP port" in sitl_log.read_text():
            log("SITL serial ports up, settling 3s")
            time.sleep(3)
            return proc
        time.sleep(0.5)
    _kill(proc)  # die() exits before main's finally — don't orphan the boot
    die(f"SITL never opened serial ports:\n{sitl_log.read_text()[-2000:]}")


def boot_backend() -> subprocess.Popen:
    be_log = RUN_DIR / "backend.log"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app:app",
         "--host", "127.0.0.1", "--port", str(BACKEND_PORT), "--log-level", "info"],
        cwd=REPO,
        stdin=subprocess.DEVNULL,
        stdout=open(be_log, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    import urllib.error
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            die(f"backend exited {proc.returncode}:\n{be_log.read_text()[-2000:]}")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=1)
            return proc
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    die("backend never became healthy")


class SimDriver:
    """Positions the SIM_Calibration vehicle via DO_SET_SERVO on SERIAL1."""

    def __init__(self):
        self.conn = mavutil.mavlink_connection("tcp:127.0.0.1:5762", source_system=250)
        if self.conn.wait_heartbeat(timeout=30) is None:
            # target_system would stay 0 and every DO_SET_SERVO would go out
            # as broadcast — die instead of half-working by accident.
            die("driver: no heartbeat on SERIAL1 (tcp:5762)")
        log(f"driver link up (sysid {self.conn.target_system})")
        # SIMSTATE (164) is ground truth for convergence checks; stream it at
        # 10 Hz regardless of SR1_* stream-group defaults.
        self.conn.mav.command_long_send(
            self.conn.target_system, self.conn.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
            164, 100000, 0, 0, 0, 0, 0)

    def servo(self, n: int, pwm: int) -> None:
        self.conn.mav.command_long_send(
            self.conn.target_system, self.conn.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO, 0,
            n, pwm, 0, 0, 0, 0, 0)

    @staticmethod
    def _norm(a: float) -> float:
        # sitl_calibration.py normalize_attitude_angle: wrap into [-pi, pi]
        a = a % (2 * math.pi)
        return a - 2 * math.pi if a > math.pi else a

    def set_attitude(self, roll: float, pitch: float, yaw: float) -> None:
        scale = 500.0 / math.pi
        self.servo(5, 1150)
        self.servo(6, 1500 + int(self._norm(roll) * scale))
        self.servo(7, 1500 + int(self._norm(pitch) * scale))
        self.servo(8, 1500 + int(self._norm(yaw) * scale))

    def start_magcal_poses(self) -> None:
        self.servo(5, 1250)

    def stop(self) -> None:
        self.servo(5, 1000)

    def wait_attitude(self, roll: float, pitch: float, tol=0.06, timeout=30.0) -> bool:
        """5 consecutive close SIMSTATE samples, wrap-aware (BACK: ±pi both ok)."""

        def close(a, b):
            d = abs(self._norm(a - b))
            return min(d, 2 * math.pi - d) < tol

        hits = 0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            m = self.conn.recv_match(type="SIMSTATE", blocking=True, timeout=2)
            if m is None:
                continue
            if close(m.roll, roll) and close(m.pitch, pitch):
                hits += 1
                if hits >= 5:
                    return True
            else:
                hits = 0
        return False


# ── ws helpers (same shapes as sitl_verify.py) ──────────────────────────────
async def ws_cmd(ws, c, p=None, **kw):
    msg = {"type": "command", "cmd": c, "param": p}
    msg.update(kw)
    await ws.send(json.dumps(msg))


async def wait_event(ws, pred, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            m = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
        except asyncio.TimeoutError:
            continue
        if m.get("type") == "event" and pred(m):
            return m
    return None


def newest_tlog(before: set) -> Path:
    new = sorted(set((REPO / "logs").glob("argus_*.tlog")) - before)
    if not new:
        die("no new tlog appeared — recording broken?")
    return new[-1]


async def session(drive) -> Path:
    """One backend connect -> drive() -> disconnect; returns the session tlog."""
    import websockets

    before = set((REPO / "logs").glob("argus_*.tlog"))
    async with websockets.connect(WS_URL, max_size=None) as ws:
        await ws.send(json.dumps(
            {"type": "connect", "port": "tcp:localhost:5760", "baud": 57600, "protocol": "auto"}))
        deadline = time.monotonic() + 15
        ok = False
        while time.monotonic() < deadline:
            m = json.loads(await asyncio.wait_for(ws.recv(), 5))
            if m.get("type") == "connect_result":
                ok = m.get("ok")
                break
        if not ok:
            die("backend failed to connect to SITL")
        # let the heartbeat latch + stream setup settle before commanding
        await asyncio.sleep(2)
        await drive(ws)
        await ws.send(json.dumps({"type": "disconnect"}))
        await asyncio.sleep(1)
    return newest_tlog(before)


async def drive_magcal(ws, sim: SimDriver):
    log("magcal: starting onboard compass cal (42424 via backend)")
    await ws_cmd(ws, "cal_compass")
    started = await wait_event(ws, lambda m: m.get("event_type") == "cal_compass", 10)
    if not started:
        die("no cal_compass start event")
    sim.start_magcal_poses()
    pct_events = 0
    done = None

    def check(m):
        nonlocal pct_events
        if m.get("event_type") != "cal_compass":
            return False
        t = m.get("text", "")
        if "%" in t:
            pct_events += 1
            return False
        return ("完成" in t) or ("complete" in t) or ("失败" in t) or ("FAILED" in t)

    done = await wait_event(ws, check, 240)
    if not done:
        die("magcal: no MAG_CAL_REPORT-driven completion event within 240s")
    text = done.get("text", "")
    if "失败" in text or "FAILED" in text:
        die(f"magcal reported failure: {text}")
    log(f"magcal: complete after {pct_events} progress events — accepting (42425)")
    await ws_cmd(ws, "cal_compass_accept")
    await asyncio.sleep(3)  # let the ACK land in the recording
    sim.stop()


async def drive_accelcal(ws, sim: SimDriver):
    log("accelcal: starting interactive accel cal (241 p5=1 via backend)")
    await ws_cmd(ws, "cal_accel")
    seen = []
    for i in range(12):  # 6 positions; headroom for FC-side retries
        # AP_AccelCal prompts "Place vehicle <pos> and press any key." via
        # STATUSTEXT (matched exactly by vehicle_test_suite.py:AccelCal).
        ev = await wait_event(
            ws, lambda m: m.get("event_type") == "statustext" and "Place vehicle" in m.get("text", ""), 30)
        if ev is None:
            die(f"accelcal: no position prompt after {seen}")
        text = ev["text"]
        side, (r, p, y) = next(
            ((k, att) for k, att in ACCEL_POSES if k in text), (None, (None,) * 3))
        if side is None:
            die(f"accelcal: unrecognized prompt {text!r}")
        log(f"accelcal: prompt {i + 1} -> {side}")
        seen.append(side)
        sim.set_attitude(r, p, y)
        if not sim.wait_attitude(r, p, timeout=30):
            log(f"accelcal: WARN attitude {side} not confirmed via SIMSTATE, proceeding")
        await asyncio.sleep(1)
        await ws_cmd(ws, "cal_accel_next")
        if len(set(seen)) == 6:
            break
    final = await wait_event(
        ws, lambda m: m.get("event_type") == "statustext" and "alibration" in m.get("text", ""), 30)
    if not final or "successful" not in final.get("text", ""):
        die(f"accelcal did not succeed: {final and final.get('text')!r}, prompts={seen}")
    log(f"accelcal: successful after positions {seen}")
    sim.stop()


async def main():
    ensure_sitl_assets()
    sitl = backend = None
    try:
        sitl = boot_sitl()
        backend = boot_backend()
        sim = SimDriver()
        FIXTURES.mkdir(exist_ok=True)

        tlog_a = await session(lambda ws: drive_magcal(ws, sim))
        dst_a = FIXTURES / "magcal_sitl.tlog"
        dst_a.write_bytes(tlog_a.read_bytes())
        log(f"fixture written: {dst_a} ({dst_a.stat().st_size} bytes)")

        tlog_b = await session(lambda ws: drive_accelcal(ws, sim))
        dst_b = FIXTURES / "accelcal_sitl.tlog"
        dst_b.write_bytes(tlog_b.read_bytes())
        log(f"fixture written: {dst_b} ({dst_b.stat().st_size} bytes)")
        log("DONE")
    finally:
        _kill(backend)
        _kill(sitl)


if __name__ == "__main__":
    asyncio.run(main())
