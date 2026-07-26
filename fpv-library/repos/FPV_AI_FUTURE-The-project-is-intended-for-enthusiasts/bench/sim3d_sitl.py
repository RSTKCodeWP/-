"""Level-B firmware-in-the-loop bridge: MuJoCo <-> Betaflight SITL.

Runs the ACTUAL Betaflight firmware (built as a host SITL binary) as the flight controller in the
loop. The bridge speaks Betaflight's SITL UDP protocol (from src/platform/SIMULATOR/):

    sim -> FC  :  fdm_packet  @ UDP 9003   (timestamp, gyro, accel, orientation quat, vel, pos)
    sim -> FC  :  rc_packet   @ UDP 9004   (timestamp, 16 RC channels)
    FC  -> sim :  servo_packet@ UDP 9002   (4 motor speeds, 0..1)

MuJoCo integrates the true 6-DOF rigid body; Betaflight closes the inner attitude/rate loops and
mixes to motors; our seeker's guidance enters as RC (roll/pitch/yaw/throttle). This gives the same
firmware you fly, with native 6-DOF attitude dynamics -- the SIL->SITL rung of the master plan.

STATUS: protocol + process launch + handshake are implemented and proven (the firmware responds
with motor outputs). The full MuJoCo 6-DOF mixer + arming sequence + guidance-RC intercept loop is
the next iteration (see `run_intercept` TODO).

Handshake proof:  PYTHONPATH=.:fpv python3 -m fpv_ai.bench.sim3d_sitl --binary /path/to/betaflight_SITL.elf
"""
from __future__ import annotations

import argparse
import os
import socket
import struct
import subprocess
import tempfile
import time

# --- Betaflight SITL UDP wire formats (little-endian; SITL runs native on the same host) ---
FDM_FMT = "<18d"          # timestamp, gyro[3], accel[3], quat[4], vel[3], pos[3], pressure
RC_FMT = "<d16H"          # timestamp, channels[16]
SERVO_FMT = "<4f"         # motor_speed[4], 0..1
PORT_PWM = 9002           # FC -> sim  (motor outputs)
PORT_STATE = 9003         # sim -> FC  (fdm)
PORT_RC = 9004            # sim -> FC  (rc)


class SitlBridge:
    """Launches the Betaflight SITL binary and speaks its UDP protocol."""

    def __init__(self, binary: str, host: str = "127.0.0.1", cwd: str | None = None):
        self.binary = binary
        self.host = host
        self.cwd = cwd or tempfile.mkdtemp(prefix="bf_sitl_")
        self.proc: subprocess.Popen | None = None
        self.rx: socket.socket | None = None
        self.tx: socket.socket | None = None

    def start(self, settle_s: float = 1.5) -> None:
        self.rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx.bind((self.host, PORT_PWM))       # we receive motor outputs here
        self.rx.settimeout(0.02)
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.proc = subprocess.Popen([self.binary], cwd=self.cwd,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(settle_s)                      # let the FC bind its UDP servers

    def send_state(self, t, gyro, accel, quat, vel, pos, pressure=101325.0) -> None:
        self.tx.sendto(struct.pack(FDM_FMT, t, *gyro, *accel, *quat, *vel, *pos, pressure),
                       (self.host, PORT_STATE))

    def send_rc(self, t, channels) -> None:
        ch = (list(channels) + [1500] * 16)[:16]
        self.tx.sendto(struct.pack(RC_FMT, t, *[int(c) for c in ch]), (self.host, PORT_RC))

    def recv_motors(self):
        try:
            data, _ = self.rx.recvfrom(128)
        except socket.timeout:
            return None
        if len(data) >= struct.calcsize(SERVO_FMT):
            return struct.unpack(SERVO_FMT, data[:struct.calcsize(SERVO_FMT)])
        return None

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        for s in (self.rx, self.tx):
            if s:
                s.close()


def handshake(binary: str, seconds: float = 3.0) -> dict:
    """Prove the firmware is in the loop: stream level-hover state + RC, collect motor replies."""
    br = SitlBridge(binary)
    br.start()
    quat = (1.0, 0.0, 0.0, 0.0)                   # level attitude
    accel = (0.0, 0.0, -9.80665)                  # 1 G, NED body frame at rest
    pos = (0.0, 0.0, -100.0)                       # 100 m up (NED z is down)
    got, n_rx = None, 0
    t0 = time.time()
    i = 0
    while time.time() - t0 < seconds:
        t = i * 0.001
        br.send_state(t, (0, 0, 0), accel, quat, (0, 0, 0), pos)
        br.send_rc(t, [1500, 1500, 1000, 1500, 1000])   # roll/pitch center, throttle low, yaw center, aux low
        m = br.recv_motors()
        if m is not None:
            got = m; n_rx += 1
        i += 1
        time.sleep(0.001)
    alive = br.alive()
    br.stop()
    return dict(motor_packets_received=n_rx, last_motors=got, fc_alive=alive)


def run_intercept(*args, **kwargs):
    """TODO (next iteration): full MuJoCo 6-DOF <-> SITL intercept loop.

    Plan: give the MuJoCo interceptor a body frame + 4 motors; each step send fdm (gyro/accel/quat
    from MuJoCo body) -> BF; feed the seeker's guidance as RC (roll/pitch/yaw/throttle) -> BF;
    receive motor_speed[4] -> quad mixer -> body thrust + torques applied in MuJoCo -> mj_step.
    Arming: send AUX arm high + throttle low until `ARMED`, then hand over to guidance RC.
    """
    raise NotImplementedError("full firmware-in-the-loop intercept is the next Level-B iteration")


def main():
    ap = argparse.ArgumentParser(description="MuJoCo <-> Betaflight SITL bridge (Level B)")
    ap.add_argument("--binary", required=True, help="path to betaflight_SITL.elf")
    ap.add_argument("--seconds", type=float, default=3.0)
    a = ap.parse_args()
    r = handshake(a.binary, a.seconds)
    print(f"firmware-in-the-loop handshake:")
    print(f"  motor packets received from FC : {r['motor_packets_received']}")
    print(f"  last motor_speed[4]            : {r['last_motors']}")
    print(f"  FC process still alive         : {r['fc_alive']}")
    print("  => LINK PROVEN" if r['motor_packets_received'] > 0 else "  => no motor packets (check ports/arming)")


if __name__ == "__main__":
    main()
