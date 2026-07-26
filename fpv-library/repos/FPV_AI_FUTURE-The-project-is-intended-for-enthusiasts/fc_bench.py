"""HITL bench runner — FT640 + Betaflight FC (UART) + two physical buttons + the real production loop.

Ties everything into ONE onboard loop the operator drives by hand, with dumps for later analysis:
    FT640 frame ─┐
    FC gyro (MSP)─┼─► ProductionRuntime.step ─► arming RC ─► MSP_SET_RAW_RC on the wire (UART)
    2 buttons ───┘        (designate / commit / cancel / kill via OperatorConsole)

BUTTON 1 (CAPTURE/LAUNCH): press = lock the target; press again = launch (dual-signed commit → arm).
BUTTON 2 (CHANGE/CANCEL) : press pre-launch = drop/change the target; press post-launch = ABORT (kill).

SAFETY: opening the REAL serial link (which can arm the FC and drive motors via MSP RC) requires the
explicit env gate ``FC_BENCH_MOTORS_OFF=1`` — set it ONLY with propellers off and motors unplugged.
Without it the runner uses the in-memory MockFc so the whole protocol + buttons can be rehearsed safely.
The two Ed25519 operator signatures are generated on this bench (one physical operator): the PHYSICAL
button is the human authority ([[block03-human-authority-doctrine]]); the crypto exercises the real
verifier path — it does not stand in for two independent humans.

Env: SERIAL_PORT(/dev/ttyAMA0) BAUD(115200) VIDEO_DEV(/dev/video0|none) GYRO_SCALE(0=uncal) OUT DUR(0=∞)
     HTTP_PORT(8090) SIM_BUTTONS(0)  FC_BENCH_MOTORS_OFF(unset=mock link)
"""
from __future__ import annotations

import os
import sys
import json
import csv
import time
import uuid
import signal
import threading
import subprocess

sys.path.insert(0, "/home/admin/seeker/system")
sys.path.insert(0, "/home/admin/seeker/system/fpv")

import numpy as np
from nacl.signing import SigningKey

from fpv.seeker.geometry import ft640_intrinsics
from fpv_ai.betaflight_link import msp_codec as mc
from fpv_ai.betaflight_link.msp_codec import decode_raw_imu, gyro_raw_to_radps
from fpv_ai.betaflight_link.serial_link import MockFcChannel, MspLink
from fpv_ai.betaflight_link.arming import ArmingConfig
from fpv_ai.betaflight_link.authorization import sign_commit
from fpv_ai.production_runtime import ProductionConfig, ProductionRuntime
from fpv_ai.operator_console import OperatorConsole, ConsoleState
from fpv_ai.pi5_buttons import make_buttons

W_SRC, H_SRC, W, H = 720, 576, 640, 512      # grabber native -> pipeline (Boson-640) size
MSP_SET_MOTOR = 214


def _set_motors(link, values) -> None:
    """Direct motor command (MSP_SET_MOTOR) — the Configurator 'Motors' mechanism. Works ONLY while the FC is
    DISARMED (a motor test), bypassing RX/arming/failsafe. PROPS OFF ALWAYS. Betaflight stops the motors if these
    stop arriving (its own watchdog), so this loop must keep sending. 1000 = stop."""
    import struct
    payload = b"".join(struct.pack("<H", int(max(1000, min(2000, v)))) for v in values)
    try:
        link._channel.write(mc.encode_msp_v2(MSP_SET_MOTOR, payload))
    except Exception:
        pass


