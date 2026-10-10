"""core/info_dipendente.py — scheda riassuntiva del dipendente in un'unica pagina A4 (da stampare per l'archivio cartaceo)."""

import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

BLU = (0.05, 0.13, 0.25)
GRIGIO = (0.42, 0.42, 0.45)


def _d(iso) -> str:
    if not iso:
        return ""
    try:
        return datetime.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return str(iso)


def _chf(v) -> str:
    try:
        return f"CHF {float(v):,.2f}".replace(",", "'")
    except (TypeError, ValueError):
        return ""


def _sezioni(az_nome: str, dip: dict) -> list[tuple[str, list[tuple[str, str]]]]:
    con = dip.get("coniuge") or {}
    v = dip.get("valori_salariali") or {}
    ultimo = (dip.get("contratti") or [None])[-1] or {}
    sez = [
        ("Dati personali", [
            ("Cognome", dip.get("cognome")), ("Nome", dip.get("nome")), ("Data di nascita", _d(dip.get("data_nascita"))),
            ("Nazionalità", dip.get("nazionalita")), ("Sesso", dip.get("sesso")), ("Stato civile", dip.get("stato_civile")),
            ("N° AVS", dip.get("numero_avs")), ("Figli", dip.get("n_figli")), ("Figli a carico", dip.get("figli_a_carico")),
            ("Cassa malati", dip.get("cassa_malati"))]),
        ("Indirizzo e contatti", [
            ("Via e numero", dip.get("via")), ("NPA / Località", " ".join(x for x in (dip.get("npa"), dip.get("localita")) if x)),
            ("E-mail", dip.get("email")), ("Telefono", dip.get("telefono"))]),
        ("Permesso", [
            ("Permesso", dip.get("permesso")), ("Entrata in Svizzera", _d(dip.get("data_entrata_svizzera"))),
            ("Scadenza permesso", _d(dip.get("scadenza_permesso")))] + ([("Rientro in Italia", dip.get("rientro"))] if dip.get("rientro") else [])),
        ("Rapporto di lavoro", [
            ("Azienda", az_nome), ("Funzione", dip.get("funzione")), ("Data di assunzione", _d(dip.get("data_assunzione"))),
            ("Stato", "Licenziato il " + _d(dip.get("data_licenziamento")) if dip.get("stato") == "licenziato" else "In servizio")]),
        ("Ultimo impiego in Svizzera", [
            ("Datore di lavoro", dip.get("ultimo_datore")), ("Ultimo giorno di lavoro", _d(dip.get("ultimo_lavoro_data")))]),
    ]
    if dip.get("stato_civile") in ("Coniugato/a", "Unione domestica registrata") and any(con.get(x) for x in con):
        sez.append(("Coniuge", [
            ("Nome e cognome", " ".join(x for x in (con.get("nome"), con.get("cognome")) if x)),
            ("Data / luogo di nascita", " – ".join(x for x in (_d(con.get("data_nascita")), con.get("luogo_nascita")) if x)),
            ("N° AVS", con.get("numero_avs")),
            ("Indirizzo", ", ".join(x for x in (con.get("via"), " ".join(y for y in (con.get("npa"), con.get("localita")) if y)) if x)),
            ("Lavora", (con.get("lavora") or "") + (f" ({con.get('lavora_dove')})" if con.get("lavora_dove") else "")),
            ("Salario maggiore", con.get("salario_maggiore")), ("Assegni familiari", con.get("assegni"))]))
    figli = [f for f in (dip.get("figli") or []) if any((f or {}).values())]
    if figli:
        sez.append(("Figli", [(f"Figlio {i + 1}", " ".join(x for x in (f.get("nome"), f.get("cognome")) if x)
                               + (f" (nato il {_d(f.get('data_nascita'))})" if f.get("data_nascita") else "")) for i, f in enumerate(figli)]))
    gen = []
    for rel, et in (("padre", "Padre"), ("madre", "Madre")):
        g = dip.get(rel) or {}
        testo = " ".join(x for x in (g.get("nome"), g.get("cognome")) if x)
        if g.get("data_nascita"):
            testo += f" (nato il {_d(g.get('data_nascita'))})"
        gen.append((et, testo))
    if any(t for _, t in gen):
        sez.append(("Genitori", gen))
    sez.append(("Dati bancari", [("IBAN", dip.get("iban")), ("Banca", dip.get("banca_nome")), ("Sede della banca", dip.get("banca_sede"))]))
    if v:
        sal = [("Salario lordo" + (" (all'ora)" if v.get("orario") else " (al mese)"), _chf(v.get("salario_lordo"))),
               ("Salario netto" + (" (all'ora)" if v.get("orario") else " (al mese)"), _chf(v.get("salario_netto"))),
               ("Imposta alla fonte", f"{v.get('imposta_fonte_pct', 0):g}% (tariffa {v.get('tariffa_fonte') or '—'})"),
               ("Contratto in vigore dal", _d(v.get("data_contratto")))]
        if ultimo.get("funzione"):
            sal.append(("Funzione nel contratto", ultimo.get("funzione")))
        sez.append(("Dati salariali (ultimo contratto)", sal))
    return sez


