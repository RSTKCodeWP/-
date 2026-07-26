# fpv-orders-update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a project-scoped `fpv-orders-update` skill that reads FPV parts orders from Gmail and records them as line items in a hand-maintainable `orders.csv`, plus the deterministic `merge_orders.py` helper that safely folds each run's parsed orders into that ledger.

**Architecture:** Reading/parsing order-confirmation emails is a language task Claude performs interactively via the Gmail MCP tools, writing parsed line items to a transient staging file `orders_new.csv`. A deterministic Python helper, `merge_orders.py`, merges the staging file into `orders.csv` — deduping by a stable key and preserving hand-filled columns — so the skill is safe to re-run. The skill body (`SKILL.md`) is the procedure Claude follows; the merge script is the only code with automated tests.

**Tech Stack:** Python 3 standard library (`csv`, `argparse`), pytest for tests, existing repo `.venv`. Gmail MCP tools (`search_threads`, `get_thread`, `get_message`) are used at skill-run time, not in the script.

## Global Constraints

- Python: standard library only for `merge_orders.py` — no third-party runtime deps (pytest is dev-only).
- CSV must be written with the `csv` module (`QUOTE_MINIMAL`) — the repo has a prior history of illegal hand-written CSV quoting; never format CSV by hand.
- `orders.csv` column order is fixed and exact: `vendor, order_date, order_number, item, qty, unit_price, line_total, category, build, flag, source, notes`.
- Dedup key is exactly `(vendor, order_number, item)`, compared case-insensitively and whitespace-trimmed.
- Hand-filled columns `build` and `notes` are NEVER overwritten by a re-run. A `?` in `flag` is never silently cleared.
- Currency assumed USD; prices stored as bare numbers, no symbol.
- Skill lives at `.claude/skills/fpv-orders-update/` (project-scoped, mirrors `fpv-fleet-update`).
- Script is invoked as `python3 .claude/skills/fpv-orders-update/scripts/merge_orders.py`.

---

### Task 1: `merge_orders()` core — dedup and add

**Files:**
- Create: `.claude/skills/fpv-orders-update/scripts/merge_orders.py`
- Test: `.claude/skills/fpv-orders-update/scripts/test_merge_orders.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `COLUMNS: list[str]` — the fixed column order.
  - `KEY_FIELDS = ("vendor", "order_number", "item")`.
  - `normalize(row: dict) -> dict` — returns a new dict containing every column in `COLUMNS`, missing values as `""`, all values coerced to `str`.
  - `row_key(row: dict) -> tuple[str, str, str]` — `(vendor, order_number, item)` each `.strip().lower()`.
  - `merge_orders(existing: list[dict], new: list[dict]) -> tuple[list[dict], dict]` — returns `(rows, stats)` where `rows` is the merged list sorted by `(order_date, vendor.lower(), order_number)` and `stats` is `{"existing": int, "added": int, "updated": int}`. In this task, an existing key is kept as-is (updated count still increments); preservation of hand columns is Task 2.

- [ ] **Step 1: Set up pytest in the repo venv**

Run:
```bash
.venv/bin/pip install pytest
```
Expected: pytest installs successfully (or "already satisfied").

- [ ] **Step 2: Write the failing test**

Create `.claude/skills/fpv-orders-update/scripts/test_merge_orders.py`:
```python
import merge_orders as m


def make(vendor, order_number, item, **kw):
    base = {"vendor": vendor, "order_number": order_number, "item": item}
    base.update(kw)
    return m.normalize(base)


def test_columns_order_is_fixed():
    assert m.COLUMNS == [
        "vendor", "order_date", "order_number", "item", "qty",
        "unit_price", "line_total", "category", "build", "flag",
        "source", "notes",
    ]


def test_new_rows_appended_to_existing():
    existing = [make("GetFPV", "1001", "Motor", order_date="2021-02-01")]
    new = [make("RaceDayQuads", "2002", "Props", order_date="2021-03-01")]
    rows, stats = m.merge_orders(existing, new)
    assert stats == {"existing": 1, "added": 1, "updated": 0}
    assert len(rows) == 2
    # sorted by order_date
    assert [r["vendor"] for r in rows] == ["GetFPV", "RaceDayQuads"]


