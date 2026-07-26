import csv
import os

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


def test_missing_order_number_falls_back_to_source():
    existing = [make("Amazon", "", "LiPo", source="msg-1")]
    new = [make("Amazon", "", "LiPo", source="msg-2")]
    rows, stats = m.merge_orders(existing, new)
    assert stats["added"] == 1
    assert len(rows) == 2


def test_missing_order_number_same_source_is_duplicate():
    existing = [make("Amazon", "", "LiPo", source="msg-1")]
    new = [make("Amazon", "", "LiPo", source="msg-1")]
    rows, stats = m.merge_orders(existing, new)
    assert len(rows) == 1


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
