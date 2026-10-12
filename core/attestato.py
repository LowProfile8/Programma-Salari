"""Attestato del datore di lavoro (assicurazione contro la disoccupazione) precompilato dai dati dell'app.
Le domande senza dato in archivio restano vuote: si completano a mano sul PDF."""
from __future__ import annotations

import calendar
import datetime as dt
import io
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject

from core.buste.calcolo import buste_dipendente
from core.contratti import calcolo as cal
from core.util import data_it

MODELLO = Path(__file__).resolve().parent.parent / "assets" / "moduli" / "attestato_datore_lavoro.pdf"


def _d(x) -> dt.date | None:
    if isinstance(x, dt.date):
        return x
    try:
        return dt.date.fromisoformat(str(x)[:10])
    except (TypeError, ValueError):
        return None


def _gma(x) -> str:
    d = _d(x)
    return d.strftime("%d%m%Y") if d else ""          # i campi data sono a caselle: GGMMAAAA


def _chf(x: float) -> str:
    return f"{round(float(x)):d}"


def _avs(x: str) -> str:
    cifre = re.sub(r"\D", "", x or "")
    return cifre[3:] if cifre.startswith("756") else cifre


def _fine_mese(a: int, m: int) -> dt.date:
    return dt.date(a, m, calendar.monthrange(a, m)[1])


def _ore(contratti: list[dict], az: dict) -> tuple[float, float]:
    """(ore settimanali dell'azienda a tempo pieno, ore settimanali del dipendente)."""
    if not contratti:
        return 0.0, 0.0
    c = contratti[-1]
    f = c.get("form") or {}
    cat = f.get("categoria") or "Normale"
    pieno = cal.ore_pieno(c.get("tipo"), cat, float(f.get("ore_aut") or 45.0))
    if c.get("durata") == cal.ORE:
        return pieno, 0.0
    return pieno, cal.ore_settimanali(c.get("tipo"), float(f.get("percentuale") or 100.0), cat, float(f.get("ore_aut") or 45.0))


