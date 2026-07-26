import asyncio
import json
import os
import shutil
import ssl
import subprocess
import time
from datetime import datetime

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

RECORDINGS_DIR = os.path.expanduser("~/recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# Static client files (viewer/clips/watch/three.js) live next to this script, so
# serve them relative to it — works no matter where the repo is cloned. (Earlier
# these hardcoded ~/, which broke once the repo moved out of the home dir.)
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Keep at least this many GB free by deleting the oldest recordings before each
# new one starts. Set RECORDINGS_MIN_FREE_GB=0 to disable auto-cleanup.
RECORDINGS_MIN_FREE_GB = float(os.environ.get("RECORDINGS_MIN_FREE_GB", "2.0"))


def _recording_files():
    """Recording files, oldest first (by mtime)."""
    try:
        names = [n for n in os.listdir(RECORDINGS_DIR) if n.endswith(".h264")]
    except FileNotFoundError:
        return []
    paths = [os.path.join(RECORDINGS_DIR, n) for n in names]
    return sorted(paths, key=lambda p: os.path.getmtime(p))


def enforce_storage_limit():
    """Delete oldest recordings until >= RECORDINGS_MIN_FREE_GB is free.

    Never deletes the file currently being recorded. Returns the list of
    deleted paths (empty if nothing was removed / cleanup is disabled).
    """
    deleted = []
    if RECORDINGS_MIN_FREE_GB <= 0:
        return deleted
    while shutil.disk_usage(RECORDINGS_DIR).free / (1024**3) < RECORDINGS_MIN_FREE_GB:
        candidates = [p for p in _recording_files() if p != current_filename]
        if not candidates:
            break  # nothing left we're allowed to delete
        oldest = candidates[0]
        try:
            os.remove(oldest)
            deleted.append(oldest)
            print(f"[storage] freed space, deleted {os.path.basename(oldest)}")
        except OSError:
            break
    return deleted

# Camera resolution / recording bitrate, tunable via env vars without editing
# source. The WebRTC stream (lores) is software-encoded to H.264 by aiortc, so
# its resolution drives CPU load/heat on the Pi — the default is deliberately
# lighter (960x540) to keep temps down. Recording (main) stays 720p since it
# uses the hardware H.264 encoder. Bump either while watching `htop`/CPU temp.
# The lores (streamed) size must not exceed the main (recorded) size.
def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default

RECORD_WIDTH = _env_int("RECORD_WIDTH", 1280)
RECORD_HEIGHT = _env_int("RECORD_HEIGHT", 720)
STREAM_WIDTH = _env_int("STREAM_WIDTH", 960)
STREAM_HEIGHT = _env_int("STREAM_HEIGHT", 540)
RECORD_BITRATE = _env_int("RECORD_BITRATE", 0)  # bits/sec; 0 = encoder default

picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": (RECORD_WIDTH, RECORD_HEIGHT)},
    lores={"size": (STREAM_WIDTH, STREAM_HEIGHT), "format": "YUV420"}
)
picam2.configure(video_config)
picam2.start()
print(f"[camera] stream {STREAM_WIDTH}x{STREAM_HEIGHT}, record {RECORD_WIDTH}x{RECORD_HEIGHT}"
      + (f" @ {RECORD_BITRATE} bps" if RECORD_BITRATE else " (default bitrate)"))

recording = False
h264_encoder = None
current_filename = None
record_start_ts = None

class CameraVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        array = picam2.capture_array("lores")
        frame = VideoFrame.from_ndarray(array, format="yuv420p")
        frame.pts = pts
        frame.time_base = time_base
        return frame

pcs = set()

async def offer(request):
    params = await request.json()
    offer_desc = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    pc.addTrack(CameraVideoTrack())

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)

    await pc.setRemoteDescription(offer_desc)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

