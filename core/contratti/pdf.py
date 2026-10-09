"""core/contratti/pdf.py — compila i modelli PDF di contratto e crea la dichiarazione di segretezza.

Modelli (cartella assets/contratti/), forniti dal titolare:
    individuale.pdf / individuale_ore.pdf        modello piatto, 2 pagine A4 (stesso layout)
    ccnl.pdf / ccnl_ore.pdf                       moduli compilabili del CCNL, 3 pagine A4
    autotrasporti.pdf / autotrasporti_ore.pdf     modello piatto, 4 pagine A3
    cpc.pdf                                       parrucchieri e coiffeur, modello piatto, 4 pagine A3

Tutti i modelli vengono compilati scrivendo il testo sopra il PDF originale (anche i moduli CCNL: il testo
viene stampato nei riquadri dei campi e poi i campi vengono rimossi, così il risultato si legge ovunque).
"""

import io
from datetime import date
from pathlib import Path

import pdfplumber
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.contratti.calcolo import AUTOTRASPORTI, CCNL, CPC, INDIVIDUALE, ORE, DETERMINATO

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets" / "contratti"
FONT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("Carlito", str(FONT_DIR / "Carlito-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Carlito-Bold", str(FONT_DIR / "Carlito-Bold.ttf")))
    _CARLITO = True
except Exception:       # se il carattere non è disponibile si ripiega su Helvetica
    _CARLITO = False
FILE_MODELLO = {
    (INDIVIDUALE, False): "individuale.pdf", (INDIVIDUALE, True): "individuale_ore.pdf",
    (CCNL, False): "ccnl.pdf", (CCNL, True): "ccnl_ore.pdf",
    (AUTOTRASPORTI, False): "autotrasporti.pdf", (AUTOTRASPORTI, True): "autotrasporti_ore.pdf",
    (CPC, False): "cpc.pdf", (CPC, True): "cpc.pdf",
}


class ModelloMancante(Exception):
    """Non esiste (ancora) il modello PDF per questo tipo di contratto."""


def modello_disponibile(tipo: str, durata: str) -> bool:
    return (tipo, durata == ORE) in FILE_MODELLO


# ── formattazione ─────────────────────────────────────────────────────────────
def chf(valore, decimali: int = 2) -> str:
    if valore is None or valore == "":
        return ""
    return f"{float(valore):,.{decimali}f}".replace(",", "'")


def data_it(iso) -> str:
    if not iso:
        return ""
    try:
        a, m, g = str(iso).split("-")
        return f"{g}.{m}.{a}"
    except ValueError:
        return str(iso)


def pct(valore) -> str:
    return f"{float(valore):.2f}".rstrip("0").rstrip(".") + "%" if valore not in (None, "") else ""


# ── scrittura sopra il PDF ────────────────────────────────────────────────────
class Operazioni:
    """Elenco di cose da scrivere: (pagina, tipo, argomenti). Le coordinate «top» sono misurate dall'alto
    della pagina (come in pdfplumber)."""

    def __init__(self, famiglia: str = "Helvetica"):
        self.ops: list[tuple] = []
        self.famiglia = famiglia if (famiglia != "Carlito" or _CARLITO) else "Helvetica"

    def testo(self, pagina, x, top, testo, dim=9, allinea="l", grassetto=False, larghezza=None):
        if testo not in (None, ""):
            font = self.famiglia + ("-Bold" if grassetto else "")
            self.ops.append((pagina, "t", (x, top, str(testo), dim, allinea, font, larghezza)))

    def bianco(self, pagina, x0, top0, x1, top1):
        self.ops.append((pagina, "w", (x0, top0, x1, top1)))

    def spunta(self, pagina, x0, top0, x1, top1):
        self.ops.append((pagina, "x", (x0, top0, x1, top1)))


def _adatta(testo, font, dim, larghezza):
    while larghezza and dim > 5.5 and stringWidth(testo, font, dim) > larghezza:
        dim -= 0.5
    return dim


def _overlay(dimensioni, ops) -> PdfReader:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, (w, h) in enumerate(dimensioni):
        c.setPageSize((w, h))
        for pagina, tipo, a in ops:
            if pagina != i:
                continue
            if tipo == "w":
                x0, t0, x1, t1 = a
                c.setFillColorRGB(1, 1, 1)
                c.setStrokeColorRGB(1, 1, 1)
                c.rect(x0, h - t1, x1 - x0, t1 - t0, fill=1, stroke=0)
            elif tipo == "t":
                x, top, testo, dim, allinea, font, larghezza = a
                dim = _adatta(testo, font, dim * (1.2 if w > 700 else 1.1), larghezza)
                c.setFillColorRGB(0, 0, 0)
                c.setFont(font, dim)
                y = h - top
                if allinea == "r":
                    c.drawRightString(x, y, testo)
                elif allinea == "c":
                    c.drawCentredString(x, y, testo)
                else:
                    c.drawString(x, y, testo)
            elif tipo == "x":
                x0, t0, x1, t1 = a
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(1.4)
                m = 1.6
                c.line(x0 + m, h - t0 - m, x1 - m, h - t1 + m)
                c.line(x0 + m, h - t1 + m, x1 - m, h - t0 - m)
        c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def _applica(percorso: Path, ops: Operazioni, rimuovi_campi: bool = False) -> PdfWriter:
    modello = PdfReader(str(percorso))
    dimensioni = [(float(p.mediabox.width), float(p.mediabox.height)) for p in modello.pages]
    overlay = _overlay(dimensioni, ops.ops)
    scrittore = PdfWriter()
    for i, pagina in enumerate(modello.pages):
        if rimuovi_campi and "/Annots" in pagina:
            del pagina["/Annots"]
        pagina.merge_page(overlay.pages[i])
        scrittore.add_page(pagina)
    return scrittore


