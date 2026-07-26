#!/usr/bin/env python3
"""
Decode Betaflight blackbox logs (.BBL/.BFL) into per-flight summaries -> flights.csv.

Raw logs are large and are NOT committed to git; this script reads them from a folder you
point it at (default: ./blackbox) and writes a compact flights.csv that IS committed. It MERGES
with any existing flights.csv keyed by (file, log_index), so previously-summarized flights survive
even after their raw log is moved or deleted.

Usage:
    python3 update_flights.py [logs_folder]      # default: ./blackbox

Dependency: the pure-Python `orangebox` blackbox parser. One-time setup:
    python3 -m venv .venv && .venv/bin/pip install orangebox
This script auto-re-execs under ./.venv if orangebox isn't importable in the current interpreter.
"""
import sys, os, csv, glob, re

# --- dependency bootstrap: prefer a project-local .venv if orangebox isn't already available ---
try:
    from orangebox import Parser
    from orangebox.reader import Reader
except ModuleNotFoundError:
    # Compare executable paths WITHOUT resolving symlinks: a venv's python is a symlink to the
    # base interpreter, so realpath() would collapse both and the re-exec would never fire.
    venv_py = os.path.join(os.getcwd(), ".venv", "bin", "python")
    if os.path.exists(venv_py) and os.path.abspath(sys.executable) != venv_py:
        os.execv(venv_py, [venv_py] + sys.argv)
    sys.exit("orangebox not installed. One-time setup:\n"
             "    python3 -m venv .venv && .venv/bin/pip install orangebox\n"
             "then re-run this script.")

LOGS_DIR = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.getcwd(), "blackbox")
OUT = os.path.join(os.getcwd(), "flights.csv")

fname_re = re.compile(
    r'BTFL_BLACKBOX_LOG_(?P<label>.+?)_(?P<date>\d{8})_(?P<time>\d{6})_(?P<board>.+)\.(?:bbl|bfl)$', re.I)

COLS = ['quad', 'date', 'time', 'board', 'craft', 'firmware', 'duration_s', 'frames', 'cells',
        'v_start', 'v_min', 'v_end', 'sag_v', 'cell_min_v', 'a_avg', 'a_peak', 'mah',
        'avg_throttle_pct', 'avg_motor_pct', 'motor_sat_pct', 'desync_pct', 'desync_motors',
        'flags', 'log_index', 'file']

# Motor desync / thrust-loss detection. A healthy motor's RPM tracks its command; a desynced or
# failing motor is commanded hard but doesn't spin up. We flag a frame as a desync event when a
# motor is commanded near max (>=90% of the output range) yet its bidirectional-DShot eRPM is well
# below the fastest motor's (<55%) — i.e. told to spin hard, spinning much slower than its peers.
# Validated against a known crash log (193 such frames, motors 0 & 3) vs a clean log (0 frames).
DESYNC_CMD_FRAC = 0.90
DESYNC_ERPM_RATIO = 0.55
DESYNC_MIN_FRAMES = 20  # absolute frame count above which we raise the MOTOR_DESYNC flag
LOW_CELL_V = 3.3        # sagged cell voltage under load below this raises LOW_CELL


def valid_logs(path):
    """Log indices whose frame data is real (skips spurious duplicate-header markers)."""
    r = Reader(path, None)
    for i in range(1, r.log_count + 1):
        try:
            r.set_log_index(i)
            if r._frame_data_len > 1000:
                yield i
        except Exception:
            continue


