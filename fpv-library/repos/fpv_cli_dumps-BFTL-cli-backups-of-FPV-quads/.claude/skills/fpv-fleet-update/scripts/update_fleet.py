#!/usr/bin/env python3
"""
Regenerate the FPV fleet inventory from Betaflight CLI dump files.

Scans every BTFL_cli_*.txt dump in the target folder and produces three outputs:
  - fpv_quads.csv         full history, one row per dump, newest per quad flagged 'latest'
  - fpv_quads_latest.csv  one row per quad, newest dump only
  - FLEET_SUMMARY.md      human-readable overview with rollups and a 'needs attention' pass

Usage:
    python update_fleet.py [folder]     # defaults to the current working directory

The parser is the single source of truth. It only reads dumps and writes those three
files, so it is safe to re-run any time new dumps are dropped in.
"""
import os, re, csv, sys, glob
from datetime import date, datetime

SRC = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
OUT = os.path.join(SRC, "fpv_quads.csv")
OUT_LATEST = os.path.join(SRC, "fpv_quads_latest.csv")
OUT_SUMMARY = os.path.join(SRC, "FLEET_SUMMARY.md")

# Filename shapes handled:
#   BTFL_cli_backup_<LABEL>_<YYYYMMDD>_<HHMMSS>_<BOARD>.txt
#   BTFL_cli_<LABEL>_<YYYYMMDD>_<HHMMSS>_<BOARD>.txt
#   BTFL_cli_dif_all_<LABEL>_<YYYYMMDD>_<HHMMSS>_<BOARD>.txt
#   ...and the same without a <LABEL> (older unnamed backups).
fname_re = re.compile(
    r'^BTFL_cli_(?:backup_|dif_all_)?(?P<label>.*?)_?(?P<date>\d{8})_(?P<time>\d{6})_(?P<board>.+)\.txt$'
)


def val(text, key):
    m = re.search(r'^set\s+' + re.escape(key) + r'\s*=\s*(.+?)\s*$', text, re.M)
    return m.group(1).strip() if m else ""


def line_after(text, prefix):
    m = re.search(r'^' + re.escape(prefix) + r'\s+(.+?)\s*$', text, re.M)
    return m.group(1).strip() if m else ""


def norm(s):
    return re.sub(r'[^A-Za-z0-9]', '', s).upper()


CLASS_ORDER = ['whoop', 'cinewhoop', 'micro', '5-inch']
# Lifecycle state of the airframe (can I fly it today?). Hand-maintained; blank defaults to 'active'
# so only exceptions need annotating. Ordered flyable -> gone for stable rollups.
STATUS_ORDER = ['active', 'building', 'rebuilding', 'broken', 'retired', 'lost']
FLYABLE = {'active', 'building', 'rebuilding', ''}   # states we still nag about (firmware/staleness)
# What the quad is built to do (how is it flown?). Orthogonal to status — a quad keeps its discipline
# after it's retired. Hand-entered only; the dump carries no signal for it, so there's no guesser.
DISCIPLINE_ORDER = ['race', 'freestyle', 'cinematic', 'long-range']


def guess_class(craft, board):
    """Best-effort size class from craft name + board. Betaflight dumps carry no frame/prop/motor/
    cell field, so class can't be read directly — this leans on product-name conventions and board
    families. It is only a fallback: an explicit `class` in hardware.csv overrides it, so fix wrong
    guesses there rather than special-casing here. Returns '' when nothing matches (left to curate).
    Note: an 'AIO' / trailing digit in a name is a board type (e.g. AIO5 = 5-in-1 board), not a
    frame size — so a whoop AIO board stays a whoop regardless of the number after it."""
    s = (craft + ' ' + board).lower()
    if 'cinelog' in s or 'cinewhoop' in s or 'cine' in s:
        return 'cinewhoop'
    if 'crux' in s or 'crocodile' in s:            # 3-4" micro / long-range product lines
        return 'micro'
    whoop_boards = ('crazybeef4', 'betafpvf4sx1280', 'betafpvf4')
    whoop_names = ('air65', 'meteor', 'mobula', 'mob6', 'beta65', 'beta75', 'beta85',
                   'us65', 'us75', 'whoop', 'happish', 'ecofree', 'diamond')
    if any(b in s for b in whoop_boards) or any(n in s for n in whoop_names):
        return 'whoop'
    stack_boards = ('xrotor', 'tmotorf7', 'flywoof7', 'f722', 'f745', 'f405', 'xilo')
    if any(b in s for b in stack_boards):
        return '5-inch'
    return ''


