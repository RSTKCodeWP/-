"""
Command-line interface for hackrf_api.

Designed to be agent-friendly: every subcommand accepts --json and prints a
single JSON object to stdout, so the result can be parsed programmatically.
Without --json it prints a human-readable summary.

Examples
--------
    python -m hackrf_api info
    python -m hackrf_api info --json
    python -m hackrf_api scan 2400 2483.5 --bin 100000 --json
    python -m hackrf_api scan 433 435 --plot
    python -m hackrf_api record out.iq --freq 433920000 --rate 8e6 --secs 2
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import HackRF, HackRFError, HackRFNotFoundError


def _emit(obj, as_json: bool, human):
    if as_json:
        print(json.dumps(obj, indent=2))
    else:
        human(obj)


def cmd_info(args) -> int:
    hrf = HackRF(serial=args.device)
    info = hrf.info()
    if args.json:
        print(json.dumps({"ok": info.found, **info.to_dict()}, indent=2))
    else:
        if not info.found:
            print("No HackRF found.")
            return 1
        print(f"HackRF found: {info.board_name}")
        print(f"  serial            {info.serial}")
        print(f"  firmware          {info.firmware_version}  (API {info.api_version})")
        print(f"  hardware revision {info.hardware_revision}")
        print(f"  part id           {info.part_id}")
        print(f"  libhackrf         {info.libhackrf_version}")
    return 0 if info.found else 1


def cmd_scan(args) -> int:
    hrf = HackRF(serial=args.device)
    spec = hrf.scan(
        start_mhz=args.start,
        stop_mhz=args.stop,
        bin_width_hz=args.bin,
        sweeps=args.sweeps,
        lna_gain=args.lna,
        vga_gain=args.vga,
        amp=args.amp,
        antenna_power=args.antenna_power,
    )
    peaks = spec.peaks(threshold_db=args.threshold)
    if args.json:
        out = spec.to_dict(include_full=args.full)
        out["ok"] = True
        out["peaks"] = [s.to_dict() for s in peaks[: args.top]]
        print(json.dumps(out, indent=2))
    else:
        print(f"Scanned {args.start:.3f}-{args.stop:.3f} MHz  "
              f"bin={args.bin/1e3:.1f} kHz  sweeps={spec.sweeps}  "
              f"bins={spec.freqs_hz.size}")
        print(f"Noise floor ~ {spec.noise_floor_dbm:.1f} dBm, "
              f"peak {float(spec.power_dbm.max()):.1f} dBm")
        if args.plot:
            print()
            print(spec.ascii_plot())
        print(f"\nTop signals (>= floor+{args.threshold:.0f} dB):")
        if not peaks:
            print("  (none above threshold)")
        for s in peaks[: args.top]:
            print(f"  {s.freq_mhz:10.3f} MHz   {s.power_dbm:7.1f} dBm")
    return 0


def cmd_waterfall(args) -> int:
    import time
    hrf = HackRF(serial=args.device)
    t0 = time.time()
    wf = hrf.waterfall(
        start_mhz=args.start,
        stop_mhz=args.stop,
        rows=args.rows,
        bin_width_hz=args.bin,
        lna_gain=args.lna,
        vga_gain=args.vga,
        amp=args.amp,
        antenna_power=args.antenna_power,
    )
    elapsed = time.time() - t0
    png = wf.to_png(args.out, cmap=args.cmap, elapsed_s=elapsed)
    if args.json:
        out = wf.to_dict()
        out["ok"] = True
        out["png"] = png
        out["elapsed_s"] = round(elapsed, 2)
        print(json.dumps(out, indent=2))
    else:
        print(f"Captured {wf.num_rows} sweeps x {wf.freqs_hz.size} bins over "
              f"{args.start:.0f}-{args.stop:.0f} MHz in {elapsed:.1f}s")
        print(f"Noise floor ~ {wf.to_dict()['noise_floor_dbm']} dBm, "
              f"peak {wf.to_dict()['peak_dbm']} dBm")
        print(f"Waterfall PNG: {png}")
    return 0


def cmd_live(args) -> int:
    from .live import live_view
    live_view(
        start_mhz=args.start,
        stop_mhz=args.stop,
        bin_width_hz=args.bin,
        history=args.history,
        lna_gain=args.lna,
        vga_gain=args.vga,
        amp=not args.no_amp,
        antenna_power=args.antenna_power,
        cmap=args.cmap,
        serial=args.device,
    )
    return 0


def cmd_webapp(args) -> int:
    from .webapp import serve
    serve(port=args.port, host=args.host, history=args.history, serial=args.device)
    return 0


def cmd_vtx(args) -> int:
    """Quick check: fetch active VTX channels from a running webapp."""
    import urllib.request
    url = f"http://{args.host}:{args.port}/api/channels"
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            data = json.loads(r.read())
    except Exception as e:
        msg = (f"could not reach VTX monitor at {url} — is it running? "
               f"start it with `python -m hackrf_api webapp`  ({e})")
        if args.json:
            print(json.dumps({"ok": False, "error": "no_monitor", "detail": msg}))
        else:
            print(msg, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        if not data.get("ok"):
            print(f"monitor error: {data.get('error')}", file=sys.stderr)
            return 1
        print(f"VTX monitor [{data['band']}]  floor ~{data['floor_dbm']} dBm  "
              f"sweeps {data['sweeps']}")
        active = data.get("active", [])
        print(f"ACTIVE channels: {', '.join(active) if active else '(none)'}")
        if data.get("signals"):
            print("Detected signals:")
            for s in data["signals"]:
                cand = ", ".join(s["candidates"]) or "unknown"
                kind = s.get("kind", "?")
                members = s.get("members", [])
                extra = f"  [{', '.join(members)}]" if len(members) > 1 else ""
                print(f"  {s['freq_mhz']:8.1f} MHz  {s['power_dbm']:6.1f} dBm "
                      f"(+{s['margin_db']:.0f} dB)  {kind:7s} duty {s.get('occupancy',0)*100:3.0f}%"
                      f"  -> {cand}{extra}")
    return 0


def cmd_elrs(args) -> int:
    """Quick check: ELRS TX activity per band from a running webapp."""
    import urllib.request
    url = f"http://{args.host}:{args.port}/api/elrs"
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            data = json.loads(r.read())
    except Exception as e:
        msg = (f"could not reach monitor at {url} — start it with "
               f"`python -m hackrf_api webapp`  ({e})")
        if args.json:
            print(json.dumps({"ok": False, "error": "no_monitor", "detail": msg}))
        else:
            print(msg, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    print(f"ELRS monitor (cycle {data.get('cycle')}, up {data.get('uptime_s')}s)")
    for bid, a in (data.get("elrs") or {}).items():
        verdict = a.get("verdict", "?")
        mark = {"tx_active": "[TX ACTIVE]", "weak": "[faint]", "quiet": "[quiet]"}.get(verdict, verdict)
        conf = a.get("confidence_smoothed", a.get("confidence", 0))
        aa = a.get("above_ambient_db")
        aa_s = f"  +{aa}dB>amb" if aa is not None else ""
        print(f"  {a.get('name', bid):12s} {mark:14s} fhss {conf:.0%}  "
              f"hops {a.get('n_hops', 0)}  interm {a.get('intermittency_db', 0)}dB  "
              f"pk {a.get('peak_dbm')}dBm{aa_s}")
        if a.get("note"):
            print(f"               {a['note']}")
    return 0


def cmd_peak(args) -> int:
    """Report the loudest signal from a running `live` viewer's status file."""
    import os
    import time
    from .live import DEFAULT_STATUS_PATH
    path = args.status_file or DEFAULT_STATUS_PATH
    if not os.path.exists(path):
        msg = ("no live viewer status found — start one with "
               "`python -m hackrf_api live <start> <stop>`")
        if args.json:
            print(json.dumps({"ok": False, "error": "no_live_view", "detail": msg}))
        else:
            print(msg, file=sys.stderr)
        return 2
    with open(path) as fh:
        data = json.load(fh)
    age = time.time() - data.get("timestamp", 0)
    if args.json:
        print(json.dumps({"ok": True, "age_s": round(age, 2), **data}, indent=2))
    else:
        loud = data["loudest"]
        print(f"Loudest: {loud['power_dbm']:.1f} dBm @ {loud['freq_mhz']:.3f} MHz "
              f"(floor ~{data['noise_floor_dbm']:.0f} dBm, {age:.1f}s ago)")
        if data.get("top_signals"):
            print("Top signals:")
            for s in data["top_signals"]:
                print(f"  {s['freq_mhz']:10.3f} MHz   {s['power_dbm']:7.1f} dBm")
    return 0


