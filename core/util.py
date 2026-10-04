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


def _uguali(a, b) -> bool:
    if isinstance(a, dict):
        b = b if isinstance(b, dict) else {}
        return all(_uguali(v, b.get(k)) for k, v in a.items())
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(_uguali(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-6
    return (a if a is not None else "") == (b if b is not None else "") if not isinstance(a, str) \
        else a.strip() == (b.strip() if isinstance(b, str) else ("" if b is None else b))


def uguali(nuovo: dict, salvato: dict | None) -> bool:
    """True se ogni campo di `nuovo` coincide con quello salvato (None e testo vuoto valgono uguale)."""
    return _uguali(nuovo, salvato or {})


def oggi() -> dt.date:
    """Data di oggi in Svizzera (non quella del server, che può essere un altro fuso orario)."""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Zurich")).date()
    except Exception:
        return dt.date.today()