def load_hw_map(path, col):
    """Map normalized quad name -> a hand-curated column value from hardware.csv, when set. Used for
    fields the dumps can't carry (`class` overrides guess_class(); `status`/`discipline` have no
    guesser at all). Blank cells are skipped so callers can apply their own default."""
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            c = (r.get(col) or '').strip()
            if c:
                out[norm(r.get('quad', ''))] = c
    return out


def extract_active_rates(text):
    """Pull the ACTIVE rateprofile's rates. The rate keys (rc_rate/srate/expo/rates_type) live
    inside a rateprofile block, and the same key name appears in every profile — so we must read
    only the active one. The active profile is the last bare `rateprofile N` line (the restore
    selection in normal dumps; the sole defined profile in older/partial dumps). Values are the RAW
    stored integers straight from the dump; their meaning depends on rates_type (BETAFLIGHT: RC Rate /
    Super Rate / Expo; ACTUAL: Center Sensitivity / Max Rate / Expo). Defaults are omitted by
    `diff all`, so unset fields come out blank. rates_type blank means firmware default (ACTUAL)."""
    sels = re.findall(r'^rateprofile (\d+)\s*$', text, re.M)
    active = sels[-1] if sels else None
    vals = {}
    if active is not None:
        cur = None
        for line in text.splitlines():
            m = re.match(r'^rateprofile (\d+)\s*$', line)
            if m:
                cur = m.group(1)
                continue
            if cur == active:
                sm = re.match(r'^set (\w+) = (.+?)\s*$', line)
                if sm:
                    vals[sm.group(1)] = sm.group(2).strip()

    def triple(a, b, c):
        parts = [vals.get(a, ''), vals.get(b, ''), vals.get(c, '')]
        return '/'.join(parts) if any(parts) else ''

    name = vals.get('rateprofile_name', '')
    return {
        'rateprofile': (f"{active}:{name}" if active is not None and name else (active or '')),
        'rates_type': vals.get('rates_type', ''),
        'rc_rate_rpy': triple('roll_rc_rate', 'pitch_rc_rate', 'yaw_rc_rate'),
        'super_rate_rpy': triple('roll_srate', 'pitch_srate', 'yaw_srate'),
        'expo_rpy': triple('roll_expo', 'pitch_expo', 'yaw_expo'),
    }


