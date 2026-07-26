#!/usr/bin/env python3
"""/rctest — verify a Betaflight FC is receiving live RC frames from its RX.

Reads MSP_RC repeatedly for a few seconds, prints per-channel min/max/last with
jitter, and renders a verdict on whether the radio link looks live or whether
the FC is sitting on failsafe / channel-default values.

A live link is signalled by ANY of:
  - throttle outside the typical resting band (RX failsafe usually pins
    throttle at 885us or 1000us; a real TX-on link sits a bit above 1000us
    with low-jitter wiggle, or the user is actively holding it elsewhere)
  - any AUX channel thrown to an extreme (<= 1400 or >= 1600)
  - sample-to-sample jitter > 2us on at least one channel (a real RX always
    pushes slightly-varying values, even with sticks still)

A no-input link looks like:
  - all channels frozen, no AUX thrown, throttle pinned at the failsafe value

Also reads MSP_STATUS_EX arming-disable flags and reports if the FC has the
RX-loss / FAILSAFE arming-disable bits raised — that's the FC's own opinion
on whether it has a valid RC link.

CLI:
  rctest.py                                   # default 3s sample window
  rctest.py --duration 5                      # longer window
  rctest.py --port /dev/cu.usbmodem...        # explicit port
  rctest.py --raw                             # dump every sample, not the summary
"""
import argparse
import glob
import struct
import sys
import time


CHAN_NAMES = ['roll', 'pitch', 'throttle', 'yaw',
              'aux1', 'aux2', 'aux3', 'aux4',
              'aux5', 'aux6', 'aux7', 'aux8',
              'aux9', 'aux10', 'aux11', 'aux12']

# BF arming-disable flag bit names, in bit order. This list matches the
# `runtimeConfig.h` enum used by BF 4.3–4.5; new bits are appended at the
# end across versions, so unknown high bits show as "BIT_N".
ARMING_DISABLE_FLAGS = [
    'NO_GYRO', 'FAILSAFE', 'RX_FAILSAFE', 'BAD_RX_RECOVERY',
    'BOXFAILSAFE', 'RUNAWAY_TAKEOFF', 'CRASH_DETECTED', 'THROTTLE',
    'ANGLE', 'BOOT_GRACE_TIME', 'NOPREARM', 'LOAD',
    'CALIBRATING', 'CLI', 'CMS_MENU', 'BST',
    'MSP', 'PARALYZE', 'GPS', 'RESC',
    'RPMFILTER', 'REBOOT_REQUIRED', 'DSHOT_BITBANG', 'ACC_CALIBRATION',
    'MOTOR_PROTOCOL', 'ARM_SWITCH',
]


def list_ports():
    return sorted(glob.glob('/dev/cu.usbmodem*'))


def log(msg):
    print(f"[rctest] {msg}", file=sys.stderr, flush=True)


# ---------- MSP framing (v1)

class MSP:
    def __init__(self, port, baud=115200):
        import serial
        self.s = serial.Serial(port, baud, timeout=0.3)
        time.sleep(0.3)

    def close(self):
        try: self.s.close()
        except Exception: pass

    def v1(self, cmd, payload=b'', wait=0.4):
        size = len(payload)
        frame = b'$M<' + bytes([size, cmd]) + payload
        cs = 0
        for b in frame[3:]:
            cs ^= b
        frame += bytes([cs])
        self.s.write(frame); self.s.flush()
        end = time.time() + wait
        buf = b''
        while time.time() < end:
            c = self.s.read(256)
            if c:
                buf += c
                idx = buf.find(b'$M>')
                if idx >= 0 and len(buf) >= idx + 6:
                    sz = buf[idx+3]
                    if len(buf) >= idx + 5 + sz + 1:
                        return buf[idx+5:idx+5+sz]
        return None


# ---------- Probes

def probe_variant(msp):
    r = msp.v1(2, wait=1.0)
    if r and len(r) >= 4:
        return r[:4].decode('ascii', errors='replace')
    return None


def read_rc(msp):
    """MSP_RC (cmd 105) → list of channel values (uint16 us)."""
    r = msp.v1(105, wait=0.4)
    if not r or len(r) < 2:
        return None
    n = len(r) // 2
    return list(struct.unpack(f'<{n}H', r[:n*2]))


