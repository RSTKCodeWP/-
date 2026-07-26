# fpv_cli_dumps

Betaflight CLI backups for my FPV quads, plus a derived fleet inventory.

## About

I use AI to help build, tune, and troubleshoot my FPV quads — extracting fleet configs from
Betaflight dumps, decoding blackbox flight logs, and diagnosing failures. That includes a motor
desync detector that reads bidirectional-DShot eRPM telemetry to catch a motor that's commanded to
spin hard but isn't — the kind of fault that only shows up under flight load. I write about it on
Substack: [Tracking Down a Flight Failure](https://irekromaniuk.substack.com/p/tracking-down-a-flight-failure-an),
the story behind the Kronos motor-desync analysis in this repo.

## Layout

```
backups/                 Betaflight CLI dumps (BTFL_cli_*.txt), one or more per quad
fpv_quads.csv            History — one row per dump (unchanged re-dumps collapsed), newest per quad flagged 'latest'
fpv_quads_latest.csv     One row per quad, newest dump only
flights.csv              One row per decoded blackbox flight (duration, sag, current, mAh, flags)
hardware.csv             Hand-maintained per-quad build details (ESC, motors, props) + size class, status, discipline, not in dumps
orders.csv               FPV parts ledger, one row per ordered line item, built from Gmail by the fpv-orders-update skill; 'build' (quad/'spare'/blank) and 'notes' hand-maintained, other columns from order emails, re-runs only add new — gitignored (personal purchase history; kept local, not committed)
FLEET_SUMMARY.md         Overview: fleet table, rollups, "needs attention", hardware, flights
blackbox/                Raw .BBL/.BFL flight logs — gitignored (large binaries; not committed)
.claude/skills/fpv-fleet-update/   Skill that regenerates the derived files above
.claude/skills/fpv-orders-update/  Skill that builds orders.csv from Gmail order confirmations
```

## Updating

Drop a new `BTFL_cli_*.txt` dump into `backups/` (any subfolder works — the parser scans
recursively), then regenerate the inventory:

```bash
python3 .claude/skills/fpv-fleet-update/scripts/update_fleet.py
```

The script is the single source of truth: it only reads the dumps and rewrites the two CSVs and
`FLEET_SUMMARY.md`, so it is safe to re-run any time. Don't hand-edit the generated files.

Values are extracted from Betaflight `diff all` output, which only records settings that differ
from firmware defaults — a blank cell means the setting is at its firmware default.

## What counts as a quad

The CLI dump is the single source of truth. A quad appears in the inventory only once there is a
`BTFL_cli_*.txt` dump for it — the Fleet table, rollups, and CSVs are built strictly from the dumps.
A quad tracked only in a separate build spreadsheet won't show up until its dump is added; adding the
dump is what registers it.

Each quad is keyed by the `craft_name` set in its dump (normalized — case, spaces, and underscores
are ignored), falling back to the filename label, then the board name. Setting a real craft name in
Betaflight makes the key stable across re-flashes and file renames.

## Hardware details

`hardware.csv` holds per-quad build details that Betaflight dumps can't carry (ESC/stack, motors,
props, camera, VTX, cells, weight) plus three curated columns — `class` (size bucket), `status`
(lifecycle), and `discipline` (what it's flown for). It is an annotation, never a source: it only
decorates a quad that a dump already put in the inventory, joined by the same normalized name. A row
whose name matches no dump is shown in the summary's Hardware section flagged as such, but does not
create a fleet entry. Edit it by hand; the generator reads it but never writes it.

## Blackbox flight logs

Drop `.BBL`/`.BFL` logs into `blackbox/` (gitignored), then decode them into `flights.csv`:

```bash
python3 -m venv .venv && .venv/bin/pip install orangebox   # one-time
python3 .claude/skills/fpv-fleet-update/scripts/update_flights.py   # -> flights.csv
python3 .claude/skills/fpv-fleet-update/scripts/update_fleet.py     # folds Flights into FLEET_SUMMARY.md
```

Raw logs are large and stay out of git; `flights.csv` is the committed, durable record.

## Orders ledger

`orders.csv` is a parts-purchase ledger — one row per ordered line item — built from Gmail order
confirmations by the `fpv-orders-update` skill (`.claude/skills/fpv-orders-update/`). It's a hybrid
file like `hardware.csv`: most columns come from the order emails, but `build` (the quad a part went
into, or `spare`, or blank) and `notes` are hand-maintained and never overwritten. Re-running only
adds new orders — the merge dedups by `(vendor, order_number, item)` and preserves your edits.

It holds personal purchase history (prices, order numbers), so it's **gitignored and kept local** —
unlike the other CSVs, it is not committed. It lives only on your machine.

To refresh it, invoke the skill (it needs Gmail authorized). It searches each known vendor from the
newest date already in `orders.csv`, extracts line items, and folds them in via:

```bash
python3 .claude/skills/fpv-orders-update/scripts/merge_orders.py
```

Don't hand-edit `orders.csv` except the `build` and `notes` columns.

### Adding a vendor

The vendor registry lives entirely in the skill's `SKILL.md` — the merge script is vendor-agnostic,
so no code changes. To register a new store, edit `.claude/skills/fpv-orders-update/SKILL.md`:

1. Add the vendor's name to the `description:` list in the YAML frontmatter (this makes the skill
   trigger when you mention that vendor).
2. Add a row to the **Vendors and senders** table (`vendor short name | sender domain | note`),
   marked "verify sender on first run" until a real search confirms the actual sending address.

On the next run the skill's per-vendor search loop picks it up automatically. For mixed-catalog
sellers (Amazon, DJI) the skill applies a best-effort FPV-only filter and flags uncertain items `?`.