def _trova(percorso: Path, pagina: int, testo: str):
    """Posizione (x0, top, x1, bottom) della prima parola uguale a `testo` nella pagina."""
    with pdfplumber.open(str(percorso)) as pdf:
        for w in pdf.pages[pagina].extract_words():
            if w["text"] == testo:
                return w["x0"], w["top"], w["x1"], w["bottom"]
    return None


def _linee(percorso: Path, pagina: int):
    with pdfplumber.open(str(percorso)) as pdf:
        p = pdf.pages[pagina]
        l = [(round(x["top"], 1), x["x0"], x["x1"]) for x in p.lines if abs(x["top"] - x["bottom"]) < 1.5]
        l += [(round(r["top"], 1), r["x0"], r["x1"]) for r in p.rects if r["height"] < 2 and r["width"] > 20]
    return sorted(set(l))


def _senza_13a(o: Operazioni, file: Path, pagina: int, riga_a_se: bool = False) -> None:
    """Toglie «incl. 13a mensilità» dalla scritta del totale (oppure l'intera riga «- 13a mensilità,» nei modelli a ore)."""
    p13 = _trova(file, pagina, "13a")
    if not p13:
        return
    if riga_a_se:
        o.bianco(pagina, p13[0] - 14, p13[1] - 2, p13[0] + 150, p13[3] + 2)
        return
    incl = _trova(file, pagina, "incl.")
    mens = _trova(file, pagina, "mensilità")
    if incl and mens:
        o.bianco(pagina, incl[0] - 3, incl[1] - 2, mens[2] + 3, mens[3] + 2)


# ── dati comuni ───────────────────────────────────────────────────────────────
def _permesso_breve(p) -> str:
    """«Permesso G (frontaliere)» -> «G»; «Notifica 90 giorni» -> «Not. 90 gg»; il testo libero resta com'è."""
    p = (p or "").strip()
    if p.startswith("Permesso "):
        return p.split(" ")[1]
    return {"Notifica 90 giorni": "Not. 90 gg", "Cittadino svizzero": "CH"}.get(p, p)


def _indirizzo(d: dict) -> str:
    cap_loc = " ".join(x for x in [d.get("npa"), d.get("localita")] if x)
    return ", ".join(x for x in [d.get("via"), cap_loc] if x)


def _sede(az: dict) -> str:
    return _indirizzo({"via": az.get("sede_via"), "npa": az.get("sede_npa"), "localita": az.get("sede_localita")})


def _luogo_data(c: dict) -> str:
    """«Luogo e data» di firma. Se il titolare esclude la data, il campo resta vuoto: si scrive a mano."""
    if not c.get("data_firma"):
        return ""
    luogo = c["azienda"].get("sede_localita") or ""
    return f"{luogo}, {data_it(c['data_firma'])}".strip(", ")


def _durata_testo(c: dict) -> str:
    if c["durata"] == ORE:
        return "Indeterminata - a ore"
    if c["durata"] == DETERMINATO:
        return f"Determinata fino al {data_it(c.get('data_fine'))}"
    return "Indeterminata"


def _righe_accordi(c: dict, orario: bool) -> list[str]:
    """Righe per «Accordi particolari»: per i contratti a ore le indennità orarie, poi il testo libero."""
    r = c["calc"]
    righe = []
    if orario:
        righe.append(f"Salario orario di base CHF {chf(r['salario_fisso'])}; indennità vacanze {pct(c.get('vacanze_pct'))} "
                     f"(CHF {chf(r['vacanze'])}), festività {pct(c.get('festivita_pct'))} (CHF {chf(r['festivita'])}), "
                     f"13a mensilità 8,33% (CHF {chf(r['quota_13'])}) all'ora.")
    for riga in (c.get("accordi") or "").splitlines():
        if riga.strip():
            righe.append(riga.strip())
    return righe


def _spezza(testo: str, font: str, dim: float, larghezza: float) -> list[str]:
    parole, righe, corrente = testo.split(), [], ""
    for p in parole:
        prova = f"{corrente} {p}".strip()
        if stringWidth(prova, font, dim) <= larghezza:
            corrente = prova
        else:
            righe.append(corrente)
            corrente = p
    if corrente:
        righe.append(corrente)
    return righe


