"""core/util.py — piccole funzioni di utilità."""

import datetime as dt
import uuid


def nuovo_id() -> str:
    return uuid.uuid4().hex[:10]


def a_data(valore) -> dt.date | None:
    """'2026-10-01' -> date; None o vuoto -> None."""
    if not valore:
        return None
    try:
        return dt.date.fromisoformat(str(valore))
    except ValueError:
        return None


def da_data(data: dt.date | None) -> str | None:
    return data.isoformat() if data else None


def data_it(valore) -> str:
    """'2026-10-01' -> '01.10.2026' (formato svizzero)."""
    d = a_data(valore)
    return d.strftime("%d.%m.%Y") if d else "—"
