"""PDF «Riepilogo annuale giorni di vacanze» e «giorni di festività» (A4 orizzontale, come il foglio dello studio):
intestazione del datore di lavoro, una riga per dipendente (cumulati dell'anno prima, giorni per mese, usufruiti, residui, firma)."""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from core import ferie_calc as fc
from core.buste.pdf import BLU, FONT, FONT_B, GRIGIO
from core.util import oggi


def _n(v) -> str:
    v = float(v or 0)
    return f"{v:g}"


def _pagina(c, az: dict, anno: int, dips: list[dict], tipo: str, nome) -> None:
    W, H = landscape(A4)
    L, R = 36, W - 36
    vac = tipo == "ferie"
    c.setFillColorRGB(0, 0, 0)
    c.setFont(FONT_B, 9)
    c.drawString(L, H - 40, az.get("ragione_sociale") or "")
    c.setFont(FONT, 8.5)
    c.drawString(L, H - 51, az.get("sede_via") or "")
    c.drawString(L, H - 62, " ".join(x for x in (az.get("sede_npa"), az.get("sede_localita")) if x))
    c.setFont(FONT_B, 10)
    c.drawRightString(R, H - 44, f"Riepilogo annuale giorni di {'vacanze' if vac else 'festività'} al 31.12.{anno}")

    colonne = [("Nome, Cognome", 150)]
    if vac:
        colonne.append((f"Cumulati {anno - 1}", 52))
    colonne += [(m[:3].lower() + ("" if False else ""), 33) for m in fc.MESI]
    colonne.append((f"Usufruiti {anno}" if vac else f"Totale {anno}", 52))
    if vac:
        colonne.append((f"Residui {anno}", 46))
        colonne.append(("Firma", R - L - 150 - 52 - 33 * 12 - 52 - 46))
    larghe = [w for _, w in colonne]
    if not vac:
        larghe[-1] = R - L - sum(larghe[:-1]) if False else larghe[-1]
    y = H - 110
    c.setStrokeColorRGB(*BLU)
    c.setLineWidth(1)
    c.line(L, y + 14, R, y + 14)
    x = L
    c.setFont(FONT_B, 8)
    for (et, w), i in zip(colonne, range(len(colonne))):
        if i == 0:
            c.drawString(x + 2, y, et)
        else:
            c.drawCentredString(x + w / 2, y, et)
        x += w
    c.line(L, y - 6, R, y - 6)
    y -= 22
    riga_h = 19
    for d in dips:
        mesi = fc.conteggio_mesi(az, anno, d["id"], tipo)
        x = L
        c.setFont(FONT, 8.5)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(x + 2, y, f"{d.get('cognome', '')} {d.get('nome', '')}".strip())
        x += larghe[0]
        if vac:
            ri = fc.riepilogo(az, anno, d["id"])
            c.setFillColorRGB(0.94, 0.94, 0.95)
            c.rect(x, y - 6, larghe[1], riga_h - 2, stroke=0, fill=1)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(x + larghe[1] / 2, y, _n(ri["cumulati"]))
            x += larghe[1]
        for v in mesi:
            c.setFillColorRGB(0.35, 0.35, 0.38) if not v else c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(x + 16.5, y, _n(v))
            x += 33
        c.setFillColorRGB(0.94, 0.94, 0.95)
        c.rect(x, y - 6, 52, riga_h - 2, stroke=0, fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont(FONT_B, 8.5)
        c.drawCentredString(x + 26, y, _n(ri["usufruiti"] if vac else sum(mesi)))
        x += 52
        if vac:
            c.setFillColorRGB(0.94, 0.94, 0.95)
            c.rect(x, y - 6, 46, riga_h - 2, stroke=0, fill=1)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(x + 23, y, _n(ri["residui"]))
        c.setStrokeColorRGB(0.1, 0.1, 0.1)
        c.setLineWidth(0.6)
        c.line(L, y - 7, R, y - 7)
        y -= riga_h
        if y < 80:
            break
    c.setFont(FONT, 8.5)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(L, 52, f"{az.get('sede_localita') or ''}, 31.12.{anno}".strip(", "))
    c.setStrokeColorRGB(0, 0, 0)
    c.line(L, 40, L + 160, 40)
    c.line(R - 190, 40, R, 40)
    c.setFont(FONT_B, 8.5)
    c.drawString(L, 30, "Luogo e data")
    c.drawRightString(R, 30, "* Firma del datore di lavoro")
    c.showPage()


def riepilogo_pdf(az: dict, anno: int, dips: list[dict]) -> bytes:
    """Pagina 1: vacanze. Pagina 2: festività."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setTitle(f"Vacanze e festività {anno} — {az.get('ragione_sociale', '')}")
    _pagina(c, az, anno, dips, "ferie", "Vacanze")
    _pagina(c, az, anno, dips, "festivita", "Festività")
    c.save()
    return buf.getvalue()
