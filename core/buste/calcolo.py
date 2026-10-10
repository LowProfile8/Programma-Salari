"""core/buste/calcolo.py — motore di calcolo della busta paga mensile.

Modellato sui fogli «Salari 2026» dello studio (conteggio paga: quota base × fattore, carenza, supplementi, 13a,
maternità, bonus → Salario lordo AVS → assegni e indennità assicurazione → Salario lordo soggetto all'imposta alla fonte
→ trattenute → netto). Il mese vale 30 giorni commerciali (come nei fogli).

Regole per infortunio e malattia (richieste dal titolare):
  • periodo d'attesa (impostato nelle Info aziendali): il datore di lavoro paga da solo la % di salario (80 / 88 %).
    Quell'importo fa parte del salario lordo AVS;
  • dal giorno successivo l'assicurazione paga l'indennità = salario annuo / 360 × 80 % × giorni. Non è salario AVS,
    ma entra nel salario lordo soggetto all'imposta alla fonte. L'aliquota è calcolata sul lordo soggetto IF complessivo.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import asdict

from core import lpp
from core.config import RAMI_PIANO1_BASIS
from core.contratti import calcolo as cal
from core.contratti import costruzione, fonte
from core.util import a_data

MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre",
        "Novembre", "Dicembre"]
MESI_BREVI = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
GIORNI_COMM = 30
IPG_MASSIMO_GIORNO = 220.0           # indennità di maternità/paternità: massimo giornaliero (80 % di CHF 274)
LAINF_GUADAGNO_MASSIMO = 148_200.0   # guadagno massimo assicurato LAINF (annuo)
PCT_INDENNITA = 80.0

SITUAZIONI = {
    "infortunio": "Infortunio",
    "malattia": "Malattia",
    "maternita": "Maternità / paternità",
    "ore_supp": "Ore supplementari",
    "bonus": "Bonus",
    "giorni": "Entrata o uscita nel mese / assenza non pagata",
    "rimborsi": "Rimborsi, vitto e alloggio, altre trattenute",
    "salario": "Cambio di salario o di aliquote",
}

V_VUOTO = {
    "salario": 0.0, "orario": False, "ore": 0.0, "tred": "mensile", "mese_13": 12, "vac_pct": 0.0, "fest_pct": 0.0, "bonus": 0.0,
    "ore_supp": 0.0, "ore_supp_tariffa": 0.0, "ore_supp_magg": 25.0,
    "rif_mensile": 0.0, "ass_pct": PCT_INDENNITA,
    "inf_inizio": None, "inf_fine": None, "inf_attesa": 0, "inf_pct": 80,
    "mal_inizio": None, "mal_fine": None, "mal_attesa": 0, "mal_pct": 80,
    "mat_inizio": None, "mat_fine": None,
    "entrata": None, "uscita": None, "nonpag_inizio": None, "nonpag_fine": None,
    "assegni": 0.0, "vitto": 0.0, "altra": 0.0, "altra_nome": "", "contributo": 0.0, "contributo_nome": "Contributo sindacale",
    "lavaggio": 0.0, "rimborsi": 0.0, "arrot_modo": "Nessuno", "arrot": 0.0,
    "lpp_man": False, "lpp": 0.0, "if_man": False, "if_pct": 0.0,
    "situazioni": [],
}


def giorni_mese(anno: int, mese: int) -> int:
    return calendar.monthrange(anno, mese)[1]


def _d(v):
    return a_data(v) if v else None


def contratto_del_mese(dip: dict, anno: int, mese: int) -> dict | None:
    """Ultimo contratto con data d'inizio entro la fine del mese (con i dati del modulo, quindi ricalcolabile)."""
    fine = dt.date(anno, mese, giorni_mese(anno, mese))
    cand = [c for c in dip.get("contratti", []) if c.get("form") and (_d(c.get("data_inizio")) or dt.date.min) <= fine]
    if not cand:
        cand = [c for c in dip.get("contratti", []) if c.get("form")]
    return max(cand, key=lambda c: c.get("data_inizio") or "") if cand else None