async def record_start(request):
    global recording, h264_encoder, current_filename, record_start_ts
    if recording:
        return web.json_response({"status": "already recording", "file": current_filename})

    enforce_storage_limit()
    record_start_ts = time.monotonic()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    current_filename = os.path.join(RECORDINGS_DIR, f"boat_{timestamp}.h264")

    h264_encoder = H264Encoder(bitrate=RECORD_BITRATE) if RECORD_BITRATE > 0 else H264Encoder()
    picam2.start_encoder(h264_encoder, FileOutput(current_filename))
    recording = True
    lights.on()

    return web.json_response({"status": "recording started", "file": current_filename})

async def record_stop(request):
    global recording, h264_encoder, current_filename
    if not recording:
        return web.json_response({"status": "not recording"})

    picam2.stop_encoder(h264_encoder)
    recording = False
    lights.off()
    finished_file = current_filename
    h264_encoder = None
    current_filename = None

    return web.json_response({"status": "recording stopped", "file": finished_file})

def _cpu_temp_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None


def _wifi_rssi_dbm():
    # Signal level in dBm from /proc/net/wireless (first station line).
    try:
        with open("/proc/net/wireless") as f:
            for line in f.readlines()[2:]:  # skip 2 header rows
                parts = line.split()
                if len(parts) >= 4 and parts[0].endswith(":"):
                    return int(float(parts[3].rstrip(".")))
    except Exception:
        pass
    return None


def _mem_free_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return round(int(line.split()[1]) / 1024)  # kB -> MB
    except Exception:
        pass
    return None


def _cpu_load():
    # 1-minute load average, and load normalized to core count (0..1+)
    try:
        load1 = os.getloadavg()[0]
        cores = os.cpu_count() or 1
        return round(load1, 2), round(load1 / cores, 2)
    except (OSError, AttributeError):
        return None, None


async def telemetry(request):
    total, used, free = shutil.disk_usage(RECORDINGS_DIR)
    load1, load_frac = _cpu_load()
    batt = battery.read()
    return web.json_response({
        "recording": recording,
        "file": current_filename,
        "storage_free_gb": round(free / (1024**3), 2),
        "storage_total_gb": round(total / (1024**3), 2),
        "cpu_temp_c": _cpu_temp_c(),
        "cpu_load": load1,
        "cpu_load_frac": load_frac,
        "armed": motors.armed,
        "lights_on": lights.state,
        "reverse_lights_on": lights.reverse_state,
        "battery_voltage": batt["voltage"],
        "battery_current_ma": batt["current_ma"],
        "battery_percent": batt["percent"],
        "battery_cells": batt["cells"],
        "battery_warn_pct": battery.warn_pct,
        "pan_angle": pan_tilt.pan,
        "tilt_angle": pan_tilt.tilt,
        "recordings_min_free_gb": RECORDINGS_MIN_FREE_GB,
        "wifi_rssi_dbm": _wifi_rssi_dbm(),
        "mem_free_mb": _mem_free_mb(),
        "rec_elapsed_s": round(time.monotonic() - record_start_ts) if (recording and record_start_ts) else None,
    })

async def recordings_list(request):
    items = []
    for path in reversed(_recording_files()):  # newest first
        st = os.stat(path)
        items.append({
            "name": os.path.basename(path),
            "size_bytes": st.st_size,
            "size_mb": round(st.st_size / (1024**2), 1),
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        })
    return web.json_response({"count": len(items), "recordings": items})


async def recording_download(request):
    name = os.path.basename(request.query.get("file", ""))  # basename guards traversal
    if not name.endswith(".h264"):
        return web.json_response({"error": "invalid file"}, status=400)
    path = os.path.join(RECORDINGS_DIR, name)
    if not os.path.isfile(path):
        return web.json_response({"error": "not found"}, status=404)
    return web.FileResponse(path)