def test_duplicate_key_is_not_duplicated():
    existing = [make("GetFPV", "1001", "Motor", order_date="2021-02-01")]
    new = [make("getfpv", " 1001 ", "  motor ", order_date="2021-02-01")]
    rows, stats = m.merge_orders(existing, new)
    assert stats["added"] == 0
    assert stats["updated"] == 1
    assert len(rows) == 1
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
cd .claude/skills/fpv-orders-update/scripts && ../../../../.venv/bin/pytest test_merge_orders.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'merge_orders'`.

- [ ] **Step 4: Write minimal implementation**

Create `.claude/skills/fpv-orders-update/scripts/merge_orders.py`:
```python
#!/usr/bin/env python3
"""Merge parsed FPV orders (orders_new.csv) into the orders.csv ledger.

Deterministic and safe to re-run: dedups by (vendor, order_number, item) and
preserves the hand-filled `build` / `notes` columns and any `?` in `flag`.
"""

COLUMNS = [
    "vendor", "order_date", "order_number", "item", "qty",
    "unit_price", "line_total", "category", "build", "flag",
    "source", "notes",
]

KEY_FIELDS = ("vendor", "order_number", "item")


def normalize(row):
    """Return a dict with every COLUMNS key present, as trimmed strings."""
    out = {}
    for col in COLUMNS:
        val = row.get(col, "")
        out[col] = "" if val is None else str(val)
    return out


def row_key(row):
    return tuple(row.get(f, "").strip().lower() for f in KEY_FIELDS)


def merge_orders(existing, new):
    merged = {}
    stats = {"existing": len(existing), "added": 0, "updated": 0}
    for row in existing:
        merged[row_key(row)] = normalize(row)
    for row in new:
        key = row_key(row)
        if key in merged:
            merged[key] = normalize(row)
            stats["updated"] += 1
        else:
            merged[key] = normalize(row)
            stats["added"] += 1
    rows = sorted(
        merged.values(),
        key=lambda r: (r["order_date"], r["vendor"].lower(), r["order_number"]),
    )
    return rows, stats
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
cd .claude/skills/fpv-orders-update/scripts && ../../../../.venv/bin/pytest test_merge_orders.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/fpv-orders-update/scripts/merge_orders.py .claude/skills/fpv-orders-update/scripts/test_merge_orders.py
git commit -m "feat: merge_orders core dedup and add"
```

---

### Task 2: Preserve hand-filled columns and flag rule

**Files:**
- Modify: `.claude/skills/fpv-orders-update/scripts/merge_orders.py` (the `merge_orders` function, the `key in merged` branch)
- Test: `.claude/skills/fpv-orders-update/scripts/test_merge_orders.py` (add tests)

**Interfaces:**
- Consumes: `merge_orders`, `normalize`, `row_key` from Task 1.
- Produces: updated `merge_orders` behavior — when a new row's key matches an existing row, the merged row takes the new row's machine columns but keeps the existing row's `build` and `notes`, and sets `flag = existing_flag or new_flag` (existing `?` survives; a blank existing flag accepts a new `?`).

- [ ] **Step 1: Write the failing tests**

Append to `.claude/skills/fpv-orders-update/scripts/test_merge_orders.py`:
```python
def test_existing_build_and_notes_are_preserved():
    existing = [make("GetFPV", "1001", "Motor", order_date="2021-02-01",
                     build="Kronos", notes="left front")]
    new = [make("GetFPV", "1001", "Motor", order_date="2021-02-01",
                unit_price="12.50", build="", notes="")]
    rows, _ = m.merge_orders(existing, new)
    assert rows[0]["build"] == "Kronos"
    assert rows[0]["notes"] == "left front"
    # machine column from the new parse is taken
    assert rows[0]["unit_price"] == "12.50"


def test_existing_question_flag_is_not_cleared():
    existing = [make("Amazon", "111", "LiPo", flag="?")]
    new = [make("Amazon", "111", "LiPo", flag="")]
    rows, _ = m.merge_orders(existing, new)
    assert rows[0]["flag"] == "?"


def test_new_question_flag_applies_when_existing_blank():
    existing = [make("Amazon", "111", "LiPo", flag="")]
    new = [make("Amazon", "111", "LiPo", flag="?")]
    rows, _ = m.merge_orders(existing, new)
    assert rows[0]["flag"] == "?"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
