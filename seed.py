"""Create and seed bizdesk.db with deterministic demo data."""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "bizdesk.db"

SCHEMA = """
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS notes;
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY, name TEXT, segment TEXT,
    status TEXT, since TEXT);
CREATE TABLE invoices (
    invoice_id TEXT PRIMARY KEY, customer_id INTEGER, amount REAL,
    issued_date TEXT, due_date TEXT, paid_date TEXT, status TEXT);
CREATE TABLE notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER,
    created_at TEXT, body TEXT);
"""

CUSTOMERS = [
    ("Lakeside Logistics", "enterprise", "active", "2023-04-10"),
    ("BrightBooks", "smb", "active", "2024-01-22"),
    ("Peak Forms", "smb", "active", "2024-06-03"),
    ("Harbor Health", "enterprise", "active", "2023-11-15"),
    ("QuietLoop Dev", "startup", "active", "2025-02-14"),
    ("Sunset Retail Co", "smb", "churned", "2022-08-30"),
    ("Northwind Traders", "enterprise", "active", "2024-09-01"),
    ("Cobalt Cafe Group", "smb", "active", "2025-05-19"),
]


def main() -> None:
    rng = random.Random(11)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    for i, (name, seg, status, since) in enumerate(CUSTOMERS, start=1):
        conn.execute("INSERT INTO customers VALUES (?,?,?,?,?)",
                     (i, name, seg, status, since))

    inv_no = 1000
    today = date(2026, 7, 17)
    for cid in range(1, len(CUSTOMERS) + 1):
        for _ in range(rng.randint(4, 9)):
            inv_no += 1
            amount = rng.choice([450, 900, 1500, 2400, 3600, 5200])
            issued = today - timedelta(days=rng.randint(5, 400))
            due = issued + timedelta(days=30)
            paid, status = None, "unpaid"
            roll = rng.random()
            if roll < 0.72:
                status, paid = "paid", (due - timedelta(days=rng.randint(0, 25))).isoformat()
            elif roll < 0.8 and due > today:
                status = "unpaid"          # not yet due
            conn.execute(
                "INSERT INTO invoices VALUES (?,?,?,?,?,?,?)",
                (f"INV-{inv_no}", cid, amount, issued.isoformat(), due.isoformat(), paid, status),
            )

    notes = [
        (1, "2026-06-30", "Asked about API rate limits during QBR — send docs."),
        (2, "2026-07-02", "Duplicate charge resolved; goodwill credit applied."),
        (5, "2026-07-10", "Interested in the automation add-on next quarter."),
    ]
    conn.executemany(
        "INSERT INTO notes (customer_id, created_at, body) VALUES (?,?,?)", notes
    )
    conn.commit()

    n_inv = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    print(f"Seeded {len(CUSTOMERS)} customers, {n_inv} invoices → {DB_PATH.name}")


if __name__ == "__main__":
    main()
