"""Dichiarazioni salariali: AVS (IAS o GastroSocial), LPP (GastroSocial), imposta alla fonte (PDF per mese)."""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from core import db
from core.buste.calcolo import buste_dipendente

MODULI = Path(__file__).resolve().parent.parent / "assets" / "moduli"
MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
LIMITE_AD = 148200.0


def _d(s):
    if isinstance(s, dt.date):
        return s
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _f(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _chf(x):
    return f"{x:,.2f}".replace(",", "'")


def _is_gastro(nome: str) -> bool:
    return "gastro" in (nome or "").lower()


# ── dati dell'anno ────────────────────────────────────────────────────────────
def dati_anno(az: dict, anno: int) -> list[dict]:
    out = []
    for d in db.ordina_dipendenti(az.get("dipendenti", [])):
        bs = [b for b in buste_dipendente(d) if b["anno"] == anno]
        if not bs:
            continue
        avs, ifm, bon = [0.0] * 12, [0.0] * 12, [0.0] * 12
        info = {}
        periodi, visti = [], set()
        for b in bs:
            c, v = b.get("calc") or {}, b.get("input") or {}
            m = b["mese"] - 1
            avs[m] += float(c.get("lordo_avs") or 0)
            ifm[m] += float(c.get("lordo_if") or 0)
            bon[m] += float(c.get("bonus") or 0)
            info[m] = (c.get("tariffa_fonte") or "", float(c.get("imposta_pct") or 0),
                       float(c.get("imposta") or 0) + float((c.get("cong") or {}).get("imposta") or 0))
            for tipo, sg, pct in (("Malato", "mal", v.get("ass_pct")), ("Infortunio", "inf", v.get("ass_pct")), ("Incinta", "mat", 100)):
                ini = _d(v.get(f"{sg}_inizio"))
                if ini and (tipo, ini) not in visti:
                    visti.add((tipo, ini))
                    periodi.append((tipo, float(pct or 80), ini, _d(v.get(f"{sg}_fine"))))
        ent = _d(d.get("data_assunzione") or d.get("data_entrata"))
        usc = next((_d((b.get("input") or {}).get("uscita")) for b in reversed(bs) if (b.get("input") or {}).get("uscita")), None)
        i0, i1 = dt.date(anno, 1, 1), dt.date(anno, 12, 31)
        dal = max(ent, i0) if ent and ent.year <= anno else i0
        al = min(usc, i1) if usc and usc.year <= anno else i1
        out.append({"cognome": d.get("cognome", ""), "nome": d.get("nome", ""), "avs": d.get("numero_avs", ""),
                    "nascita": _d(d.get("data_nascita")), "entrata": ent, "uscita": usc, "dal": dal, "al": al,
                    "lordo_avs": avs, "lordo_if": ifm, "bonus": bon, "fonte": info, "periodi": periodi})
    return out


def _unisci(overlay_pagine: list[tuple[int, bytes]], modello: Path, solo_overlay_pagine=None) -> bytes:
    """Sovrappone ad ogni pagina del modello il testo dell'overlay (lista di (indice pagina modello, pdf overlay))."""
    w = PdfWriter()
    for idx, ov in overlay_pagine:
        base = PdfReader(str(modello)).pages[idx]
        if "/Annots" in base:
            del base["/Annots"]
        base.merge_page(PdfReader(io.BytesIO(ov)).pages[0])
        w.add_page(base)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _ov(size, fn) -> bytes:
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=size)
    fn(c)
    c.showPage()
    c.save()
    return b.getvalue()


