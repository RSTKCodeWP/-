---
name: fpv-orders-update
description: >-
  Search the pilot's Gmail for FPV parts orders and record them as line items in orders.csv,
  a hand-maintainable parts ledger (each part links to a build or stays a spare). Use whenever
  the user asks to find, refresh, import, or update their FPV orders / purchases / parts ledger
  from email, mentions a new order from a vendor (flyfive33, GetFPV, Pyrodrone, RaceDayQuads,
  Webleedfpv, Wrecked, HDZero, DJI, Amazon), or asks "what parts did I buy". Runs interactively where Gmail
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
| flyfive33 | support@flyfive33.com | confirmation subject: "Order #NNNNN received, we're on it!" |
| GetFPV | support@getfpv.com | itemized email: "Invoice for your GetFPV order" (has prices) |
| Pyrodrone | support@pyrodrone.com | confirmation subject: "Order #NNN confirmed"; use plaintextBody |
| RaceDayQuads | support@racedayquads.com | confirmation subject: "Order #NNN Confirmed"; use plaintextBody |
| Webleedfpv | info@webleedfpv.com | confirmed; "weBLEEDfpv Order #NNN …" |
| Wrecked | wrekd.com | confirmed domain (NOT wreckedfpv.com); marketing only, no order confirmations |
| HDZero | sales@divimath.com | HDZero Shop(US) is run by Divimath; Shopify store, subject "Order #NNNN confirmed", clean plaintextBody. (hdzero.us only sends judge.me review requests + tracking) |
| DJI | noreply@dji.com / noreply.dji@dji.com | best-effort FPV filter. NOTE: on the 2021→2026 run DJI had **no FPV gear** — only DJI Mini 2 / Mavic Mini camera drones + DJI Care Refresh service plans (2021-2022), all correctly dropped by the filter. Skip unless the user bought DJI FPV gear (O4 air unit, Goggles, Avata). |
| Amazon | amazon.com | order-confirm / shipment addresses; best-effort FPV filter |

Senders confirmed on a real run (2026-07). Tip: RDQ/Pyrodrone/Webleed are Shopify stores whose
messages include a clean `plaintextBody` — parse that instead of the giant `htmlBody` to save tokens.
GetFPV's itemized email is the "Invoice" (html only). flyfive33's "received, we're on it" is the
order confirmation.

**Registering a new vendor** is two text edits in this file — no code changes (`merge_orders.py` is
vendor-agnostic): (1) add the vendor's name to the `description:` list in the frontmatter above so the
skill triggers when the user mentions it; (2) add a row to the table above with `vendor short name |
sender domain | note`, marked "verify sender on first run" until a real search confirms the actual
sending address (store domain ≠ sender domain sometimes). On the next run the per-vendor search loop
picks it up automatically. Mixed-catalog vendors (marketplaces, gimbal/camera brands) also get the
best-effort FPV filter of step 4.

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

4. **Mixed-catalog vendors (Amazon, DJI)** — best-effort FPV-only filter: include only items that
   read as FPV / drone gear (batteries, connectors, chargers, props, motors, tools, goggles, VTX,
   etc.). Set `flag = ?` on anything you are not confident is FPV gear. Drop clearly non-FPV items.
   The FPV-native vendors (flyfive33, GetFPV, Pyrodrone, RaceDayQuads, Webleedfpv, HDZero) sell only
   FPV gear, so take every line item from them.

5. **Write the staging file** `orders_new.csv` (same columns as `orders.csv`) using the `csv`
   module — never hand-format CSV.

6. **Merge** into the ledger:
   ```bash
   python3 .claude/skills/fpv-orders-update/scripts/merge_orders.py
   ```
   Run this from the **repo root** — it reads/writes the relative `orders.csv` and
   `orders_new.csv` paths by default.
   The script dedups by `(vendor, order_number, item)`, preserves hand-filled `build` / `notes`,
   keeps any existing `?` flag, sorts by date, and prints a summary (added / updated / total).

7. **Clean up** the staging file and report the summary to the user, reminding them they can now
   fill in the `build` column (quad name or `spare`) for the new rows.

## Notes

- **Pricing gotcha (verify qty>1 lines):** the per-item price shown in these emails is inconsistent
  about per-unit vs. extended line total. GetFPV's Invoice price is the extended line total;
  flyfive33's "Total" is per-unit; RaceDayQuads labels a **per-unit** price as "Total" on many
  (esp. 2021-2023) orders while newer ones are extended; Pyrodrone/Webleed (Shopify) show extended.
  For any line with qty>1, reconcile against the order's printed Subtotal (which interpretation makes
  the line items sum to Subtotal) before trusting unit_price/line_total.
- Amazon orders were deferred in the first full run (2021→now); Wrecked = `wrekd.com` had zero order
  confirmations in Gmail (marketing only). Complete BNF/RTF quads land in `category=misc` with `flag=?`.
- HDZero swept 2026-07-22: 4 orders (#1567/#3336/#4476/#4582, 2025-07→2026-01) from `sales@divimath.com`.
  DJI swept same day: no FPV gear (camera drones + Care Refresh only), nothing added.
- `orders_new.csv` is transient and gitignored; only `orders.csv` is committed.
- Do not hand-edit `orders.csv` except the `build` and `notes` columns.
- Tests for the merge script: `.venv/bin/pytest .claude/skills/fpv-orders-update/scripts/test_merge_orders.py`.
- Future enhancement (not yet built): auto-guess `build` from order timing vs. quad dump dates.