cd .claude/skills/fpv-orders-update/scripts && ../../../../.venv/bin/pytest test_merge_orders.py -v
```
Expected: the three new tests FAIL (`build` is `""`, flag assertions fail).

- [ ] **Step 3: Update the merge branch**

In `.claude/skills/fpv-orders-update/scripts/merge_orders.py`, replace the `if key in merged:` branch inside `merge_orders` with:
```python
        if key in merged:
            prev = merged[key]
            row = normalize(row)
            row["build"] = prev["build"]
            row["notes"] = prev["notes"]
            row["flag"] = prev["flag"] or row["flag"]
            merged[key] = row
            stats["updated"] += 1
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
cd .claude/skills/fpv-orders-update/scripts && ../../../../.venv/bin/pytest test_merge_orders.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/fpv-orders-update/scripts/merge_orders.py .claude/skills/fpv-orders-update/scripts/test_merge_orders.py
git commit -m "feat: preserve hand-filled build/notes and sticky ? flag"
```

---

### Task 3: CSV I/O, first-run handling, and CLI

**Files:**
- Modify: `.claude/skills/fpv-orders-update/scripts/merge_orders.py` (add `read_csv`, `write_csv`, `main`, `__main__` guard)
- Test: `.claude/skills/fpv-orders-update/scripts/test_merge_orders.py` (add I/O tests)

**Interfaces:**
- Consumes: `COLUMNS`, `normalize`, `merge_orders` from Tasks 1–2.
- Produces:
  - `read_csv(path: str) -> list[dict]` — returns `[]` if the file does not exist; otherwise reads with `csv.DictReader` and `normalize`s each row.
  - `write_csv(path: str, rows: list[dict]) -> None` — writes with `csv.DictWriter`, `QUOTE_MINIMAL`, columns in `COLUMNS` order.
  - `main(argv=None) -> int` — argparse CLI with `--orders` (default `orders.csv`) and `--new` (default `orders_new.csv`); reads both, merges, writes `--orders`, prints a one-line summary, returns 0. Errors to stderr and returns 1 if `--new` is missing.

- [ ] **Step 1: Write the failing tests**

Append to `.claude/skills/fpv-orders-update/scripts/test_merge_orders.py`:
```python
import csv
import os


def _write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=m.COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(m.normalize(r))


def test_read_csv_missing_file_returns_empty(tmp_path):
    assert m.read_csv(str(tmp_path / "nope.csv")) == []


def test_write_then_read_roundtrip(tmp_path):
    path = str(tmp_path / "orders.csv")
    rows = [make("GetFPV", "1001", "Motor, 2306", order_date="2021-02-01",
                 notes='has "quotes" and, comma')]
    m.write_csv(path, rows)
    back = m.read_csv(path)
    assert back[0]["item"] == "Motor, 2306"
    assert back[0]["notes"] == 'has "quotes" and, comma'


def test_main_first_run_creates_orders_csv(tmp_path):
    orders = str(tmp_path / "orders.csv")
    new = str(tmp_path / "orders_new.csv")
    _write(new, [make("GetFPV", "1001", "Motor", order_date="2021-02-01")])
    rc = m.main(["--orders", orders, "--new", new])
    assert rc == 0
    assert os.path.exists(orders)
    assert m.read_csv(orders)[0]["vendor"] == "GetFPV"


def test_main_missing_new_file_returns_1(tmp_path):
    rc = m.main(["--orders", str(tmp_path / "orders.csv"),
                 "--new", str(tmp_path / "absent.csv")])
    assert rc == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