def summarize_log(path, log_index):
    p = Parser.load(path, log_index=log_index)
    fn = p.field_names
    idx = {n: i for i, n in enumerate(fn)}
    tm, vb, am = idx.get('time'), idx.get('vbatLatest'), idx.get('amperageLatest')
    thr = idx.get('rcCommand[3]')
    mot = [idx[f'motor[{i}]'] for i in range(4) if f'motor[{i}]' in idx]
    erp = [idx[f'eRPM[{i}]'] for i in range(4) if f'eRPM[{i}]' in idx]
    mo = p.headers.get('motorOutput', [0, 1000])
    m_lo, m_hi = mo[0], mo[1]
    desync_cmd = m_lo + DESYNC_CMD_FRAC * (m_hi - m_lo)
    desync_per_motor = [0, 0, 0, 0]

    n = 0
    t0 = tN = tprev = None
    v_start = v_end = None
    v_min = 1e9
    a_max = 0.0
    mah = 0.0
    motor_sum = 0.0
    sat_frames = 0
    thr_sum = 0.0
    for fr in p.frames():
        d = fr.data
        t = d[tm]
        if t0 is None:
            t0 = t
        else:
            dt = (t - tprev) / 1e6
            if am is not None and 0 < dt < 1:  # integrate charge; ignore gaps/log joins
                mah += (d[am] / 100.0) * dt / 3.6
        tprev = t
        tN = t
        if vb is not None:
            v = d[vb] / 100.0
            v_start = v if v_start is None else v_start
            v_end = v
            v_min = min(v_min, v)
        if am is not None:
            a_max = max(a_max, d[am] / 100.0)
        if mot:
            if max(d[i] for i in mot) >= m_lo + 0.99 * (m_hi - m_lo):
                sat_frames += 1
            motor_sum += sum(d[i] for i in mot) / len(mot)
            if len(erp) == 4:
                erpms = [d[e] for e in erp]
                emax = max(erpms)
                if emax > 0:
                    for i in range(4):
                        if d[mot[i]] >= desync_cmd and erpms[i] < DESYNC_ERPM_RATIO * emax:
                            desync_per_motor[i] += 1
        if thr is not None:
            thr_sum += d[thr]
        n += 1

    if n == 0 or t0 is None:
        return None
    dur = (tN - t0) / 1e6
    cells = round(v_start / 4.2) if v_start else 0

    desync_total = sum(desync_per_motor)
    # motors carrying a meaningful share of the desync frames (>=25% of the worst motor's count)
    worst = max(desync_per_motor) if desync_per_motor else 0
    bad_motors = [i for i, c in enumerate(desync_per_motor) if c >= max(worst * 0.25, 5)]
    cell_min = (v_min / cells) if cells else None
    flags = []
    if desync_total >= DESYNC_MIN_FRAMES:
        flags.append("MOTOR_DESYNC(" + ",".join(f"m{i}" for i in bad_motors) + ")")
    if cell_min is not None and cell_min < LOW_CELL_V:
        flags.append("LOW_CELL")
    return {
        'craft': p.headers.get('Craft name', ''),
        'firmware': p.headers.get('Firmware revision', ''),
        'duration_s': round(dur, 1),
        'frames': n,
        'cells': cells,
        'v_start': round(v_start, 2) if v_start else '',
        'v_min': round(v_min, 2),
        'v_end': round(v_end, 2) if v_end else '',
        'sag_v': round(v_start - v_min, 2) if v_start else '',
        'cell_min_v': round(v_min / cells, 2) if cells else '',
        'a_avg': round(mah * 3.6 / dur, 1) if dur else 0,  # avg current back-derived from mAh
        'a_peak': round(a_max, 1),
        'mah': round(mah),
        'avg_throttle_pct': round((thr_sum / n - 1000) / 10.0) if thr is not None else '',
        'avg_motor_pct': round((motor_sum / n - m_lo) / (m_hi - m_lo) * 100) if mot and m_hi > m_lo else '',
        'motor_sat_pct': round(sat_frames / n * 100, 1),
        'desync_pct': round(desync_total / n * 100, 2),
        'desync_motors': ",".join(f"m{i}" for i in bad_motors) if desync_total >= DESYNC_MIN_FRAMES else '',
        'flags': "; ".join(flags),
    }


def main():
    # Load existing flights (durable record) keyed by (file, log_index).
    existing = {}
    if os.path.exists(OUT):
        with open(OUT, newline='') as f:
            for row in csv.DictReader(f):
                existing[(row['file'], row['log_index'])] = row

    logs = sorted(glob.glob(os.path.join(LOGS_DIR, '*.BBL')) + glob.glob(os.path.join(LOGS_DIR, '*.bbl')) +
                  glob.glob(os.path.join(LOGS_DIR, '*.BFL')) + glob.glob(os.path.join(LOGS_DIR, '*.bfl')))
    added = 0
    for path in logs:
        base = os.path.basename(path)
        m = fname_re.search(base)
        meta = {
            'file': base,
            'quad': m.group('label') if m else '',
            'date': (lambda d: f"{d[:4]}-{d[4:6]}-{d[6:8]}")(m.group('date')) if m else '',
            'time': (lambda t: f"{t[:2]}:{t[2:4]}:{t[4:6]}")(m.group('time')) if m else '',
            'board': m.group('board') if m else '',
        }
        for li in valid_logs(path):
            key = (base, str(li))
            if key in existing:
                continue
            s = summarize_log(path, li)
            if s:
                existing[key] = {**meta, **s, 'log_index': li}
                added += 1

    rows = sorted(existing.values(), key=lambda r: (str(r['quad']).lower(), r['date'], r['time']))
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

    print(f"Logs folder: {LOGS_DIR} ({len(logs)} file(s))")
    print(f"flights.csv: {len(rows)} flight(s) total, {added} new -> {OUT}")


if __name__ == '__main__':
    main()