# ══════════════════════════════════════════════════════════════════════════════
# Contratto individuale (A4, 2 pagine)
# ══════════════════════════════════════════════════════════════════════════════
def _individuale(c: dict) -> PdfWriter:
    orario = c["durata"] == ORE
    file = ASSETS / FILE_MODELLO[(INDIVIDUALE, orario)]
    az, d, r = c["azienda"], c["dip"], c["calc"]
    o = Operazioni("Carlito")
    # pagina 1 — il testo sta sopra la riga di ogni campo (misure ricavate dal modello)
    o.testo(0, 100, 110.2, az["nome"], 9, larghezza=190)
    o.testo(0, 360, 110.2, _sede(az), 8.5, larghezza=200)
    o.testo(0, 132, 141.2, d["cognome"], 9, larghezza=175)
    o.testo(0, 360, 141.2, d["nome"], 9, larghezza=200)
    o.testo(0, 100, 185.4, _indirizzo(d), 9, larghezza=460)
    o.testo(0, 100, 214.9, d.get("telefono"), 9, larghezza=110)
    o.testo(0, 295, 214.9, data_it(d.get("data_nascita")), 9, larghezza=78)
    o.testo(0, 514, 214.9, _permesso_breve(d.get("permesso")), 9, larghezza=48)
    o.testo(0, 100, 241.3, d.get("numero_avs"), 9, larghezza=110)
    o.testo(0, 278, 241.3, d.get("stato_civile"), 9, larghezza=95)
    o.testo(0, 466, 241.3, d.get("n_figli"), 9, larghezza=95)
    o.testo(0, 100, 314.2, c.get("funzione"), 9, larghezza=175)
    o.testo(0, 165, 416.6, data_it(c["data_inizio"]), 9, larghezza=110)
    o.testo(0, 165, 446.1, _durata_testo(c), 8, larghezza=112)
    if not orario:
        o.testo(0, 410, 462.5, f"{c['percentuale']:g}%", 8.5)
        o.testo(0, 446, 474.3, f"{c['ore_sett']:g}".replace(".", ","), 8.5, allinea="r")
    # pagina 2 — importi allineati a destra sopra le righe
    X = 288.0
    unita = " (orario)" if orario else ""
    o.testo(1, 205, 156, "salario orario" if orario else "", 7, allinea="r")
    if c.get("tredicesima") in ("annuale", "nessuna"):
        q = _trova(file, 1, "Quota")
        if q:
            o.bianco(1, q[0] - 3, q[1] - 5, 300, q[3] + 9)   # riga «Quota mensile 13a mensilità 8,33%» con il suo importo
    importi = [
        (156.0, r["salario_fisso"]), (185.4, r["quota_13"]), (270.0, r["lordo_avs"]),
        (329.0, r["avs"]), (358.0, r["ad"]), (387.0, r["igm"]), (416.6, r["lainf"]), (446.0, r["lpp"]),
        (474.4, r["imposta_fonte"]), (503.9, r["vitto_alloggio"]), (533.3, r["altra_deduzione"]),
        (562.8, r["totale_deduzioni"]), (652.7, r["assegni_figli"]), (682.2, r["rimborsi"] + r["rimborsi_sett"]),
        (711.6, r["arrotondamenti"]), (741.1, r["totale_assegni"] + r["arrotondamenti"]), (773.3, r["netto"]),
    ]
    for top, valore in importi:
        if top == 446.0 and c.get("lpp_mensile"):
            o.testo(1, X, top, "Mensile", 9, allinea="r")
        elif top == 773.3 and orario:
            continue
        elif valore not in (None, 0, 0.0) or top in (156.0, 270.0, 773.3, 562.8):
            o.testo(1, X, top, chf(valore), 9, allinea="r")
    if orario:
        _togli_netto_orario(o, file, 1, "Totale salario netto")
    for top, p_ in [(387.0, c["aliq"]["igm"]), (416.6, c["aliq"]["lainf"]), (446.0, c.get("lpp_pct")), (474.4, r["imposta_fonte_pct"])]:
        if p_:
            o.testo(1, 203, top, pct(p_), 8, allinea="r")
    for etichetta, valore in (("5,300%", c["aliq"].get("avs", 5.3)), ("1,100%", c["aliq"].get("ad", 1.1))):
        pos = _trova(file, 1, etichetta)       # il modello stampa già 5,300% e 1,100%: si sostituiscono con quelli dell'azienda
        if pos:
            o.bianco(1, pos[0] - 1, pos[1] - 1, pos[2] + 1, pos[3] + 1)
            o.testo(1, pos[2], pos[3] - 2.5, f"{valore:.3f}%".replace(".", ","), 8, allinea="r")
    if r["altra_deduzione"] and c.get("altra_deduzione_nome"):
        o.testo(1, 100, 533.3, c["altra_deduzione_nome"], 8, larghezza=100)
    if r["arrotondamenti"]:
        o.testo(1, 100, 711.6, "Arrotondamenti", 8, larghezza=100)
    if r["rimborsi_sett"] and c.get("rimborsi_sett_nome"):
        o.testo(1, 205, 682.2 - 9, c["rimborsi_sett_nome"], 6.5, "r", larghezza=100)
    righe = _righe_accordi(c, orario)
    lavoro = []
    for riga in righe:
        lavoro += _spezza(riga, "Helvetica", 7.5, 205)
    for top, riga in zip([503.9, 548.1, 592.3, 638.0, 682.2], lavoro):
        o.testo(1, 340, top, riga, 7.5, larghezza=208)
    o.testo(1, 390, 726.2, _luogo_data(c), 9, larghezza=158)
    return _applica(file, o)