def cmd_record(args) -> int:
    hrf = HackRF(serial=args.device)
    manifest = hrf.record(
        out_path=args.out,
        freq_hz=args.freq,
        sample_rate_hz=args.rate,
        seconds=args.secs,
        lna_gain=args.lna,
        vga_gain=args.vga,
        amp=args.amp,
    )
    if args.json:
        print(json.dumps({"ok": True, **manifest}, indent=2))
    else:
        print(f"Recorded {manifest['num_samples']} samples "
              f"({manifest['size_bytes']} bytes) to {manifest['path']}")
    return 0


def cmd_emit(args) -> int:
    """Emit a fake analog FPV signal on a VTX channel (test signal). GUARDED."""
    from .vtx_emit import emit_vtx
    if not args.i_understand_tx:
        msg = ("Refusing to transmit. This puts RF on a 5.8 GHz video channel, "
               "which is illegal without a licence in many places. Re-run with "
               "--i-understand-tx once you are sure you may legally transmit.")
        if args.json:
            print(json.dumps({"ok": False, "error": "tx_guard", "detail": msg}))
        else:
            print(msg, file=sys.stderr)
        return 2
    res = emit_vtx(
        channel=args.channel,
        index=args.index,
        mw=args.mw,
        seconds=args.seconds,
        sample_rate_hz=args.rate,
        amp=not args.no_amp,
        tx_vga_gain=args.gain,
        serial=args.device,
        i_understand_tx_may_be_illegal=True,
    )
    if args.json:
        print(json.dumps({"ok": True, **res}, indent=2))
    else:
        print(f"Emitted {res['channel']} @ {res['freq_mhz']:.0f} MHz  "
              f"~{res['requested_mw']:.0f} mW (relative)  "
              f"VGA {res['tx_vga_gain_db']} dB  amp {'on' if res['amp'] else 'off'}  "
              f"BW ~{res['occupied_bw_hz']/1e6:.0f} MHz  for {res['seconds']:.0f}s")
        print(f"  NOTE: {res['note']}")
    return 0