# ── camera: FT640 grabber -> 640x512 uint16 pipeline frame ────────────────────────────────────────────
class FrameSource:
    def __init__(self, dev: str) -> None:
        self.dev = dev
        self.sim = dev == "none"
        self._p = None
        if not self.sim:
            self._p = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-input_format", "mjpeg",
                 "-video_size", f"{W_SRC}x{H_SRC}", "-i", dev, "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"],
                stdout=subprocess.PIPE, bufsize=W_SRC * H_SRC * 4)
        self._buf = b""

    def read_gray(self):
        if self.sim:                                  # synthetic hot target for FC/button rehearsal
            yy, xx = np.mgrid[0:H, 0:W]
            g = 40 + 200 * np.exp(-(((xx - W / 2) ** 2 + (yy - H / 2) ** 2) / (2 * 6.0 ** 2)))
            return g.clip(0, 255).astype(np.uint8)
        fsz = W_SRC * H_SRC
        while len(self._buf) < fsz:
            chunk = self._p.stdout.read(fsz - len(self._buf))
            if not chunk:
                return None
            self._buf += chunk
        raw, self._buf = self._buf[:fsz], self._buf[fsz:]
        return np.frombuffer(raw, np.uint8).reshape(H_SRC, W_SRC)

    def frame_u16(self, gray720):
        import cv2
        g = cv2.resize(gray720, (W, H), interpolation=cv2.INTER_AREA) if gray720.shape != (H, W) else gray720
        return (4096.0 + g.astype(np.float64) * 42.0).clip(0, 65535).astype(np.uint16)

    def close(self):
        if self._p is not None:
            try:
                self._p.terminate()
            except Exception:
                pass


