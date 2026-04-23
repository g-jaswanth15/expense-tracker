# 💰 Expense Tracker

A production-structured full-stack personal finance tool to record, filter,
and review daily expenses.

**Stack:** Flask · SQLite · Bootstrap 5 · Vanilla JS · Pytest

---

## Quick Start

```bash
# 1. Create & activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
# → Open http://127.0.0.1:5000
```

### Run Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
expense_tracker/
├── app.py               # App factory & entry point
├── config.py            # Dev / Test / Prod config classes
├── requirements.txt
├── README.md
│
├── core/
│   ├── __init__.py
│   ├── database.py      # DB connection, schema init, test hook
│   └── models.py        # Validation, value objects, row serialiser
│
├── routes/
│   ├── __init__.py
│   ├── views.py         # HTML page route (Blueprint)
│   └── expenses.py      # REST API routes (Blueprint)
│
├── static/
│   ├── css/
│   │   └── main.css     # All custom styles
│   └── js/
│       └── main.js      # All frontend JavaScript
│
├── templates/
│   ├── base.html        # Base layout
│   └── index.html       # Main dashboard
│
├── db/
│   └── expenses.db      # SQLite DB (auto-created on first run)
│
└── tests/
    ├── __init__.py
    └── test_expenses.py # Integration tests
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/expenses` | Create a new expense |
| `GET` | `/expenses` | List expenses (filter + sort) |
| `DELETE` | `/expenses/<id>` | Delete an expense |
| `GET` | `/expenses/summary` | Total spend grouped by category |

### Query Parameters — `GET /expenses`

| Param | Values | Description |
|-------|--------|-------------|
| `category` | e.g. `Food` | Filter by category |
| `sort` | `date_desc` (default) · `date_asc` | Sort by date |

### Request Body — `POST /expenses`

```json
{
  "amount": "150.00",
  "category": "Food",
  "description": "Lunch at café",
  "date": "2024-06-01",
  "idempotency_key": "a1b2-c3d4-e5f6"
}
```

### Response — `POST /expenses` (201 Created)

```json
{
  "id": 1,
  "amount": "150.00",
  "amount_display": "₹150.00",
  "category": "Food",
  "description": "Lunch at café",
  "date": "2024-06-01",
  "created_at": "2024-06-01T10:30:00Z"
}
```

### Response — `GET /expenses` (200 OK)

```json
{
  "expenses": [...],
  "total": "150.00",
  "total_display": "₹150.00",
  "count": 1
}
```

---

## Key Design Decisions

### 1. Money stored as INTEGER (paise, not rupees)
Floating-point types like `REAL` / `float` are fundamentally unsafe for
money — they silently introduce rounding errors (e.g. `0.1 + 0.2 ≠ 0.3`).
Storing paise as an integer (100 paise = ₹1) is the same approach used by
Stripe, Razorpay, and PayPal. All arithmetic uses Python's `Decimal` with
explicit `quantize()` — no `float` anywhere in the money path.

```
User inputs  →  "150.00"
Stored in DB →  15000   (paise, INTEGER)
Returned     →  "150.00" (Decimal, 2dp always)
Displayed    →  "₹150.00"
```

### 2. Idempotency key on every write
Users on unreliable networks may click "Submit" multiple times or refresh
the page mid-request. Without protection this creates duplicate expenses.
The client generates a UUID once per form load and re-sends it on every
retry. The server checks for an existing record with that key before
inserting — and the database enforces a `UNIQUE` constraint as a final
safety net.

Three independent layers of duplicate protection:

```
Layer 1 — Frontend  : Same UUID kept until server confirms success
Layer 2 — Backend   : Checks if key exists before inserting
Layer 3 — Database  : UNIQUE constraint rejects duplicate keys entirely
```

### 3. App factory pattern (`create_app()`)
The Flask app is created inside a factory function rather than at module
level. This makes it trivial to spin up isolated instances for different
environments (development, testing, production) without any global state
leaking between them. Tests get their own in-memory SQLite instance with
a clean schema every time.

### 4. Blueprints for route separation
API routes (`/expenses`) and page routes (`/`) live in separate Blueprint
files. This keeps concerns clearly separated, makes each file easy to
navigate, and mirrors how a larger production codebase would be structured.

```
routes/
├── views.py      →  GET  /                  (renders HTML page)
└── expenses.py   →  POST /expenses          (create)
                     GET  /expenses          (list + filter + sort)
                     DELETE /expenses/<id>   (delete)
                     GET  /expenses/summary  (grouped totals)
