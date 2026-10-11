"""Calcoli di ferie, malattia, infortunio e festività (tabelle per azienda e anno, come i fogli «Ferie/Malattie/Infortuni»).

Un'assenza (evento) è un periodo (dal … al …) oppure un semplice numero di giorni in un mese.
Si contano i giorni di calendario: nel foglio Excel ogni giorno segnato vale 1, anche sabato e domenica."""
from __future__ import annotations

import calendar
import datetime as dt

TIPI = {
    "ferie": ("Ferie", "F", "#BBD9FB"),
    "malattia": ("Malattia", "M", "#FDE3A7"),
    "infortunio": ("Infortunio", "I", "#F9B8B8"),
    "festivita": ("Festività", "H", "#B7E4C7"),
}
MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
GIORNI_SETT = ["L", "M", "M", "G", "V", "S", "D"]
DIRITTO_FERIE = 35.0      # 5 settimane = 35 giorni civili all'anno


def _d(x) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(x)[:10])
    except (TypeError, ValueError):
        return None


def dati_anno(az: dict, anno: int) -> dict:
    tutti = az.get("ferie") or {}
    d = tutti.get(str(anno)) or {}
    d.setdefault("eventi", [])
    d.setdefault("cumulati", {})
    d.setdefault("diritto", {})
    return d


def giorni_evento(ev: dict, anno: int) -> dict[int, list[int] | int]:
    """mese → elenco dei giorni coperti (periodo) oppure numero di giorni (evento «numero»)."""
    if ev.get("modo") == "numero":
        m = int(ev.get("mese") or 1)
        return {m: int(ev.get("n") or 0)}
    dal, al = _d(ev.get("dal")), _d(ev.get("al")) or _d(ev.get("dal"))
    out: dict[int, list[int]] = {}
    if not dal or not al:
        return out
    g = max(dal, dt.date(anno, 1, 1))
    while g <= min(al, dt.date(anno, 12, 31)):
        out.setdefault(g.month, []).append(g.day)
        g += dt.timedelta(days=1)
    return out


def conteggio_mesi(az: dict, anno: int, dip_id: str, tipo: str) -> list[int]:
    """Giorni per mese (12 valori) di un dipendente per un tipo di assenza."""
    mesi = [0] * 12
    for ev in dati_anno(az, anno)["eventi"]:
        if ev.get("dip") != dip_id or ev.get("tipo") != tipo:
            continue
        for m, v in giorni_evento(ev, anno).items():
            mesi[m - 1] += len(v) if isinstance(v, list) else int(v)
    return mesi


def riepilogo(az: dict, anno: int, dip_id: str) -> dict:
    d = dati_anno(az, anno)
    cum = float(d["cumulati"].get(dip_id) or 0.0)
    dir_ = float(d["diritto"].get(dip_id, DIRITTO_FERIE) if d["diritto"].get(dip_id) not in (None, "") else DIRITTO_FERIE)
    usati = sum(conteggio_mesi(az, anno, dip_id, "ferie"))
    return {"cumulati": cum, "diritto": dir_, "usufruiti": usati, "residui": cum + dir_ - usati}


def griglia_mese(az: dict, anno: int, mese: int, dip_id: str) -> dict[int, str]:
    """giorno → lettera (F/M/I/H) per un dipendente in un mese. Con sovrapposizioni vince il primo tipo dell'elenco."""
    out: dict[int, str] = {}
    for tipo in ("infortunio", "malattia", "ferie", "festivita"):
        for ev in dati_anno(az, anno)["eventi"]:
            if ev.get("dip") != dip_id or ev.get("tipo") != tipo or ev.get("modo") == "numero":
                continue
            for g in giorni_evento(ev, anno).get(mese, []):
                out.setdefault(g, TIPI[tipo][1])
    return out


def giorni_nel_mese(anno: int, mese: int) -> int:
    return calendar.monthrange(anno, mese)[1]