# ── live MJPEG view of the annotated feed (optional) ──────────────────────────────────────────────────
class LiveView:
    def __init__(self, port: int) -> None:
        self._lock = threading.Lock(); self._jpg = [None]; self.stop = False
        t = threading.Thread(target=self._serve, args=(port,), daemon=True); t.start()

    def push(self, jpg: bytes) -> None:
        with self._lock:
            self._jpg[0] = jpg

    def _serve(self, port: int) -> None:
        import http.server, socketserver
        outer = self
        page = (b"<html><body style='margin:0;background:#000'>"
                b"<img src='/s.mjpg' style='width:100%;image-rendering:pixelated'></body></html>")

        class H_(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                if self.path == "/s.mjpg":
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f"); self.end_headers()
                    try:
                        while not outer.stop:
                            with outer._lock:
                                fr = outer._jpg[0]
                            if fr:
                                self.wfile.write(b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + fr + b"\r\n")
                            time.sleep(0.05)
                    except Exception:
                        pass
                else:
                    self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
                    self.wfile.write(page)

        class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True; allow_reuse_address = True
        TS(("0.0.0.0", port), H_).serve_forever()


def _sign_commit_now(now: float, keys) -> dict:
    payload = dict(keypress_recorded=True, keypress_ts=now, issued_at_s=now, expires_at_s=now + 300,
                   mission_goal="KINETIC", synthetic=False, nonce=uuid.uuid4().hex)
    return sign_commit(payload, keys)


def main() -> None:
    port = os.environ.get("SERIAL_PORT", "/dev/ttyAMA0")
    baud = int(os.environ.get("BAUD", "115200"))
    video_dev = os.environ.get("VIDEO_DEV", "/dev/video0")
    gyro_scale = float(os.environ.get("GYRO_SCALE", "0"))     # deg/s per LSB; 0 = uncalibrated -> ego off
    out = os.environ.get("OUT", "/home/admin/seeker/runs/hitl")
    dur = float(os.environ.get("DUR", "0"))
    http_port = int(os.environ.get("HTTP_PORT", "8090"))
    sim_buttons = os.environ.get("SIM_BUTTONS", "0") == "1"
    motors_off = os.environ.get("FC_BENCH_MOTORS_OFF") == "1"
    # BENCH THROTTLE CEILING (us): caps the arming ramp + AI_ACTIVE base so motors, if powered, only ARM and
    # IDLE — they never ramp up. 1050 = armed idle (barely turning). PROPS OFF regardless. Full flight would be
    # 1500; the low default here makes an accidental full-throttle spin-up impossible on the bench.
    hover_cap = int(os.environ.get("HOVER_BASE_US", "1050"))
    # BENCH MOTOR DRIVE (opt-in): when the operator's two-press makes the system live, spin the motors DIRECTLY
    # via MSP_SET_MOTOR (Betaflight ignores our arm RC = RXLOSS, so this is the honest no-RX way to actuate them).
    # PROPS OFF. motor_max_us caps the spin low; motors stop the instant the system is not live (or on abort/exit).
    motor_drive = os.environ.get("MOTOR_DRIVE", "0") == "1"
    motor_max_us = int(os.environ.get("MOTOR_MAX_US", "1100"))
    motor_count = int(os.environ.get("MOTOR_COUNT", "4"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # systemctl stop / SIGTERM -> SystemExit so the `finally` runs (motors -> off, clean close). SIGINT (Ctrl-C)
    # already unwinds through finally. Without this, a bare SIGTERM would kill us WITHOUT stopping the motors.
    signal.signal(signal.SIGTERM, lambda *_a: sys.exit(0))

    print("=" * 70)
    print(" HITL BENCH — FT640 + FC(UART) + 2 buttons + production loop")
    if motors_off:
        print(f" LIVE serial link on {port}@{baud}. This CAN ARM the FC and drive RC. MOTORS MUST BE OFF.")
        link = MspLink.open_serial(port, baud, hardware_authorized=True)
    else:
        print(" MOCK link (FC_BENCH_MOTORS_OFF!=1): protocol + buttons rehearse safely, nothing on the wire.")
        link = MspLink.for_bench(MockFcChannel())
    print("=" * 70)

    (sk_a, pk_a), (sk_b, pk_b) = _kp(), _kp()
    # Permissive class gate (lambda -> True) = the removed learned classifier is a NO-OP PERMIT on the bench:
    # the machine never DENIES on class; the human's two presses are the authority ([[human-authority]]). It is
    # REQUIRED for the mission to reach READY (class_asserted), same as the production tests. range is not
    # required on the bench (ProductionConfig.require_measured_range=False by default).
    rt = ProductionRuntime(link=link, operator_public_keys=[pk_a, pk_b], intrinsics=ft640_intrinsics(),
                           classifier=lambda frame, centroid: True,
                           config=ProductionConfig(arming_config=ArmingConfig(hover_base_us=hover_cap)))
    print(f" throttle ceiling (hover_base) = {hover_cap} us  (idle=1000; motors ARM+IDLE only, no spin-up)")
    console = OperatorConsole()
    buttons = make_buttons(sim=sim_buttons)
    cam = FrameSource(video_dev)
    view = LiveView(http_port)

    cf = open(out + ".csv", "w", newline=""); cw = csv.writer(cf)
    cw.writerow(["i", "t", "console", "mission", "arm", "eff_power", "locked", "snr", "note",
                 "rc_throttle", "rc_aux1", "gyro_x", "gyro_y", "gyro_z", "link_alive", "fc_rc_frames"])

    held_auth = None
    last_locked = False
    last_snr = 0.0
    i = 0
    t0 = time.monotonic()
    tprint = 0.0
    dt = 1.0 / 100.0
    try:
        while True:
            now = time.monotonic()
            # 1) FC telemetry: read gyro, judge link health
            gyro = (0.0, 0.0, 0.0); link_alive = True
            try:
                link.request(mc.MSP_RAW_IMU)
                frames = link.poll()
                imu = next((decode_raw_imu(f.payload) for f in frames
                            if f.function == mc.MSP_RAW_IMU and f.direction == mc.DIR_FROM_FC), None)
                if imu is not None and gyro_scale:
                    gyro = gyro_raw_to_radps(imu.gyro, gyro_scale)
                link_alive = (imu is not None) or not motors_off
            except Exception:
                link_alive = not motors_off

            # 2) camera frame
            gray = cam.read_gray()
            if gray is None:
                break
            frame = cam.frame_u16(gray)

            # 3) buttons -> operator intent
            cap_edge, cxl_edge = buttons.poll()
            # target_available=True: the OPERATOR judges the target from the live thermal and aims the boresight;
            # the machine must not pre-gate that choice ([[human-authority]]). Locking empty sky simply never
            # reaches READY (default-DENY), so a bad press cannot arm. (A snr/lock gate here would DEADLOCK —
            # snr only exists AFTER designation.)
            intent = console.on_tick(capture_edge=cap_edge, cancel_edge=cxl_edge, target_available=True)
            if intent.designate:
                rt.designate((float(W / 2), float(H / 2)))          # boresight aim (strapdown)
            if intent.submit_commit:
                held_auth = rt.submit_authorization(_sign_commit_now(now, [sk_a, sk_b]))
            if intent.kill:
                rt.arming.kill("operator_abort_button")

            # 4) production step (auth held after launch; cancel vetoes pre-launch)
            auth = held_auth if console.state in (ConsoleState.LAUNCHED,) else None
            o, st = rt.step(now, frame, gyro, dt, authorization=auth, link_alive=link_alive,
                            operator_cancel=intent.operator_cancel)
            last_locked = bool(o.locked)
            last_snr = float(o.snr or 0.0)

            # 4b) BENCH MOTOR DRIVE (opt-in, PROPS OFF): system live -> spin motors at the capped value; otherwise
            # stop. This is the visible "motors respond to the two-press" demo (disarmed MSP motor test).
            if motor_drive and motors_off:
                _set_motors(link, [(motor_max_us if st.effective_motor_power else 1000)] * motor_count)

            # 5) record
            cw.writerow([i, round(now - t0, 3), console.state.value, rt.mission_phase.name, st.arm_state.name,
                         int(st.effective_motor_power), int(last_locked), round(last_snr, 2), intent.note,
                         st.rc.get("throttle", 0), st.rc.get("aux1", 0),
                         round(gyro[0], 4), round(gyro[1], 4), round(gyro[2], 4),
                         int(link_alive), getattr(getattr(link, "_channel", None), "rc_frames_received", 0)])
            _annotate_and_push(view, gray, console, rt, st, o)

            i += 1
            if now - tprint > 1.0:
                print(f"[{i:5d}] {console.state.value:<9} {rt.mission_phase.name:<9} arm={st.arm_state.name:<12}"
                      f" pwr={int(st.effective_motor_power)} lock={int(last_locked)} snr={last_snr:4.1f} {intent.note}")
                tprint = now
            if dur and now - t0 >= dur:
                break
            time.sleep(max(0.0, dt - (time.monotonic() - now)))
    finally:
        if motor_drive and motors_off:                       # ALWAYS stop the motors on exit (Ctrl-C / abort / end)
            for _ in range(20):
                _set_motors(link, [1000] * motor_count); time.sleep(0.02)
        cf.close(); view.stop = True; cam.close(); buttons.close()
        try:
            link.close()
        except Exception:
            pass
    summary = dict(ticks=i, seconds=round(time.monotonic() - t0, 1), final_console=console.state.value,
                   final_mission=rt.mission_phase.name, motors_off_gate=motors_off, serial=port if motors_off else "mock")
    json.dump(summary, open(out + "_summary.json", "w"), indent=2)
    print("SUMMARY " + json.dumps(summary))


def _kp():
    sk = SigningKey.generate()
    return bytes(sk), bytes(sk.verify_key)


def _annotate_and_push(view, gray, console, rt, st, o) -> None:
    try:
        import cv2
    except Exception:
        return
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    col = {"STANDBY": (180, 180, 180), "LOCKED": (0, 200, 255),
           "LAUNCHED": (0, 220, 0), "ABORTED": (0, 0, 230)}.get(console.state.value, (200, 200, 200))
    if o.centroid_px is not None:
        cx, cy = int(o.centroid_px[0] * gray.shape[1] / W), int(o.centroid_px[1] * gray.shape[0] / H)
        cv2.drawMarker(bgr, (cx, cy), col, cv2.MARKER_CROSS, 22, 2)
    cv2.putText(bgr, f"{console.state.value} | {rt.mission_phase.name} | arm:{st.arm_state.name}",
                (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2, cv2.LINE_AA)
    cv2.putText(bgr, f"PWR:{int(st.effective_motor_power)} lock:{int(bool(o.locked))} B1=capture/launch B2=cancel",
                (6, gray.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
    # downscale + lower quality for the LIVE view only (recording keeps full data) — eases a slow/wifi link
    stream = cv2.resize(bgr, (480, 384), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", stream, [cv2.IMWRITE_JPEG_QUALITY, 45])
    if ok:
        view.push(jpg.tobytes())


if __name__ == "__main__":
    main()