def read_status_ex(msp):
    """MSP_STATUS_EX (cmd 150). Returns dict of fields we care about, or None.

    Layout (BF 4.x), little-endian:
      u16 cycleTime
      u16 i2c_errors
      u16 sensor flags
      u32 mode flags  (low 32 of activeFlightModes)
      u8  currentPidProfile
      u16 cpuLoadPercent
      u8  flightModeFlagsCount
      u8  armingDisableFlagsCount  (number of *defined* bits, NOT a length)
      u32 armingDisableFlags
      u8  configStateFlag
    Newer builds append:
      u16 cpuTemperature
      u16 averageSystemLoadPercent
    """
    r = msp.v1(150, wait=0.6)
    if not r or len(r) < 20:
        return None
    try:
        cycleTime    = struct.unpack_from('<H', r, 0)[0]
        i2c_errors   = struct.unpack_from('<H', r, 2)[0]
        sensors      = struct.unpack_from('<H', r, 4)[0]
        modeFlags    = struct.unpack_from('<I', r, 6)[0]
        pidProfile   = r[10]
        cpuLoad      = struct.unpack_from('<H', r, 11)[0]
        # 13: flightModeFlagsCount, 14: armingDisableFlagsCount
        armDisable   = struct.unpack_from('<I', r, 15)[0]
        return {
            'cycleTime': cycleTime,
            'i2c_errors': i2c_errors,
            'sensors': sensors,
            'modeFlags': modeFlags,
            'pidProfile': pidProfile,
            'cpuLoad': cpuLoad,
            'armingDisable': armDisable,
        }
    except struct.error:
        return None


def decode_arming_disable(flags):
    if not flags:
        return []
    out = []
    for i in range(32):
        if flags & (1 << i):
            out.append(ARMING_DISABLE_FLAGS[i] if i < len(ARMING_DISABLE_FLAGS) else f'BIT_{i}')
    return out


# ---------- Sampling

def sample_rc(msp, duration, on_sample=None):
    """Sample MSP_RC for `duration` seconds, returning list of (t_ms, channels).
    `on_sample` is called per-sample for --raw mode."""
    samples = []
    t0 = time.time()
    while time.time() - t0 < duration:
        rc = read_rc(msp)
        if rc:
            t_ms = int((time.time() - t0) * 1000)
            samples.append((t_ms, rc))
            if on_sample:
                on_sample(t_ms, rc)
        # MSP_RC is cheap — let it run as fast as the FC will respond
    return samples


# ---------- Verdict

def channel_stats(samples, n_channels):
    """Per-channel min/max/last/jitter across all samples."""
    stats = []
    for ch in range(n_channels):
        vals = [s[1][ch] for s in samples if ch < len(s[1])]
        if not vals:
            stats.append(None)
            continue
        mn, mx = min(vals), max(vals)
        stats.append({
            'min': mn,
            'max': mx,
            'last': vals[-1],
            'jitter': mx - mn,
        })
    return stats


def is_throttle_resting(v):
    """Throttle value that looks like 'TX is on but stick held min/idle'.
    A typical BF rx_min_usec is ~885, rc midrc 1500, and idle throttle ~1000.
    Anything outside these resting bands suggests the user (or failsafe) is
    actively driving throttle."""
    return (870 <= v <= 1020) or (1490 <= v <= 1510)


def verdict(stats):
    """Decide whether the link looks live.
    Returns (live: bool, reasons: list[str], warnings: list[str])"""
    reasons = []
    warnings = []
    if not stats or all(s is None for s in stats):
        return False, [], ['no RC frames received at all — MSP_RC empty']

    # Jitter check across all channels
    any_jitter = False
    for ch, s in enumerate(stats):
        if s and s['jitter'] >= 3:
            any_jitter = True
            reasons.append(f"{CHAN_NAMES[ch] if ch < len(CHAN_NAMES) else f'ch{ch+1}'} jittered {s['jitter']}us")
            break  # one is enough to call it live

    # Throttle position
    thr = stats[2] if len(stats) > 2 and stats[2] else None
    if thr and not is_throttle_resting(thr['last']):
        reasons.append(f"throttle at {thr['last']}us (outside resting band)")

    # AUX switches thrown
    for ch in range(4, len(stats)):
        s = stats[ch]
        if not s:
            continue
        if s['last'] <= 1400 or s['last'] >= 1600:
            reasons.append(f"{CHAN_NAMES[ch] if ch < len(CHAN_NAMES) else f'ch{ch+1}'} thrown to {s['last']}us")

    # All-1500 lock = nothing connected (BF default fill when no RX frames)
    aetr_vals = [stats[i]['last'] for i in range(4) if stats[i]]
    if all(v == 1500 for v in aetr_vals) and not any_jitter:
        warnings.append("AETR all locked at 1500us with no jitter — looks like BF default fill, not real RX frames")

    live = bool(reasons)
    return live, reasons, warnings


# ---------- Output

