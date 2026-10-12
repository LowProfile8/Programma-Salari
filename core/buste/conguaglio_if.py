"""Conguaglio dell'imposta alla fonte di fine anno, secondo gli esempi dello studio («Regole Personale Generali - Conguagli IF Esempi»).

Regole ricavate dagli esempi:
  • il lordo annuo DETERMINANTE è quanto il collaboratore guadagnerebbe in un anno intero: lordi realmente percepiti (con bonus,
    malattia, infortunio, assegni familiari…) + per i mesi senza busta (assunzione a metà anno, uscita) il lordo mensile regolare;
  • mese d'entrata o d'uscita non completo (licenziato il 18.7): conta come mese intero regolare;
  • contratti a ore: il lordo determinante è sempre 2160 × salario orario (aliquota forfettaria, anche a conguaglio) e l'aliquota
    trovata si applica al lordo realmente percepito;
  • per ogni mese si usa la sua tariffa (A0, B0, C1…: cambia con matrimonio, figli, assegni…) con la nuova aliquota del lordo determinante;
  • conguaglio = imposta dovuta (lordo del mese × aliquota corretta) − imposta già trattenuta. Positivo = si trattiene, negativo = si restituisce;
  • durante malattia e infortunio l'aliquota NON si abbassa (resta quella del mese prima): si corregge solo qui, a fine anno.
"""
from __future__ import annotations

from core.buste.calcolo import MESI, buste_dipendente
from core.contratti import fonte

ORE_ANNUE_FORFAIT = 2160


def _regolare(c: dict) -> bool:
    g = c.get("giorni") or {}
    assenza = g.get("inf_att", 0) + g.get("inf_ass", 0) + g.get("mal_att", 0) + g.get("mal_ass", 0) + g.get("mat", 0)
    return not assenza and not float(c.get("bonus") or 0) and not float(c.get("ore_supp") or 0)


def analisi(dip: dict, anno: int) -> dict | None:
    buste = {b["mese"]: b for b in buste_dipendente(dip) if b["anno"] == anno}
    if not buste:
        return None
    mesi = sorted(buste)
    orario = any((b["calc"] or {}).get("orario") for b in buste.values())
    # lordo mensile regolare: l'ultimo mese senza assenze/bonus (i mesi parziali per entrata/uscita contano, perché non sono assenze malattia)
    regolari = [m for m in mesi if _regolare(buste[m]["calc"])]
    reg_m = regolari[-1] if regolari else mesi[-1]
    c_reg = buste[reg_m]["calc"]
    g_reg = c_reg.get("giorni") or {}
    # se l'ultimo mese regolare è parziale (entrata/uscita), si riporta a 30 giorni
    lavoro = g_reg.get("lavoro") or 30
    regolare = float(c_reg.get("lordo_if") or 0.0)
    if lavoro and lavoro < 30 and not orario:
        regolare = round(regolare / lavoro * 30, 2)
    parti, determinante = [], 0.0
    if orario:
        ultimo = buste[mesi[-1]]
        determinante = ORE_ANNUE_FORFAIT * float((ultimo.get("input") or {}).get("salario") or 0.0)
        formula = f"2160 × salario orario CHF {float((ultimo.get('input') or {}).get('salario') or 0):,.2f}".replace(",", "'")
    else:
        reali, ipotetici = 0.0, 0
        for m in range(1, 13):
            if m in buste:
                c = buste[m]["calc"]
                g = c.get("giorni") or {}
                parziale = (g.get("lavoro", 30) < 30) and _regolare(c)
                reali += regolare if parziale else float(c.get("lordo_if") or 0.0)
            else:
                ipotetici += 1
        determinante = reali + regolare * ipotetici
        formula = f"lordi dei {len(buste)} mesi con busta CHF {reali:,.2f}".replace(",", "'")
        if ipotetici:
            formula += f" + {ipotetici} mesi × lordo regolare CHF {regolare:,.2f}".replace(",", "'")
    righe, tot_tr, tot_do = [], 0.0, 0.0
    for m in mesi:
        c = buste[m]["calc"]
        lordo = float(c.get("lordo_if") or 0.0)
        tar = c.get("tariffa_fonte")
        trattenuta = float(c.get("imposta") or 0.0)
        pct_app = float(c.get("imposta_pct") or 0.0)
        pct_giusta = None
        if tar and tar != "—":
            pct_giusta = fonte.aliquota(tar, determinante)
        dovuta = round(lordo * pct_giusta / 100, 2) if pct_giusta is not None else trattenuta
        righe.append({"mese": m, "lordo_if": lordo, "tariffa": tar or "—", "pct_applicata": pct_app, "trattenuta": trattenuta,
                      "pct_corretta": pct_giusta if pct_giusta is not None else pct_app, "dovuta": dovuta, "differenza": round(dovuta - trattenuta, 2),
                      "assenza": not _regolare(c)})
        tot_tr += trattenuta
        tot_do += dovuta
    casi = []
    if mesi[0] > 1:
        casi.append(f"Assunto a {MESI[mesi[0] - 1].lower()}: per i mesi precedenti si conta il lordo regolare (il lordo annuo è come se avesse lavorato tutto l'anno).")
    if dip.get("stato") == "licenziato" or mesi[-1] < 12:
        casi.append("Rapporto concluso o ancora in corso: i mesi senza busta si completano con il lordo regolare; il mese d'uscita parziale conta come intero.")
    if any(r["assenza"] for r in righe):
        casi.append("Malattia / infortunio / bonus: contano per il loro importo reale; l'aliquota durante l'anno è rimasta quella del mese prima, qui si corregge.")
    if len({r["tariffa"] for r in righe}) > 1:
        casi.append("La tariffa è cambiata durante l'anno (matrimonio, figli, assegni): ogni mese usa la sua tariffa con la nuova aliquota.")
    if orario:
        casi.append("Contratto a ore: aliquota forfettaria su 2160 × salario orario, applicata al lordo realmente percepito.")
    if not casi:
        casi.append("Anno regolare: il lordo annuo corrisponde a 12 mesi uguali, il conguaglio è pari a zero o minimo.")
    return {"righe": righe, "determinante": round(determinante, 2), "formula": formula, "conguaglio": round(tot_do - tot_tr, 2),
            "trattenuta": round(tot_tr, 2), "dovuta": round(tot_do, 2), "casi": casi, "completo": 12 in buste or dip.get("stato") == "licenziato"}