def scheda_pdf(az_nome: str, dip: dict) -> bytes:
    """Una pagina A4 in due colonne con tutti i dati del dipendente."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    m = 36
    nome = f"{dip.get('cognome', '')} {dip.get('nome', '')}".strip()
    c.setTitle(f"Scheda dipendente - {nome}")
    c.setFillColorRGB(*BLU)
    c.rect(0, alt - 62, larg, 62, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(m, alt - 30, nome or "Dipendente")
    c.setFont("Helvetica", 10)
    c.drawString(m, alt - 48, f"{az_nome}  ·  Scheda dipendente")
    c.drawRightString(larg - m, alt - 48, "Stampata il " + datetime.now().strftime("%d.%m.%Y"))

    sezioni = _sezioni(az_nome, dip)
    col_l = (larg - 2 * m - 18) / 2
    colonne = [m, m + col_l + 18]
    # si dispongono le sezioni sulle due colonne bilanciando l'altezza
    riga_h, tit_h, sp = 14.5, 22, 8
    altezze = [tit_h + len(r) * riga_h + sp for _, r in sezioni]
    totale, acc, meta = sum(altezze), 0, 0
    for i, h in enumerate(altezze):
        if acc + h / 2 > totale / 2:
            meta = i
            break
        acc += h
    else:
        meta = len(sezioni)
    gruppi = [sezioni[:meta], sezioni[meta:]]
    for x0, gruppo in zip(colonne, gruppi):
        y = alt - 90
        for titolo, righe in gruppo:
            c.setFillColorRGB(*BLU)
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(x0, y, titolo.upper())
            c.setStrokeColorRGB(0.29, 0.64, 0.97)
            c.setLineWidth(1.2)
            c.line(x0, y - 4, x0 + col_l, y - 4)
            y -= tit_h - 2
            for et, val in righe:
                c.setFillColorRGB(*GRIGIO)
                c.setFont("Helvetica", 8.2)
                c.drawString(x0, y, et)
                c.setFillColorRGB(0, 0, 0)
                c.setFont("Helvetica", 9.4)
                testo = str(val or "—")
                spazio = col_l - 92
                while stringWidth(testo, "Helvetica", 9.4) > spazio and len(testo) > 4:
                    testo = testo[:-2]
                    if stringWidth(testo + "…", "Helvetica", 9.4) <= spazio:
                        testo += "…"
                        break
                c.drawString(x0 + 92, y, testo)
                c.setStrokeColorRGB(0.88, 0.88, 0.9)
                c.setLineWidth(0.4)
                c.line(x0, y - 3.5, x0 + col_l, y - 3.5)
                y -= riga_h
            y -= sp
    c.setFillColorRGB(*GRIGIO)
    c.setFont("Helvetica", 7.5)
    c.drawString(m, 24, "Documento interno per l'archivio cartaceo.")
    c.showPage()
    c.save()
    return buf.getvalue()