# ══════════════════════════════════════════════════════════════════════════════
# Contratto autotrasporti (A3, 4 pagine)
# ══════════════════════════════════════════════════════════════════════════════
def _autotrasporti(c: dict) -> PdfWriter:
    orario = c["durata"] == ORE
    file = ASSETS / FILE_MODELLO[(AUTOTRASPORTI, orario)]
    az, d, r = c["azienda"], c["dip"], c["calc"]
    o = Operazioni("Carlito")
    # pagina 1: le posizioni vengono dalle righe del modello (nato il / parti / decorrenza / termine / funzione / durata)
    l1 = _linee(file, 0)
    nato, parte1, decorrenza, termine, funzione, durata_riga = l1[0][0], l1[1][0], l1[3][0], l1[4][0], l1[5][0], l1[6][0]
    cx = 421.0
    o.testo(0, cx, nato - 45, f"{d['nome']} {d['cognome']}", 14, "c", False, 420)
    o.testo(0, 398, nato - 2.5, data_it(d.get("data_nascita")), 13)
    o.testo(0, 398, nato + 14, _indirizzo(d), 13, larghezza=330)
    o.testo(0, cx, parte1 + 78, az["nome"], 14, "c", False, 420)
    o.testo(0, cx, parte1 + 95, _sede(az), 13, "c", larghezza=420)
    o.testo(0, 350, decorrenza - 3, data_it(c["data_inizio"]), 13)
    if c["durata"] == DETERMINATO:
        o.bianco(0, 505, termine - 14, 532, termine + 1)           # copre il «--» stampato
        o.testo(0, 350, termine - 3, data_it(c.get("data_fine")), 12)
    o.testo(0, 350, funzione - 3, c.get("funzione"), 13, larghezza=335)
    if c.get("tredicesima") in ("annuale", "nessuna"):
        _senza_13a(o, file, 1, riga_a_se=orario)
    if c["durata"] != DETERMINATO:                   # contratto indeterminato: la riga «Termine contratto» si toglie
        et = _trova(file, 0, "Termine")
        if et:
            o.bianco(0, et[0] - 4, et[1] - 4, 710, termine + 4)
    # numerazione del modello: dopo l'articolo 2 c'è «2.1»; diventa «3.» e si prosegue con 4, 5, ...
    n21 = _trova(file, 1, "2.1")
    if n21:
        o.bianco(1, n21[0] - 2, n21[1] - 2, n21[2] + 4, n21[3] + 2)
        o.testo(1, n21[0] + 2, n21[3] - 3, "3.", 12, grassetto=True)
    if not orario:
        o.testo(0, 350, durata_riga - 3, _durata_testo(c), 12)
    righe4 = _linee(file, 3)
    if righe4:
        o.testo(3, righe4[0][1] + 3, righe4[0][0] - 4, _luogo_data(c), 12, larghezza=145)   # «Luogo e data» sopra la riga

    # pagina 2: stesse posizioni nei due modelli (la riga della percentuale, sopra y=400, si salta)
    righe = [x[0] for x in _linee(file, 1) if x[0] > 400]
    top_lordo, top_ded, top_totded = righe[0], righe[1:8], righe[8]
    top_ass, top_totass = righe[9:12], righe[12]
    X = 716.0
    if not orario:
        o.testo(1, 375, 253.7, f"{c['percentuale']:g}%", 12)
        o.testo(1, 380, 272.9, f"{c['ore_sett']:g}".replace(".", ","), 12)
    o.testo(1, X, top_lordo - 3, chf(r["lordo_avs"]), 12, "r", True)
    for top, v in zip(top_ded, [r["avs"], r["ad"], r["igm"], r["lainf"], r["lpp"], r["imposta_fonte"],
                                0.0 if orario else r["commissione_paritetica"]]):
        if v or top == top_ded[0]:
            o.testo(1, X, top - 3, chf(v), 12, "r")
    if c.get("lpp_mensile"):
        o.testo(1, X, top_ded[4] - 3, "Mensile", 12, "r")
    # percentuali delle aliquote, prima di «CHF»
    parole_chf = [w for w in pdfplumber.open(str(file)).pages[1].extract_words() if w["text"] == "CHF"]
    for top, perc in zip(top_ded, [c["aliq"].get("avs"), c["aliq"].get("ad"), c["aliq"].get("igm"), c["aliq"].get("lainf"),
                                    c.get("lpp_pct"), r["imposta_fonte_pct"]]):
        if perc:
            vicino = min(parole_chf, key=lambda w: abs(w["bottom"] - top), default=None)
            if vicino is not None:
                o.testo(1, vicino["x0"] - 8, top - 6.5, pct(perc), 11, "r")
    if orario and c.get("comm_mensile"):     # contributo paritetico: importo mensile, non orario
        o.testo(1, X, top_ded[6] - 3, f"{chf(c['comm_mensile'])} / mese", 11, "r")
    o.testo(1, X, top_totded - 3, chf(r["totale_deduzioni"]), 12, "r", True)
    for i, (top, v) in enumerate(zip(top_ass, [r["assegni_figli"], r["rimborsi_sett"], r["rimborsi"] + r["arrotondamenti"]])):
        if v:
            o.testo(1, X, top - 3, chf(v) + (" / mese" if (orario and i < 2) else ""), 12, "r")
    if r["rimborsi"] or r["arrotondamenti"]:
        o.testo(1, 215, top_ass[2] - 6.5, "Rimborsi / arrotondamenti", 10)
    o.testo(1, X, top_totass - 3, chf(r["totale_assegni"] + r["arrotondamenti"]), 12, "r", True)
    if not orario:
        o.testo(1, X, l_netto(file) - 3, chf(r["netto"]), 12, "r", True)
    else:
        # il modello a ore non ha la riga del netto: la scriviamo sotto il totale assegni, con il dettaglio del lordo orario
        o.testo(1, 215, top_lordo + 17,
                f"Base {chf(r['salario_fisso'])} + festività {chf(r['festivita'])} + vacanze {chf(r['vacanze'])} "
                f"+ 13a {chf(r['quota_13'])} (CHF all'ora)", 9.5, larghezza=500)
        if c.get("vacanze_pct") and abs(c["vacanze_pct"] - 8.33) > 0.005:     # 5 settimane di vacanze: 10,64%
            for pagina in (1, 2):
                pos = _trova(file, pagina, "8,33%")
                if pos:
                    o.bianco(pagina, pos[0] - 1, pos[1] - 1, pos[2] + 1, pos[3] + 1)
                    o.testo(pagina, pos[0], pos[3] - 3, pct(c["vacanze_pct"]).replace(".", ","), 12)
    return _applica(file, o)


def _togli_netto_orario(o, file, pagina: int, frase: str) -> None:
    """Nei contratti a ore non si indica il salario netto orario (l'LPP è mensile): si cancella la riga del modello."""
    pg = pdfplumber.open(str(file)).pages[pagina]
    for riga in pg.extract_text_lines():
        if frase.lower() in riga["text"].lower():
            o.bianco(pagina, riga["x0"] - 3, riga["top"] - 4, pg.width - 20, riga["bottom"] + 8)


