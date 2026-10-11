"""core/buste/pdf.py — PDF della busta paga (A4, una pagina) e PDF annuale (buste del solo anno unite)."""

from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from core.buste.calcolo import MESI
from core.contratti import calcolo as cal
from core.contratti import pdf as cpdf    # registra anche i caratteri Carlito

FONT = "Carlito" if cpdf._CARLITO else "Helvetica"
FONT_B = "Carlito-Bold" if cpdf._CARLITO else "Helvetica-Bold"
BLU = (0.05, 0.13, 0.25)
GRIGIO = (0.45, 0.45, 0.48)
FONDO = (0.93, 0.95, 0.98)
AZZURRO = (0.29, 0.64, 0.97)
TESTO_FIRMA = ("Con la firma della presente busta paga si conferma l'accettazione della stessa, nel caso in cui ci siano eventuali "
               "errori o differenze, siete invitati a notificarle entro e non oltre 5 giorni dal ricevimento della stessa.")

# righe che si mostrano sempre; le altre solo se hanno un importo
FISSE = {"stipendio", "lordo_avs", "lordo_if", "avs", "ad", "deduzioni", "netto"}
TOTALI = {"lordo_avs", "lordo_if", "deduzioni", "netto"}


def _chf(v) -> str:
    return f"{float(v):,.2f}".replace(",", "'")


def _data(iso) -> str:
    return cpdf.data_it(iso)


def _spezza(testo: str, font: str, dim: float, larghezza: float) -> list[str]:
    righe, riga = [], ""
    for parola in testo.split():
        prova = f"{riga} {parola}".strip()
        if stringWidth(prova, font, dim) <= larghezza:
            riga = prova
        else:
            righe.append(riga)
            riga = parola
    if riga:
        righe.append(riga)
    return righe


def _quota(riga) -> str:
    cod, _, qb, fattore, tot = riga
    if qb is None:
        return ""
    if cod in ("avs", "ad", "igm", "lainf", "imposta", "vac", "fest"):
        return f"{qb:g}%".replace(".", ".")
    return _chf(qb)


def _fattore(riga, orario: bool) -> str:
    cod, _, qb, fattore, tot = riga
    if fattore is None:
        return ""
    if cod == "stipendio":
        return f"{fattore:g} {'ore' if orario else 'gg'}"
    return f"{fattore:g} {'ore' if cod == 'ore_supp' else 'gg'}"


