"""Calcoli di ferie, malattia, infortunio e festività (tabelle per azienda e anno, come i fogli «Ferie/Malattie/Infortuni»).

Un'assenza (evento) è un periodo (dal … al …) oppure un semplice numero di giorni in un mese.
Si contano i giorni di calendario: nel foglio Excel ogni giorno segnato vale 1, anche sabato e domenica."""
from __future__ import annotations

import calendar
import datetime as dt

TIPI = {
    "ferie": ("Vacanze", "V", "#BBD9FB"),
    "malattia": ("Malattia", "M", "#D5D8DD"),        # grigi: si prendono in automatico dalle buste paga
    "infortunio": ("Infortunio", "I", "#C2C6CD"),
    "festivita": ("Festività", "H", "#B7E4C7"),
}
MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
GIORNI_SETT = ["L", "M", "M", "G", "V", "S", "D"]
DIRITTO_FERIE = 35.0      # 5 settimane = 35 giorni civili all'anno
DA_BUSTE = ("malattia", "infortunio")      # tipi non modificabili qui: derivano dalle buste paga salvate
_SIGLA = {"malattia": "mal", "infortunio": "inf"}


def giorni_da_buste(az: dict, anno: int, dip_id: str, tipo: str) -> dict[int, list[int]]:
    """mese → giorni di calendario di malattia/infortunio presi dalle buste paga salvate (periodo indicato nella busta, solo giorni di quel mese)."""
    dip = next((d for d in az.get("dipendenti", []) if d.get("id") == dip_id), None)
    out: dict[int, list[int]] = {}
    if not dip:
        return out
    sg = _SIGLA[tipo]
    for b in dip.get("buste_paga", []):
        if b.get("anno") != anno:
            continue
        v = b.get("input") or {}
        ini = _d(v.get(f"{sg}_inizio"))
        if not ini or tipo not in [{"mal": "malattia", "inf": "infortunio"}[sg]]:
            continue
        m = b["mese"]
        fine = _d(v.get(f"{sg}_fine")) or dt.date(anno, m, calendar.monthrange(anno, m)[1])
        g, ultimo = max(ini, dt.date(anno, m, 1)), min(fine, dt.date(anno, m, calendar.monthrange(anno, m)[1]))
        giorni = []
        while g <= ultimo:
            giorni.append(g.day)
            g += dt.timedelta(days=1)
        if giorni:
            out[m] = giorni
    return out


# Diritto annuo di vacanze in GIORNI DI CALENDARIO (4 settimane = 28, 5 settimane = 35), secondo il contratto collettivo dell'azienda.
# CCNL ristorazione/alberghiero art. 17: 5 settimane per tutti. CCL autotrasporti Ticino art. 18.1: 4 settimane dal 20° anno, 5 fino ai 20 anni
# o con 50 anni e 15 di servizio. CCL autorimesse Ticino: 25 gg lavorativi fino a 20 anni e dai 50, 20 gg lavorativi nel mezzo.
# CCL pulizie e CPC parrucchieri: 5 settimane fino a 20 anni e dopo 5 anni nella stessa azienda (pulizie: dai 50 con 5 anni), altrimenti 4.
# Contratto individuale / standard: CO art. 329a, 4 settimane (5 fino a 20 anni).
REGOLE_CCL = {
    "CCNL ristorazione / alberghiero": {"fisso": 35.0},
    "CCL autotrasporti": {"base": 28.0, "alto": 35.0, "eta_max": 19, "eta_min": 50, "servizio_min": 15},
    "CCL autorimesse": {"base": 28.0, "alto": 35.0, "eta_max": 20, "eta_min": 50, "servizio_min": 0},
    "CCL pulizie e facility services": {"base": 28.0, "alto": 35.0, "eta_max": 20, "eta_min": None, "servizio_min": 5},
    "CPC parrucchieri e coiffeur": {"base": 28.0, "alto": 35.0, "eta_max": 20, "eta_min": None, "servizio_min": 5},
}
REGOLA_STANDARD = {"base": 28.0, "alto": 35.0, "eta_max": 20, "eta_min": None, "servizio_min": 0}