def l_netto(file: Path) -> float:
    """Riga del «Totale salario netto» (ultima riga della pagina 2 del modello a tempo indeterminato)."""
    return [x[0] for x in _linee(file, 1) if x[0] > 400][13]


# ══════════════════════════════════════════════════════════════════════════════
# Contratto CPC parrucchieri e coiffeur (A3, 4 pagine)
# ══════════════════════════════════════════════════════════════════════════════
def _cpc(c: dict) -> PdfWriter:
    file = ASSETS / FILE_MODELLO[(CPC, False)]
    az, d, r = c["azienda"], c["dip"], c["calc"]
    o = Operazioni("Carlito")
    l1 = _linee(file, 0)           # nato il / PER UNA PARTE / PER L'ALTRA PARTE / decorrenza / funzione / durata
    nato, decorrenza, funzione, durata_riga = l1[0][0], l1[3][0], l1[4][0], l1[5][0]
    cx = 421.0
    o.testo(0, cx, nato - 45, f"{d['nome']} {d['cognome']}", 14, "c", False, 420)
    o.testo(0, 398, nato - 2.5, data_it(d.get("data_nascita")), 13)
    o.testo(0, 398, nato + 14, _indirizzo(d), 13, larghezza=330)
    o.testo(0, cx, 432, az["nome"], 14, "c", False, 420)
    o.testo(0, cx, 450, _sede(az), 13, "c", larghezza=420)
    o.testo(0, 350, decorrenza - 3, data_it(c["data_inizio"]), 13)
    o.testo(0, 350, funzione - 3, c.get("funzione"), 13, larghezza=335)
    if c["durata"] in (DETERMINATO, ORE):
        pos = _trova(file, 0, "Indeterminata")
        if pos:
            o.bianco(0, pos[0] - 2, pos[1] - 2, pos[2] + 4, pos[3] + 2)
        o.testo(0, 350, durata_riga - 3, _durata_testo(c), 12)
    # pagina 2
    righe = [x[0] for x in _linee(file, 1)]
    top_pct, top_ore = righe[0], righe[1]
    top_lordo, top_ded, top_totded = righe[2], righe[3:9], righe[9]
    top_ass, top_totass, top_netto = righe[10:13], righe[13], righe[14]
    sede_pos = _trova(file, 1, "sede.")
    if sede_pos and _sede(az):
        o.testo(1, sede_pos[2] + 6, sede_pos[3] - 4, f"({_sede(az)})", 11, larghezza=300)
    orario = c["durata"] == ORE
    if orario:
        o.testo(1, 352, top_pct - 3, "irregolare", 12)
        o.testo(1, 352, top_ore - 3, "variabile", 12)
    else:
        o.testo(1, 352, top_pct - 3, f"{c['percentuale']:g}%", 12)
        o.testo(1, 352, top_ore - 3, f"{c['ore_sett']:g}".replace(".", ","), 12)
    if c.get("tredicesima") in ("annuale", "nessuna") or orario:
        _senza_13a(o, file, 1)
    if orario:     # etichette riscritte per il salario orario
        for parola, nuova in (("Totale", None),):
            pass
        for testo_vecchio, nuova in (("lordo", "Totale salario orario lordo AVS"),):
            pass
        lordo = _trova(file, 1, "Totale")
        if lordo:
            o.bianco(1, lordo[0] - 2, lordo[1] - 2, 500, lordo[3] + 3)
            o.testo(1, lordo[0], lordo[3] - 2, "Totale salario orario lordo AVS", 12, grassetto=True)
    X = 692.0
    o.testo(1, X, top_lordo - 3, chf(r["lordo_avs"]), 12, "r", True)
    valori = [r["avs"], r["ad"], r["igm"], r["lainf"], r["lpp"], r["imposta_fonte"]]
    percentuali = [c["aliq"].get("avs"), c["aliq"].get("ad"), c["aliq"].get("igm"), c["aliq"].get("lainf"),
                   c.get("lpp_pct"), r["imposta_fonte_pct"]]
    for top, v, perc in zip(top_ded, valori, percentuali):
        if v or top == top_ded[0]:
            o.testo(1, X, top - 3, chf(v), 12, "r")
        if perc:
            o.testo(1, 512, top - 6.5, pct(perc), 11, "r")
    if c.get("lpp_mensile"):
        o.testo(1, X, top_ded[4] - 3, "Mensile", 12, "r")
    altre = r["vitto_alloggio"] + r["altra_deduzione"] + r["commissione_paritetica"]
    if altre:
        riga_extra = top_ded[5] + (top_ded[5] - top_ded[4])          # una riga sotto «IF», come le altre
        o.testo(1, 146, riga_extra - 3, c.get("altra_deduzione_nome") or "Vitto e alloggio / altre trattenute", 11, larghezza=300)
        o.testo(1, X, riga_extra - 3, chf(altre), 12, "r")
    o.testo(1, X, top_totded - 3, chf(r["totale_deduzioni"]), 12, "r", True)
    for top, v in zip(top_ass, [r["assegni_figli"], r["rimborsi_sett"], r["rimborsi"] + r["arrotondamenti"]]):
        if v:
            o.testo(1, X, top - 3, chf(v), 12, "r")
    if r["rimborsi"] or r["arrotondamenti"]:
        o.testo(1, 215, top_ass[2] - 6.5, "Rimborsi / arrotondamenti", 10)
    o.testo(1, X, top_totass - 3, chf(r["totale_assegni"] + r["arrotondamenti"]), 12, "r", True)
    if not orario:
        o.testo(1, X, top_netto - 3, chf(r["netto"]), 12, "r", True)
    if orario:
        _togli_netto_orario(o, file, 1, "Totale salario netto")
        o.testo(1, 215, top_lordo + 22, f"Base {chf(r['salario_fisso'])} + festività {chf(r['festivita'])} + vacanze {chf(r['vacanze'])} "
                f"+ 13a {chf(r['quota_13'])} (CHF all'ora); assegni e rimborsi sono importi mensili, pagati a parte", 9.5, larghezza=480)
    righe4 = _linee(file, 3)
    if righe4:
        o.testo(3, righe4[0][1] + 3, righe4[0][0] - 4, _luogo_data(c), 12, larghezza=145)
    return _applica(file, o)


