"""core/contratti/costruzione.py — da dati azienda + dipendente + moduli del contratto a conteggio completo.

È l'unico posto dove si decide LPP e imposta alla fonte automatiche: lo usano sia la pagina «Crea contratto» sia il
ricalcolo automatico quando si modificano i dati di un dipendente (età, nazionalità, stato civile, figli...).
"""

import dataclasses

from core import lpp
from core.config import RAMI_PIANO1_BASIS
from core.contratti import calcolo as cal
from core.contratti import fonte, minimi
from core.util import a_data

FORM_VUOTO = {"durata": cal.INDETERMINATO, "percentuale": 100.0, "categoria": "Normale", "ore_aut": 45.0, "tredicesima": "mensile",
              "salario": 0.0, "bonus": 0.0, "lpp_manuale": False, "lpp": 0.0, "if_manuale": False, "if_pct": 0.0}


def costruisci(az: dict, dip: dict, tipo: str, F: dict, oggi) -> dict:
    """`dip` = dati del dipendente (anche coniuge dall'archivio). `F` = valori inseriti nel contratto."""
    F = {**FORM_VUOTO, **F}
    durata = F["durata"]
    orario = durata == cal.ORE
    inizio = a_data(F.get("inizio")) or oggi
    nascita = a_data(dip.get("data_nascita"))
    eta = cal.eta_anni(nascita, inizio)
    categoria = F.get("categoria") or "Normale"
    percentuale = float(F["percentuale"]) if not orario else 100.0

    ore_pieno_aut = float(F.get("ore_aut") or (41.5 if tipo == cal.AUTORIMESSE else 45.0))
    pieno = cal.ore_pieno(tipo, categoria, ore_pieno_aut)
    ore_sett = 0.0 if orario else cal.ore_settimanali(tipo, percentuale, categoria, ore_pieno_aut)
    vf = cal.info_vacanze_festivita(tipo, eta, bool(F.get("c1550")))
    if tipo == cal.PULIZIE and F.get("cat_ccl") in minimi.PULIZIE_2026:      # festività: 1,35% pulizie ordinarie, 3,58% le altre
        vf["festivita_pct"] = 1.35 if minimi.PULIZIE_2026[F["cat_ccl"]][2] else 3.58

    # classificazione per i minimi
    cls: dict = {}
    if tipo == cal.AUTOTRASPORTI:
        cls = dict(settore=F.get("settore") or "", categoria=F.get("categoria_veicolo") or "",
                   anni_servizio=5 if str(F.get("anni") or "").startswith("5") else 1, afc=bool(F.get("afc")))
    elif tipo == cal.CPC:
        cls = dict(qualifica=F.get("qualifica") or "", anno_prof=int(F.get("anno_prof") or 0))
    elif tipo == cal.CCNL:
        cls = dict(livello_ccnl=F.get("cat_ccnl") or "", riduzione_introduzione=0.08 if F.get("scelta_rid") in (1, 2, 4) else 0.0)
    elif tipo in (cal.AUTORIMESSE, cal.PULIZIE):
        cls = dict(cat_ccl=F.get("cat_ccl") or "", anno_ccl=int(F.get("anno_ccl") or 0), eta=eta)
    minimo = cal.verifica_minimo(tipo=tipo, durata=durata, salario_fisso=float(F["salario"]), percentuale=percentuale,
                                 ore_sett=ore_sett, ore_pieno_sett=pieno, anno=inizio.year, **cls)

    ali = cal.aliquote_da_azienda(az, dip.get("sesso"))
    tred = F.get("tredicesima") or "mensile"
    vac_pct = float(F.get("vac_pct") or 0.0) if orario else 0.0
    fest_pct = float(F.get("fest_pct") or 0.0) if orario else 0.0
    prelim = cal.calcola(cal.Parametri(tipo, durata, float(F["salario"]), tred, float(F.get("bonus") or 0.0), vac_pct, fest_pct, ali))

    # LPP: automatica per il Piano 1 Basis, salvo importo scritto a mano
    piano1 = az.get("lpp_modalita") == "piano1_basis" and az.get("ramo") in RAMI_PIANO1_BASIS
    lpp_sugg, lpp_pct_sugg = 0.0, None
    if piano1 and not orario:
        cat_lpp = (lpp.categoria_eta(nascita, inizio.year) if nascita else lpp.CATEGORIA_ADULTI) or lpp.CATEGORIA_ADULTI
        lpp_sugg = lpp.trattenuta_dipendente(prelim.lordo_avs, cat_lpp)
        lpp_pct_sugg = float(lpp.ALIQUOTA_DIPENDENTE[cat_lpp] * 100)
    # contratti a ore: l'LPP è su base mensile, quindi non si conteggia nel salario orario (nel PDF compare «Mensile»)
    lpp_importo = 0.0 if orario else (float(F.get("lpp") or 0.0) if (F.get("lpp_manuale") or not piano1) else lpp_sugg)

    # imposta alla fonte: tariffa e aliquota dalle tabelle del Cantone Ticino
    coniuge = dip.get("coniuge") or {}
    extra_mensili = 0.0 if orario else float(F.get("assegni") or 0.0) + float(F.get("rimborsi") or 0.0)
    nuovo_front, nota_front = fonte.nuovo_frontaliere(dip.get("permesso"), dip.get("data_entrata_svizzera"), F.get("inizio"))
    info_if = fonte.valuta(
        nazionalita=dip.get("nazionalita"), permesso=dip.get("permesso"), stato_civile=dip.get("stato_civile"),
        coniuge_lavora=coniuge.get("lavora"), n_figli=dip.get("n_figli"), figli_a_carico=dip.get("figli_a_carico"),
        reddito_annuo=prelim.lordo_annuo + 12 * extra_mensili, anno_nascita=nascita.year if nascita else None,
        anno=inizio.year, nuovo_frontaliere=nuovo_front)
    esente_if = not info_if["dovuta"]
    if esente_if:
        if_pct, if_auto = 0.0, True
    elif F.get("if_manuale") or info_if["aliquota"] is None:
        if_pct, if_auto = float(F.get("if_pct") or 0.0), False
    else:
        if_pct, if_auto = float(info_if["aliquota"]), True

    # rimborsi settoriali
    rimb_sett, rimb_nome = 0.0, ""
    if tipo == cal.AUTOTRASPORTI:
        rimb_sett = cal.FORFAIT_TRASFERTA.get(F.get("trasferta") or "Nessuno", 0.0)
    elif tipo == cal.CCNL and not orario:       # i rimborsi 50 + 20 non si danno nei contratti CCNL a ore
        salvati = F.get("ccnl_rimb") or []
        rimb_sett = sum(imp for i, (_, imp) in enumerate(cal.RIMBORSI_CCNL) if i < len(salvati) and salvati[i])
    elif tipo == cal.AUTORIMESSE:
        rimb_sett = float(F.get("trasferta_importo") or 0.0)
    elif tipo == cal.PULIZIE:
        rimb_sett = float(F.get("vestiario_importo") or 0.0)
    comm = comm_mensile = 0.0
    contributo_pct = 0.0
    if tipo == cal.AUTOTRASPORTI:
        comm_mensile = cal.commissione_paritetica_autotrasporti(percentuale if not orario else 100)
        comm = 0.0 if orario else comm_mensile
    elif tipo == cal.AUTORIMESSE:
        comm_mensile = cal.contributo_paritetico_autorimesse()
        comm = 0.0 if orario else comm_mensile
    elif tipo == cal.PULIZIE:
        contributo_pct = cal.CONTRIBUTO_PARITETICO_PULIZIE_PCT

    par = cal.Parametri(tipo, durata, float(F["salario"]), tred, float(F.get("bonus") or 0.0), vac_pct, fest_pct, ali,
                        lpp_importo, if_pct, float(F.get("vitto") or 0.0), float(F.get("altra") or 0.0), comm,
                        float(F.get("assegni") or 0.0), float(F.get("rimborsi") or 0.0), float(F.get("arrot") or 0.0), rimb_sett, contributo_pct)
    r = cal.calcola(par)

    controlli = cal.controlla_conteggio(
        tipo=tipo, durata=durata, r=r, par=par, eta=eta, anno_inizio=inizio.year,
        anno_nascita=nascita.year if nascita else None, ore_sett=ore_sett, percentuale=percentuale, esente_if=esente_if,
        lpp_max=lpp_sugg if (piano1 and not orario) else None, minimo=minimo)
    controlli += cal.avviso_vitto_alloggio(tipo, par.vitto_alloggio, F.get("vitto_prest"))
    if not esente_if and info_if["aliquota"] is None:
        controlli.append(("avviso", "Aliquota dell'imposta alla fonte non calcolabile automaticamente (reddito oltre CHF 1'200'000): "
                                    "inseriscila a mano."))
    if nota_front:
        controlli.append(("avviso", nota_front + f" Tabella {info_if['codice']}."))
    if not dip.get("sesso"):
        controlli.append(("avviso", "Sesso del dipendente non indicato: per l'aliquota malattia uso «uomo». Indicalo nei dati del dipendente."))
    if not esente_if and "non indicata" in info_if["spiegazione"]:
        controlli.append(("avviso", f"Tariffa {info_if['codice']} ({info_if['spiegazione']}): completa i dati del dipendente per una tariffa sicura."))

    contratto = {
        "tipo": tipo, "durata": durata,
        "azienda": {"nome": _nome(az), "sede_via": az.get("sede_via"), "sede_npa": az.get("sede_npa"),
                    "sede_localita": az.get("sede_localita"), "numero_che": az.get("numero_che")},
        "dip": dip, "funzione": (F.get("funzione") or "").strip(), "data_inizio": F.get("inizio"), "data_fine": F.get("fine"),
        "percentuale": percentuale, "ore_sett": ore_sett, "categoria_azienda": categoria, "calc": dataclasses.asdict(r),
        "aliq": {"avs": ali.avs, "ad": ali.ad, "igm": ali.igm, "lainf": ali.lainf},
        "lpp_pct": lpp_pct_sugg if (piano1 and not orario and abs(lpp_importo - lpp_sugg) < 0.005) else None,
        "vacanze_pct": vac_pct if orario else None, "festivita_pct": fest_pct if orario else None,
        "accordi": F.get("accordi") or "", "segretezza": bool(F.get("segretezza")),
        "data_firma": "" if F.get("senza_data") else (F.get("firma") or oggi.isoformat()), "lpp_link": az.get("lpp_link") or "", "altra_deduzione_nome": F.get("altra_nome") or "",
        "comm_mensile": comm_mensile if orario else None, "tredicesima": tred, "lpp_mensile": orario,
        "contributo_pct": contributo_pct, "n_mensilita": 13 if tred == "annuale" else 12, "cat_ccl": F.get("cat_ccl") or "",
    }
    if tipo == cal.CCNL:
        contratto["ccnl"] = {"livello": F.get("cat_ccnl"), "riduzione": F.get("scelta_rid"), "prova": F.get("prova") or "3 mesi",
                             "vkb": F.get("vkb_testo") or ""}
    valori = {"data_contratto": F.get("inizio"), "tipo": tipo, "durata": durata, "orario": orario,
              "salario_lordo": r.lordo_avs, "salario_netto": r.netto, "imposta_fonte_pct": r.imposta_fonte_pct,
              "tariffa_fonte": info_if["codice"], "lordo_annuo": r.lordo_annuo, "avs_annuo": r.avs_annuo}
    return {"r": r, "par": par, "minimo": minimo, "controlli": controlli, "contratto": contratto, "valori": valori,
            "ore_sett": ore_sett, "pieno": pieno, "info_if": info_if, "if_pct": if_pct, "if_auto": if_auto, "esente_if": esente_if,
            "lpp_sugg": lpp_sugg, "lpp_pct_sugg": lpp_pct_sugg, "lpp_importo": lpp_importo, "piano1": piano1, "vf": vf,
            "prelim": prelim, "ali": ali, "nuovo_front": nuovo_front, "nota_front": nota_front, "eta": eta, "inizio": inizio, "comm_mensile": comm_mensile, "rimb_sett": rimb_sett}


def _nome(az: dict) -> str:
    return (az.get("ragione_sociale") or "").strip() or "(senza ragione sociale)"