# ── contesto: contratto, aliquote e valori proposti ───────────────────────────
def contesto(az: dict, dip: dict, anno: int, mese: int) -> dict:
    """Tutto ciò che serve a proporre la busta paga: conteggio del contratto (base), aliquote, LPP, imposta alla fonte."""
    c = contratto_del_mese(dip, anno, mese)
    ctx = {"contratto": c, "base": None, "ali": cal.aliquote_da_azienda(az, dip.get("sesso")), "tipo": None}
    if c:
        form = dict(c["form"])
        try:
            b = costruzione.costruisci(az, dip, c["tipo"], form, dt.date(anno, mese, 1))
        except Exception:        # un contratto «strano» non deve impedire di fare la busta paga
            b = None
        ctx.update(base=b, tipo=c["tipo"])
        if b:
            ctx["ali"] = b["ali"]
    return ctx


def valori_proposti(az: dict, dip: dict, anno: int, mese: int, precedente: dict | None) -> dict:
    """Valori di partenza della busta: dal mese precedente se esiste, altrimenti dal contratto."""
    ctx = contesto(az, dip, anno, mese)
    V = dict(V_VUOTO)
    b = ctx["base"]
    if b:
        r, par = b["r"], b["par"]
        orario = par.durata == cal.ORE
        V.update(salario=par.salario_fisso, orario=orario, tred=par.tredicesima, vac_pct=par.vacanze_pct, fest_pct=par.festivita_pct,
                 assegni=par.assegni_figli if not orario else 0.0, vitto=par.vitto_alloggio, altra=par.altra_deduzione,
                 contributo=r.commissione_paritetica if not orario else 0.0, lavaggio=par.rimborsi_sett + par.rimborsi,
                 lpp=b["lpp_importo"], if_pct=b["if_pct"])
        if orario:
            V["ore"] = 0.0
            V["rif_mensile"] = 0.0
        else:
            V["rif_mensile"] = r.salario_fisso
        if ctx["contratto"] and ctx["contratto"].get("form", {}).get("bonus"):
            V["bonus"] = 0.0           # il bonus del contratto è «mensile»: nelle buste lo si inserisce a parte
    V["inf_attesa"] = int(az.get("attesa_infortunio") or 0)
    V["mal_attesa"] = int(az.get("attesa_malattia") or 0)
    V["inf_pct"] = int(az.get("carenza_pct_infortunio") or 80)
    V["mal_pct"] = int(az.get("carenza_pct_malattia") or 80)
    if precedente:
        pv = precedente.get("input") or {}
        for k in ("salario", "orario", "tred", "mese_13", "vac_pct", "fest_pct", "ore_supp_tariffa", "ore_supp_magg", "assegni", "vitto",
                  "altra", "altra_nome", "contributo", "contributo_nome", "lavaggio", "arrot_modo", "lpp_man", "lpp", "if_man", "if_pct",
                  "rif_mensile", "ass_pct", "ore"):
            if k in pv:
                V[k] = pv[k]
        if V["orario"]:
            V["ore"] = pv.get("ore", 0.0)
        # assenze ancora in corso nel mese precedente: restano aperte
        for sigla in ("inf", "mal", "mat"):
            if pv.get(f"{sigla}_inizio") and not pv.get(f"{sigla}_fine"):
                V[f"{sigla}_inizio"] = pv[f"{sigla}_inizio"]
                V[f"{sigla}_fine"] = None
                if sigla != "mat":
                    V[f"{sigla}_attesa"] = pv.get(f"{sigla}_attesa", V[f"{sigla}_attesa"])
                    V[f"{sigla}_pct"] = pv.get(f"{sigla}_pct", V[f"{sigla}_pct"])
        V["situazioni"] = [s for s in ("infortunio", "malattia", "maternita")
                           if pv.get({"infortunio": "inf_inizio", "malattia": "mal_inizio", "maternita": "mat_inizio"}[s])
                           and not pv.get({"infortunio": "inf_fine", "malattia": "mal_fine", "maternita": "mat_fine"}[s])]
    return V