def precompila(az: dict, dip: dict, oggi: dt.date | None = None) -> tuple[dict, dict]:
    """Restituisce (testi, scelte): testi = campi di testo, scelte = {campo: stato}."""
    oggi = oggi or dt.date.today()
    T: dict = {}
    S: dict = {}
    spunte_extra: list[str] = []
    contratti = sorted([c for c in dip.get("contratti", []) if c.get("form")], key=lambda c: c.get("data_inizio") or "")
    ultimo = contratti[-1] if contratti else None
    buste = buste_dipendente(dip)

    T["2"], T["3"] = dip.get("cognome") or "", dip.get("nome") or ""
    T["txtAHV-Nr"] = _avs(dip.get("numero_avs"))
    T["txtGeburtsdatum"] = _gma(dip.get("data_nascita"))
    T["4"] = az.get("ragione_sociale") or ""
    che = re.sub(r"\D", "", az.get("numero_che") or "")
    if che:
        T["txtUID-Nr"] = che[:9]
    S["Optionsfeld 21"] = "/0"                      # persona di contatto: dell'azienda
    pc = (az.get("persona_contatto") or "").split()
    if pc:
        T["39"], T["56"] = pc[-1], " ".join(pc[:-1])
    T["57"], T["58"] = az.get("telefono") or "", az.get("email") or ""

    # rapporto di lavoro
    inizio = _d(dip.get("data_assunzione")) or (_d(contratti[0].get("data_inizio")) if contratti else None)
    if buste:
        inizio = min(inizio or dt.date.max, dt.date(buste[0]["anno"], buste[0]["mese"], 1))
    licenz = _d(dip.get("data_licenziamento")) if dip.get("stato") == "licenziato" else None
    fine = licenz or (_d(ultimo.get("data_fine")) if ultimo and ultimo.get("durata") == cal.DETERMINATO else None)
    if inizio and inizio != dt.date.max:
        T["txt_2_von"] = _gma(inizio)
    if fine:
        T["txt_2_bis"] = _gma(fine)
    T["45"] = (ultimo or {}).get("funzione") or dip.get("funzione") or ""
    if ultimo:
        parziale = ultimo.get("durata") == cal.ORE or float(ultimo.get("percentuale") or 100) < 100
        S["Optionsfeld 62"] = "/1" if parziale else "/0"
        S["Optionsfeld 63"] = "/0" if ultimo.get("durata") == cal.DETERMINATO else "/1"
        pieno, ore = _ore(contratti, az)
        if pieno:
            T["34"] = f"{pieno:g}"
        if ore:
            T["35"] = f"{ore:g}"
        S["Optionsfeld 72"] = "/1"                  # contratto scritto: sì
        ccl = ultimo.get("tipo") != cal.STANDARD
        S["Optionsfeld 74"] = "/1" if ccl else "/0"
        if ccl:
            T["36"] = az.get("contratto_collettivo") or cal.NOMI_TIPO.get(ultimo.get("tipo"), "")
    S["Optionsfeld 71"] = "/1" if az.get("soci") and any(
        ((s.get("socio") or "").lower() in f"{dip.get('nome', '')} {dip.get('cognome', '')}".lower()
         or (s.get("socio") or "").lower() in f"{dip.get('cognome', '')} {dip.get('nome', '')}".lower())
        for s in az["soci"] if (s.get("socio") or "").strip()) else "/0"
    T["37"] = az.get("cassa_avs") or ""

    # termine del rapporto
    if licenz:
        T["Textfeld 137"] = _gma(licenz)                    # ultimo giorno di lavoro
        pagato = _fine_mese(buste[-1]["anno"], buste[-1]["mese"]) if buste else licenz
        T["Textfeld 138"] = _gma(min(pagato, licenz))      # salario pagato fino al
        lic = dip.get("licenziamento") or {}
        tipo = lic.get("tipo") or "datore"
        S["Optionsfeld 75"] = {"datore": "/0", "causa_grave": "/0", "consensuale": "/2"}.get(tipo, "/0")
        T["46"] = {"datore": "Licenziamento da parte del datore di lavoro", "consensuale": "Disdetta di comune accordo",
                   "causa_grave": "Disdetta immediata per giusta causa (art. 337 CO)"}.get(tipo, "")
        dl = _d(lic.get("data_lettera"))
        if dl:
            T["txt_10_wann"] = _gma(dl)
        T["txt_10_zeitpunkt"] = _gma(licenz)
        if lic.get("con_lettera"):
            S["Optionsfeld 76"] = "/1"                      # disdetta per iscritto
            spunte_extra.append("Kontrollkästchen 46")      # allegare la lettera di disdetta
            if dl and licenz >= dl:
                T["55"] = str((licenz - dl).days)
                S["Optionsfeld 77"] = "/0"                  # giorni
    elif fine:
        S["Optionsfeld 75"] = "/3"                          # rapporto a durata determinata
        T["Textfeld 137"] = _gma(fine)
    # periodi di occupazione degli ultimi due anni
    if inizio and inizio != dt.date.max:
        riferimento = licenz or fine or oggi
        dal = max(inizio, dt.date(riferimento.year - 2, riferimento.month, min(riferimento.day, 28)))
        T["Textfeld 96"], T["Textfeld 1015"] = _gma(dal), _gma(riferimento)

    # salario
    if buste:
        u = buste[-1]
        if u.get("orario"):
            q = next((r["qb"] for r in u.get("righe", []) if r.get("cod") == "stipendio"), 0)
            if q:
                T["64"] = f"{q:.2f}"
        else:
            T["41"] = _chf(next((r["qb"] for r in u.get("righe", []) if r.get("cod") == "stipendio"), u.get("stipendio") or 0))
    S["Optionsfeld 6"] = None
    T["44"] = az.get("cassa_lpp") or ""
    T["16"] = az.get("sede_localita") or ""
    T["Textfeld 142"] = _gma(oggi)

    # assenze degli ultimi 12 mesi (malattia / infortunio / maternità) dalle buste paga
    rif = licenz or oggi
    limite = dt.date(rif.year - 1, rif.month, 1)
    righe_ass = []
    for lettera, chiavi in (("a", ("mal_att", "mal_ass")), ("b", ("inf_att", "inf_ass")), ("c", ("mat",))):
        mesi = [b for b in buste if dt.date(b["anno"], b["mese"], 1) >= limite and sum((b.get("giorni") or {}).get(k, 0) for k in chiavi) > 0]
        if mesi:
            dal_, al_ = mesi[0], mesi[-1]
            righe_ass.append((lettera, dt.date(dal_["anno"], dal_["mese"], 1), _fine_mese(al_["anno"], al_["mese"])))
    if ultimo:
        spunte_extra.append("Kontrollkästchen 49")          # contratto di lavoro in allegato (domanda 7)
    if buste:
        spunte_extra.append("Kontrollkästchen 48")          # conteggi salariali (domanda 20)
    return T, {"scelte": S, "assenze": righe_ass, "spunte": spunte_extra}