async def recording_delete(request):
    name = os.path.basename(request.query.get("file", ""))  # basename guards traversal
    if not name.endswith(".h264"):
        return web.json_response({"error": "invalid file"}, status=400)
    path = os.path.join(RECORDINGS_DIR, name)
    if not os.path.isfile(path):
        return web.json_response({"error": "not found"}, status=404)
    if path == current_filename:
        return web.json_response({"error": "cannot delete the active recording"}, status=409)
    try:
        os.remove(path)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)
    return web.json_response({"status": "deleted", "file": name})


async def clips(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "clips.html"))


async def watch(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "watch.html"))


async def viewer(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "webxr_viewer.html"))

async def three_js(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "three.module.js"),
                             headers={"Content-Type": "application/javascript"})

latest_control = {"throttle": 0.0, "steer": 0.0, "reverse": False, "head_yaw": 0.0, "head_pitch": 0.0}

# Differential-thrust motor driver (L298N). Kept in its own module so it can be
# bench-tested independently; runs as a no-op if the GPIO libs aren't present, so
# streaming/recording still work on a machine without the hardware wired up.
from motor_control import MotorController
motors = MotorController()

# Front/rear running lights (GPIO-switched, see lights_control.py). Auto-triggered
# by record start/stop rather than a controller button. No-op if gpiozero absent.
from lights_control import LightController
lights = LightController()

# LiPo battery telemetry via INA219 (see battery_control.py). Reports all-None
# until the sensor is wired / the ina219 lib is present, so the HUD just shows --%.
from battery_control import BatteryMonitor
battery = BatteryMonitor()

# Camera pan/tilt head-tracking via PCA9685 (see pan_tilt_control.py). No-op until
# the PCA9685 + servos are wired; the viewer streams head yaw/pitch over /ws/control.
from pan_tilt_control import PanTiltController
pan_tilt = PanTiltController()

# Thermal safety: if the CPU sustains this temperature, shut the Pi down to
# protect it. The check needs a few consecutive strikes so a transient spike
# doesn't trigger it. Requires passwordless `sudo shutdown` (see HARDWARE.md).
CPU_OVERHEAT_C = float(os.environ.get("CPU_OVERHEAT_C", "80"))
_THERMAL_INTERVAL_S = 3
_THERMAL_STRIKES = 3

def _safe_poweroff(reason):
    """Bring the boat to a safe state, then power the Pi down.

    Shared by the thermal monitor and the in-headset shutdown combo so both
    take the same path: zero the motors, kill the lights, close any active
    recording cleanly (so the .mp4 isn't left half-written), then hand off to
    `sudo shutdown`. Returns True if the shutdown command launched.
    """
    print(f"[system] shutting down: {reason} — stopping motors/lights/recording")
    try:
        motors.stop()
    except Exception:
        pass
    try:
        lights.off()
    except Exception:
        pass
    global recording, h264_encoder
    if recording and h264_encoder is not None:
        try:
            picam2.stop_encoder(h264_encoder)
        except Exception:
            pass
        recording = False
    try:
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return True
    except Exception as e:
        print(f"[system] shutdown failed ({e}); is passwordless sudo set up?")
        return False

async def thermal_monitor():
    strikes = 0
    while True:
        await asyncio.sleep(_THERMAL_INTERVAL_S)
        t = _cpu_temp_c()
        if t is not None and t >= CPU_OVERHEAT_C:
            strikes += 1
            print(f"[thermal] {t}C >= {CPU_OVERHEAT_C}C overheat strike {strikes}/{_THERMAL_STRIKES}")
            if strikes >= _THERMAL_STRIKES:
                print("[thermal] OVERHEAT — shutting the Pi down to protect it")
                _safe_poweroff(f"thermal overheat ({t}C)")
                return
        else:
            strikes = 0

async def _on_startup(app):
    app["thermal_task"] = asyncio.create_task(thermal_monitor())

