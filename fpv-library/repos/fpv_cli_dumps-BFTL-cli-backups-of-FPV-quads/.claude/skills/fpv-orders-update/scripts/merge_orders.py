#!/usr/bin/env python3
"""Merge parsed FPV orders (orders_new.csv) into the orders.csv ledger.

Deterministic and safe to re-run: dedups by (vendor, order_number, item) and
preserves the hand-filled `build` / `notes` columns and any `?` in `flag`.
"""

import argparse
import csv
import os
import sys

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


# When order_number is blank (e.g. some Amazon confirmations), fall back to
# `source` (the Gmail message id) so distinct orders don't collapse to one key.
def row_key(row):
    vendor = row.get("vendor", "").strip().lower()
    order_number = row.get("order_number", "").strip().lower()
    item = row.get("item", "").strip().lower()
    if not order_number:
        order_number = row.get("source", "").strip().lower()
    return (vendor, order_number, item)


def merge_orders(existing, new):
    merged = {}
    stats = {"existing": len(existing), "added": 0, "updated": 0}
    for row in existing:
        merged[row_key(row)] = normalize(row)
    for row in new:
        key = row_key(row)
        if key in merged:
            prev = merged[key]
            row = normalize(row)
            row["build"] = prev["build"]
            row["notes"] = prev["notes"]
            row["flag"] = prev["flag"] or row["flag"]
            merged[key] = row
            stats["updated"] += 1
        else:
            merged[key] = normalize(row)
            stats["added"] += 1
    rows = sorted(
        merged.values(),
        key=lambda r: (r["order_date"], r["vendor"].lower(), r["order_number"]),
    )
    return rows, stats


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [normalize(row) for row in csv.DictReader(f)]


def write_csv(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            writer.writerow(normalize(row))
    os.replace(tmp, path)


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
