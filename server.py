"""BizDesk MCP — an MCP server that gives Claude safe, structured access
to a small-business back office (customers, invoices, notes).

Run standalone:      python server.py            (stdio transport)
Wire into Claude:    see README — one JSON block in claude_desktop_config
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).parent / "bizdesk.db"

mcp = FastMCP(
    "bizdesk",
    instructions=(
        "Back-office data for a small business. Amounts are USD. "
        "Use overdue_invoices before drafting any payment reminder."
    ),
)


def _conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise RuntimeError("Database missing — run `python seed.py` first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def list_customers(status: str = "all") -> list[dict]:
    """List customers. status: all | active | churned."""
    q = "SELECT * FROM customers"
    args: tuple = ()
    if status in ("active", "churned"):
        q += " WHERE status=?"
        args = (status,)
    with _conn() as conn:
        return [dict(r) for r in conn.execute(q + " ORDER BY name", args)]


@mcp.tool()
def overdue_invoices(min_days_overdue: int = 1) -> list[dict]:
    """Invoices past their due date, most overdue first."""
    today = date.today().isoformat()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT i.invoice_id, c.name AS customer, i.amount, i.due_date,
                      CAST(julianday(?) - julianday(i.due_date) AS INTEGER) AS days_overdue
               FROM invoices i JOIN customers c ON c.customer_id = i.customer_id
               WHERE i.status = 'unpaid' AND i.due_date < ?
               ORDER BY days_overdue DESC""",
            (today, today),
        ).fetchall()
    return [dict(r) for r in rows if r["days_overdue"] >= min_days_overdue]


@mcp.tool()
def revenue_summary(year: int = 2026) -> dict:
    """Paid revenue by month for a year, plus totals and top customer."""
    with _conn() as conn:
        months = conn.execute(
            """SELECT substr(paid_date, 1, 7) AS month, ROUND(SUM(amount), 2) AS revenue
               FROM invoices WHERE status='paid' AND paid_date LIKE ?
               GROUP BY month ORDER BY month""",
            (f"{year}-%",),
        ).fetchall()
        top = conn.execute(
            """SELECT c.name, ROUND(SUM(i.amount), 2) AS total
               FROM invoices i JOIN customers c ON c.customer_id = i.customer_id
               WHERE i.status='paid' AND i.paid_date LIKE ?
               GROUP BY c.name ORDER BY total DESC LIMIT 1""",
            (f"{year}-%",),
        ).fetchone()
    return {
        "year": year,
        "by_month": [dict(m) for m in months],
        "total": round(sum(m["revenue"] for m in months), 2),
        "top_customer": dict(top) if top else None,
    }


@mcp.tool()
def add_note(customer_name: str, note: str) -> str:
    """Attach a timestamped note to a customer record."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT customer_id FROM customers WHERE LOWER(name) = LOWER(?)",
            (customer_name,),
        ).fetchone()
        if not row:
            return f"No customer named '{customer_name}' found."
        conn.execute(
            "INSERT INTO notes (customer_id, created_at, body) VALUES (?, date('now'), ?)",
            (row["customer_id"], note),
        )
    return f"Note added to {customer_name}."


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #

@mcp.resource("bizdesk://customers/{name}")
def customer_card(name: str) -> str:
    """Full customer card: profile, invoices, notes."""
    with _conn() as conn:
        cust = conn.execute(
            "SELECT * FROM customers WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if not cust:
            return f"No customer named '{name}'."
        invoices = conn.execute(
            "SELECT * FROM invoices WHERE customer_id=? ORDER BY due_date DESC",
            (cust["customer_id"],),
        ).fetchall()
        notes = conn.execute(
            "SELECT * FROM notes WHERE customer_id=? ORDER BY created_at DESC",
            (cust["customer_id"],),
        ).fetchall()

    lines = [
        f"# {cust['name']}  ({cust['status']})",
        f"Segment: {cust['segment']} · Since: {cust['since']}",
        "",
        "## Invoices",
    ]
    for i in invoices:
        lines.append(
            f"- {i['invoice_id']} · ${i['amount']} · due {i['due_date']} · {i['status']}"
        )
    lines.append("\n## Notes")
    for n in notes:
        lines.append(f"- [{n['created_at']}] {n['body']}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
