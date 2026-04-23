"""
Integration tests — Expense Tracker API
Run:  pytest tests/ -v
"""

import json
import sqlite3
import uuid

import pytest

# ── Import app & db helpers ───────────────────────────────────────────────────
from app import create_app
import core.database as db_module
from core.database import init_db_with_connection, force_connection


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    """
    Each test gets:
      • A brand-new in-memory SQLite connection (shared for its lifetime).
      • A fresh Flask test client.
      • Automatic teardown: schema dropped & forced connection cleared.
    """
    # 1. Open ONE in-memory connection and build the schema on it
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    init_db_with_connection(conn)

    # 2. Force ALL get_connection() calls to return this same connection
    force_connection(conn)

    # 3. Create the Flask app (init_db inside will be a no-op for schema
    #    because we've already forced the connection)
    app = create_app("testing")
    app.config["TESTING"] = True

    with app.test_client() as c:
        yield c

    # 4. Teardown: release shared connection & restore normal behaviour
    force_connection(None)
    conn.close()


# ── Helper ────────────────────────────────────────────────────────────────────

def add(
    client,
    amount="150.00",
    category="Food",
    description="Test expense",
    date="2024-06-01",
    key=None,
):
    return client.post(
        "/expenses",
        json={
            "amount":          amount,
            "category":        category,
            "description":     description,
            "date":            date,
            "idempotency_key": key or str(uuid.uuid4()),
        },
        content_type="application/json",
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /expenses
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateExpense:

    def test_creates_successfully(self, client):
        res  = add(client)
        data = json.loads(res.data)
        assert res.status_code == 201
        assert data["category"] == "Food"
        assert data["amount"]   == "150"

    def test_response_has_all_fields(self, client):
        data = json.loads(add(client).data)
        for field in ("id", "amount", "amount_display",
                      "category", "description", "date", "created_at"):
            assert field in data, f"Missing field: {field}"

    def test_idempotency_deduplicates(self, client):
        key = str(uuid.uuid4())
        r1  = add(client, key=key)
        r2  = add(client, key=key)
        assert r1.status_code == 201
        assert r2.status_code == 200
        assert json.loads(r1.data)["id"] == json.loads(r2.data)["id"]

    def test_idempotency_third_retry(self, client):
        """Three requests with the same key must all return the same record."""
        key = str(uuid.uuid4())
        ids = [json.loads(add(client, key=key).data)["id"] for _ in range(3)]
        assert len(set(ids)) == 1

    def test_rejects_negative_amount(self, client):
        assert add(client, amount="-50").status_code == 400

    def test_rejects_zero_amount(self, client):
        assert add(client, amount="0").status_code == 400

    def test_rejects_string_amount(self, client):
        assert add(client, amount="abc").status_code == 400

    def test_rejects_invalid_category(self, client):
        assert add(client, category="Rockets").status_code == 400

    def test_rejects_missing_date(self, client):
        res = client.post(
            "/expenses",
            json={"amount": "100", "category": "Food"},
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_rejects_bad_date_format(self, client):
        assert add(client, date="01/06/2024").status_code == 400

    def test_rejects_missing_body(self, client):
        res = client.post(
            "/expenses", data="not-json", content_type="text/plain"
        )
        assert res.status_code == 400

    def test_amount_stored_and_returned_correctly(self, client):
        """₹99.99 must round-trip without floating-point drift."""
        data = json.loads(add(client, amount="99.99").data)
        assert data["amount"] == "99.99"
        assert data["amount_display"] == "₹99.99"


# ══════════════════════════════════════════════════════════════════════════════
# GET /expenses
# ══════════════════════════════════════════════════════════════════════════════

class TestListExpenses:

    def test_returns_list_and_total(self, client):
        add(client, amount="100.00", key=str(uuid.uuid4()))
        add(client, amount="200.00", key=str(uuid.uuid4()))
        data = json.loads(client.get("/expenses").data)
        assert len(data["expenses"]) >= 2
        assert float(data["total"]) >= 300.0

    def test_count_matches_expenses_length(self, client):
        add(client, key=str(uuid.uuid4()))
        add(client, key=str(uuid.uuid4()))
        data = json.loads(client.get("/expenses").data)
        assert data["count"] == len(data["expenses"])

    def test_filter_by_category(self, client):
        add(client, category="Food",      key=str(uuid.uuid4()))
        add(client, category="Transport", key=str(uuid.uuid4()))
        data = json.loads(client.get("/expenses?category=Food").data)
        assert all(e["category"] == "Food" for e in data["expenses"])

    def test_filter_returns_empty_list_not_error(self, client):
        data = json.loads(client.get("/expenses?category=Healthcare").data)
        assert data["expenses"] == []
        assert data["total"] == "0"

    def test_sort_date_descending(self, client):
        add(client, date="2024-01-01", key=str(uuid.uuid4()))
        add(client, date="2024-12-31", key=str(uuid.uuid4()))
        data  = json.loads(client.get("/expenses?sort=date_desc").data)
        dates = [e["date"] for e in data["expenses"]]
        assert dates == sorted(dates, reverse=True)

    def test_sort_date_ascending(self, client):
        add(client, date="2024-01-01", key=str(uuid.uuid4()))
        add(client, date="2024-12-31", key=str(uuid.uuid4()))
        data  = json.loads(client.get("/expenses?sort=date_asc").data)
        dates = [e["date"] for e in data["expenses"]]
        assert dates == sorted(dates)

    def test_invalid_category_filter_returns_400(self, client):
        assert client.get("/expenses?category=Aliens").status_code == 400

    def test_total_is_zero_when_empty(self, client):
        data = json.loads(client.get("/expenses").data)
        assert data["total"] == "0"
        assert data["count"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /expenses/<id>
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteExpense:

    def test_delete_existing(self, client):
        eid = json.loads(add(client).data)["id"]
        res = client.delete(f"/expenses/{eid}")
        assert res.status_code == 200

    def test_deleted_expense_not_in_list(self, client):
        eid = json.loads(add(client).data)["id"]
        client.delete(f"/expenses/{eid}")
        data = json.loads(client.get("/expenses").data)
        ids  = [e["id"] for e in data["expenses"]]
        assert eid not in ids

    def test_delete_nonexistent_returns_404(self, client):
        assert client.delete("/expenses/999999").status_code == 404

    def test_delete_response_message(self, client):
        eid  = json.loads(add(client).data)["id"]
        data = json.loads(client.delete(f"/expenses/{eid}").data)
        assert "message" in data


# ══════════════════════════════════════════════════════════════════════════════
# GET /expenses/summary
# ══════════════════════════════════════════════════════════════════════════════

class TestSummary:

    def test_groups_by_category(self, client):
        add(client, category="Food",      amount="100.00", key=str(uuid.uuid4()))
        add(client, category="Food",      amount="200.00", key=str(uuid.uuid4()))
        add(client, category="Transport", amount="50.00",  key=str(uuid.uuid4()))
        data = json.loads(client.get("/expenses/summary").data)
        cats = {d["category"]: float(d["total"]) for d in data}
        assert cats["Food"]      == pytest.approx(300.0)
        assert cats["Transport"] == pytest.approx(50.0)

    def test_summary_ordered_by_total_desc(self, client):
        add(client, category="Education",     amount="10.00",  key=str(uuid.uuid4()))
        add(client, category="Food",          amount="500.00", key=str(uuid.uuid4()))
        add(client, category="Entertainment", amount="200.00", key=str(uuid.uuid4()))
        data   = json.loads(client.get("/expenses/summary").data)
        totals = [float(d["total"]) for d in data]
        assert totals == sorted(totals, reverse=True)

    def test_summary_empty_returns_list(self, client):
        data = json.loads(client.get("/expenses/summary").data)
        assert isinstance(data, list)
        assert data == []

    def test_summary_count_correct(self, client):
        add(client, category="Food", key=str(uuid.uuid4()))
        add(client, category="Food", key=str(uuid.uuid4()))
        data = json.loads(client.get("/expenses/summary").data)
        food = next(d for d in data if d["category"] == "Food")
        assert food["count"] == 2