def busta_pdf(az: dict, dip: dict, busta: dict) -> bytes:
    """`busta` = {anno, mese, input, calc}. Genera la pagina come nei fogli «Salari 2026»."""
    calc = busta["calc"]
    anno, mese = busta["anno"], busta["mese"]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Busta paga {MESI[mese - 1]} {anno} — {dip.get('cognome', '')} {dip.get('nome', '')}")
    W, H = A4
    L, R = 48, W - 48

    def testo(x, y, s, dim=10, bold=False, allinea="l", colore=(0, 0, 0)):
        c.setFont(FONT_B if bold else FONT, dim)
        c.setFillColorRGB(*colore)
        {"l": c.drawString, "r": c.drawRightString, "c": c.drawCentredString}[allinea](x, y, s)

    # intestazione: datore di lavoro (sinistra) e dipendente (destra)
    y = H - 56
    testo(L, y, "Sede Amministrativa:", 8.5, colore=GRIGIO)
    testo(L, y - 14, az.get("ragione_sociale") or "", 12, True, colore=BLU)
    sede1 = az.get("sede_via") or ""
    sede2 = " ".join(x for x in (az.get("sede_npa"), az.get("sede_localita")) if x)
    testo(L, y - 28, sede1, 10)
    testo(L, y - 41, sede2, 10)
    xd = W / 2 + 25
    testo(xd, y, "Egregio Sig. / Gent. Sig.ra", 8.5, colore=GRIGIO)
    testo(xd, y - 14, f"{dip.get('nome', '')} {dip.get('cognome', '')}".strip(), 12, True, colore=BLU)
    testo(xd, y - 28, dip.get("via") or "", 10)
    testo(xd, y - 41, " ".join(x for x in (dip.get("npa"), dip.get("localita")) if x), 10)

    # dati del dipendente
    y -= 74
    dati = [("Data di entrata:", _data(dip.get("data_assunzione")) or _data(dip.get("data_entrata"))),
            ("Data di nascita:", _data(dip.get("data_nascita"))),
            ("No. AVS:", dip.get("numero_avs") or ""), ("Impiego:", dip.get("funzione") or "")]
    for i, (et, val) in enumerate(dati):
        testo(L, y - i * 13.5, et, 9.5, colore=GRIGIO)
        testo(L + 88, y - i * 13.5, val, 9.5)
    durata = "A ore" if calc.get("orario") else "Indeterminato"
    contr = next((x for x in dip.get("contratti", []) if x.get("form")), None)
    if contr and contr.get("form", {}).get("durata") == cal.DETERMINATO:
        durata = "Determinato"
    testo(R, y, f"{MESI[mese - 1]} {anno}", 15, True, "r", BLU)
    testo(R, y - 15, durata, 10, False, "r", GRIGIO)

    # tabella del conteggio
    y -= 76
    xq, xf, xt = L + 255, L + 345, R
    c.setFillColorRGB(*BLU)
    c.rect(L, y - 4, R - L, 18, stroke=0, fill=1)
    testo(L + 6, y + 1, "Conteggio paga", 10, True, colore=(1, 1, 1))
    testo(xq, y + 1, "Quota base", 10, True, "r", (1, 1, 1))
    testo(xf, y + 1, "Fattore", 10, True, "r", (1, 1, 1))
    testo(xt - 6, y + 1, "Totale", 10, True, "r", (1, 1, 1))
    y -= 20
    pas = 15.2
    for riga in calc["righe"]:
        cod, etichetta, qb, fattore, tot = riga
        if cod not in FISSE and not tot:
            continue
        if cod in TOTALI:
            c.setFillColorRGB(*FONDO)
            c.rect(L, y - 4, R - L, pas, stroke=0, fill=1)
            c.setStrokeColorRGB(*AZZURRO)
            c.setLineWidth(0.8)
            c.line(L, y + pas - 4, R, y + pas - 4)
        grassetto = cod in TOTALI
        testo(L + 6, y, etichetta, 10.5 if cod == "netto" else 10, grassetto)
        if cod not in TOTALI:
            testo(xq, y, _quota(riga), 9.5, False, "r", GRIGIO)
            testo(xf, y, _fattore(riga, calc.get("orario")), 9.5, False, "r", GRIGIO)
        testo(xt - 6, y, _chf(tot), 10.5 if cod == "netto" else 10, grassetto, "r", BLU if cod == "netto" else (0, 0, 0))
        y -= pas + (2 if cod in TOTALI else 0)
    c.setStrokeColorRGB(*BLU)
    c.setLineWidth(1.2)
    c.line(L, y + pas - 2, R, y + pas - 2)

    # note sulle assenze (infortunio / malattia / maternità), solo se presenti
    g = calc.get("giorni") or {}
    note = []
    if g.get("inf_att") or g.get("inf_ass"):
        note.append(f"Infortunio: {g.get('inf_att', 0)} gg a carico del datore di lavoro, {g.get('inf_ass', 0)} gg indennizzati dall'assicurazione.")
    if g.get("mal_att") or g.get("mal_ass"):
        note.append(f"Malattia: {g.get('mal_att', 0)} gg a carico del datore di lavoro, {g.get('mal_ass', 0)} gg indennizzati dall'assicurazione.")
    if g.get("mat"):
        note.append(f"Maternità / paternità: {g['mat']} gg.")
    y -= 12
    for n in note:
        testo(L, y, n, 8.5, colore=GRIGIO)
        y -= 11

    # conferma e firme
    y -= 12
    for riga in _spezza(TESTO_FIRMA, FONT, 8.5, R - L):
        testo(L, y, riga, 8.5, colore=GRIGIO)
        y -= 11
    y -= 18
    testo(L, y, "Data:", 10, colore=GRIGIO)
    data_pag = busta.get("data_pagamento") or ""
    testo(L + 34, y, _data(data_pag), 10)
    testo(R, y, "PAGATO BONIFICO", 10, True, "r", BLU)
    y -= 52
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.setLineWidth(0.6)
    c.line(L, y + 12, L + 190, y + 12)
    c.line(R - 190, y + 12, R, y + 12)
    testo(L + 95, y, az.get("ragione_sociale") or "", 10, False, "c")
    testo(R - 95, y, f"{dip.get('nome', '')} {dip.get('cognome', '')}".strip(), 10, False, "c")
    c.showPage()
    c.save()
    return buf.getvalue()


def unisci_pdf(parti: list[bytes]) -> bytes:
    w = PdfWriter()
    for p in parti:
        for pagina in PdfReader(io.BytesIO(p)).pages:
            w.add_page(pagina)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()