def parse_dumps():
    rows = []
    # Recursive so dumps organized into subfolders (e.g. backups/) are still found.
    # Non-matching .txt files are skipped by fname_re below, so this is safe.
    for path in sorted(glob.glob(os.path.join(SRC, "**", "*.txt"), recursive=True)):
        base = os.path.basename(path)
        m = fname_re.match(base)
        if not m:
            continue
        label = m.group('label').strip() or ""
        d = m.group('date')
        date_fmt = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
        board_fname = m.group('board')

        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read()

        # A truncated/aborted dump (e.g. just "defaults nosave") carries no config.
        if len(text.strip()) < 40:
            rows.append({
                '_ident': norm(label) or norm(board_fname),
                'quad': label or board_fname, 'dump_date': date_fmt, 'craft_name': '',
                'board': board_fname, 'manufacturer': '', 'bf_version': '',
                'mcu': '', 'motor_protocol': '', 'motor_poles': '', 'dshot_bidir': '',
                'rx_protocol': '', 'video_system': '', 'vtx_band': '', 'vtx_channel': '',
                'vtx_power': '', 'vtx_freq': '', 'cell_min_v': '', 'cell_max_v': '',
                'cell_warn_v': '', 'rx_spi_protocol': '', 'elrs_uid': '', 'bind_group': '',
                'gyro_align': '', 'pilot': '', 'file': base, 'note': 'EMPTY/INCOMPLETE DUMP'
            })
            continue

        ver = re.search(r'# Betaflight / (\S+) \(\S+\) (\S+)', text)
        mcu = ver.group(1) if ver else ''
        bf_version = ver.group(2) if ver else ''

        board = line_after(text, 'board_name') or board_fname
        manuf = line_after(text, 'manufacturer_id')

        craft = val(text, 'craft_name')
        if not craft:
            nm = re.search(r'^# name:\s*(.+?)\s*$', text, re.M)
            craft = nm.group(1).strip() if nm else ''

        # Receiver link: SPI (onboard) vs serial, plus the serial provider if set.
        rx = ''
        if re.search(r'^feature\s+RX_SPI', text, re.M):
            rx = 'RX_SPI'
        elif re.search(r'^feature\s+RX_SERIAL', text, re.M) and not re.search(r'^feature\s+-RX_SERIAL', text, re.M):
            rx = 'RX_SERIAL'
        srx = val(text, 'serialrx_provider')
        if srx:
            rx = (rx + ' / ' if rx else '') + srx
        if not rx and val(text, 'rx_spi_protocol'):
            rx = 'RX_SPI / ' + val(text, 'rx_spi_protocol')

        # Quad identity: prefer the craft name baked into the dump (survives file renames),
        # then the filename label, then the board. norm() makes "M85 HDZero" == "M85_HDZERO".
        quad_display = craft or label or board
        ident = norm(craft) or norm(label) or norm(board)

        rows.append({
            '_ident': ident,
            'quad': quad_display,
            'dump_date': date_fmt,
            'craft_name': craft,
            'board': board,
            'manufacturer': manuf,
            'bf_version': bf_version,
            'mcu': mcu,
            'motor_protocol': val(text, 'motor_pwm_protocol'),
            'motor_poles': val(text, 'motor_poles'),
            'dshot_bidir': val(text, 'dshot_bidir'),
            'rx_protocol': rx,
            'video_system': val(text, 'vcd_video_system'),
            'vtx_band': val(text, 'vtx_band'),
            'vtx_channel': val(text, 'vtx_channel'),
            'vtx_power': val(text, 'vtx_power'),
            'vtx_freq': val(text, 'vtx_freq'),
            'cell_min_v': val(text, 'vbat_min_cell_voltage'),
            'cell_max_v': val(text, 'vbat_max_cell_voltage'),
            'cell_warn_v': val(text, 'vbat_warning_cell_voltage'),
            'rx_spi_protocol': val(text, 'rx_spi_protocol'),
            'elrs_uid': val(text, 'expresslrs_uid'),
            'bind_group': '',
            'gyro_align': val(text, 'gyro_1_sensor_align'),
            **extract_active_rates(text),
            'pilot': val(text, 'pilot_name'),
            'file': base,
            'note': '',
        })

    # Quads sharing an ExpressLRS UID bind to the same radio -> same group (ELRS-A, ELRS-B, ...).
    # Most common UID becomes A; ties broken by UID string so labels are stable across re-runs.
    uid_counts = {}
    for r in rows:
        if r['elrs_uid']:
            uid_counts[r['elrs_uid']] = uid_counts.get(r['elrs_uid'], 0) + 1
    ordered = sorted(uid_counts, key=lambda u: (-uid_counts[u], u))
    uid_label = {u: f"ELRS-{chr(ord('A') + i)}" for i, u in enumerate(ordered)}
    for r in rows:
        if r['elrs_uid']:
            r['bind_group'] = uid_label[r['elrs_uid']]

    # Curated fields that dumps can't carry, all keyed by normalized quad name from hardware.csv:
    #   class      — size bucket; falls back to the guess_class() heuristic when unset.
    #   status     — lifecycle (active/retired/...); blank means active (see status_of()).
    #   discipline — what it's flown for (race/freestyle/cinematic); blank stays blank, no guesser.
    hw_path = os.path.join(SRC, "hardware.csv")
    hw_class = load_hw_map(hw_path, "class")
    hw_status = load_hw_map(hw_path, "status")
    hw_discipline = load_hw_map(hw_path, "discipline")
    for r in rows:
        r['class'] = hw_class.get(r['_ident'], '') or guess_class(r.get('craft_name', ''), r.get('board', ''))
        r['status'] = hw_status.get(r['_ident'], '')
        r['discipline'] = hw_discipline.get(r['_ident'], '')

    # Collapse duplicate dumps: when several dumps of one quad share identical extracted
    # inventory values (differing only in date/file), keep just the most recent. The older
    # ones carry no information at this level of detail — even if the raw dump differed in
    # fields we don't track (PIDs, OSD layout), the inventory row would be identical.
    scanned = len(rows)
    ignore = {'_ident', 'dump_date', 'note', 'file'}
    keycols = [c for c in COLS if c not in ignore]  # canonical + stable across row shapes
    dedup = {}
    for r in rows:
        k = (r['_ident'],) + tuple(r.get(c, '') for c in keycols)
        cur = dedup.get(k)
        if cur is None or (r['dump_date'], r['file']) > (cur['dump_date'], cur['file']):
            dedup[k] = r
    rows = list(dedup.values())

    rows.sort(key=lambda r: (r['_ident'], r['dump_date'], r['file']))

    latest = {}
    for r in rows:
        k = r['_ident']
        if k not in latest or r['dump_date'] > latest[k]:
            latest[k] = r['dump_date']
    for r in rows:
        if r['dump_date'] == latest[r['_ident']] and 'EMPTY' not in r['note']:
            r['note'] = 'latest' + (('; ' + r['note']) if r['note'] else '')

    return rows, scanned


