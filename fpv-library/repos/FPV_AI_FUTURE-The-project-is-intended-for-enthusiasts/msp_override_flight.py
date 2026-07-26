"""MSP_OVERRIDE flight bridge (Block-3 hardware phase) -- REAL flight test WITH a manual backup.

THE POINT
---------
Fly the interceptor manually on your normal RC transmitter, and let the SEEKER SYSTEM take the
sticks only while YOU hold a toggle switch. The switch is an AUX channel on your transmitter mapped
to Betaflight's ``MSP OVERRIDE`` mode:

    switch DOWN  -> Betaflight uses the RECEIVER  -> you fly manually (the safety layer)
    switch UP    -> Betaflight uses this Pi's MSP RC on the masked axes  -> the system flies
    flip DOWN    -> instant manual reclaim (the FC does the handover, not this code)

Two safety properties come FROM BETAFLIGHT, not from this script, so they hold even if the Pi
crashes:  (1) arming stays on the receiver -- this bridge NEVER arms;  (2) if the MSP RC stream
stops (Pi dies, USB pulled, loop hangs) Betaflight's MSP-override times out and falls back to the
receiver = your sticks.  This script's job is only to compute good channels and stream them, and to
be conservative when it is unsure.

MODES
-----
  scan  -- print the live MSP_RC channels so you can identify which index is your toggle (flip it
           and watch which number jumps).  Sends NOTHING to the FC.
  dry   -- run the full camera->perception->guidance chain and LOG what it WOULD command, reading
           the switch, but send NOTHING.  Zero flight authority.  Use to validate the system in the
           air under pure manual control before ever giving it a channel.
  live  -- stream MSP_SET_RAW_RC continuously.  When the switch is UP and a target is locked, the
           masked axes carry the guidance command (throttle hard-capped).  When the switch is DOWN,
           neutral is streamed (Betaflight ignores it -- the mode is off).  When the switch is UP but
           the target is lost, the bridge commands LEVEL + a gentle throttle and waits for you.

Betaflight setup (do this in Configurator FIRST, props OFF -- see docs/FLIGHT_TEST_OVERRIDE.md):
    feature MSP_OVERRIDE ;  set msp_override_channels_mask = <axes> ;  Modes tab: MSP OVERRIDE on
    your toggle AUX.  Keep your real receiver as the RX -- do NOT set MSP as the RX provider.

This bridge is deliberately SEPARATE from the SAFE default seeker.service (perception+web+record).
It is the deliberate-authority tool, run by hand, exactly like run_motors.sh.
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field

from fpv.guidance.pipeline import PipelineOutput, SeekerGuidancePipeline
from fpv_ai.betaflight_link.msp_codec import (RC_CHANNEL_ORDER, US_MID, US_MIN, MSP_RC,
                                              ai_command_to_channels, channels_to_list, decode_rc)
from fpv_ai.betaflight_link.serial_link import MspLink

_FLIGHT_AXES = ("roll", "pitch", "yaw", "throttle")


@dataclass(frozen=True)
class BridgeConfig:
    switch_index: int = 5                 # MSP_RC index of the toggle. Owner mapped the override to AUX2,
                                          # and MSP RC order is R,P,Y,T,AUX1,AUX2,... so AUX2 == 5.
    switch_threshold_us: int = 1600       # switch >= this == ENGAGED (system flies)
    override_axes: frozenset = field(default_factory=lambda: frozenset(_FLIGHT_AXES))  # which axes system takes
    throttle_max_us: int = 1700           # HARD throttle ceiling given to guidance -- SET FOR YOUR AIRCRAFT
    throttle_min_us: int = 1000           # throttle floor (idle)
    lostlock_throttle_us: int = 1450      # engaged but NO target -> level + this gentle throttle; you retake
    hz: float = 50.0                      # MSP RC stream rate (Betaflight wants a steady stream)


@dataclass
class BridgeSample:
    t: float
    engaged: bool
    switch_us: int
    tracking_state: str
    locked: bool
    have_cmd: bool
    sent: bool                            # did we actually transmit RC this tick?
    channels_us: dict                     # what we sent (or would send in dry)
    cmd: object | None                    # the AICommand (roll/pitch/yaw/throttle) or None
    aux: tuple = (0, 0, 0, 0)             # AUX1..4 raw us (to spot which channel is your toggle)
    link_ok: bool = True                  # False if this tick had no fresh RC (held the last value)


def read_rc_channels(link: MspLink, *, attempts: int = 12, sleep_s: float = 0.001) -> list[int] | None:
    """Request MSP_RC and return the decoded channel pulse widths, or None if no reply in time.

    While MSP OVERRIDE is active, MSP_RC reports the POST-override rcData for the masked axes (i.e.
    our own values) but the UNmasked axes -- crucially the toggle AUX -- still reflect the receiver,
    so the switch is always readable here."""
    try:
        link.request(MSP_RC)
        for _ in range(attempts):
            for fr in link.poll():
                if fr.function == MSP_RC:
                    return decode_rc(fr.payload)
            time.sleep(sleep_s)
    except Exception:
        return None                       # transient link glitch -> no RC this tick (bridge -> neutral/hold)
    return None


class OverrideFlightBridge:
    """Camera + seeker guidance -> masked MSP_OVERRIDE channels, gated by a transmitter toggle.

    The FC owns arming, failsafe, and the manual layer; this class only computes channels and, in
    ``live`` mode, streams them.  It is default-DENY: no target / not engaged / dry mode -> the
    aircraft is left to the pilot."""

    def __init__(self, capture, link: MspLink, pipe: SeekerGuidancePipeline,
                 cfg: BridgeConfig | None = None, *, live: bool = False) -> None:
        self.capture = capture
        self.link = link
        self.pipe = pipe
        self.cfg = cfg or BridgeConfig()
        self.live = live
        self._last_cmd = None            # hold the last guidance between camera frames (loop > cam rate)
        self._last_state = "NO_FRAME"
        self._last_locked = False
        self._last_rc = None             # hold the last good RC across a link glitch (stable switch state)

    def _perceive(self, now: float, dt: float) -> None:
        frame = self.capture.frame_u16()
        if frame is None:
            return                        # no new frame -> keep the last command (brief hold)
        out: PipelineOutput = self.pipe.step(now, frame, (0.0, 0.0, 0.0), dt)   # gyro off (ego needs S0)
        self._last_cmd = out.command      # AICommand when locked & not aborted, else None
        self._last_state = out.tracking_state
        self._last_locked = bool(out.locked)

    def _channels(self, engaged: bool, rc: list[int] | None) -> dict:
        cfg = self.cfg
        ch = {"roll": US_MID, "pitch": US_MID, "yaw": US_MID, "throttle": cfg.throttle_min_us,
              "aux1": US_MIN, "aux2": US_MIN, "aux3": US_MIN, "aux4": US_MIN}
        if rc is not None:                # pass the pilot's AUX values through (harmless; not masked)
            for i, name in enumerate(RC_CHANNEL_ORDER):
                if name.startswith("aux") and i < len(rc):
                    ch[name] = int(rc[i])
        if not engaged:
            return ch                     # neutral/idle -> Betaflight ignores it (mode off) -> RX flies
        cmd = self._last_cmd
        if cmd is not None:               # ENGAGED + target: guidance on the masked axes
            g = ai_command_to_channels(cmd)
            g["throttle"] = max(cfg.throttle_min_us, min(int(g["throttle"]), cfg.throttle_max_us))  # HARD cap
            for name in _FLIGHT_AXES:
                if name in cfg.override_axes:
                    ch[name] = int(g[name])
                elif rc is not None:      # unmasked axis -> pass the pilot's stick through
                    ch[name] = int(rc[RC_CHANNEL_ORDER.index(name)])
            return ch
        # ENGAGED but NO target -> safe posture: level attitude, gentle throttle, pilot retakes.
        ch["roll"] = ch["pitch"] = ch["yaw"] = US_MID
        ch["throttle"] = cfg.lostlock_throttle_us
        return ch

    def step(self, now: float, dt: float) -> BridgeSample:
        self._perceive(now, dt)
        fresh = read_rc_channels(self.link)
        link_ok = fresh is not None
        if link_ok:
            self._last_rc = fresh         # remember the last good frame
        rc = fresh if link_ok else self._last_rc   # HOLD last good on a glitch -> switch never flickers to 0
        switch_us = int(rc[self.cfg.switch_index]) if (rc is not None and self.cfg.switch_index < len(rc)) else 0
        engaged = switch_us >= self.cfg.switch_threshold_us
        aux = tuple(int(rc[i]) if (rc is not None and i < len(rc)) else 0 for i in (4, 5, 6, 7))
        ch = self._channels(engaged, rc)
        sent = False
        if self.live:                     # live: stream continuously so BF's override never starves
            try:
                self.link.send_set_raw_rc(channels_to_list(ch))
                sent = True
            except Exception:
                sent = False              # dropped frame on a link glitch -> FC override failsafe -> RX
        return BridgeSample(t=now, engaged=engaged, switch_us=switch_us, tracking_state=self._last_state,
                            locked=self._last_locked, have_cmd=self._last_cmd is not None, sent=sent,
                            channels_us=ch, cmd=self._last_cmd, aux=aux, link_ok=link_ok)


def _fmt_cmd(cmd) -> str:
    if cmd is None:
        return "-- (no target)"
    return "roll=%+.2f pitch=%+.2f yaw=%+.2f thr=%.2f" % (
        cmd.roll_cmd, cmd.pitch_cmd, cmd.yaw_rate_cmd, cmd.throttle_cmd)


def main() -> None:  # pragma: no cover - hardware bench
    ap = argparse.ArgumentParser(description="MSP_OVERRIDE flight bridge -- manual RC + toggle-gated system control")
    ap.add_argument("mode", choices=("scan", "dry", "live"), help="scan=find toggle; dry=log only; live=stream RC")
    ap.add_argument("--device", default="/dev/video0", help="thermal capture (CVBS->USB grabber)")
    ap.add_argument("--width", type=int, default=720)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fourcc", default="MJPG")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "W", "H"), default=None)
    ap.add_argument("--hfov", type=float, default=48.7)
    ap.add_argument("--port", default="/dev/ttyAMA0", help="FC MSP UART")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--switch-index", type=int, default=5, help="MSP_RC index of the toggle (AUX2==5; find it with `scan`)")
    ap.add_argument("--switch-threshold-us", type=int, default=1600)
    ap.add_argument("--axes", default="rpyt", help="axes the system takes when engaged (subset of r,p,y,t)")
    ap.add_argument("--throttle-max-us", type=int, default=1700, help="HARD throttle ceiling -- SET FOR YOUR AIRCRAFT")
    ap.add_argument("--lostlock-throttle-us", type=int, default=1450)
    ap.add_argument("--no-camera", action="store_true",
                    help="skip the thermal camera: just show the toggle->override handover (engaged => level+gentle)")
    ap.add_argument("--up-camera", action="store_true",
                    help="camera boresight = straight UP: intercept from below (PN in roll+pitch, throttle climbs)")
    ap.add_argument("--climb-throttle", type=float, default=0.62, help="up-camera: throttle that closes the vertical gap")
    ap.add_argument("--designate", type=float, nargs=2, metavar=("CX", "CY"), default=None,
                    help="acquire a target near this pixel at start (default: frame centre)")
    ap.add_argument("--hz", type=float, default=50.0)
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--log", default=None, help="CSV log path")
    args = ap.parse_args()

    axmap = {"r": "roll", "p": "pitch", "y": "yaw", "t": "throttle"}
    axes = frozenset(axmap[c] for c in args.axes if c in axmap)
    cfg = BridgeConfig(switch_index=args.switch_index, switch_threshold_us=args.switch_threshold_us,
                       override_axes=axes, throttle_max_us=args.throttle_max_us,
                       lostlock_throttle_us=args.lostlock_throttle_us, hz=args.hz)

    link = MspLink.open_serial(args.port, args.baud, hardware_authorized=True)

    # --- scan: identify the toggle channel, send NOTHING ---
    if args.mode == "scan":
        print("SCAN -- flip your toggle and watch which index jumps (~1000 <-> ~2000). Ctrl-C to stop.")
        t0 = time.monotonic()
        while time.monotonic() - t0 < args.duration:
            rc = read_rc_channels(link)
            if rc is not None:
                print("  " + "  ".join("[%d]%4d" % (i, v) for i, v in enumerate(rc)))
            time.sleep(0.2)
        link.close()
        return

    if args.no_camera:                                # handover demo only -- no perception, no target
        class _NoCam:
            def frame_u16(self): return None
            def close(self): pass
        cap, pipe = _NoCam(), None
    else:
        from fpv_ai.sensor.thermal_capture import CaptureConfig, ThermalCapture, V4L2Source, ft640_intrinsics
        from fpv.guidance.command_map import PilotConfig
        cap = ThermalCapture(V4L2Source(args.device, width=args.width, height=args.height, fourcc=args.fourcc),
                             CaptureConfig(roi=tuple(args.roi) if args.roi else None, invert=args.invert))
        pilot_cfg = PilotConfig(up_looking_camera=True, climb_throttle=args.climb_throttle) if args.up_camera else None
        pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(hfov_deg=args.hfov), pilot_config=pilot_cfg)
        cx, cy = (args.designate if args.designate else (args.width / 2.0, args.height / 2.0))
        pipe.designate((float(cx), float(cy)))

    live = args.mode == "live"
    bridge = OverrideFlightBridge(cap, link, pipe, cfg, live=live)

    print("=" * 78)
    print(" MSP_OVERRIDE FLIGHT BRIDGE -- mode=%s  axes=%s  thr_cap=%dus" % (
        args.mode, "".join(sorted(args.axes)), cfg.throttle_max_us))
    if live:
        print(" LIVE: switch UP => system flies the masked axes. Switch DOWN or Pi loss => YOUR RX.")
        print(" Keep your thumb on the toggle. The FC owns arming + failsafe; this never arms.")
    else:
        print(" DRY: reads the switch + runs guidance, logs what it WOULD command. Sends NOTHING.")
    print("=" * 78)

    logf = open(args.log, "w") if args.log else None
    if logf:
        logf.write("t,engaged,switch_us,state,locked,have_cmd,sent,roll,pitch,yaw,throttle\n")

    t0 = last = time.monotonic()
    period = 1.0 / max(cfg.hz, 1.0)
    n = 0
    try:
        while time.monotonic() - t0 < args.duration:
            now = time.monotonic()
            dt = now - last
            last = now
            s = bridge.step(now, max(dt, 1e-4))
            n += 1
            if n % max(int(cfg.hz // 5), 1) == 0:
                print("[%6.1fs] %-4s sw=%4d AUX[1:%d 2:%d 3:%d 4:%d]%s %s%s" % (
                    now - t0, "ENGA" if s.engaged else "man", s.switch_us,
                    s.aux[0], s.aux[1], s.aux[2], s.aux[3], "" if s.link_ok else " (held)",
                    _fmt_cmd(s.cmd), "  >>SENT" if (s.sent and s.engaged) else ""))
            if logf:
                c = s.channels_us
                logf.write("%.3f,%d,%d,%s,%d,%d,%d,%d,%d,%d,%d\n" % (
                    now - t0, s.engaged, s.switch_us, s.tracking_state, s.locked, s.have_cmd, s.sent,
                    c["roll"], c["pitch"], c["yaw"], c["throttle"]))
            slack = period - (time.monotonic() - now)
            if slack > 0:
                time.sleep(slack)
    finally:
        if live:                          # release authority cleanly -> neutral, then the FC failsafe -> RX
            for _ in range(10):
                bridge.link.send_set_raw_rc(channels_to_list(
                    {"roll": US_MID, "pitch": US_MID, "yaw": US_MID, "throttle": cfg.throttle_min_us,
                     "aux1": US_MIN, "aux2": US_MIN, "aux3": US_MIN, "aux4": US_MIN}))
                time.sleep(0.02)
        cap.close()
        link.close()
        if logf:
            logf.close()
        print("[bridge] done (%d ticks). Manual RC was available the whole time." % n)


if __name__ == "__main__":
    main()