# ══════════════════════════════════════════════════════════════════════════════
# Contratto CCNL (moduli compilabili, 3 pagine A4)
# ══════════════════════════════════════════════════════════════════════════════
_NUMERICI = {"Festlohn", "Umsatzlohn", "garantierter ML", "13. ML", "Andere", "Total Bruttolohn",
             "AHV / IV / EO.0", "ALV", "KTG", "NBU", "BVG", "Krankenpflege", "Quellensteuer",
             "Unterk. und Verpfl", "Andere Abzüge", "Total Lohnabzüge", "Kinderzulagen", "Berufswäsche",
             "Andere Zulagen", "Total Zulagen", "Total Nettolohn", "Ferienentschädigung", "Feiertagsentschädigung"}
_PERCENTUALI = {"% KTG", "% NBU", "% BVG", "% Quellensteuer", "% Pensum", "% Umsatz"}


def _nome_completo(a) -> tuple[str | None, str | None]:
    """Nome qualificato del campo (genitori + figlio, come in pypdf: «13» + «. ML» -> «13. ML») e tipo (/Tx, /Btn, /Ch)."""
    parti, ft, nodo = [], a.get("/FT"), a
    while nodo is not None:
        nodo = nodo.get_object()
        if nodo.get("/T") is not None:
            parti.append(str(nodo["/T"]))
        ft = ft or nodo.get("/FT")
        nodo = nodo.get("/Parent")
    if not parti:
        return None, ft
    return ".".join(reversed(parti)).replace("..", "."), ft


def _campi_modulo(percorso: Path) -> dict:
    """Mappa nome campo -> lista di (pagina, rect, stato) leggendo i widget del modulo.
    `stato` è il nome dello stato «attivo» solo per caselle e radio (/Btn)."""
    lettore = PdfReader(str(percorso))
    campi: dict[str, list] = {}
    for i, pagina in enumerate(lettore.pages):
        for a in pagina.get("/Annots", []):
            a = a.get_object()
            nome, ft = _nome_completo(a)
            if nome is None:
                continue
            nome = nome.strip() if nome.strip() in ("13. ML",) else nome
            rect = [float(x) for x in a["/Rect"]]
            stato = None
            ap = a.get("/AP")
            if ft == "/Btn" and ap and "/N" in ap:
                chiavi = [k for k in ap["/N"].keys() if k != "/Off"]
                stato = chiavi[0] if chiavi else None
            campi.setdefault(nome, []).append((i, rect, stato))
    return campi