# ── ripartizione dei giorni del mese ──────────────────────────────────────────
def ripartisci_giorni(V: dict, anno: int, mese: int) -> dict:
    """Assegna ogni giorno del mese a una categoria (lavoro, carenza infortunio...) e porta tutto su 30 giorni commerciali."""
    dim = giorni_mese(anno, mese)
    inf, mal, mat = _d(V.get("inf_inizio")), _d(V.get("mal_inizio")), _d(V.get("mat_inizio"))
    inf_f, mal_f, mat_f = _d(V.get("inf_fine")), _d(V.get("mal_fine")), _d(V.get("mat_fine"))
    entrata, uscita = _d(V.get("entrata")), _d(V.get("uscita"))
    np_i, np_f = _d(V.get("nonpag_inizio")), _d(V.get("nonpag_fine"))
    cont = {"fuori": 0, "mat": 0, "inf_att": 0, "inf_ass": 0, "mal_att": 0, "mal_ass": 0, "nonpag": 0, "lavoro": 0}
    for g in range(1, dim + 1):
        giorno = dt.date(anno, mese, g)
        if (entrata and giorno < entrata) or (uscita and giorno > uscita):
            cont["fuori"] += 1
        elif mat and giorno >= mat and (not mat_f or giorno <= mat_f):
            cont["mat"] += 1
        elif inf and giorno >= inf and (not inf_f or giorno <= inf_f):
            cont["inf_att" if (giorno - inf).days < int(V.get("inf_attesa") or 0) else "inf_ass"] += 1
        elif mal and giorno >= mal and (not mal_f or giorno <= mal_f):
            cont["mal_att" if (giorno - mal).days < int(V.get("mal_attesa") or 0) else "mal_ass"] += 1
        elif np_i and giorno >= np_i and (not np_f or giorno <= np_f):
            cont["nonpag"] += 1
        else:
            cont["lavoro"] += 1
    if cont["lavoro"] == dim:
        return {**cont, "lavoro": GIORNI_COMM, "calendario": dim}
    # mese incompleto: i giorni di lavoro si contano come sono (max 30), le assenze riempiono il resto dei 30 giorni
    ordine = ["fuori", "mat", "inf_att", "inf_ass", "mal_att", "mal_ass", "nonpag"]
    lavoro = min(GIORNI_COMM, cont["lavoro"])
    resto = GIORNI_COMM - lavoro
    out = {}
    for k in ordine:
        out[k] = min(cont[k], resto)
        resto -= out[k]
    if lavoro == 0 and resto > 0:          # tutto il mese assente (es. febbraio): si arriva a 30 giorni
        grande = max(ordine, key=lambda k: cont[k])
        out[grande] += resto
        resto = 0
    out["lavoro"] = lavoro
    out["calendario"] = dim
    return out


# ── calcolo ───────────────────────────────────────────────────────────────────
def _r2(x: float) -> float:
    return cal.arrotonda(x)