_RIGHE_ASS = [
    (["Kontrollkästchen 103", "Kontrollkästchen 108", "Kontrollkästchen 113", "Kontrollkästchen 118", "Kontrollkästchen 123"], "Textfeld 99", "Textfeld 109"),
    (["Kontrollkästchen 101", "Kontrollkästchen 106", "Kontrollkästchen 111", "Kontrollkästchen 116", "Kontrollkästchen 121"], "Textfeld 100", "Textfeld 1010"),
    (["Kontrollkästchen 102", "Kontrollkästchen 107", "Kontrollkästchen 112", "Kontrollkästchen 117", "Kontrollkästchen 122"], "Textfeld 101", "Textfeld 1011"),
    (["Kontrollkästchen 100", "Kontrollkästchen 105", "Kontrollkästchen 110", "Kontrollkästchen 115", "Kontrollkästchen 120"], "Textfeld 102", "Textfeld 1012"),
    (["Kontrollkästchen 99", "Kontrollkästchen 104", "Kontrollkästchen 109", "Kontrollkästchen 114", "Kontrollkästchen 119"], "Textfeld 108", "Textfeld 1013"),
]


def attestato_pdf(az: dict, dip: dict) -> bytes:
    T, extra = precompila(az, dip)
    scelte = {k: v for k, v in extra["scelte"].items() if v}
    spunte: list[str] = list(extra.get("spunte", []))
    for i, (lettera, dal, al) in enumerate(extra["assenze"][:5]):
        caselle, f_dal, f_al = _RIGHE_ASS[i]
        spunte.append(caselle["abcde".index(lettera)])
        T[f_dal], T[f_al] = _gma(dal), _gma(al)
    if extra["assenze"]:
        scelte["Optionsfeld 78"] = "/1"
    r = PdfReader(str(MODELLO))
    w = PdfWriter()
    w.append(r)
    campi = {k: v for k, v in T.items() if v}
    for pg in w.pages:
        w.update_page_form_field_values(pg, {k: v for k, v in campi.items()}, auto_regenerate=False)
    for pg in w.pages:                                # pulsanti d'opzione e caselle
        for a in pg.get("/Annots", []):
            o = a.get_object()
            nome = o.get("/T") or (o["/Parent"].get_object().get("/T") if "/Parent" in o else None)
            ap = o.get("/AP", {}).get("/N")
            stati = [k for k in (ap.keys() if ap is not None else []) if k != "/Off"]
            if nome in scelte and scelte[nome] in stati:
                o[NameObject("/AS")] = NameObject(scelte[nome])
                tgt = o["/Parent"].get_object() if "/Parent" in o else o
                tgt[NameObject("/V")] = NameObject(scelte[nome])
            elif nome in spunte and stati:
                o[NameObject("/AS")] = NameObject(stati[0])
                o[NameObject("/V")] = NameObject(stati[0])
    w._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()
