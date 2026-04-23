from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from typing import Optional
import re


VALID_CATEGORIES: list[str] = [
    "Food",
    "Transport",
    "Housing",
    "Entertainment",
    "Healthcare",
    "Shopping",
    "Education",
    "Other",
]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _to_paise(raw) -> int:
    """
    Parse a user-supplied amount into paise (integer).
    Uses Decimal to avoid float imprecision.
    Raises ValueError on invalid, zero, or negative values.
    """
    try:
        d = Decimal(str(raw)).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"Invalid amount: {raw!r}. Must be a number.")
    if d <= 0:
        raise ValueError("Amount must be greater than zero.")
    if d > Decimal("10000000"):   # 1 crore safety cap
        raise ValueError("Amount exceeds the maximum allowed value (₹1,00,00,000).")
    return int(d * 100)


def _validate_date(raw: str) -> str:
    if not isinstance(raw, str) or not _DATE_RE.match(raw):
        raise ValueError("Date must be in YYYY-MM-DD format.")
    return raw


def _validate_category(raw: str) -> str:
    if raw not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}."
        )
    return raw


@dataclass(frozen=True)
class ExpenseInput:
    """
    Validated, immutable value object representing a new expense.
    Construct via ExpenseInput.from_dict(raw_dict).
    """
    amount_paise:    int
    category:        str
    description:     str
    date:            str
    idempotency_key: Optional[str]

    @classmethod
    def from_dict(cls, data: dict) -> "ExpenseInput":
        required = ("amount", "category", "date")
        missing  = [f for f in required if not str(data.get(f, "")).strip()]
        if missing:
            raise ValueError(f"Missing required field(s): {', '.join(missing)}.")

        return cls(
            amount_paise    = _to_paise(data["amount"]),
            category        = _validate_category(str(data["category"]).strip()),
            description     = str(data.get("description", "")).strip()[:500],
            date            = _validate_date(str(data["date"]).strip()),
            idempotency_key = data.get("idempotency_key") or None,
        )


def row_to_dict(row) -> dict:
    """Convert a sqlite3.Row expense record to a JSON-safe dict."""
    rupees = Decimal(row["amount"]) / 100
    return {
        "id":             row["id"],
        "amount":         str(rupees),
        "amount_display": f"₹{rupees:,.2f}",
        "category":       row["category"],
        "description":    row["description"],
        "date":           row["date"],
        "created_at":     row["created_at"],
    }