def calcola_busta(az: dict, dip: dict, anno: int, mese: int, V: dict) -> dict:
    V = {**V_VUOTO, **V}
    ctx = contesto(az, dip, anno, mese)
    ali = ctx["ali"]
    b = ctx["base"]
    tipo = ctx["tipo"] or cal.STANDARD
    orario = bool(V["orario"])
    q = float(V["salario"] or 0.0)
    g = ripartisci_giorni(V, anno, mese)
    avvisi: list[tuple[str, str]] = []

    # salario di riferimento (per carenza, indennità, maternità)
    if orario:
        ref_mensile = float(V.get("rif_mensile") or 0.0)
    else:
        ref_mensile = q
    stipendio = _r2(float(V["ore"] or 0.0) * q) if orario else (q if g["lavoro"] == GIORNI_COMM else _r2(q / GIORNI_COMM * g["lavoro"]))
    base_riga = {"qb": q, "fattore": float(V["ore"] or 0.0) if orario else g["lavoro"], "unita": "ore" if orario else "giorni"}

    carenza_inf = _r2(ref_mensile / GIORNI_COMM * float(V["inf_pct"]) / 100 * g["inf_att"])
    carenza_mal = _r2(ref_mensile / GIORNI_COMM * float(V["mal_pct"]) / 100 * g["mal_att"])
    carenza = _r2(carenza_inf + carenza_mal)

    vac = fest = q13 = 0.0
    if orario:
        pr = cal.calcola(cal.Parametri(tipo, cal.ORE, stipendio, V["tred"], 0.0, float(V["vac_pct"]), float(V["fest_pct"]), ali))
        vac, fest, q13 = pr.vacanze, pr.festivita, pr.quota_13
    else:
        if V["tred"] == "mensile":
            q13 = _r2((stipendio + carenza) * cal.ALIQUOTA_13)
    tredicesima_annuale = _r2(q) if (V["tred"] == "annuale" and not orario and int(V.get("mese_13") or 12) == mese) else 0.0

    tariffa_supp = float(V.get("ore_supp_tariffa") or 0.0)
    ore_supp_imp = _r2(float(V["ore_supp"] or 0.0) * tariffa_supp * (1 + float(V["ore_supp_magg"] or 0.0) / 100))

    # maternità / paternità: 80 % del salario medio giornaliero, massimo CHF 220 al giorno
    fattore_13 = 13 / 12 if V["tred"] != "nessuna" and not orario else 1.0
    ipg_giorno = min(IPG_MASSIMO_GIORNO, ref_mensile * 12 * fattore_13 / 365 * 0.8) if g["mat"] else 0.0
    maternita = _r2(ipg_giorno * g["mat"])

    bonus = _r2(float(V["bonus"] or 0.0))
    lordo_avs = _r2(stipendio + carenza + vac + fest + q13 + tredicesima_annuale + ore_supp_imp + maternita + bonus)

    # indennità dell'assicurazione: salario annuo / 360 × 80 %  (non è salario AVS)
    annuo = min(ref_mensile * 12 * fattore_13, LAINF_GUADAGNO_MASSIMO)
    ind_giorno = annuo / 360 * float(V.get("ass_pct") or PCT_INDENNITA) / 100
    giorni_ass = g["inf_ass"] + g["mal_ass"]
    ind_ass = _r2(ind_giorno * giorni_ass)
    assegni = _r2(float(V["assegni"] or 0.0))
    lordo_if = _r2(lordo_avs + assegni + ind_ass)

    # trattenute sociali
    base_ad = lordo_avs if orario else min(lordo_avs, cal.LIMITE_AD_MENSILE)
    avs = _r2(lordo_avs * ali.avs / 100)
    ad = _r2(base_ad * ali.ad / 100)
    igm = _r2(lordo_avs * ali.igm / 100)
    lainf = _r2((lordo_avs - maternita) * ali.lainf / 100)

    # LPP
    nascita = a_data(dip.get("data_nascita"))
    piano1 = az.get("lpp_modalita") == "piano1_basis" and az.get("ramo") in RAMI_PIANO1_BASIS
    lpp_sugg = None
    if piano1:
        cat = (lpp.categoria_eta(nascita, anno) if nascita else lpp.CATEGORIA_ADULTI) or lpp.CATEGORIA_ADULTI
        riferimento = lordo_avs if orario else _r2(ref_mensile * (1 + (cal.ALIQUOTA_13 if V["tred"] == "mensile" else 0.0)) + bonus)
        lpp_sugg = lpp.trattenuta_dipendente(riferimento, cat)
    if V["lpp_man"] or lpp_sugg is None:
        lpp_imp = _r2(float(V["lpp"] or 0.0))
    else:
        lpp_imp = lpp_sugg

    # imposta alla fonte: aliquota proposta sul salario lordo soggetto IF del mese
    fattore_tot = b["fattore_tot"] if b else 1.0
    if_sugg, if_info = None, None
    if b:
        coniuge = dip.get("coniuge") or {}
        annualizzato = (lordo_if - tredicesima_annuale) * 12 * fattore_tot
        if_info = fonte.valuta(nazionalita=dip.get("nazionalita"), permesso=dip.get("permesso"), stato_civile=dip.get("stato_civile"),
                               coniuge_lavora=coniuge.get("lavora"), n_figli=dip.get("n_figli"), figli_a_carico=dip.get("figli_a_carico"),
                               reddito_annuo=max(annualizzato, 1.0), anno_nascita=nascita.year if nascita else None, anno=anno,
                               nuovo_frontaliere=b["nuovo_front"])
        if not if_info["dovuta"]:
            if_sugg = 0.0
        elif if_info["aliquota"] is not None:
            if_sugg = float(if_info["aliquota"])
    if V["if_man"] or if_sugg is None:
        if_pct = float(V["if_pct"] or 0.0)
    else:
        if_pct = if_sugg
    imposta = _r2(lordo_if * if_pct / 100)

    vitto = _r2(float(V["vitto"] or 0.0))
    altra = _r2(float(V["altra"] or 0.0))
    contributo = _r2(float(V["contributo"] or 0.0))
    deduzioni = _r2(avs + ad + igm + lainf + lpp_imp + imposta + vitto + altra + contributo)
    lavaggio, rimborsi = _r2(float(V["lavaggio"] or 0.0)), _r2(float(V["rimborsi"] or 0.0))
    netto_pre = lordo_if - deduzioni + lavaggio + rimborsi
    modo = V.get("arrot_modo") or "Nessuno"
    if modo == "Manuale":
        arrot = _r2(float(V["arrot"] or 0.0))
    elif modo in ("A CHF 5", "A CHF 10"):
        passo = 5 if modo.endswith("5") else 10
        arrot = _r2(round(netto_pre / passo) * passo - netto_pre)
    else:
        arrot = 0.0
    netto = _r2(netto_pre + arrot)

    # controlli
    if netto < 0:
        avvisi.append(("errore", "Il netto è negativo: controlla le trattenute."))
    if (g["inf_att"] or g["inf_ass"]) and not V.get("inf_attesa") and g["inf_ass"]:
        avvisi.append(("avviso", "Periodo d'attesa dell'infortunio a 0 giorni: l'assicurazione paga dal primo giorno. "
                                 "Verifica nelle Info aziendali."))
    if giorni_ass and ref_mensile <= 0:
        avvisi.append(("errore", "Manca il salario di riferimento: senza di esso non si calcolano carenza e indennità."))
    if orario and (g["inf_att"] or g["inf_ass"] or g["mal_att"] or g["mal_ass"] or g["mat"]) and not V.get("rif_mensile"):
        avvisi.append(("errore", "Contratto a ore con assenze: inserisci il salario mensile di riferimento (media dei mesi precedenti)."))
    if (g["inf_ass"] or g["mal_ass"]) and not (az.get("assicuratore_infortuni") if g["inf_ass"] else az.get("assicuratore_malattia")):
        avvisi.append(("avviso", "Manca l'assicuratore nelle Info aziendali: l'indennità dell'assicurazione va incassata da loro."))
    if if_sugg is not None and V["if_man"] and abs(if_sugg - if_pct) > 0.0005:
        avvisi.append(("avviso", f"Aliquota imposta alla fonte inserita a mano ({if_pct:g}%) diversa da quella calcolata ({if_sugg:g}%)."))
    if if_info and if_info["dovuta"] and if_info["aliquota"] is None:
        avvisi.append(("avviso", "Aliquota non calcolabile automaticamente (reddito oltre CHF 1'200'000): inseriscila a mano."))
    if not b:
        avvisi.append(("avviso", "Nessun contratto salvato per questo dipendente: aliquote e imposta alla fonte vanno controllate a mano."))
    if V["inf_inizio"] and V["mal_inizio"] and g["inf_att"] + g["inf_ass"] and g["mal_att"] + g["mal_ass"]:
        avvisi.append(("avviso", "Infortunio e malattia nello stesso mese: l'infortunio ha la precedenza nei giorni sovrapposti."))
    if g["mat"] and ali.lainf:
        avvisi.append(("info", "Maternità: la trattenuta LAINF non si applica all'indennità di maternità."))

    righe = [
        ("stipendio", "Stipendio lordo", base_riga["qb"], base_riga["fattore"], stipendio),
        ("carenza", "Stipendio lordo periodo di carenza", ref_mensile if carenza else None,
         (g["inf_att"] + g["mal_att"]) or None, carenza),
        ("vac", "Supplemento vacanze", float(V["vac_pct"]) if orario else None, None, vac),
        ("fest", "Supplemento festività", float(V["fest_pct"]) if orario else None, None, fest),
        ("q13", "Quota mensile 13ma" if V["tred"] == "mensile" else "13ma mensilità", None, None, q13 + tredicesima_annuale),
        ("ore_supp", "Ore supplementari", tariffa_supp if ore_supp_imp else None, float(V["ore_supp"]) or None, ore_supp_imp),
        ("mat", "Indennità Maternità / Paternità", ipg_giorno if maternita else None, g["mat"] or None, maternita),
        ("bonus", "Bonus", None, None, bonus),
        ("lordo_avs", "Salario Lordo AVS", None, None, lordo_avs),
        ("assegni", "Assegni Familiari", None, None, assegni),
        ("ind_ass", "Indennità Assicurazione", ind_giorno if ind_ass else None, giorni_ass or None, ind_ass),
        ("lordo_if", "Salario Lordo soggetto IF", None, None, lordo_if),
        ("avs", "Trattenuta AVS", ali.avs, None, avs),
        ("ad", "Trattenuta AD", ali.ad, None, ad),
        ("igm", "Trattenuta IGM/IPG", ali.igm, None, igm),
        ("lainf", "Trattenuta LAINF", ali.lainf, None, lainf),
        ("lpp", "Trattenuta LPP", None, None, lpp_imp),
        ("imposta", "Trattenuta Imposta alla fonte", if_pct, None, imposta),
        ("vitto", "Vitto e alloggio", None, None, vitto),
        ("altra", V.get("altra_nome") or "Altra trattenuta", None, None, altra),
        ("contributo", V.get("contributo_nome") or "Contributo sindacale", None, None, contributo),
        ("deduzioni", "Totale deduzioni", None, None, deduzioni),
        ("lavaggio", "Rimborso lavaggio abiti", None, None, lavaggio),
        ("rimborsi", "Rimborsi diversi", None, None, rimborsi),
        ("arrot", "Arrotondamento", None, None, arrot),
        ("netto", "Salario netto in CHF", None, None, netto),
    ]
    return {
        "anno": anno, "mese": mese, "orario": orario, "tipo": tipo, "giorni": g, "righe": righe,
        "stipendio": stipendio, "carenza": carenza, "carenza_inf": carenza_inf, "carenza_mal": carenza_mal, "vac": vac, "fest": fest,
        "q13": q13 + tredicesima_annuale, "ore_supp": ore_supp_imp, "maternita": maternita, "bonus": bonus,
        "lordo_avs": lordo_avs, "assegni": assegni, "ind_ass": ind_ass, "lordo_if": lordo_if,
        "avs": avs, "ad": ad, "igm": igm, "lainf": lainf, "lpp": lpp_imp, "imposta": imposta, "imposta_pct": if_pct,
        "imposta_sugg": if_sugg, "tariffa_fonte": (if_info or {}).get("codice"), "lpp_sugg": lpp_sugg,
        "vitto": vitto, "altra": altra, "contributo": contributo, "deduzioni": deduzioni,
        "lavaggio": lavaggio, "rimborsi": rimborsi, "arrot": arrot, "netto": netto,
        "ind_giorno": ind_giorno, "ipg_giorno": ipg_giorno, "avvisi": avvisi,
    }


# ── archivio delle buste del dipendente ───────────────────────────────────────
def buste_dipendente(dip: dict) -> list[dict]:
    return sorted(dip.get("buste_paga", []), key=lambda b: (b["anno"], b["mese"]))


def busta_del_mese(dip: dict, anno: int, mese: int) -> dict | None:
    for b in dip.get("buste_paga", []):
        if b["anno"] == anno and b["mese"] == mese:
            return b
    return None


def busta_precedente(dip: dict, anno: int, mese: int) -> dict | None:
    prima = [b for b in dip.get("buste_paga", []) if (b["anno"], b["mese"]) < (anno, mese)]
    return max(prima, key=lambda b: (b["anno"], b["mese"])) if prima else None


def anni_con_buste(dip: dict) -> list[int]:
    return sorted({b["anno"] for b in dip.get("buste_paga", [])}, reverse=True)


def prossimo_mese(dip: dict, oggi: dt.date) -> tuple[int, int]:
    """Mese «da fare»: il mese corrente."""
    return oggi.year, oggi.month
