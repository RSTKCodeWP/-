"""
Persistent multi-band HackRF monitor web app (stdlib HTTP server, no framework).

A single HackRF can only sweep one range at a time, so a scheduler thread
ROTATES the radio across three bands, dwelling on each in turn (equal rotation):

  * VTX    5288-5962 MHz  -> FPV video channel estimation (vtx.VTXAnalyzer)
  * 2.4G   2100-2500 MHz  -> ELRS / FHSS link detection (elrs.ELRSDetector)
  * 900M    700-1200 MHz  -> ELRS / FHSS link detection

The browser dashboard shows all three waterfalls side by side plus a live ELRS
status panel. Each band updates in bursts (only while the radio is dwelling on
it). Quick machine checks:

  GET /api/channels   -> active VTX channels      (python -m hackrf_api vtx)
  GET /api/elrs       -> ELRS presence/confidence (python -m hackrf_api elrs)

It can also TRANSMIT fake VTX test signals (to exercise the detector / bench):

  POST /api/emit/start  {mode,channels,seconds,...,confirm:true} -> start (GUARDED)
        mode="broadcast": emit channels[] (one steady, many = round-robin).
        mode="sweep":     cycle Raceband R1..R8 (seconds_each on / gap_s off).
  POST /api/emit/stop   -> stop the running broadcast/sweep
  GET  /api/emit        -> status (idle|running|done|error)

Broadcasting pauses the band scheduler and takes exclusive ownership of the
radio while active, then resumes monitoring. Guarded: confirm=true required.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse, parse_qs

import numpy as np

from .core import HackRF, Spectrum, HackRFNotFoundError, HackRFError
from . import vtx
from . import elrs
from . import vtx_emit
from .webui import INDEX_HTML

# Bound on how long a single emit may stay on the air (seconds).
EMIT_MAX_SECONDS = 30.0


@dataclass
class BandCfg:
    id: str
    name: str
    lo_mhz: float
    hi_mhz: float
    bin_hz: int
    kind: str            # "vtx" | "elrs"
    dwell: int           # sweeps per visit
    amp: bool
    lna: int = 32
    vga: int = 30
    elrs_band: object = None   # elrs.ELRSBand for kind == "elrs"


DEFAULT_BANDS = [
    BandCfg("vtx", "VTX 5.3-6 GHz", vtx.VIEW_LOW_MHZ, vtx.VIEW_HIGH_MHZ,
            1_000_000, "vtx", dwell=18, amp=True),
    BandCfg("elrs24", "2.4 GHz ELRS", elrs.BAND_24.sweep_lo_mhz,
            elrs.BAND_24.sweep_hi_mhz, 500_000, "elrs", dwell=30, amp=False,
            elrs_band=elrs.BAND_24),
    BandCfg("elrs900", "900 MHz ELRS", elrs.BAND_900.sweep_lo_mhz,
            elrs.BAND_900.sweep_hi_mhz, 500_000, "elrs", dwell=30, amp=False,
            elrs_band=elrs.BAND_900),
]


class BandState:
    """Runtime state + ring buffer for one band."""

    def __init__(self, cfg: BandCfg, history: int):
        self.cfg = cfg
        self.history = history
        self.lock = threading.Lock()
        self.freqs_mhz: list = []
        self.rows: deque = deque(maxlen=history)   # (idx, np.ndarray)
        self.count = 0
        self.maxhold: Optional[np.ndarray] = None
        self.avg: Optional[np.ndarray] = None
        self.analysis: dict = {}
        self.last_update = 0.0
        # per-kind analyzers
        if cfg.kind == "vtx":
            self.vtx_analyzer = vtx.VTXAnalyzer()
            self._vtx_last_t = None
        elif cfg.kind == "elrs":
            amb = elrs.load_ambient(cfg.elrs_band)
            self.elrs_detector = elrs.ELRSDetector(cfg.elrs_band, ambient=amb)
            self.elrs_has_ambient = amb is not None
            self.elrs_conf_ewma = 0.0
            self.elrs_present_ewma = 0.0

    def ingest(self, freqs_hz: np.ndarray, block: np.ndarray):
        """block: (n_sweeps, n_freqs) from one dwell."""
        cfg = self.cfg
        now = time.time()
        fmhz = (freqs_hz / 1e6).round(3).tolist()

        if cfg.kind == "vtx":
            analysis = None
            for r in range(block.shape[0]):
                row = block[r]
                dt = 0.12 if self._vtx_last_t is None else min(2.0, max(0.02, 0.12))
                spec = Spectrum(freqs_hz, row, float(cfg.bin_hz), 1,
                                cfg.lo_mhz * 1e6, cfg.hi_mhz * 1e6)
                analysis = self.vtx_analyzer.update(spec, dt)
            self._vtx_last_t = now
        else:  # elrs
            res = self.elrs_detector.detect(freqs_hz, block)
            # smooth the GATED presence (not raw confidence — ambient still
            # scores high confidence but must be rejected) so the light is steady
            self.elrs_conf_ewma = 0.5 * self.elrs_conf_ewma + 0.5 * res.confidence
            self.elrs_present_ewma = (0.5 * self.elrs_present_ewma
                                      + 0.5 * (1.0 if res.present else 0.0))
            d = res.to_dict()
            d["confidence_smoothed"] = round(self.elrs_conf_ewma, 2)
            d["presence"] = round(self.elrs_present_ewma, 2)   # gated, smoothed
            d["has_ambient"] = self.elrs_has_ambient
            present = self.elrs_present_ewma >= 0.5
            d["present"] = present
            if present:
                d["verdict"] = "tx_active"
            # else keep the detector's verdict (ambient / weak / quiet)
            analysis = d

        maxhold = block.max(axis=0)
        avg = block.mean(axis=0)
        with self.lock:
            self.freqs_mhz = fmhz
            for r in range(block.shape[0]):
                self.count += 1
                self.rows.append((self.count, block[r]))
            self.maxhold = maxhold
            self.avg = avg
            self.analysis = analysis or self.analysis
            self.last_update = now

    def data(self, since: int) -> dict:
        with self.lock:
            new = [(i, r) for (i, r) in self.rows if i > since]
            count = self.count
            analysis = self.analysis
            maxhold = self.maxhold
            avg = self.avg
            last = self.last_update
        rows = [[round(float(v), 1) for v in r] for (_i, r) in new]
        return {
            "id": self.cfg.id,
            "count": count,
            "rows": rows,
            "maxhold": None if maxhold is None else [round(float(v), 1) for v in maxhold],
            "avg": None if avg is None else [round(float(v), 1) for v in avg],
            "analysis": analysis,
            "age_s": round(time.time() - last, 1) if last else None,
        }


class MultiBandMonitor:
    def __init__(self, bands=None, history=160, serial=None):
        self.bands_cfg = bands or DEFAULT_BANDS
        self.serial = serial
        self.hrf = HackRF(serial=serial)
        if not self.hrf.is_present():
            raise HackRFNotFoundError("no HackRF device found")
        self.states = {b.id: BandState(b, history) for b in self.bands_cfg}
        self.cfg_by_id = {b.id: b for b in self.bands_cfg}
        self.history = history
        # Visit schedule: VTX changes fast, so ping it before EACH ELRS band
        # (2 VTX pings per full rotation) -> VTX updates ~2x as often.
        vtx_ids = [b.id for b in self.bands_cfg if b.kind == "vtx"]
        elrs_ids = [b.id for b in self.bands_cfg if b.kind == "elrs"]
        self.schedule = []
        for e in elrs_ids:
            self.schedule += vtx_ids + [e]
        if not self.schedule:
            self.schedule = [b.id for b in self.bands_cfg]
        self._stop = threading.Event()
        self.paused: set = set()   # band ids the scheduler should skip (UI pause)
        # Radio exclusivity for TX: the scheduler holds `_radio` while sweeping; an
        # emit sets `_pause` (so the scheduler yields between bands) then takes
        # `_radio` for the transmission. Only one process may own the HackRF.
        self._radio = threading.Lock()
        self._pause = threading.Event()
        self._emit_lock = threading.Lock()
        self._emit_stop = threading.Event()    # signals a running broadcast to end
        self._emit_timer = None                # optional fixed-duration auto-stop
        self.emit = {"status": "idle"}
        self.active_band = None
        self.cycle = 0
        self.error = None
        self.started = time.time()
        self._thread = threading.Thread(target=self._scheduler, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def set_paused(self, band_id: str, paused: bool) -> dict:
        if band_id not in self.cfg_by_id:
            return {"error": "unknown band", "id": band_id}
        if paused:
            self.paused.add(band_id)
        else:
            self.paused.discard(band_id)
        return {"id": band_id, "paused": band_id in self.paused,
                "paused_all": sorted(self.paused)}

    def _scheduler(self):
        while not self._stop.is_set():
            active = [bid for bid in self.schedule if bid not in self.paused]
            if not active:                 # everything paused -> idle the radio
                self.active_band = None
                self._stop.wait(0.3)
                continue
            for bid in active:
                if self._stop.is_set():
                    break
                if bid in self.paused:     # paused mid-rotation (UI pause)
                    continue
                # Yield the radio while an emit is in progress (or pending).
                while self._pause.is_set() and not self._stop.is_set():
                    time.sleep(0.05)
                if self._stop.is_set():
                    break
                b = self.cfg_by_id[bid]
                self.active_band = b.id
                try:
                    with self._radio:
                        wf = self.hrf.waterfall(
                            b.lo_mhz, b.hi_mhz, rows=b.dwell, bin_width_hz=b.bin_hz,
                            lna_gain=b.lna, vga_gain=b.vga, amp=b.amp,
                        )
                    if wf.freqs_hz.size:
                        self.states[b.id].ingest(wf.freqs_hz, wf.power_dbm)
                    self.error = None
                except Exception as e:  # keep rotating even if one band hiccups
                    self.error = f"{b.id}: {e}"
            self.cycle += 1

    # -- transmit (broadcast fake VTX test signals) -------------------------
    def start_broadcast(self, mode="broadcast", channels=None, seconds=0.0,
                        seconds_each=None, gap_s=0.0, mw=25.0, gain=None,
                        waveform="cw") -> dict:
        """Validate + kick off a broadcast in a worker thread. Returns at once.

        mode="broadcast": emit `channels` (one steady, or several as a fast
        round-robin so they read simultaneous). `seconds` is the total on-air
        time; 0 = until stopped.
        mode="sweep": cycle Raceband R1..R8, `seconds_each` on / `gap_s` off,
        looping until stopped.

        Either way the worker pauses the band scheduler and owns the radio while
        active. Stop with stop_broadcast().
        """
        if mode == "sweep":
            chans = [f"R{i}" for i in range(1, 9)]
            seconds_each = float(seconds_each or 10.0)
            gap_s = float(gap_s or 3.0)
            seconds = 0.0   # continuous toggle
            label = "sweep R1-R8"
        else:
            try:
                resolved = [vtx_emit.resolve_channel(c) for c in (channels or [])]
            except HackRFError as e:
                return {"ok": False, "error": str(e)}
            if not resolved:
                return {"ok": False, "error": "no channels given"}
            chans = [c.name for c in resolved]
            # one channel -> steady-ish (re-key every 2s, stoppable); several ->
            # fast round-robin so a max-hold view shows them all "at once".
            seconds_each = float(seconds_each or (2.0 if len(chans) == 1 else 0.4))
            gap_s = float(gap_s or 0.0)
            label = " + ".join(chans)
        try:
            seconds = max(0.0, float(seconds))
        except (TypeError, ValueError):
            return {"ok": False, "error": "seconds must be a number"}
        gain = int(gain) if gain is not None else vtx_emit.mw_to_tx_gain(float(mw))
        gain = max(0, min(47, gain))

        with self._emit_lock:
            if self.emit.get("status") == "running":
                return {"ok": False, "error": "broadcast_in_progress",
                        "emit": self.emit}
            now = time.time()
            self.emit = {
                "status": "running", "mode": mode, "channels": chans,
                "label": label, "seconds_each": seconds_each, "gap_s": gap_s,
                "tx_vga_gain_db": gain, "waveform": waveform,
                "started_at": now,
                "ends_at": (now + seconds) if seconds > 0 else None,
                "current": None,
            }
        self._emit_stop.clear()
        if seconds > 0:   # fixed-duration broadcast: auto-stop at the deadline
            self._emit_timer = threading.Timer(seconds, self._emit_stop.set)
            self._emit_timer.daemon = True
            self._emit_timer.start()
        threading.Thread(
            target=self._broadcast_worker,
            args=(chans, seconds_each, gap_s, gain, waveform), daemon=True,
        ).start()
        return {"ok": True, "accepted": True, "emit": self.emit_status()}

    def stop_broadcast(self) -> dict:
        """Signal a running broadcast/sweep to stop after the current hop."""
        self._emit_stop.set()
        if self._emit_timer is not None:
            self._emit_timer.cancel()
            self._emit_timer = None
        return self.emit_status()

    def _broadcast_worker(self, channels, seconds_each, gap_s, gain, waveform):
        def before(step):
            with self._emit_lock:
                if self.emit.get("status") == "running":
                    self.emit["current"] = {"channel": step["channel"],
                                            "freq_mhz": step["freq_mhz"]}
        self._pause.set()
        try:
            with self._radio:   # wait out any in-flight sweep, then own the radio
                res = vtx_emit.emit_sweep(
                    channels=channels, waveform=waveform, seconds_each=seconds_each,
                    gap_s=gap_s, cycles=10 ** 9, tx_vga_gain=gain, serial=self.serial,
                    i_understand_tx_may_be_illegal=True, before_step=before,
                    should_stop=self._emit_stop.is_set,
                )
            with self._emit_lock:
                self.emit = {"status": "done", "ended_at": time.time(),
                             "channels": channels, "hops": len(res),
                             "mode": self.emit.get("mode")}
        except Exception as e:
            with self._emit_lock:
                self.emit = {"status": "error", "error": str(e),
                             "channels": channels}
        finally:
            self._emit_stop.clear()
            self._pause.clear()

    def emit_status(self) -> dict:
        with self._emit_lock:
            e = dict(self.emit)
        if e.get("status") == "running" and e.get("ends_at"):
            e["remaining_s"] = round(max(0.0, e["ends_at"] - time.time()), 1)
        return e

    # -- snapshots ----------------------------------------------------------
    def meta(self) -> dict:
        out = []
        for b in self.bands_cfg:
            st = self.states[b.id]
            with st.lock:
                freqs = st.freqs_mhz
            entry = {
                "id": b.id, "name": b.name, "kind": b.kind,
                "lo_mhz": b.lo_mhz, "hi_mhz": b.hi_mhz,
                "bin_hz": b.bin_hz, "history": self.history,
                "num_bins": len(freqs), "freqs_mhz": freqs,
                "paused": b.id in self.paused,
            }
            if b.kind == "vtx":
                entry["bands"] = vtx.VTX_BANDS
            if b.kind == "elrs" and b.elrs_band is not None:
                entry["focus_lo_mhz"] = b.elrs_band.focus_lo_mhz
                entry["focus_hi_mhz"] = b.elrs_band.focus_hi_mhz
            out.append(entry)
        return {"bands": out, "history": self.history}

    def band_data(self, band_id: str, since: int) -> dict:
        st = self.states.get(band_id)
        if st is None:
            return {"error": "unknown band"}
        d = st.data(since)
        d["active_band"] = self.active_band
        d["cycle"] = self.cycle
        d["error"] = self.error
        d["paused"] = band_id in self.paused
        return d

    def elrs_summary(self) -> dict:
        out = {}
        for b in self.bands_cfg:
            if b.kind == "elrs":
                with self.states[b.id].lock:
                    out[b.id] = self.states[b.id].analysis or {"name": b.name}
        return {"ok": self.error is None, "cycle": self.cycle,
                "uptime_s": round(time.time() - self.started, 1), "elrs": out}

    def vtx_summary(self) -> dict:
        st = self.states.get("vtx")
        if st is None:
            return {"ok": False, "error": "no vtx band"}
        with st.lock:
            a = st.analysis or {}
            cfg = st.cfg
        return {
            "ok": self.error is None, "cycle": self.cycle,
            "band": f"{cfg.lo_mhz:.0f}-{cfg.hi_mhz:.0f} MHz",
            "active": a.get("active", []),
            "signals": a.get("signals", []),
            "floor_dbm": a.get("floor_dbm"),
            "threshold_db": a.get("threshold_db"),
        }


_MON: Optional[MultiBandMonitor] = None


class Handler(BaseHTTPRequestHandler):
    server_version = "hackrf-multiband/0.2"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                self._send(200, INDEX_HTML, "text/html; charset=utf-8")
            elif path == "/api/meta":
                self._send(200, _MON.meta())
            elif path == "/api/band":
                bid = q.get("id", [""])[0]
                since = int(q.get("since", ["0"])[0])
                self._send(200, _MON.band_data(bid, since))
            elif path == "/api/pause":
                bid = q.get("id", [""])[0]
                pv = q.get("paused", ["1"])[0].lower()
                paused = pv not in ("0", "false", "no", "")
                self._send(200, _MON.set_paused(bid, paused))
            elif path == "/api/elrs":
                self._send(200, _MON.elrs_summary())
            elif path == "/api/channels":
                self._send(200, _MON.vtx_summary())
            elif path == "/api/emit":
                self._send(200, _MON.emit_status())
            elif path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
            else:
                self._send(404, {"error": "not found", "path": path})
        except BrokenPipeError:
            pass
        except Exception as e:  # pragma: no cover
            try:
                self._send(500, {"error": str(e)})
            except Exception:
                pass

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/emit/stop":
                self._send(200, _MON.stop_broadcast())
                return
            if path not in ("/api/emit/start", "/api/emit"):
                self._send(404, {"error": "not found", "path": path})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except Exception:
                self._send(400, {"ok": False, "error": "invalid JSON body"})
                return
            # TX is guarded: refuse unless the caller explicitly confirms. This
            # is the propose->confirm gate; the UI shows a dialog before sending.
            if not body.get("confirm"):
                self._send(403, {"ok": False, "error": "tx_guard",
                                 "detail": "transmitting requires confirm=true; "
                                 "ensure you may legally transmit here"})
                return
            res = _MON.start_broadcast(
                mode=body.get("mode", "broadcast"),
                channels=body.get("channels"),
                seconds=body.get("seconds", 0),
                seconds_each=body.get("seconds_each"),
                gap_s=body.get("gap_s", 0),
                mw=body.get("mw", 25),
                gain=body.get("gain"),
                waveform=body.get("waveform", "cw"),
            )
            self._send(200 if res.get("ok") else 400, res)
        except BrokenPipeError:
            pass
        except Exception as e:  # pragma: no cover
            try:
                self._send(500, {"ok": False, "error": str(e)})
            except Exception:
                pass


def serve(port=8080, host="127.0.0.1", history=160, serial=None, **_ignore):
    """Start the multi-band monitor + HTTP server. Blocks forever."""
    global _MON
    _MON = MultiBandMonitor(history=history, serial=serial)
    _MON.start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"Multi-band monitor live at {url}")
    print(f"  bands: " + ", ".join(f"{b.name}" for b in _MON.bands_cfg))
    print(f"  quick checks: {url}api/channels  |  {url}api/elrs")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _MON.stop()
        httpd.server_close()
