import sqlite3
import uuid
from decimal import Decimal

from flask import Blueprint, jsonify, request

from core.database import get_connection
from core.models import ExpenseInput, row_to_dict, VALID_CATEGORIES

expenses_bp = Blueprint("expenses", __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _err(msg: str, status: int = 400):
    return jsonify({"error": msg}), status


def _commit(conn):
    """Commit without closing — important for shared test connections."""
    conn.commit()


# ── POST /expenses ────────────────────────────────────────────────────────────

@expenses_bp.route("", methods=["POST"])
def create_expense():
    """
    Create a new expense.

    Body (JSON):
        amount           – positive decimal (rupees)
        category         – one of VALID_CATEGORIES
        description      – optional, max 500 chars
        date             – YYYY-MM-DD
        idempotency_key  – optional UUID; de-duplicates retried requests
    """
    data = request.get_json(silent=True)
    if not data:
        return _err("Request body must be valid JSON.")

    try:
        expense = ExpenseInput.from_dict(data)
    except ValueError as exc:
        return _err(str(exc))

    idem_key = expense.idempotency_key or str(uuid.uuid4())
    conn = get_connection()

    try:
        # ── Idempotency check ─────────────────────────────────────────────────
        existing = conn.execute(
            "SELECT * FROM expenses WHERE idempotency_key = ?",
            (idem_key,)
        ).fetchone()
        if existing:
            return jsonify(row_to_dict(existing)), 200

        # ── Insert ────────────────────────────────────────────────────────────
        try:
            cursor = conn.execute(
                """INSERT INTO expenses
                       (idempotency_key, amount, category, description, date)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    idem_key,
                    expense.amount_paise,
                    expense.category,
                    expense.description,
                    expense.date,
                ),
            )
            _commit(conn)

            row = conn.execute(
                "SELECT * FROM expenses WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()
            return jsonify(row_to_dict(row)), 201

        except sqlite3.IntegrityError:
            # Parallel request committed the same idempotency key first
            existing = conn.execute(
                "SELECT * FROM expenses WHERE idempotency_key = ?",
                (idem_key,)
            ).fetchone()
            return jsonify(row_to_dict(existing)), 200

    finally:
        # Only close if this is a real per-request connection (not test shared)
        from core.database import _forced_connection
        if _forced_connection is None:
            conn.close()


# ── GET /expenses ─────────────────────────────────────────────────────────────

@expenses_bp.route("", methods=["GET"])
def list_expenses():
    """
    List expenses.

    Query params:
        category  – filter by exact category name
        sort      – 'date_desc' (default) | 'date_asc'
    """
    category = request.args.get("category", "").strip()
    sort     = request.args.get("sort", "date_desc")
    order    = "ASC" if sort == "date_asc" else "DESC"

    if category and category not in VALID_CATEGORIES:
        return _err(f"Unknown category: {category!r}")

    conn = get_connection()
    try:
        if category:
            rows = conn.execute(
                f"""SELECT * FROM expenses
                    WHERE  category = ?
                    ORDER  BY date {order}, id {order}""",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT * FROM expenses
                    ORDER BY date {order}, id {order}"""
            ).fetchall()
    finally:
        from core.database import _forced_connection
        if _forced_connection is None:
            conn.close()

    expenses     = [row_to_dict(r) for r in rows]
    total_paise  = sum(int(Decimal(e["amount"]) * 100) for e in expenses)
    total_rupees = Decimal(total_paise) / 100

    return jsonify({
        "expenses":      expenses,
        "total":         str(total_rupees),
        "total_display": f"₹{total_rupees:,.2f}",
        "count":         len(expenses),
    }), 200


# ── DELETE /expenses/<id> ─────────────────────────────────────────────────────

@expenses_bp.route("/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id: int):
    conn = get_connection()
    try:
        result = conn.execute(
            "DELETE FROM expenses WHERE id = ?",
            (expense_id,)
        )
        _commit(conn)
    finally:
        from core.database import _forced_connection
        if _forced_connection is None:
            conn.close()

    if result.rowcount == 0:
        return _err("Expense not found.", 404)
    return jsonify({"message": "Deleted successfully."}), 200


# ── GET /expenses/summary ─────────────────────────────────────────────────────

@expenses_bp.route("/summary", methods=["GET"])
def summary():
    """Return spend + count grouped by category."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT   category,
                        SUM(amount) AS total_paise,
                        COUNT(*)    AS count
               FROM     expenses
               GROUP BY category
               ORDER BY total_paise DESC"""
        ).fetchall()
    finally:
        from core.database import _forced_connection
        if _forced_connection is None:
            conn.close()

    return jsonify([
        {
            "category":      r["category"],
            "total":         str(Decimal(r["total_paise"]) / 100),
            "total_display": f"₹{Decimal(r['total_paise']) / 100:,.2f}",
            "count":         r["count"],
        }
        for r in rows
    ]), 200