# ── AVS: IAS ──────────────────────────────────────────────────────────────────
def avs_ias_pdf(az: dict, anno: int) -> bytes:
    righe = dati_anno(az, anno)
    H = A4[1]
    nome_az = az.get("ragione_sociale") or db.nome_azienda(az)
    indirizzo = ", ".join(x for x in (az.get("sede_via"),) if x)
    npa = " ".join(x for x in (az.get("sede_npa"), az.get("sede_localita")) if x)

    def p0(c):
        c.setFont("Helvetica", 9)
        c.drawString(371, 603, nome_az[:44])
        c.drawString(95, 575, str(az.get("numero_che") or ""))
        c.drawString(95, 515, indirizzo)
        c.drawString(465, 515, npa)
        c.drawString(95, 440, az.get("persona_contatto") or "")
        c.drawString(95, 413, az.get("email") or "")
        c.drawString(340, 413, az.get("telefono") or "")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(88 if righe else 336, 337, "X")
        c.setFont("Helvetica", 9)
        c.drawString(90, 254, az.get("cassa_lpp") or "")
        c.drawString(90, 83, az.get("assicuratore_infortuni") or "")
    pagine = [(0, _ov(A4, p0))]
    tot_a = sum(sum(r["lordo_avs"]) for r in righe)
    tot_ad = sum(min(sum(r["lordo_avs"]), LIMITE_AD) for r in righe)
    blocchi = [righe[i:i + 10] for i in range(0, max(len(righe), 1), 10)] or [[]]
    for bi, blocco in enumerate(blocchi):
        def p1(c, blocco=blocco, ultimo=(bi == len(blocchi) - 1)):
            c.setFont("Helvetica", 9)
            c.drawString(340, 722, nome_az[:44])
            c.drawString(95, 696, str(az.get("numero_che") or ""))
            for i, r in enumerate(blocco):
                y = [607, 573, 539, 505, 471, 437, 403, 369, 335, 301][i]
                c.setFont("Helvetica", 8.5)
                c.drawString(140, y + 3, (r["avs"] or "").replace("756.", "", 1))
                c.drawString(224, y + 3, r["cognome"][:20])
                c.drawString(96, y - 14, _f(r["nascita"]))
                c.drawString(224, y - 14, r["nome"][:20])
                c.drawString(369, y - 14, f"{r['dal'].strftime('%d.%m')} – {r['al'].strftime('%d.%m')}")
                c.drawRightString(570, y - 14, _chf(sum(r["lordo_avs"])))
            if ultimo:
                c.setFont("Helvetica-Bold", 8.5)
                c.drawRightString(294, 206, _chf(tot_a))
                c.drawRightString(478, 206, _chf(tot_a))
                c.drawRightString(570, 206, _chf(tot_ad))
                c.setFont("Helvetica", 9)
                c.drawString(87, 95, f"{az.get('sede_localita') or ''}, {dt.date.today().strftime('%d.%m.%Y')}")
        pagine.append((1, _ov(A4, p1)))
    # la pagina 3 del modulo (istruzioni) resta uguale
    pagine.append((2, _ov(A4, lambda c: None)))
    return _unisci(pagine, MODULI / "avs_ias.pdf")


# ── AVS: GastroSocial (modulo non fornito: elenco equivalente generato) ────────
def _tabella_pdf(titolo: str, sotto: str, intestazioni: list[str], righe: list[list[str]], larghezze: list[float],
                 totale: list[str] | None = None, orient=landscape) -> bytes:
    size = orient(A4)
    W, H = size
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=size)
    blu = colors.HexColor("#1B6FA8")

    def testa(c):
        c.setFont("Helvetica-Bold", 14)
        c.drawString(30, H - 40, titolo)
        c.setFont("Helvetica", 9)
        for i, t in enumerate(sotto.split("\n")):
            c.drawString(30, H - 56 - i * 12, t)
        return H - 56 - len(sotto.split("\n")) * 12 - 14

    y = testa(c)

    def riga(c, y, vals, bold=False, fill=None):
        x = 30
        h = 16
        if fill:
            c.setFillColor(fill)
            c.rect(30, y - 4, sum(larghezze), h, stroke=0, fill=1)
            c.setFillColor(colors.white)
        else:
            c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 8)
        for i, (v, w) in enumerate(zip(vals, larghezze)):
            if i >= 3 or v.replace("'", "").replace(".", "").replace("-", "").isdigit():
                c.drawRightString(x + w - 3, y, v)
            else:
                c.drawString(x + 3, y, v[:int(w / 4.2)])
            x += w
        c.setStrokeColor(colors.HexColor("#BBBBBB"))
        c.line(30, y - 4, 30 + sum(larghezze), y - 4)
        return y - h

    y = riga(c, y, intestazioni, True, blu)
    for r in righe:
        if y < 50:
            c.showPage()
            y = testa(c)
            y = riga(c, y, intestazioni, True, blu)
        y = riga(c, y, r)
    if totale:
        y = riga(c, y - 2, totale, True)
    c.save()
    return buf.getvalue()