def _ccnl(c: dict) -> PdfWriter:
    orario = c["durata"] == ORE
    file = ASSETS / FILE_MODELLO[(CCNL, orario)]
    az, d, r, cc = c["azienda"], c["dip"], c["calc"], c.get("ccnl", {})
    campi = _campi_modulo(file)
    lettore = PdfReader(str(file))
    alt = [float(p.mediabox.height) for p in lettore.pages]
    o = Operazioni()

    testi = {
        "Arbeitgeber": f"{az['nome']}, {_sede(az)}".strip(", "),
        "Name MA": d["cognome"], "Vorname MA": d["nome"], "Adresse MA": _indirizzo(d), "Tel MA": d.get("telefono"),
        "Geburtsdatum MA": data_it(d.get("data_nascita")), "Ausländerausweis MA": _permesso_breve(d.get("permesso")),
        "AHV MA": d.get("numero_avs"), "Kinder MA": d.get("n_figli"), "Krankenkasse MA": d.get("cassa_malati"),
        "Funktion": c.get("funzione"), "Vertragsbeginn": data_it(c["data_inizio"]),
        "Festlohn": chf(r["salario_fisso"]), "13. ML": chf(r["quota_13"]) if r["quota_13"] else "",
        "Andere": chf(r["bonus"]) if r["bonus"] else "", "Total Bruttolohn": chf(r["lordo_avs"]),
        "AHV / IV / EO.0": chf(r["avs"]), "ALV": chf(r["ad"]), "KTG": chf(r["igm"]) if r["igm"] else "",
        "% KTG": f"{c['aliq']['igm']:g}" if c["aliq"]["igm"] else "",
        "NBU": chf(r["lainf"]) if r["lainf"] else "", "% NBU": f"{c['aliq']['lainf']:g}" if c["aliq"]["lainf"] else "",
        "BVG": "Mensile" if c.get("lpp_mensile") else (chf(r["lpp"]) if r["lpp"] else ""), "% BVG": f"{c['lpp_pct']:g}" if c.get("lpp_pct") else "",
        "Quellensteuer": chf(r["imposta_fonte"]) if r["imposta_fonte"] else "",
        "% Quellensteuer": f"{r['imposta_fonte_pct']:g}" if r["imposta_fonte_pct"] else "",
        "Unterk. und Verpfl": chf(r["vitto_alloggio"]) if r["vitto_alloggio"] else "",
        "Andere Abzüge": chf(r["altra_deduzione"]) if r["altra_deduzione"] else "",
        "Total Lohnabzüge": chf(r["totale_deduzioni"]),
        "Kinderzulagen": chf(r["assegni_figli"]) if r["assegni_figli"] else "",
        "Berufswäsche": chf(r["rimborsi_sett"]) if r["rimborsi_sett"] else "",
        "Andere Zulagen": chf(r["rimborsi"] + r["arrotondamenti"]) if (r["rimborsi"] or r["arrotondamenti"]) else "",
        "Total Zulagen": chf(r["totale_assegni"] + r["arrotondamenti"]), "Total Nettolohn": "" if orario else chf(r["netto"]),
        "Ort und Datum": _luogo_data(c),
    }
    if orario:
        testi["Ferienentschädigung"] = chf(r["vacanze"])
        testi["Feiertagsentschädigung"] = chf(r["festivita"])
        testi["13. ML"] = chf(r["quota_13"])
    else:
        # orario di lavoro: a tempo pieno si segna il tipo di azienda, a tempo parziale ore e percentuale
        if c["percentuale"] < 100:
            testi["wöchentliche AZ"] = f"{c['ore_sett']:g}".replace(".", ",")
            testi["% Pensum"] = f"{c['percentuale']:g}"
    stato_civile = {"Celibe/Nubile": "celibe/nubile", "Coniugato/a": "coniugato/a", "Divorziato/a": "divorziato/a",
                    "Vedovo/a": "vedovo/a"}.get(d.get("stato_civile"))
    testi["Zivilstand MA"] = stato_civile
    testi["VKB"] = cc.get("vkb")
    testi["Besondere Vereinbarungen 1"] = ""
    righe_acc = [x for x in (c.get("accordi") or "").splitlines() if x.strip()]
    for i, riga in enumerate(righe_acc[:3], 1):
        testi[f"Besondere Vereinbarungen {i}"] = riga.strip()
    if righe_acc:
        pass
    # scelte (radio e caselle): nome campo -> stato
    scelte: list[tuple[str, str]] = [("Lohnauszahlung", "/Choice1"), ("Nachtarbeit", "/Choice1"),
                                     ("Kündigungsfrist Auswahl", "/Choice1")]
    prova = cc.get("prova", "3 mesi")
    scelte.append(("Probezeit" if orario else "Probezeit Auswahl",
                   {"3 mesi": "/Choice6", "Nessuno": "/Choice8", "14 giorni": "/Choice9"}.get(prova, "/Choice6")))
    if orario:
        scelte.append(("Verftragsdauer", "/Choice1"))
    else:
        if c["percentuale"] >= 100:
            scelte.append(("wöchentliche AZ Betrieb",
                           {"Normale": "/Choice1", "Stagionale": "/Choice2", "Piccola": "/Choice3"}.get(c.get("categoria_azienda"), "/Choice1")))
    liv = cc.get("livello", "")
    riduzione = cc.get("riduzione")   # codice 1..5 del modulo
    if riduzione:
        scelte.append(("Lohnreduktion Auswahl", f"/Choice{riduzione}"))
    formazione = {"Ia": 7, "Ib": 6, "II": 1, "IIIa": 2, "IIIb": 3, "IV": 4}   # lettere g, f, a, b, c, d del modulo
    chiave = liv.split(" ")[0] if liv else ""
    if chiave in formazione:
        scelte.append((f"Check Berufsausbildung {formazione[chiave]}", "/Yes"))

    for nome, valore in testi.items():
        if valore in (None, ""):
            continue
        for pagina, rect, _ in campi.get(nome, []):
            x0, y0, x1, y1 = rect
            top = alt[pagina] - y0 - (y1 - y0 - 8.5) / 2 - 1.2
            if nome in _NUMERICI or nome in _PERCENTUALI:
                o.testo(pagina, x1 - 2, top, str(valore), 9.5, "r", larghezza=x1 - x0 - 3)
            else:
                o.testo(pagina, x0 + 2, top, str(valore), 9.5, larghezza=x1 - x0 - 4)
    for nome, stato in scelte:
        for pagina, rect, st_ in campi.get(nome, []):
            if st_ == stato or (st_ is None and stato == "/Yes"):
                x0, y0, x1, y1 = rect
                o.spunta(pagina, x0, alt[pagina] - y1, x1, alt[pagina] - y0)
    for etichetta, valore in (("5.30%", c["aliq"].get("avs", 5.3)), ("1.10%", c["aliq"].get("ad", 1.1))):
        if abs(valore - float(etichetta[:-1])) > 0.005:
            pos = _trova(file, 1, etichetta)
            if pos:
                o.bianco(1, pos[0] - 1, pos[1] - 1, pos[2] + 1, pos[3] + 1)
                o.testo(1, pos[0], pos[3] - 3, f"{valore:.2f}%", 10)
    # contratto a tempo determinato su modulo «indeterminato»: si corregge la frase stampata
    if c["durata"] == DETERMINATO and not orario:
        pos = _trova(file, 0, "indeterminata.")
        if pos:
            o.bianco(0, pos[0] - 1, pos[1] - 1, pos[2] + 2, pos[3] + 1)
            o.testo(0, pos[0], pos[3] - 2, "determinata", 8.5)
            o.testo(0, 51, pos[3] + 9, f"fino al {data_it(c.get('data_fine'))}.", 8.5)
    if orario:
        _togli_netto_orario(o, file, 1, "Totale salario orario netto")
    return _applica(file, o, rimuovi_campi=True)