COLS = ['quad', 'class', 'discipline', 'status', 'dump_date', 'craft_name', 'board', 'manufacturer', 'bf_version', 'mcu',
        'motor_protocol', 'motor_poles', 'dshot_bidir', 'rx_protocol', 'rx_spi_protocol',
        'elrs_uid', 'bind_group', 'video_system', 'vtx_band', 'vtx_channel', 'vtx_power',
        'vtx_freq', 'cell_min_v', 'cell_max_v', 'cell_warn_v', 'gyro_align',
        'rateprofile', 'rates_type', 'rc_rate_rpy', 'super_rate_rpy', 'expo_rpy', 'pilot',
        'note', 'file']


def write_csv(path, data):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore')
        w.writeheader()
        w.writerows(data)


def latest_per_quad(rows):
    by_quad = {}
    for r in rows:
        by_quad.setdefault(r['_ident'], []).append(r)
    out = []
    for rs in by_quad.values():
        good = [r for r in rs if 'EMPTY' not in r['note']] or rs
        out.append(max(good, key=lambda r: (r['dump_date'], r['file'])))
    out.sort(key=lambda r: r['quad'].lower())
    return out


def status_of(r):
    """Lifecycle status with the blank-means-active default applied. Everything that reasons about
    whether a quad is still in service goes through this so the default lives in one place."""
    return (r.get('status') or 'active').strip().lower()


def short_mcu(mcu):
    return re.sub(r'^STM32', '', mcu) if mcu else '-'


def short_video(v):
    return {'HD': 'HD', 'NTSC': 'Analog', 'PAL': 'Analog', 'AUTO': 'Auto', '': '-'}.get(v, v)


def ver_tuple(v):
    """Leading major.minor of a firmware string as ints, e.g. '4.5.2.KAACK' -> (4, 5)."""
    nums = re.findall(r'\d+', v or '')
    return (int(nums[0]), int(nums[1])) if len(nums) >= 2 else (0, 0)