def avs_gastro_pdf(az: dict, anno: int) -> bytes:
    righe = dati_anno(az, anno)
    nome_az = az.get("ragione_sociale") or db.nome_azienda(az)
    rr = [[f"{r['cognome']} {r['nome']}", r["avs"] or "", _f(r["nascita"]),
           f"{r['dal'].strftime('%d.%m')}–{r['al'].strftime('%d.%m')}", _chf(sum(r["lordo_avs"])),
           _chf(min(sum(r["lordo_avs"]), LIMITE_AD))] for r in righe]
    tot = ["Totale", "", "", "", _chf(sum(sum(r["lordo_avs"]) for r in righe)),
           _chf(sum(min(sum(r["lordo_avs"]), LIMITE_AD) for r in righe))]
    return _tabella_pdf(
        f"Dichiarazione dei salari AVS {anno} – GastroSocial",
        f"{nome_az} – {az.get('sede_via') or ''}, {az.get('sede_npa') or ''} {az.get('sede_localita') or ''}\n"
        f"N. IDI: {az.get('numero_che') or ''}   Cassa AVS: {az.get('cassa_avs') or ''}   Periodo: 01.01.{anno} – 31.12.{anno}",
        ["Cognome e nome", "N. AVS", "Data di nascita", "Occupato dal–al", "Salario AVS/AI/IPG CHF", "Salario AD fino a 148'200 CHF"],
        rr, [190, 100, 80, 90, 130, 150], tot)


# ── LPP GastroSocial ──────────────────────────────────────────────────────────
def lpp_gastro_pdf(az: dict, anno: int, trimestrale: bool = False) -> bytes:
    righe = dati_anno(az, anno)
    nome_az = az.get("ragione_sociale") or db.nome_azienda(az)
    size = landscape(A4)
    H = size[1]
    per_pagina = 12
    blocchi = [righe[i:i + per_pagina] for i in range(0, max(len(righe), 1), per_pagina)] or [[]]
    pagine = []
    for blocco in blocchi:
        def fn(c, blocco=blocco):
            c.setFont("Helvetica", 8)
            c.drawString(215, H - 72, f"01.01.{anno} – 31.12.{anno}")
            c.drawString(215, H - 85, str(az.get("numero_che") or ""))
            c.drawString(262, H - 97, nome_az[:40])
            c.drawString(482, H - 72, nome_az[:40])
            c.drawString(482, H - 85, az.get("sede_via") or "")
            c.drawString(482, H - 97, f"{az.get('sede_npa') or ''} {az.get('sede_localita') or ''}")
            for i, r in enumerate(blocco):
                top = 172.5 + i * 29.9
                c.setFont("Helvetica", 7.5)
                c.drawString(22, H - top - 13, f"{r['cognome']} {r['nome']}"[:34])
                c.drawString(22, H - top - 25, f"{r['avs']}  {_f(r['nascita'])}")
                c.drawString(232, H - top - 13, _f(r["entrata"]) if r["entrata"] and r["entrata"].year == anno else "")
                c.drawString(232, H - top - 25, _f(r["uscita"]) if r["uscita"] and r["uscita"].year == anno else "")
                ordinari = [p for p in r["periodi"] if p[0] != "Incinta"][:2]
                mat = [p for p in r["periodi"] if p[0] == "Incinta"][:1]
                for k, (tipo, pct, ini, fin) in [(i, p) for i, p in enumerate(ordinari)] + [(2, p) for p in mat]:
                    yy = H - top - 8 - k * 10
                    if tipo != "Incinta":
                        cx = {"Malato": 228, "Infortunio": 284}[tipo]
                        c.setFont("Helvetica-Bold", 8)
                        c.drawString(cx, yy, "X")
                        c.setFont("Helvetica", 7)
                        c.drawString(322, yy, f"{pct:g}")
                    c.setFont("Helvetica", 7)
                    c.drawString(339, yy, _f(ini)[:6] + _f(ini)[8:])
                    c.drawString(377, yy, (_f(fin)[:6] + _f(fin)[8:]) if fin else "")
                c.setFont("Helvetica", 6.5)
                for m in range(12):
                    v = r["lordo_avs"][m]
                    if v:
                        c.drawCentredString(434 + 33.3 * m, H - top - 18, f"{round(v):,}.–".replace(",", "'"))
        pagine.append((0, _ov(size, fn)))
    return _unisci(pagine, MODULI / ("lpp_trim.pdf" if trimestrale else "lpp_annuale.pdf"))