def _pct_lavoro(dip: dict | None) -> float:
    cs = [c for c in (dip or {}).get('contratti', []) if c.get('form')]
    if not cs:
        return 100.0
    try:
        return float(max(cs, key=lambda c: c.get('data_inizio') or '')['form'].get('percentuale') or 100.0)
    except (TypeError, ValueError):
        return 100.0


def diritto_default(az: dict, dip: dict | None, anno: int) -> float:
    """Diritto al 100 % scalato alla percentuale di lavoro (es. 80 % → 80 % dei giorni)."""
    return round(_diritto_pieno(az, dip, anno) * _pct_lavoro(dip) / 100 * 2) / 2


def _diritto_pieno(az: dict, dip: dict | None, anno: int) -> float:
    """Giorni di vacanze all'anno secondo il contratto collettivo dell'azienda (età e anni di servizio della persona)."""
    r = REGOLE_CCL.get(az.get("contratto_collettivo") or "", REGOLA_STANDARD)
    if "fisso" in r:
        return r["fisso"]
    dip = dip or {}
    nasc, ass = _d(dip.get("data_nascita")), _d(dip.get("data_assunzione") or dip.get("data_entrata"))
    if nasc and (anno - nasc.year) <= r["eta_max"]:
        return r["alto"]
    anni_serv = (anno - ass.year) if ass else 0
    if r.get("eta_min") is not None:
        if nasc and (anno - nasc.year) >= r["eta_min"] and anni_serv >= r["servizio_min"]:
            return r["alto"]
    elif r["servizio_min"] and anni_serv >= r["servizio_min"]:
        return r["alto"]
    return r["base"]


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
    if tipo in DA_BUSTE:
        for m, gg in giorni_da_buste(az, anno, dip_id, tipo).items():
            mesi[m - 1] = len(gg)
        return mesi
    for ev in dati_anno(az, anno)["eventi"]:
        if ev.get("dip") != dip_id or ev.get("tipo") != tipo:
            continue
        for m, v in giorni_evento(ev, anno).items():
            mesi[m - 1] += len(v) if isinstance(v, list) else int(v)
    return mesi


def riepilogo(az: dict, anno: int, dip_id: str) -> dict:
    d = dati_anno(az, anno)
    cum = float(d["cumulati"].get(dip_id) or 0.0)
    dip = next((x for x in az.get("dipendenti", []) if x.get("id") == dip_id), None)
    dir_ = float(d["diritto"][dip_id]) if d["diritto"].get(dip_id) not in (None, "") else diritto_default(az, dip, anno)
    usati = sum(conteggio_mesi(az, anno, dip_id, "ferie"))
    return {"cumulati": cum, "diritto": dir_, "usufruiti": usati, "residui": cum + dir_ - usati}


def griglia_mese(az: dict, anno: int, mese: int, dip_id: str) -> dict[int, str]:
    """giorno → lettera (F/M/I/H) per un dipendente in un mese. Con sovrapposizioni vince il primo tipo dell'elenco."""
    out: dict[int, str] = {}
    for tipo in DA_BUSTE:
        for g in giorni_da_buste(az, anno, dip_id, tipo).get(mese, []):
            out.setdefault(g, TIPI[tipo][1])
    for tipo in ("ferie", "festivita"):
        for ev in dati_anno(az, anno)["eventi"]:
            if ev.get("dip") != dip_id or ev.get("tipo") != tipo or ev.get("modo") == "numero":
                continue
            for g in giorni_evento(ev, anno).get(mese, []):
                out.setdefault(g, TIPI[tipo][1])
    return out


def giorni_nel_mese(anno: int, mese: int) -> int:
    return calendar.monthrange(anno, mese)[1]