# ══════════════════════════════════════════════════════════════════════════════
# Dichiarazione di segretezza e non concorrenza (ultima pagina)
# ══════════════════════════════════════════════════════════════════════════════
def _dichiarazione(c: dict) -> PdfReader:
    az, d = c["azienda"], c["dip"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=18 * mm)
    base = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=14.5)
    tit = ParagraphStyle("t", parent=base, fontName="Helvetica-Bold", fontSize=14, leading=18, spaceAfter=6)
    art = ParagraphStyle("a", parent=base, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=2)
    pic = ParagraphStyle("p", parent=base, fontSize=8.5, leading=12)
    nome_dip = f"{d['nome']} {d['cognome']}"
    intest = Table(
        [[Paragraph(f"<b>Datore di lavoro</b><br/>{az['nome']}<br/>{_sede(az)}" + (f"<br/>{az['numero_che']}" if az.get("numero_che") else ""), pic),
          Paragraph(f"<b>Collaboratore</b><br/>{nome_dip}<br/>{_indirizzo(d)}" + (f"<br/>Nato/a il {data_it(d.get('data_nascita'))}" if d.get("data_nascita") else ""), pic)]],
        colWidths=[83 * mm, 83 * mm])
    intest.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, (0.3, 0.3, 0.3)), ("INNERGRID", (0, 0), (-1, -1), 0.6, (0.3, 0.3, 0.3)),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    storia = [
        Paragraph("Dichiarazione di segretezza e di non concorrenza", tit),
        Paragraph(f"Allegata al contratto individuale di lavoro con decorrenza {data_it(c['data_inizio'])}", pic),
        Spacer(1, 8), intest, Spacer(1, 8),
        Paragraph("1. Obbligo di segretezza", art),
        Paragraph("Il Collaboratore si impegna a mantenere il più assoluto riserbo su tutti i fatti e le informazioni di natura "
                  "professionale, commerciale, finanziaria o personale di cui viene a conoscenza nell'ambito del rapporto di lavoro, "
                  "in particolare su dati dei clienti, prezzi, condizioni, metodi di lavoro, organizzazione e altri segreti aziendali o "
                  "d'affari del Datore di lavoro (art. 321a cpv. 4 CO). L'obbligo vale durante il rapporto di lavoro e, per quanto "
                  "necessario a tutela degli interessi legittimi del Datore di lavoro, anche dopo la sua cessazione. Non è considerata "
                  "violazione la comunicazione richiesta dalla legge o da un'autorità.", base),
        Paragraph("2. Restituzione di documenti e dati", art),
        Paragraph("Alla cessazione del rapporto di lavoro, o su richiesta del Datore di lavoro, il Collaboratore restituisce tutti i "
                  "documenti, i supporti, le chiavi, le attrezzature e i dati (anche in copia o in formato elettronico) di proprietà del "
                  "Datore di lavoro o relativi alla sua attività, senza trattenerne copia.", base),
        Paragraph("3. Divieto di concorrenza", art),
        Paragraph("Per tutta la durata del rapporto di lavoro il Collaboratore non svolge attività concorrenti e non accetta impieghi "
                  "o collaborazioni presso imprese concorrenti o clienti del Datore di lavoro senza il consenso scritto di quest'ultimo "
                  "(art. 321a cpv. 3 CO). Dopo la cessazione del rapporto di lavoro, il Collaboratore si astiene da attività concorrenti "
                  "nella misura e per la durata consentite dagli art. 340-340c CO, nel caso in cui, grazie al rapporto di lavoro, abbia "
                  "avuto conoscenza della cerchia dei clienti o di segreti di fabbricazione o d'affari e il suo uso potesse "
                  "danneggiare sensibilmente il Datore di lavoro. Eventuali limiti di tempo, luogo e oggetto devono essere precisati per "
                  "iscritto nel contratto di lavoro e non possono superare i tre anni.", base),
        Paragraph("4. Pena convenzionale e conseguenze", art),
        Paragraph("La violazione di questa dichiarazione può comportare il risarcimento del danno e, ove pattuito per iscritto, "
                  "il pagamento di una pena convenzionale secondo gli art. 340b e 160 e segg. CO.", base),
        Paragraph("5. Diritto applicabile e foro", art),
        Paragraph(f"La presente dichiarazione è retta dal diritto svizzero. Foro competente è quello della sede del Datore di lavoro "
                  f"({az.get('sede_localita') or '—'}) o del domicilio del convenuto.", base),
        Spacer(1, 22),
        Paragraph(f"Luogo e data: {_luogo_data(c) or '______________________________'}", base),
        Spacer(1, 38),
        Table([[Paragraph("______________________________<br/>Il Datore di lavoro", pic), Paragraph("______________________________<br/>Il Collaboratore", pic)]],
              colWidths=[83 * mm, 83 * mm]),
    ]
    doc.build(storia)
    buf.seek(0)
    return PdfReader(buf)


# ══════════════════════════════════════════════════════════════════════════════
def genera_pdf(c: dict) -> bytes:
    """Compila il modello giusto per `c['tipo']` / `c['durata']` e, se richiesto, aggiunge la dichiarazione di
    segretezza come ultima pagina. Solleva ModelloMancante se il modello non esiste."""
    tipo = c["tipo"]
    if not modello_disponibile(tipo, c["durata"]):
        raise ModelloMancante(f"Il modello PDF per «{tipo}» non è ancora disponibile.")
    scrittore = {INDIVIDUALE: _individuale, CCNL: _ccnl, AUTOTRASPORTI: _autotrasporti, CPC: _cpc}[tipo](c)
    if c.get("segretezza"):
        for pagina in _dichiarazione(c).pages:
            scrittore.add_page(pagina)
    uscita = io.BytesIO()
    scrittore.write(uscita)
    return uscita.getvalue()