# ── Imposta alla fonte: PDF per mesi ──────────────────────────────────────────
def ifonte_pdf(az: dict, anno: int) -> bytes:
    righe = dati_anno(az, anno)
    nome_az = az.get("ragione_sociale") or db.nome_azienda(az)
    size = landscape(A4)
    W, H = size
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=size)
    larg = [80, 190, 110, 120, 70, 70, 90]
    intest = ["AVS", "Cognome e nome", "Salario mensile", "Comp. aperiodica", "Tabella", "Aliquota", "Imposta"]
    blu = colors.HexColor("#0D2140")
    prima = True
    for m in range(12):
        dm = [(r, r["lordo_if"][m], r["bonus"][m], r["fonte"].get(m)) for r in righe if r["fonte"].get(m)]
        if not dm:
            continue
        if not prima:
            c.showPage()
        prima = False
        c.setFont("Helvetica-Bold", 14)
        c.drawString(30, H - 40, f"Dichiarazione imposta alla fonte – {MESI[m]} {anno}")
        c.setFont("Helvetica", 9)
        c.drawString(30, H - 56, f"{nome_az} – {az.get('sede_via') or ''}, {az.get('sede_npa') or ''} {az.get('sede_localita') or ''}")
        y = H - 85
        c.setFillColor(blu)
        c.rect(30, y - 5, sum(larg), 17, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8.5)
        x = 30
        for t, w in zip(intest, larg):
            c.drawString(x + 3, y, t)
            x += w
        y -= 17
        tot_s = tot_i = 0.0
        for r, lordo, bon, (tab, pct, imp) in dm:
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 8.5)
            vals = [r["avs"], f"{r['cognome']} {r['nome']}", _chf(lordo), _chf(bon) if bon else "", tab, f"{pct:g}%", _chf(imp)]
            x = 30
            for i, (v, w) in enumerate(zip(vals, larg)):
                (c.drawRightString(x + w - 4, y, v) if i in (2, 3, 5, 6) else c.drawString(x + 3, y, str(v)[:int(w / 4.3)]))
                x += w
            c.setStrokeColor(colors.HexColor("#CCCCCC"))
            c.line(30, y - 5, 30 + sum(larg), y - 5)
            tot_s += lordo
            tot_i += imp
            y -= 17
        c.setFont("Helvetica-Bold", 9)
        c.drawString(33, y - 4, "TOTALE (CHF)")
        c.drawRightString(30 + sum(larg[:3]) - 4, y - 4, _chf(tot_s))
        c.drawRightString(30 + sum(larg) - 4, y - 4, _chf(tot_i))
    if prima:
        c.setFont("Helvetica", 11)
        c.drawString(30, H - 60, f"Nessuna busta paga con imposta alla fonte nel {anno}.")
    c.save()
    return buf.getvalue()