def build_summary(latest_rows):
    from collections import Counter
    lines = []
    A = lines.append

    A("# FPV Fleet Summary")
    A("")
    A(f"_Auto-generated by the `fpv-fleet-update` skill on {date.today().isoformat()} "
      f"from the Betaflight CLI dumps in this folder._")
    A("")
    A("Source data: `fpv_quads.csv` (full history) and `fpv_quads_latest.csv` (newest dump per quad, "
      f"{len(latest_rows)} quads). Values come from `diff all` dumps, which only record settings that "
      "differ from firmware defaults — a blank cell means the setting is at its firmware default, "
      "not that it is missing.")
    A("")

    # ---- Fleet table ----
    A("## Fleet (latest dump per quad)")
    A("")
    A("| Quad | Class | Use | Status | Board | MCU | BF | ESC | Video | RX / bind | Last dump |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in latest_rows:
        name = r['quad']
        if not r['craft_name'] and norm(r['quad']) == norm(r['board']):
            name += " *(unnamed)*"
        rx = r['rx_protocol'] or ''
        if r['bind_group']:
            rx = (rx + ' ' if rx else 'ELRS ') + f"**[{r['bind_group'].split('-')[-1]}]**"
        rx = rx or '-'
        st = status_of(r)
        st_cell = st if st == 'active' else f"**{st}**"   # make retired/lost/building stand out
        A(f"| {name} | {r.get('class') or '—'} | {r.get('discipline') or '—'} | {st_cell} | "
          f"{r['board']} | {short_mcu(r['mcu'])} | "
          f"{r['bf_version'] or '-'} | {r['motor_protocol'] or '-'} | {short_video(r['video_system'])} | "
          f"{rx} | {r['dump_date']} |")
    A("")

    # ---- Rollups ----
    A("## Fleet rollups")
    A("")
    classes = Counter(r['class'] for r in latest_rows if r.get('class'))
    if classes:
        order = {c: i for i, c in enumerate(CLASS_ORDER)}
        items = sorted(classes.items(), key=lambda kv: (order.get(kv[0], 99), kv[0]))
        A("- **Class:** " + ", ".join(f"{n}× {c}" for c, n in items) +
          ". Size class inferred from craft name / board where `hardware.csv` doesn't set it.")
    statuses = Counter(status_of(r) for r in latest_rows)
    if statuses:
        order = {s: i for i, s in enumerate(STATUS_ORDER)}
        items = sorted(statuses.items(), key=lambda kv: (order.get(kv[0], 99), kv[0]))
        A("- **Status:** " + ", ".join(f"{n}× {s}" for s, n in items) +
          ". Lifecycle from `hardware.csv`; a blank there counts as active.")
    disciplines = Counter(r['discipline'] for r in latest_rows if r.get('discipline'))
    if disciplines:
        order = {d: i for i, d in enumerate(DISCIPLINE_ORDER)}
        items = sorted(disciplines.items(), key=lambda kv: (order.get(kv[0], 99), kv[0]))
        blank = sum(1 for r in latest_rows if not r.get('discipline'))
        A("- **Discipline:** " + ", ".join(f"{n}× {d}" for d, n in items) +
          (f", {blank} unset" if blank else "") +
          ". Hand-entered in `hardware.csv` (no heuristic — the dump gives no signal).")
    mcus = Counter(short_mcu(r['mcu']) for r in latest_rows if r['mcu'])
    A("- **Flight controllers:** " + ", ".join(f"{n}× {m}" for m, n in mcus.most_common()) + ".")
    bfs = Counter(f"{a}.{b}" for a, b in (ver_tuple(r['bf_version']) for r in latest_rows) if a)
    A("- **Firmware:** " + ", ".join(f"{n} on BF {v}.x" for v, n in
                                      sorted(bfs.items(), key=lambda kv: (-kv[1], kv[0]))) + ".")
    escs = Counter(r['motor_protocol'] for r in latest_rows if r['motor_protocol'])
    A("- **ESC protocol:** " + ", ".join(f"{n}× {e}" for e, n in escs.most_common()) + ".")
    groups = Counter(r['bind_group'] for r in latest_rows if r['bind_group'])
    if groups:
        parts = []
        for g, n in groups.most_common():
            members = [r['quad'] for r in latest_rows if r['bind_group'] == g]
            uid = next(r['elrs_uid'] for r in latest_rows if r['bind_group'] == g)
            parts.append(f"**{g}** ({n} quad{'s' if n != 1 else ''}, UID `{uid}`)")
        A("- **ExpressLRS bind groups:** " + "; ".join(parts) +
          ". Quads in the same group share a binding phrase and bind to the same radio together.")
    vids = Counter(short_video(r['video_system']) for r in latest_rows if r['video_system'])
    if vids:
        A("- **Video:** " + ", ".join(f"{n}× {v}" for v, n in vids.most_common()) +
          ". Quads showing `-` have `vcd_video_system` at firmware default in the diff — "
          "not necessarily video-less.")
    A("")

    # ---- Needs attention ----
    A("## Needs attention")
    A("")
    # Retired/lost quads are intentionally excluded from the firmware/staleness nags below — a
    # shelved or gone quad doesn't need a fresh backup or a flash. They still appear in the fleet
    # table (flagged by status); this section is only about things worth acting on.
    inservice = [r for r in latest_rows if status_of(r) in FLYABLE]

    broken = [r for r in latest_rows if status_of(r) == 'broken']
    if broken:
        A("**Broken (needs repair — grounded until fixed):** "
          + ", ".join(r['quad'] for r in broken) + ".")
        A("")

    building = [r for r in latest_rows if status_of(r) in ('building', 'rebuilding')]
    if building:
        A("**In progress (config expected incomplete — not a truncated dump):** "
          + ", ".join(f"{r['quad']} ({status_of(r)})" for r in building) + ".")
        A("")

    aging = [r for r in inservice if r['bf_version'] and ver_tuple(r['bf_version']) < (4, 4)]
    if aging:
        A("**Aging firmware (older than BF 4.4):**")
        for r in sorted(aging, key=lambda r: ver_tuple(r['bf_version'])):
            A(f"- {r['quad']} ({r['bf_version']})")
        A("")

    today = date.today()
    stale = []
    for r in inservice:
        try:
            age_days = (today - datetime.strptime(r['dump_date'], "%Y-%m-%d").date()).days
        except ValueError:
            continue
        if age_days > 365:
            stale.append((r, age_days))
    if stale:
        A("**Not re-dumped in over a year (take a fresh backup next time on the bench):**")
        for r, _ in sorted(stale, key=lambda t: t[1], reverse=True):
            A(f"- {r['quad']} (last dump {r['dump_date']})")
        A("")

    empties = [r for r in latest_rows if 'EMPTY' in r['note']]
    if empties:
        A("**Truncated dumps (re-export a full backup):**")
        for r in empties:
            A(f"- {r['quad']} — `{r['file']}`")
        A("")

    unclassed = [r for r in latest_rows if not r.get('class')]
    if unclassed:
        A("**Unclassified (heuristic couldn't tell — set `class` in `hardware.csv`):** "
          + ", ".join(r['quad'] for r in unclassed) + ".")
        A("")

    unnamed = [r for r in latest_rows if not r['craft_name'] and norm(r['quad']) == norm(r['board'])]
    if unnamed:
        A("_Note: " + ", ".join(r['quad'] for r in unnamed) +
          " are keyed by board name because their dumps had no craft name set "
          "(`set craft_name` / `# name:`). Setting a craft name makes future tracking more reliable._")
        A("")

    return "\n".join(lines).rstrip() + "\n"


def build_rates_section(latest_rows):
    """Compact per-quad rates table. Only lists quads that set any rate (the rest are at firmware
    default). Values are the raw stored r/p/y integers; meaning depends on rates_type."""
    have = [r for r in latest_rows
            if r.get('rates_type') or r.get('rc_rate_rpy') or r.get('super_rate_rpy') or r.get('expo_rpy')]
    if not have:
        return ""
    lines = ["", "## Rates", "",
             "_Active rateprofile only, raw stored r/p/y values (see `fpv_quads_latest.csv`). Meaning "
             "depends on type — BETAFLIGHT: RC Rate / Super / Expo; ACTUAL: Center Sens / Max Rate / "
             "Expo. Blank type = firmware default (ACTUAL); quads at all-default rates are omitted._",
             "",
             "| Quad | Type | RC rate | Super | Expo | Profile |",
             "|---|---|---|---|---|---|"]
    for r in sorted(have, key=lambda r: r['quad'].lower()):
        lines.append(f"| {r['quad']} | {r.get('rates_type') or 'default'} | "
                     f"{r.get('rc_rate_rpy') or '—'} | {r.get('super_rate_rpy') or '—'} | "
                     f"{r.get('expo_rpy') or '—'} | {r.get('rateprofile') or '—'} |")
    lines.append("")
    return "\n".join(lines)


def build_hardware_section(path, latest_rows):
    """Optional '## Hardware' section from a hand-maintained hardware.csv. This data (ESC stack,
    motors, props, cell count) isn't in the Betaflight dumps, so it's curated separately and joined
    to quads by normalized name."""
    if not os.path.exists(path):
        return ""
    with open(path, newline='') as f:
        hw = list(csv.DictReader(f))
    if not hw:
        return ""
    known = {norm(r['quad']) for r in latest_rows}
    lines = ["", "## Hardware", "",
             "_Curated per-quad build details (not captured in Betaflight dumps), largely seeded from a "
             "hand-maintained spreadsheet. Edit `hardware.csv`; some rows may be stale (see notes)._",
             "",
             "| Quad | Cells | Weight | ESC / stack | Motors | Props | Camera | VTX | Notes |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(hw, key=lambda r: r['quad'].lower()):
        star = "" if norm(r['quad']) in known else " *(no matching dump)*"
        lines.append(f"| {r.get('quad','')}{star} | {r.get('cells','')} | {r.get('weight','')} | "
                     f"{r.get('esc_stack','')} | {r.get('motors','')} | {r.get('props','')} | "
                     f"{r.get('camera','')} | {r.get('vtx','')} | {r.get('notes','')} |")
    lines.append("")
    return "\n".join(lines)


def build_flights_section(path):
    """Optional '## Flights' section, built from flights.csv if it exists (produced by
    update_flights.py). Kept separate so this stdlib-only script never needs the blackbox parser."""
    if not os.path.exists(path):
        return ""
    with open(path, newline='') as f:
        flights = list(csv.DictReader(f))
    if not flights:
        return ""

    def num(v):
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    groups = {}
    for fl in flights:
        key = fl.get('craft') or fl.get('quad') or '?'
        groups.setdefault(key, []).append(fl)

    lines = ["", "## Flights", "",
             "_From decoded Betaflight blackbox logs (see `flights.csv`). Raw `.BBL` logs are not "
             "committed._", ""]
    for quad in sorted(groups, key=str.lower):
        fs = sorted(groups[quad], key=lambda r: (r['date'], r['time']))
        tot_t = sum(num(f['duration_s']) for f in fs)
        tot_mah = sum(num(f['mah']) for f in fs)
        worst = max(fs, key=lambda f: num(f['sag_v']))
        flagged = [f for f in fs if f.get('flags')]
        head = (f"**{quad}** — {len(fs)} flight{'s' if len(fs) != 1 else ''}, "
                f"{tot_t:.0f}s total, {tot_mah:.0f} mAh total, "
                f"worst sag {num(worst['sag_v']):.2f}V ({worst['date']}).")
        if flagged:
            head += f"  ⚠️ {len(flagged)} flagged flight{'s' if len(flagged) != 1 else ''}."
        lines.append(head)
        lines.append("")
        lines.append("| Date | Dur | Batt | Min | Sag | Avg A | Peak A | mAh | Motor sat | Flags |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for f in fs:
            lines.append(f"| {f['date']} | {num(f['duration_s']):.0f}s | {f['cells']}S "
                         f"{f['v_start']}V | {f['v_min']}V | {num(f['sag_v']):.2f}V | "
                         f"{f['a_avg']}A | {f['a_peak']}A | {f['mah']} | {num(f['motor_sat_pct']):.1f}% | "
                         f"{f.get('flags') or '—'} |")
        lines.append("")
    return "\n".join(lines)


def main():
    rows, scanned = parse_dumps()
    if not rows:
        print(f"No BTFL_cli_*.txt dumps found in {SRC}", file=sys.stderr)
        sys.exit(1)
    latest_rows = latest_per_quad(rows)

    write_csv(OUT, rows)
    write_csv(OUT_LATEST, latest_rows)
    with open(OUT_SUMMARY, 'w') as f:
        f.write(build_summary(latest_rows).rstrip() + "\n")
        f.write(build_rates_section(latest_rows))
        f.write(build_hardware_section(os.path.join(SRC, "hardware.csv"), latest_rows))
        f.write(build_flights_section(os.path.join(SRC, "flights.csv")))

    dropped = scanned - len(rows)
    print(f"Scanned {scanned} dumps -> {len(rows)} rows "
          f"({dropped} duplicate{'s' if dropped != 1 else ''} collapsed) -> {len(latest_rows)} quads")
    print(f"  {OUT}")
    print(f"  {OUT_LATEST}")
    print(f"  {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