```

### 5. SQLite with WAL mode
SQLite was chosen for zero-config simplicity — appropriate for a
single-user personal finance tool. WAL (Write-Ahead Logging) journal mode
is enabled on every connection for safer concurrent reads and writes.
The DB file lives in its own `/db` folder, separate from source code,
making it easy to back up or exclude from version control.

### 6. Shared connection hook for tests
SQLite `:memory:` databases are connection-scoped — a second
`sqlite3.connect(":memory:")` opens a completely separate empty database.
To make integration tests reliable, a `force_connection()` hook injects a
single shared connection for the lifetime of each test, ensuring that data
written in one request is visible to the next.

### 7. Server-side validation via value objects
All input validation lives in `core/models.py` inside a frozen dataclass
`ExpenseInput`. This means validation is completely decoupled from the
HTTP layer — it can be tested independently and reused if a CLI or
background job ever needs to create expenses.

---

## Trade-offs Made Due to Timebox

### Integration tests only — no unit tests
All 24 tests are integration tests that exercise the full
`HTTP → route → validation → database → response` stack. Pure unit tests
for individual functions (`_to_paise`, `_validate_date`, etc.) were
skipped. The integration tests already catch bugs in those functions
indirectly, and they deliver more coverage per line of test code for a
project this size.

### No pagination
The `GET /expenses` endpoint returns all matching rows in one response.
For a personal tool with a few hundred rows this is perfectly acceptable.
Adding cursor-based or offset pagination would require additional API
parameters, frontend state, and tests — not worth the complexity here.

### No edit / update endpoint
There is no `PATCH /expenses/<id>`. Users who need to correct an entry
must delete and re-add it. A full edit flow would need a second form state
on the frontend, a new API endpoint, and extra validation — skipped to
keep the scope tight.

### CSS and JS loaded from CDN
Bootstrap 5 and Bootstrap Icons are loaded from jsDelivr CDN rather than
bundled locally. This means the UI requires an internet connection to load
styles. In a real production deployment these would be bundled with a tool
like Vite or served from the same origin.

### No frontend framework
The frontend is plain vanilla JS with direct DOM manipulation. For a UI
this simple it is the right call — no build step, no dependencies, easy
to read. At the point where state management becomes complex a lightweight
framework (e.g. Vue or Alpine.js) would be the natural next step.

---

## Intentionally Not Done

| Feature | Reason skipped |
|---------|----------------|
| **User authentication / login** | Out of scope — this is a single-user personal tool |
| **Multi-currency support** | Adds significant complexity (exchange rates, display logic) |
| **CSV / PDF export** | Useful but not part of the core user story |
| **Pagination** | Unnecessary for a personal tool at this data volume |
| **HTTPS / production hardening** | Deployment config (gunicorn, nginx, TLS) is out of scope |
| **Unit tests** | Integration tests cover the same logic indirectly at this scale |
| **Edit / update expense** | Delete and re-add is acceptable for a personal tool |

---

## Database Choice

**SQLite** was chosen because:

- Zero configuration — no server process to manage
- Single file, trivial to back up (`cp db/expenses.db backup.db`)
- More than fast enough for a single-user personal finance tool
- WAL mode makes it safe for the occasional concurrent request
- Keeps the project self-contained with zero external dependencies

If this tool were extended to multiple users or high concurrency,
**PostgreSQL** would be the straightforward migration path —
the SQLAlchemy ORM (or raw psycopg2) could replace the sqlite3 calls
with minimal changes to the rest of the codebase.

---

## Environment Configuration

| Environment | DB | Debug | How to run |
|-------------|-----|-------|------------|
| `development` | `db/expenses.db` | On | `python app.py` |
| `testing` | `:memory:` | On | `pytest tests/ -v` |
| `production` | `db/expenses.db` | Off | `FLASK_ENV=production python app.py` |