def print_table(stats, n_channels):
    print()
    print(f"  {'channel':10s} {'last':>6s} {'min':>6s} {'max':>6s} {'jitter':>7s}  notes")
    print(f"  {'-'*10} {'-'*6} {'-'*6} {'-'*6} {'-'*7}  {'-'*30}")
    for ch in range(n_channels):
        s = stats[ch]
        name = CHAN_NAMES[ch] if ch < len(CHAN_NAMES) else f'ch{ch+1}'
        if not s:
            print(f"  {name:10s} {'-':>6s} {'-':>6s} {'-':>6s} {'-':>7s}  (no data)")
            continue
        notes = []
        if ch == 2:  # throttle
            if 870 <= s['last'] <= 900:
                notes.append("throttle min/failsafe")
            elif 990 <= s['last'] <= 1020:
                notes.append("throttle idle")
            elif s['last'] >= 1100:
                notes.append("THROTTLE UP")
        elif ch >= 4:  # aux
            if s['last'] <= 1300:
                notes.append("switch LOW")
            elif s['last'] >= 1700:
                notes.append("switch HIGH")
            elif 1450 <= s['last'] <= 1550:
                notes.append("switch MID/center")
        if s['jitter'] >= 3:
            notes.append(f"live jitter")
        elif s['jitter'] == 0:
            notes.append(f"FROZEN")
        print(f"  {name:10s} {s['last']:>6d} {s['min']:>6d} {s['max']:>6d} {s['jitter']:>6d}u  {', '.join(notes)}")
    print()


def print_status_summary(status):
    if not status:
        print("  MSP_STATUS_EX: <no response>")
        return
    flags = decode_arming_disable(status['armingDisable'])
    print(f"  cycleTime={status['cycleTime']}us  cpuLoad={status['cpuLoad']}%")
    if not flags:
        print(f"  armingDisable: <none> — FC believes it is arm-ready")
    else:
        rx_related = [f for f in flags if f in ('FAILSAFE', 'RX_FAILSAFE', 'BAD_RX_RECOVERY', 'BOXFAILSAFE')]
        if rx_related:
            print(f"  armingDisable (RX-related): {', '.join(rx_related)}  <-- RX link bad / failsafe active")
        else:
            print(f"  armingDisable: {', '.join(flags)}  (none are RX-related)")
    print()


# ---------- Main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', default=None,
                    help='/dev/cu.usbmodem* path; auto-detect if omitted')
    ap.add_argument('--duration', type=float, default=3.0,
                    help='seconds to sample MSP_RC (default 3)')
    ap.add_argument('--channels', type=int, default=12,
                    help='how many channels to show in table (default 12)')
    ap.add_argument('--raw', action='store_true',
                    help='print every sample as it arrives instead of summary')
    args = ap.parse_args()

    port = args.port
    if not port:
        ports = list_ports()
        if not ports:
            print("[error] no /dev/cu.usbmodem* found — is the FC plugged in?",
                  file=sys.stderr)
            return 1
        port = ports[0]
        if len(ports) > 1:
            log(f"multiple ports, picking {port}")
    log(f"port: {port}")

    msp = MSP(port)
    try:
        variant = probe_variant(msp)
        log(f"FC variant: {variant!r}")
        if variant != 'BTFL':
            print(f"[error] /rctest is Betaflight-only; got variant {variant!r}",
                  file=sys.stderr)
            return 2

        print()
        print("=== FC status before RC sampling ===")
        status = read_status_ex(msp)
        print_status_summary(status)

        # First read tells us how many channels the build is reporting
        first = read_rc(msp)
        if first is None:
            print("[error] MSP_RC returned no data — RX may be unbound or "
                  "feature RX_SERIAL disabled", file=sys.stderr)
            return 3
        n_channels = min(args.channels, len(first))
        log(f"sampling {n_channels} channels for {args.duration:.1f}s...")

        if args.raw:
            def on_sample(t_ms, rc):
                vals = ' '.join(f"{v:4d}" for v in rc[:n_channels])
                print(f"  t={t_ms:5d}ms  {vals}")
            samples = sample_rc(msp, args.duration, on_sample=on_sample)
        else:
            samples = sample_rc(msp, args.duration)

        if not samples:
            print("[error] no MSP_RC samples in window", file=sys.stderr)
            return 4
        log(f"got {len(samples)} samples ({len(samples)/args.duration:.1f} Hz)")

        stats = channel_stats(samples, n_channels)
        print_table(stats, n_channels)

        live, reasons, warnings = verdict(stats)
        print("=== verdict ===")
        if live:
            print("  RX link looks LIVE — FC is receiving RC frames from the radio.")
            for r in reasons:
                print(f"    - {r}")
        else:
            print("  RX link does NOT look live — no convincing signal of TX input.")
            print("    Possible causes:")
            print("      - TX powered off / out of range / not bound to RX")
            print("      - RX wired but not configured (check `feature RX_SERIAL`,")
            print("        `serialrx_provider`, and the UART's `serial` function bit 64)")
            print("      - RX powered but not pushing frames (check RX LED)")
        for w in warnings:
            print(f"  WARNING: {w}")
        print()
        return 0 if live else 5
    finally:
        msp.close()


if __name__ == '__main__':
    sys.exit(main())