async def control_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
                latest_control["throttle"] = float(data.get("throttle", 0.0))
                latest_control["steer"] = float(data.get("steer", 0.0))
                latest_control["reverse"] = bool(data.get("reverse", False))
                # rear backup lights follow reverse mode (no-op until wired)
                lights.reverse(latest_control["reverse"])
                # throttle already carries the reverse sign from the client;
                # steering is differential, handled inside set_drive()
                motors.set_drive(latest_control["throttle"], latest_control["steer"])
                # head-tracking: aim the camera where the pilot looks (no-op until wired)
                if "yaw" in data or "pitch" in data:
                    # recenter first (freeze current aim as neutral) so the camera
                    # holds its position instead of snapping to a fixed angle
                    if data.get("recenter"):
                        pan_tilt.recenter()
                    latest_control["head_yaw"] = float(data.get("yaw", 0.0))
                    latest_control["head_pitch"] = float(data.get("pitch", 0.0))
                    pan_tilt.set_head(latest_control["head_yaw"], latest_control["head_pitch"])
                # echo the client timestamp back for control-latency measurement (J.9)
                ts = data.get("ts")
                if ts is not None:
                    await ws.send_json({"ack": ts})
            except Exception:
                pass
    # stop the motors (and drop reverse lights) if the control link drops;
    # recenter the camera so it isn't left cranked to one side
    motors.stop()
    lights.reverse(False)
    pan_tilt.center()
    return ws

async def control_status(request):
    return web.json_response(latest_control)

async def lights_toggle(request):
    # Manual running-lights toggle (single-tap Y in the viewer). Independent of
    # the auto-on-with-recording behavior — just flips the same LED groups.
    state = lights.toggle()
    return web.json_response({"lights": "on" if state else "off"})

async def system_shutdown(request):
    # Graceful, in-headset power-off (both grips + B, confirmed in the viewer).
    # Backgrounded via `sudo shutdown`, so respond before the box actually goes
    # down — the client shows a "shutting down" state rather than awaiting a
    # response the Pi may never send. Pairs with the physical master switch,
    # which stays the true power cutoff, flipped only after this completes.
    ok = _safe_poweroff("viewer shutdown combo")
    return web.json_response({"status": "shutting down" if ok else "shutdown unavailable"})

app = web.Application()
app.on_startup.append(_on_startup)
app.router.add_post("/offer", offer)
app.router.add_get("/record/start", record_start)
app.router.add_get("/record/stop", record_stop)
app.router.add_get("/telemetry", telemetry)
app.router.add_get("/recordings", recordings_list)
app.router.add_get("/recordings/download", recording_download)
app.router.add_get("/recordings/delete", recording_delete)
app.router.add_get("/clips", clips)
app.router.add_get("/watch", watch)
app.router.add_get("/viewer", viewer)
app.router.add_get("/three.module.js", three_js)
app.router.add_get("/ws/control", control_ws)
app.router.add_get("/control_status", control_status)
app.router.add_get("/lights/toggle", lights_toggle)
app.router.add_get("/system/shutdown", system_shutdown)

if __name__ == "__main__":
    # WebXR needs a secure context: the Quest browser only exposes navigator.xr
    # over HTTPS (or localhost), so VR + controller input require TLS. Drop a
    # self-signed cert at ~/cert.pem + ~/key.pem to serve HTTPS; without it we
    # fall back to plain HTTP (fine for desktop gamepad testing, but VR won't
    # start). Generate one with:
    #   openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    #     -keyout ~/key.pem -out ~/cert.pem -subj "/CN=fpv-boat"
    cert = os.path.expanduser("~/cert.pem")
    key = os.path.expanduser("~/key.pem")
    ssl_ctx = None
    if os.path.exists(cert) and os.path.exists(key):
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert, key)
        print("[server] HTTPS on :5000 (self-signed cert)")
    else:
        print("[server] no ~/cert.pem; plain HTTP on :5000 — VR needs HTTPS")
    web.run_app(app, host="0.0.0.0", port=5000, ssl_context=ssl_ctx)
