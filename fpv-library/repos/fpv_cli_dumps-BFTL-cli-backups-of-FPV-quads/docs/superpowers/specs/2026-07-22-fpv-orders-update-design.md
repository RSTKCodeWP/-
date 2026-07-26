# fpv-orders-update — Design Spec

**Date:** 2026-07-22
**Status:** Approved, ready for implementation plan

## Purpose

A new project-scoped skill, `fpv-orders-update`, that searches the pilot's Gmail for
FPV parts orders and records them in a hand-maintainable ledger, `orders.csv`. Each row is
a single purchased line item. The ledger serves two goals:

1. **Fleet-linked parts inventory** — tie purchased parts back to the quads they were built
   into (the `build` column).
2. **Spares tracking** — parts that were ordered but never made it into a build remain as
   `spare`, so the ledger doubles as a spares inventory.

This complements the existing `fpv-fleet-update` skill (Betaflight CLI dumps → fleet CSVs).
It is a **separate** skill: different data source (Gmail vs. local `.txt` dumps), different
lifecycle, different execution model.

## Execution model

Reading and parsing order-confirmation emails is a language task, not a deterministic parse,
so this skill is a **procedure Claude follows** in an interactive Claude Code session where
the Gmail MCP tools are authorized — not a headless script. It uses:

- `mcp__claude_ai_Gmail__search_threads` — scoped per-vendor queries
- `mcp__claude_ai_Gmail__get_thread` / `get_message` — read order-confirmation bodies

CSV writing stays deterministic and safe via a thin helper script, `merge_orders.py`:
Claude parses emails into a **staging file** (`orders_new.csv`), and the script **merges**
that into `orders.csv`. The merge preserves hand-edited columns and skips orders already
recorded. This mirrors the repo's rule that hand-maintained data (as in `hardware.csv`) must
never be clobbered by a re-run. `orders.csv` is therefore a hybrid: machine-filled columns
plus hand-filled columns.

Rationale for the staging + merge split (rather than Claude editing `orders.csv` directly):
Claude hand-editing a growing CSV every run is error-prone and risks clobbering the manual
`build` / `notes` columns. A deterministic merge keyed on a stable identity is safe to
re-run any number of times.

## `orders.csv` schema

One row per purchased line item. Columns:

| column | filled by | description |
|--------------|-----------|-------------|
| `vendor` | machine | Vendor short name (e.g. `GetFPV`, `RaceDayQuads`, `Amazon`) |
| `order_date` | machine | `YYYY-MM-DD` of the order |
| `order_number`| machine | Vendor order/confirmation number (stable id) |
| `item` | machine | Product name as it appears in the email |
| `qty` | machine | Quantity ordered |
| `unit_price` | machine | Per-unit price (numeric, no currency symbol; USD assumed) |
| `line_total` | machine | `qty * unit_price` as shown on the order |
| `category` | machine | One of: motor, prop, esc, frame, vtx, cam, battery, rx, tool, misc |
| `build` | **hand** | Quad name, `spare`, or blank (= unassigned). **Never overwritten.** |
| `flag` | machine | `?` for uncertain Amazon items or a shaky parse; else blank |
| `source` | machine | Gmail message id (traceability + dedup fallback) |
| `notes` | **hand** | Free-text; **preserved** across re-runs |

Conventions:
- Currency is assumed USD; no symbol stored. If a non-USD order is seen, note it in `notes`.
- `category` is a coarse best-effort bucket to make spares easy to group/scan.
- `build` semantics: blank = not yet assigned; a quad name = went into that build; `spare` =
  ordered but never built in. The pilot fills this by hand after each run.

## Gmail search strategy