cd .claude/skills/fpv-orders-update/scripts && ../../../../.venv/bin/pytest test_merge_orders.py -v
```
Expected: the new tests FAIL (`AttributeError: module 'merge_orders' has no attribute 'read_csv'`).

- [ ] **Step 3: Add I/O and CLI to the script**

Append to `.claude/skills/fpv-orders-update/scripts/merge_orders.py`:
```python
import argparse
import csv
import os
import sys


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return [normalize(row) for row in csv.DictReader(f)]


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            writer.writerow(normalize(row))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Merge orders_new.csv into orders.csv")
    parser.add_argument("--orders", default="orders.csv")
    parser.add_argument("--new", default="orders_new.csv")
    args = parser.parse_args(argv)

    if not os.path.exists(args.new):
        print(f"error: staging file not found: {args.new}", file=sys.stderr)
        return 1

    existing = read_csv(args.orders)
    new = read_csv(args.new)
    rows, stats = merge_orders(existing, new)
    write_csv(args.orders, rows)
    print(
        f"orders.csv: {len(rows)} rows "
        f"({stats['added']} added, {stats['updated']} updated, "
        f"{stats['existing']} pre-existing) from {len(new)} staged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full test file to verify it passes**

Run:
```bash
cd .claude/skills/fpv-orders-update/scripts && ../../../../.venv/bin/pytest test_merge_orders.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/fpv-orders-update/scripts/merge_orders.py .claude/skills/fpv-orders-update/scripts/test_merge_orders.py
git commit -m "feat: orders.csv read/write, first-run and CLI"
```

---

### Task 4: Write `SKILL.md` (the procedure)

**Files:**
- Create: `.claude/skills/fpv-orders-update/SKILL.md`

**Interfaces:**
- Consumes: the `merge_orders.py` CLI from Task 3 (`--orders`, `--new` defaults).
- Produces: the human/agent-facing procedure; no code.

- [ ] **Step 1: Write SKILL.md**

Create `.claude/skills/fpv-orders-update/SKILL.md` with exactly this content:
````markdown
---
name: fpv-orders-update
description: >-
  Search the pilot's Gmail for FPV parts orders and record them as line items in orders.csv,
  a hand-maintainable parts ledger (each part links to a build or stays a spare). Use whenever
  the user asks to find, refresh, import, or update their FPV orders / purchases / parts ledger
  from email, mentions a new order from a vendor (flyfive33, GetFPV, Pyrodrone, RaceDayQuads,
  Webleedfpv, Wrecked, Amazon), or asks "what parts did I buy". Runs interactively where Gmail
  is authorized; it reads order-confirmation emails and merges them into orders.csv.
---

# FPV Orders Update

This skill builds and refreshes `orders.csv` — a ledger of FPV parts the pilot has ordered, one
row per purchased line item. Parts are linked to builds by hand (`build` column) or left as
`spare`. It complements `fpv-fleet-update` (which tracks the quads themselves from CLI dumps).

`orders.csv` is a hybrid file, like `hardware.csv`: most columns are filled from email, but
`build` and `notes` are hand-maintained and must never be clobbered. That is why parsed orders
go through a staging file and a deterministic merge — re-running is always safe.

## Columns

`vendor, order_date, order_number, item, qty, unit_price, line_total, category, build, flag, source, notes`

- `category` — one of: motor, prop, esc, frame, vtx, cam, battery, rx, tool, misc.
- `build` — **hand-filled**: a quad name, `spare`, or blank (= unassigned). Never overwritten.
- `flag` — `?` for uncertain Amazon items or a shaky parse; else blank. A `?` is never cleared.
- `source` — Gmail message id (traceability + dedup fallback).
- `notes` — **hand-filled**, preserved across runs.
- Prices are bare USD numbers (no `$`). Note any non-USD order in `notes`.

## Vendors and senders

| vendor short name | sender domain | note |
|-------------------|---------------|------|
| flyfive33 | flyfive33.com | verify on first run |
| GetFPV | getfpv.com | |
| Pyrodrone | pyrodrone.com | |
| RaceDayQuads | racedayquads.com | |
| Webleedfpv | webleedfpv.com | verify on first run |
| Wrecked | wreckedfpv.com | **guess — verify on first run** |
| Amazon | amazon.com | order-confirm / shipment addresses |

When a sender is confirmed on a real run, update this table so later runs skip discovery.

## Procedure

1. **Determine the search window.**
   - If `orders.csv` exists, read the newest `order_date` in it and search Gmail from a few days
     before that date (overlap is fine — the merge dedups). 
   - If it does not exist (first run), use `after:2021/01/01`.

2. **For each vendor**, search order-confirmation threads with the Gmail MCP tools, e.g.:
   `mcp__claude_ai_Gmail__search_threads` with query
   `from:getfpv.com subject:(order OR confirmation OR receipt OR shipped) after:2021/01/01`.
   - If the sender is marked "verify", first run a broad search (e.g. `from:wrecked`) to confirm
     the real sending address, then narrow.
   - Read the confirmation body with `get_thread` / `get_message`. Prefer the order/confirmation
     email (it has line items + prices); use shipping notices only to fill gaps.

3. **Extract each line item** into a staging row: `vendor, order_date, order_number, item, qty,
   unit_price, line_total, category, source`. Leave `build` and `notes` blank. Choose `category`
   from the fixed list above.

4. **Amazon** — best-effort FPV-only filter: include only items that read as FPV / drone gear
   (batteries, connectors, chargers, props, motors, tools, etc.). Set `flag = ?` on anything you
   are not confident is FPV gear. Drop clearly non-FPV items.

5. **Write the staging file** `orders_new.csv` (same columns as `orders.csv`) using the `csv`
   module — never hand-format CSV.

6. **Merge** into the ledger:
   ```bash
   python3 .claude/skills/fpv-orders-update/scripts/merge_orders.py
   ```
   The script dedups by `(vendor, order_number, item)`, preserves hand-filled `build` / `notes`,
   keeps any existing `?` flag, sorts by date, and prints a summary (added / updated / total).

7. **Clean up** the staging file and report the summary to the user, reminding them they can now
   fill in the `build` column (quad name or `spare`) for the new rows.

## Notes

- `orders_new.csv` is transient and gitignored; only `orders.csv` is committed.
- Do not hand-edit `orders.csv` except the `build` and `notes` columns.
- Tests for the merge script: `.venv/bin/pytest .claude/skills/fpv-orders-update/scripts/test_merge_orders.py`.
- Future enhancement (not yet built): auto-guess `build` from order timing vs. quad dump dates.
````

- [ ] **Step 2: Sanity-check the frontmatter and script path**

Run:
```bash
head -12 .claude/skills/fpv-orders-update/SKILL.md
test -f .claude/skills/fpv-orders-update/scripts/merge_orders.py && echo "script path OK"
```
Expected: frontmatter prints with a `name:` and `description:`; prints `script path OK`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/fpv-orders-update/SKILL.md
git commit -m "docs: fpv-orders-update SKILL.md procedure"
```

---

### Task 5: Repo integration (gitignore, README, TODO)

**Files:**
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `TODO.md`

**Interfaces:**
- Consumes: the skill and script from Tasks 1–4.
- Produces: repo wiring so the staging file is ignored and the skill is documented.

- [ ] **Step 1: Ignore the staging file**

Add to the end of `.gitignore`:
```
# transient staging file for the fpv-orders-update skill; only orders.csv is committed
orders_new.csv
```

- [ ] **Step 2: Verify the staging file is ignored**

Run:
```bash
touch orders_new.csv && git check-ignore orders_new.csv && rm orders_new.csv
```
Expected: prints `orders_new.csv` (confirming it is ignored).

- [ ] **Step 3: Document the skill in README.md**

Add a bullet to the README where the existing `fpv-fleet-update` skill / generated files are described (match the surrounding wording and list style):
```markdown
- `orders.csv` — FPV parts ledger, one row per ordered line item, built from Gmail by the
  `fpv-orders-update` skill. `build` (quad name / `spare` / blank) and `notes` are hand-maintained;
  all other columns come from order-confirmation emails. Re-running only adds new orders.
```

- [ ] **Step 4: Note the deferred enhancement in TODO.md**

Add a new top-level section to `TODO.md`:
```markdown
## Auto-link ordered parts to builds (fpv-orders-update)

The `fpv-orders-update` skill currently leaves the `build` column blank for the pilot to fill.
Future: propose a best-guess `build` from order timing vs. quad dump dates (e.g. motors bought
just before a Kronos dump → `Kronos?`), left as a `?`-flagged suggestion to confirm.
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore README.md TODO.md
git commit -m "chore: wire fpv-orders-update into repo (gitignore, README, TODO)"
```

---

## Self-Review

**Spec coverage:**
- Execution model (staging + deterministic merge) → Tasks 1–3 + SKILL.md (Task 4). ✓
- `orders.csv` schema (exact columns, hand vs. machine) → Global Constraints, Task 1 `COLUMNS`, Task 4 doc. ✓
- Gmail search strategy (per-vendor queries, sender discovery, Amazon `?` filter) → Task 4 procedure steps 2–4. ✓
- Incremental re-runs & dedup (key, preserve edits, `after:` window) → Tasks 1–2 (key + preserve), Task 4 step 1 (window). ✓
- `merge_orders.py` behavior (dedup, preserve, sticky `?`, sort, summary, first-run) → Tasks 1–3. ✓
- Files (skill dir, script, staging gitignore, README/TODO) → Tasks 4–5. ✓
- Out-of-scope items (auto-guess build, currency, returns) → deferred; recorded in Task 5 TODO. ✓

**Placeholder scan:** No TBD/TODO-in-code, no "add error handling" hand-waves — every code step shows complete code and every command shows expected output. The only "TODO" text is the intentional `TODO.md` enhancement note. ✓

**Type consistency:** `COLUMNS`, `KEY_FIELDS`, `normalize`, `row_key`, `merge_orders`, `read_csv`, `write_csv`, `main` are named identically across tasks and the SKILL.md CLI invocation (`--orders` default `orders.csv`, `--new` default `orders_new.csv`) matches Task 3. Dedup key `(vendor, order_number, item)` is consistent in Global Constraints, Task 1, and SKILL.md. ✓
