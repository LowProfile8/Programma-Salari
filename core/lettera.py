"""core/lettera.py — lettera di disdetta/licenziamento, sul modello della bozza del titolare
(«2026 - Lettera di licenziamento»): mittente in alto, destinatario, luogo e data, oggetto, testo, firme."""

import io
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from core.contratti.pdf import _CARLITO, _indirizzo, data_it
from core.util import oggi


def _riga_font(c, grassetto=False, dim=11):
    c.setFont(("Carlito-Bold" if grassetto else "Carlito") if _CARLITO else ("Helvetica-Bold" if grassetto else "Helvetica"), dim)


def _paragrafo(c, testo: str, x: float, y: float, larghezza: float, interlinea: float = 15.5) -> float:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    font = "Carlito" if _CARLITO else "Helvetica"
    righe, corrente = [], ""
    for parola in testo.split():
        prova = f"{corrente} {parola}".strip()
        if stringWidth(prova, font, 11) <= larghezza:
            corrente = prova
        else:
            righe.append(corrente)
            corrente = parola
    righe.append(corrente)
    for r in righe:
        c.drawString(x, y, r)
        y -= interlinea
    return y


TIPI_LETTERA = {
    "datore": "Licenziamento da parte del datore di lavoro",
    "consensuale": "Termine consensuale del rapporto",
    "causa_grave": "Licenziamento immediato per causa grave",
}


def lettera_licenziamento(azienda: dict, dip: dict, data_lettera: str, data_cessazione: str, tipo: str = "datore") -> bytes:
    """Restituisce il PDF della lettera. Le date sono in formato ISO (aaaa-mm-gg)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    x0, larg = 25 * mm, w - 50 * mm
    y = h - 28 * mm
    _riga_font(c, True, 12)
    c.drawString(x0, y, azienda.get("ragione_sociale") or "")
    _riga_font(c)
    for riga in (azienda.get("sede_via"), " ".join(p for p in (azienda.get("sede_npa"), azienda.get("sede_localita")) if p)):
        if riga:
            y -= 15
            c.drawString(x0, y, riga)
    y -= 46
    donna = (dip.get("sesso") or "").lower().startswith("d")
    c.drawString(w - 95 * mm, y, "Spett.le" if not donna else "Spett.le")
    nome = f"{dip.get('nome', '')} {dip.get('cognome', '')}".strip()
    _riga_font(c, True)
    c.drawString(w - 95 * mm, y - 15, nome)
    _riga_font(c)
    yy = y - 30
    for riga in (dip.get("via"), " ".join(p for p in (dip.get("npa"), dip.get("localita")) if p)):
        if riga:
            c.drawString(w - 95 * mm, yy, riga)
            yy -= 15
    y = yy - 30
    luogo = azienda.get("sede_localita") or ""
    c.drawString(x0, y, f"{luogo}, {data_it(data_lettera)}".strip(", "))
    y -= 36
    _riga_font(c, True)
    c.drawString(x0, y, {"datore": "Oggetto: Termine rapporto di lavoro", "consensuale": "Oggetto: Termine rapporto di lavoro - disdetta consensuale", "causa_grave": "Oggetto: Disdetta immediata del rapporto di lavoro per giusta causa"}.get(tipo, "Oggetto: Termine rapporto di lavoro"))
    _riga_font(c)
    y -= 34
    titolo = "la Signora" if donna else "il Signor"
    residenza = _indirizzo(dip)
    testo1 = (f"La presente per comunicare il termine del rapporto lavorativo tra la {azienda.get('ragione_sociale') or ''} e "
              f"{titolo} {nome}" + (f" residente in {residenza}." if residenza else "."))
    if tipo == "consensuale":
        testo1 = testo1.replace("il termine del rapporto lavorativo", "il termine consensuale del rapporto lavorativo")
    y = _paragrafo(c, testo1, x0, y, larg) - 10
    if tipo == "causa_grave":
        y = _paragrafo(c, "La disdetta viene pronunciata con effetto immediato per giusta causa, ai sensi dell\u2019art. 337 del Codice delle obbligazioni svizzero (CO).", x0, y, larg) - 10
        y = _paragrafo(c, "La presente comunicazione costituisce pertanto formale dichiarazione di scioglimento immediato del rapporto di lavoro.", x0, y, larg) - 22
    elif tipo == "consensuale":
        y = _paragrafo(c, f"Come da accordi tra le parti, il termine di disdetta è previsto per il giorno {data_it(data_cessazione)}.", x0, y, larg) - 22
    else:
        y = _paragrafo(c, f"Nel rispetto dei termini sanciti dal CCL in atto il termine di disdetta è previsto per il giorno {data_it(data_cessazione)}.", x0, y, larg) - 22
    c.drawString(x0, y, "Cordiali saluti")
    y -= 52
    firmatario = azienda.get("amministratore") or azienda.get("persona_contatto") or ""
    c.drawString(x0, y + 22, azienda.get("ragione_sociale") or "")
    if firmatario:
        c.drawString(x0, y + 8, firmatario)
    c.line(x0, y - 4, x0 + 62 * mm, y - 4)
    c.drawString(w - 95 * mm, y + 22, "Per ricevuta (il dipendente)")
    c.line(w - 95 * mm, y - 4, w - 25 * mm, y - 4)
    c.drawString(w - 95 * mm, y - 20, f"Data: ____________________")
    c.showPage()
    c.save()
    return buf.getvalue()