def _float(s: str) -> float:
    # accept things like 8e6, 433.92e6, 2_000_000
    return float(s.replace("_", ""))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hackrf_api",
        description="Drive a HackRF One: device info, spectrum scan, IQ record.",
    )
    p.add_argument("-d", "--device", help="device serial (or unique suffix)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("info", help="show device identity / firmware")
    pi.add_argument("--json", action="store_true")
    pi.set_defaults(func=cmd_info)

    ps = sub.add_parser("scan", help="spectrum sweep over a frequency range")
    ps.add_argument("start", type=_float, help="start frequency in MHz")
    ps.add_argument("stop", type=_float, help="stop frequency in MHz")
    ps.add_argument("--bin", type=lambda s: int(_float(s)), default=100_000,
                    help="FFT bin width in Hz (default 100000)")
    ps.add_argument("--sweeps", type=int, default=1, help="sweeps to average")
    ps.add_argument("--threshold", type=float, default=10.0,
                    help="peak threshold in dB above noise floor")
    ps.add_argument("--top", type=int, default=15, help="max peaks to report")
    ps.add_argument("--lna", type=int, default=16, help="LNA gain 0..40")
    ps.add_argument("--vga", type=int, default=20, help="VGA gain 0..62")
    ps.add_argument("--amp", action="store_true", help="enable +14dB RF amp")
    ps.add_argument("--antenna-power", action="store_true",
                    help="enable bias-tee (3.3V on antenna port)")
    ps.add_argument("--full", action="store_true",
                    help="include full freq/power arrays in JSON")
    ps.add_argument("--plot", action="store_true", help="ASCII spectrum plot")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_scan)

    pw = sub.add_parser("waterfall", help="capture N sweeps and render a PNG waterfall")
    pw.add_argument("start", type=_float, help="start frequency in MHz")
    pw.add_argument("stop", type=_float, help="stop frequency in MHz")
    pw.add_argument("--out", default="waterfall.png", help="output PNG path")
    pw.add_argument("--rows", type=int, default=80, help="number of sweeps (time rows)")
    pw.add_argument("--bin", type=lambda s: int(_float(s)), default=1_000_000,
                    help="FFT bin width in Hz (default 1000000)")
    pw.add_argument("--cmap", default="turbo", help="matplotlib colormap")
    pw.add_argument("--lna", type=int, default=16, help="LNA gain 0..40")
    pw.add_argument("--vga", type=int, default=20, help="VGA gain 0..62")
    pw.add_argument("--amp", action="store_true", help="enable +14dB RF amp")
    pw.add_argument("--antenna-power", action="store_true",
                    help="enable bias-tee (3.3V on antenna port)")
    pw.add_argument("--json", action="store_true")
    pw.set_defaults(func=cmd_waterfall)

    pl = sub.add_parser("live", help="open a live spectrum + waterfall window")
    pl.add_argument("start", type=_float, help="start frequency in MHz")
    pl.add_argument("stop", type=_float, help="stop frequency in MHz")
    pl.add_argument("--bin", type=lambda s: int(_float(s)), default=1_000_000,
                    help="FFT bin width in Hz (default 1000000)")
    pl.add_argument("--history", type=int, default=200,
                    help="waterfall rows (time depth)")
    pl.add_argument("--cmap", default="turbo", help="matplotlib colormap")
    pl.add_argument("--lna", type=int, default=32, help="LNA gain 0..40")
    pl.add_argument("--vga", type=int, default=30, help="VGA gain 0..62")
    pl.add_argument("--no-amp", action="store_true",
                    help="disable the +14dB RF amp (on by default for live)")
    pl.add_argument("--antenna-power", action="store_true",
                    help="enable bias-tee (3.3V on antenna port)")
    pl.set_defaults(func=cmd_live)

    pwa = sub.add_parser("webapp", help="run the multi-band monitor web app (VTX + ELRS)")
    pwa.add_argument("--port", type=int, default=8080)
    pwa.add_argument("--host", default="127.0.0.1")
    pwa.add_argument("--history", type=int, default=160, help="waterfall rows per band")
    pwa.set_defaults(func=cmd_webapp)

    pv = sub.add_parser("vtx", help="quick check: active VTX channels from a running webapp")
    pv.add_argument("--port", type=int, default=8080)
    pv.add_argument("--host", default="127.0.0.1")
    pv.add_argument("--json", action="store_true")
    pv.set_defaults(func=cmd_vtx)

    pe = sub.add_parser("elrs", help="quick check: ELRS TX activity from a running webapp")
    pe.add_argument("--port", type=int, default=8080)
    pe.add_argument("--host", default="127.0.0.1")
    pe.add_argument("--json", action="store_true")
    pe.set_defaults(func=cmd_elrs)

    pp = sub.add_parser("peak", help="report the loudest signal from a running live viewer")
    pp.add_argument("--status-file", help="path to live status JSON (default: temp)")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_peak)

    pr = sub.add_parser("record", help="record raw IQ to a file")
    pr.add_argument("out", help="output .iq path (int8 interleaved I,Q)")
    pr.add_argument("--freq", type=_float, required=True, help="center freq in Hz")
    pr.add_argument("--rate", type=_float, default=10_000_000, help="sample rate in Hz")
    pr.add_argument("--secs", type=float, default=1.0, help="duration in seconds")
    pr.add_argument("--lna", type=int, default=16)
    pr.add_argument("--vga", type=int, default=20)
    pr.add_argument("--amp", action="store_true")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_record)

    pm = sub.add_parser("emit",
                        help="GUARDED: emit a fake analog FPV test signal on a VTX channel")
    pm.add_argument("channel", help="channel like R1 / R4, or band name like raceband")
    pm.add_argument("index", nargs="?", type=int,
                    help="channel index 1..8 when channel is a band name (e.g. emit raceband 4)")
    pm.add_argument("--mw", type=float, default=25.0,
                    help="RELATIVE loudness target in mW (NOT calibrated; default 25)")
    pm.add_argument("--seconds", type=float, default=10.0, help="on-air duration (default 10)")
    pm.add_argument("--rate", type=_float, default=10_000_000, help="sample rate Hz (default 10e6)")
    pm.add_argument("--gain", type=int, default=None,
                    help="override TX VGA gain 0..47 dB (ignores --mw)")
    pm.add_argument("--no-amp", action="store_true", help="disable the front-end amp (on by default)")
    pm.add_argument("--i-understand-tx", action="store_true",
                    help="required: confirm you may legally transmit here")
    pm.add_argument("--json", action="store_true")
    pm.set_defaults(func=cmd_emit)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except HackRFNotFoundError as e:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": "no_device", "detail": str(e)}))
        else:
            print(f"No HackRF device: {e}", file=sys.stderr)
        return 2
    except HackRFError as e:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": "hackrf_error", "detail": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