Target vendors (pilot's top FPV suppliers) and their expected sender domains:

| vendor short name | expected sender domain | confidence |
|-------------------|------------------------|------------|
| flyfive33 | flyfive33.com | to verify |
| GetFPV | getfpv.com | likely |
| Pyrodrone | pyrodrone.com | likely |
| RaceDayQuads | racedayquads.com | likely |
| Webleedfpv | webleedfpv.com | to verify |
| Wrecked | wreckedfpv.com | **guess — verify** |
| Amazon | amazon.com (e.g. auto-confirm@amazon.com, shipment-tracking@amazon.com) | likely |

Procedure:
1. **Discover** the real order-confirmation sender for each vendor with a broad first search
   (e.g. `from:wrecked` or a name search) before narrowing. Record the confirmed address in
   SKILL.md over time so later runs skip discovery.
2. **Scoped query** per vendor, e.g.:
   `from:getfpv.com subject:(order OR confirmation OR receipt OR shipped) after:2021/01/01`
   Prefer the order/confirmation email (has line items + prices) over shipping notices; use
   shipping notices only to fill gaps.
3. **Parse** each confirmation into line items → `orders_new.csv` staging rows.
4. **Amazon handling** — best-effort FPV-only filter: include only items that read as FPV /
   drone gear (batteries, connectors, chargers, props, motors, tools, etc.); set `flag = ?`
   on anything uncertain so the pilot can confirm. Non-FPV Amazon items are dropped.

### Initial run scope
- Date range: **since 2021-01-01** (`after:2021/01/01`).
- All seven vendors.

## Incremental re-runs & dedup

- **Dedup key:** `vendor + order_number + item`. A line already present is never duplicated.
  (`source` message id is a secondary tiebreaker if `order_number` is ever missing.)
- **Preserve hand edits:** for a row whose key already exists in `orders.csv`, the merge keeps
  the existing `build`, `notes`, and `flag` values rather than overwriting them.
- **Efficient re-runs:** before searching, the skill reads the newest `order_date` already in
  `orders.csv` and searches Gmail only `after:` that date minus a few days of overlap, so it
  does not re-read years of email each time. (First run uses the 2021-01-01 floor.)

## `merge_orders.py` behavior

Inputs: existing `orders.csv` (may not exist yet) and `orders_new.csv` (staging, produced by
Claude this run). Behavior:

1. Read both. Build an index of existing rows by dedup key.
2. For each staging row:
   - **New key** → append it.
   - **Existing key** → keep the existing row's hand-filled `build` / `notes`, and keep the
     existing `flag` unless it was blank and the new row proposes `?` (never silently clear a
     `?`). Machine columns may be refreshed if the parse improved, but identity columns are
     stable.
3. Write `orders.csv` sorted by `order_date`, then `vendor`, then `order_number`.
4. Print a summary: rows scanned, new rows added, rows skipped as duplicates.

The script is the single source of truth for writing `orders.csv`. It is safe to re-run; it
only ever reads the two inputs and rewrites `orders.csv`.

## Files

```
.claude/skills/fpv-orders-update/
├── SKILL.md                    # procedure, vendor list + confirmed senders, search queries,
│                               # Amazon rules, incremental logic, invocation triggers
└── scripts/merge_orders.py     # staging → orders.csv merge (dedup + preserve hand columns)
```

Repo touch-ups:
- `orders.csv` — generated on first run (committed; `build`/`notes` hand-maintained afterward).
- `orders_new.csv` — transient staging file; **gitignored**.
- `README.md` — mention the new skill alongside `fpv-fleet-update`.
- `TODO.md` — optional: note future enhancement (auto-guess `build` from order timing vs.
  fleet dump dates — deferred out of v1).

## Out of scope (v1 / YAGNI)

- **Auto-guessing `build`** from order timing vs. quad dump dates. Deferred; `build` is blank
  for the pilot to fill on the first run. Noted as a future enhancement.
- Non-USD currency normalization (just flag in `notes` if encountered).
- Returns / refunds / partial cancellations reconciliation.
- Vendors beyond the seven listed.

## Success criteria

- Running the skill on a fresh repo produces an `orders.csv` with line-item rows from all
  seven vendors since 2021-01-01, Amazon items best-effort filtered with `?` flags.
- Re-running after new orders adds only the new lines and never duplicates or clobbers
  hand-filled `build` / `notes`.
- The pilot can assign `build` / `spare` by hand and those edits survive every subsequent run.
