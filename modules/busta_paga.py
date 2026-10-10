"""modules/busta_paga.py — Crea busta paga.

1. Si sceglie l'azienda. A sinistra l'elenco dei dipendenti, a destra le buste dei 12 mesi dell'anno del dipendente scelto
   (carte tutte uguali: mese fatto = netto e tasti; mese da fare = «＋») e, sotto, il riepilogo dell'anno.
2. Per un mese da fare si sceglie «come il mese precedente» oppure si segnalano situazioni particolari (infortunio, malattia,
   maternità, ore supplementari, bonus...). Il programma ricalcola tutto (carenza, indennità dell'assicurazione, AVS, LPP,
   imposta alla fonte) e mostra il conteggio in tempo reale.
3. «Salva» crea il PDF e lo archivia: lo si ritrova nell'archivio delle buste paga e nella scheda del dipendente.
"""

from __future__ import annotations

import datetime as dt

import streamlit as st

from core import db
from core.buste import calcolo as bc
from core.buste import pdf as bpdf
from core.config import NOME_STUDIO
from core.nav import tasto_home, vai
from core.stile import intestazione
from core.util import a_data, oggi
from modules import buste_ui

MIN_DATA = dt.date(oggi().year - 100, 1, 1)
MAX_DATA = dt.date(oggi().year + 100, 12, 31)
MODI = ["Come il mese precedente", "Ci sono situazioni particolari"]


def _chf(v) -> str:
    return f"{float(v or 0):,.2f}".replace(",", "'")


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, dt.date) else None


# ══════════════════════════════════════════════════════════════════════════════
# Editor di una busta paga
# ══════════════════════════════════════════════════════════════════════════════
def _imposta_stato(P: str, V0: dict) -> None:
    """Riempie i campi (una sola volta per visita) dai valori proposti."""
    s = st.session_state
    for k in ("salario", "ore", "vac_pct", "fest_pct", "bonus", "ore_supp", "ore_supp_tariffa", "ore_supp_magg", "rif_mensile", "ass_pct",
              "assegni", "vitto", "altra", "contributo", "lavaggio", "rimborsi", "arrot", "lpp", "if_pct"):
        s.setdefault(P + k, float(V0.get(k) or 0.0))
    tred = V0.get("tred") or "mensile"
    if V0.get("orario") and tred == "annuale":
        tred = "mensile"
    s.setdefault(P + "tred", tred)
    s.setdefault(P + "altra_nome", V0.get("altra_nome") or "")
    s.setdefault(P + "contributo_nome", V0.get("contributo_nome") or "Contributo sindacale")
    s.setdefault(P + "arrot_modo", V0.get("arrot_modo") or "Nessuno")
    for k in ("inf_attesa", "mal_attesa", "inf_pct", "mal_pct"):
        s.setdefault(P + k, int(V0.get(k) or 0))
    s.setdefault(P + "mese_13", int(V0.get("mese_13") or 12))
    for k in ("lpp_man", "if_man"):
        s.setdefault(P + k, bool(V0.get(k)))
    for sigla in ("inf", "mal", "mat", "nonpag"):
        ini, fine = a_data(V0.get(f"{sigla}_inizio")), a_data(V0.get(f"{sigla}_fine"))
        s.setdefault(P + f"{sigla}_inizio", ini)
        s.setdefault(P + f"{sigla}_fine", fine)
        s.setdefault(P + f"{sigla}_aperta", bool(ini and not fine) if ini else True)
    for k in ("entrata", "uscita"):
        s.setdefault(P + k, a_data(V0.get(k)))
        s.setdefault(P + k + "_si", bool(V0.get(k)))
    s.setdefault(P + "sit", list(V0.get("situazioni") or []))
    s.setdefault(P + "init", True)


def _data_assenza(P: str, sigla: str, etichetta: str, minimo: dt.date, con_attesa: bool, anno: int, mese: int) -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.date_input(f"{etichetta}: primo giorno", key=P + f"{sigla}_inizio", min_value=MIN_DATA, max_value=MAX_DATA, format="DD.MM.YYYY")
    with c2:
        st.checkbox("Ancora in corso (fine non definita)", key=P + f"{sigla}_aperta")
        if not st.session_state[P + f"{sigla}_aperta"]:
            st.date_input(f"{etichetta}: ultimo giorno", key=P + f"{sigla}_fine", min_value=MIN_DATA, max_value=MAX_DATA, format="DD.MM.YYYY")
    if con_attesa:
        a, b = st.columns(2)
        a.number_input("Periodo d'attesa (giorni a carico del datore di lavoro)", min_value=0, max_value=730, step=1, key=P + f"{sigla}_attesa",
                       help="Preso dalle Info aziendali: si può cambiare per questo caso.")
        b.selectbox("Salario pagato dal datore di lavoro nel periodo d'attesa (%)", [80, 88, 100], key=P + f"{sigla}_pct")


def _leggi_V(P: str, V0: dict, sit: list[str], orario: bool) -> dict:
    s = st.session_state
    V = dict(bc.V_VUOTO)
    for k in ("salario", "ore", "vac_pct", "fest_pct", "bonus", "ore_supp", "ore_supp_tariffa", "ore_supp_magg", "rif_mensile", "ass_pct",
              "assegni", "vitto", "altra", "contributo", "lavaggio", "rimborsi", "arrot", "lpp", "if_pct"):
        V[k] = float(s.get(P + k) or 0.0)
    for k in ("tred", "altra_nome", "contributo_nome", "arrot_modo", "lpp_man", "if_man"):
        V[k] = s.get(P + k)
    for k in ("inf_attesa", "mal_attesa", "inf_pct", "mal_pct", "mese_13"):
        V[k] = int(s.get(P + k) or 0)
    V["altra_nome"] = s.get(P + "altra_nome") or ""
    V["orario"] = orario
    for sigla, codice in (("inf", "infortunio"), ("mal", "malattia"), ("mat", "maternita")):
        if codice in sit:
            V[f"{sigla}_inizio"] = _iso(s.get(P + f"{sigla}_inizio"))
            V[f"{sigla}_fine"] = None if s.get(P + f"{sigla}_aperta") else _iso(s.get(P + f"{sigla}_fine"))
    if "giorni" in sit:
        if s.get(P + "entrata_si"):
            V["entrata"] = _iso(s.get(P + "entrata"))
        if s.get(P + "uscita_si"):
            V["uscita"] = _iso(s.get(P + "uscita"))
        V["nonpag_inizio"] = _iso(s.get(P + "nonpag_inizio"))
        V["nonpag_fine"] = None if s.get(P + "nonpag_aperta") else _iso(s.get(P + "nonpag_fine"))
    if "bonus" not in sit:
        V["bonus"] = 0.0
    if "ore_supp" not in sit:
        V["ore_supp"] = 0.0
    V["situazioni"] = list(sit)
    return V


def _anteprima(calc: dict) -> None:
    righe = []
    for cod, et, qb, fattore, tot in calc["righe"]:
        if cod in bpdf.FISSE or tot:
            righe.append({"Voce": et, "Quota base": "" if qb is None else f"{qb:g}" if cod in ("avs", "ad", "igm", "lainf", "imposta", "vac", "fest") else _chf(qb),
                          "Fattore": "" if fattore is None else f"{fattore:g}", "Totale (CHF)": _chf(tot)})
    st.dataframe(righe, hide_index=True, width="stretch", height=min(36 * (len(righe) + 1) + 4, 900))


def _editor(az: dict, dip: dict, anno: int, mese: int, esistente: dict | None) -> None:
    ver = st.session_state.get(f"bpver_{dip['id']}_{anno}_{mese}", 0)
    P = f"bp{ver}_{dip['id']}_{anno}_{mese}_"
    prec = bc.busta_precedente(dip, anno, mese)
    nome_mese = f"{bc.MESI[mese - 1]} {anno}"
    if P + "init" not in st.session_state:
        V0 = dict(esistente["input"]) if esistente else bc.valori_proposti(az, dip, anno, mese, prec)
        # entrata / uscita nel mese corrente
        ass = a_data(dip.get("data_assunzione"))
        if not esistente and ass and (ass.year, ass.month) == (anno, mese) and ass.day > 1:
            V0["entrata"] = ass.isoformat()
            V0["situazioni"] = list(V0.get("situazioni") or []) + ["giorni"]
        lic = a_data(dip.get("data_licenziamento"))
        if not esistente and lic and (lic.year, lic.month) == (anno, mese) and lic < dt.date(anno, mese, bc.giorni_mese(anno, mese)):
            V0["uscita"] = lic.isoformat()
            V0["situazioni"] = list(V0.get("situazioni") or []) + ["giorni"]
        if esistente:      # in modifica: le situazioni si ricavano dai dati salvati
            sit = list(V0.get("situazioni") or [])
            V0["situazioni"] = sit
        st.session_state[P + "V0"] = V0
        _imposta_stato(P, V0)
        st.session_state.setdefault(P + "modo", MODI[1] if (esistente or V0.get("situazioni")) else MODI[0])
        st.session_state.setdefault(P + "pagamento", a_data(esistente.get("data_pagamento")) if esistente and esistente.get("data_pagamento")
                                    else dt.date(anno, mese, bc.giorni_mese(anno, mese)))
    V0 = st.session_state[P + "V0"]
    orario = bool(V0.get("orario"))

    st.markdown(f"### {'Modifica' if esistente else 'Nuova'} busta paga — {nome_mese}")
    st.caption(f"{dip['cognome']} {dip['nome']} · {db.nome_azienda(az)}")
    if prec:
        st.caption(f"Mese precedente: {bc.MESI[prec['mese'] - 1]} {prec['anno']} · lordo AVS CHF {_chf(prec['calc']['lordo_avs'])} · "
                   f"netto CHF {_chf(prec['calc']['netto'])}")
    else:
        st.caption("Nessuna busta precedente: parto dai dati del contratto.")

    # ── 1. come procedere ──
    if not esistente:
        st.radio("Come vuoi creare questa busta paga?", MODI, key=P + "modo", horizontal=True)
        particolare = st.session_state[P + "modo"] == MODI[1]
    else:
        particolare = True
    if particolare:
        extra = ["giorni"] if "giorni" in (V0.get("situazioni") or []) else []
        st.multiselect("Situazioni particolari del mese", list(bc.SITUAZIONI), format_func=lambda k: bc.SITUAZIONI[k], key=P + "sit",
                       placeholder="Scegli una o più situazioni (infortunio, malattia, maternità, bonus, ore supplementari…)")
        sit = list(st.session_state[P + "sit"])
    else:
        sit = list(V0.get("situazioni") or [])
        if sit:
            st.info("Dal mese precedente proseguono: " + ", ".join(bc.SITUAZIONI[x].lower() for x in sit) +
                    ". Per cambiarle scegli «Ci sono situazioni particolari».")
    if mese == 12 and V0.get("tred") == "annuale":
        st.info("A dicembre si paga la 13a mensilità (13a «annuale» del contratto).")

    # ── 2. dati salariali ──
    with st.expander("Dati salariali", expanded=("salario" in sit or orario)):
        if orario:
            a, b, c = st.columns(3)
            a.number_input("Ore lavorate nel mese", min_value=0.0, step=0.5, format="%.2f", key=P + "ore")
            b.number_input("Salario orario lordo (CHF)", min_value=0.0, step=0.05, format="%.2f", key=P + "salario")
            c.number_input("Salario mensile di riferimento (CHF)", min_value=0.0, step=10.0, format="%.2f", key=P + "rif_mensile",
                           help="Serve solo se ci sono assenze (infortunio, malattia, maternità): di solito la media dei mesi precedenti.")
            a, b, c = st.columns(3)
            a.number_input("Supplemento vacanze (%)", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=P + "vac_pct")
            b.number_input("Supplemento festività (%)", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=P + "fest_pct")
            c.selectbox("Tredicesima", ["mensile", "nessuna"], key=P + "tred")
        else:
            a, b = st.columns(2)
            a.number_input("Salario mensile lordo (CHF)", min_value=0.0, step=10.0, format="%.2f", key=P + "salario")
            b.selectbox("Tredicesima", ["mensile", "annuale", "nessuna"], key=P + "tred",
                        format_func=lambda x: {"mensile": "Quota mensile nel salario", "annuale": "Una volta l'anno", "nessuna": "Nessuna"}[x])
            if st.session_state[P + "tred"] == "annuale":
                st.selectbox("Mese di pagamento della 13a", list(range(1, 13)), format_func=lambda m: bc.MESI[m - 1], key=P + "mese_13")
        st.number_input("Indennità dell'assicurazione (% del salario annuo / 360)", min_value=0.0, max_value=100.0, step=1.0, key=P + "ass_pct",
                        help="80 % del salario annuo diviso 360, per ogni giorno dopo il periodo d'attesa.")

    # ── 3. situazioni particolari ──
    if "infortunio" in sit:
        with st.container(border=True):
            st.markdown("**Infortunio**")
            _data_assenza(P, "inf", "Infortunio", MIN_DATA, True, anno, mese)
    if "malattia" in sit:
        with st.container(border=True):
            st.markdown("**Malattia**")
            _data_assenza(P, "mal", "Malattia", MIN_DATA, True, anno, mese)
    if "maternita" in sit:
        with st.container(border=True):
            st.markdown("**Maternità / paternità**")
            _data_assenza(P, "mat", "Congedo", MIN_DATA, False, anno, mese)
            st.caption("Indennità: 80 % del salario medio giornaliero, massimo CHF 220 al giorno (calcolo come nei fogli Excel).")
    if "ore_supp" in sit:
        with st.container(border=True):
            st.markdown("**Ore supplementari**")
            a, b, c = st.columns(3)
            a.number_input("Ore supplementari", min_value=0.0, step=0.5, format="%.2f", key=P + "ore_supp")
            b.number_input("Importo per ora (CHF)", min_value=0.0, step=0.5, format="%.2f", key=P + "ore_supp_tariffa",
                           help="Per i salari mensili: salario mensile × 12 / (ore settimanali × 52).")
            c.number_input("Maggiorazione (%)", min_value=0.0, max_value=200.0, step=5.0, key=P + "ore_supp_magg")
    if "bonus" in sit:
        with st.container(border=True):
            st.markdown("**Bonus**")
            st.number_input("Bonus lordo (CHF)", min_value=0.0, step=10.0, format="%.2f", key=P + "bonus")
            st.caption("Il bonus è salario AVS e soggetto all'imposta alla fonte: l'aliquota viene ricalcolata sul lordo complessivo del mese.")
    if "giorni" in sit:
        with st.container(border=True):
            st.markdown("**Entrata, uscita o assenza non pagata**")
            a, b = st.columns(2)
            with a:
                st.checkbox("Entrato durante questo mese", key=P + "entrata_si")
                if st.session_state[P + "entrata_si"]:
                    st.date_input("Primo giorno di lavoro", key=P + "entrata", min_value=MIN_DATA, max_value=MAX_DATA, format="DD.MM.YYYY")
            with b:
                st.checkbox("Uscito durante questo mese", key=P + "uscita_si")
                if st.session_state[P + "uscita_si"]:
                    st.date_input("Ultimo giorno di lavoro", key=P + "uscita", min_value=MIN_DATA, max_value=MAX_DATA, format="DD.MM.YYYY")
            st.markdown("Assenza non pagata")
            _data_assenza(P, "nonpag", "Assenza", MIN_DATA, False, anno, mese)
            if st.session_state.get(P + "nonpag_inizio") is None:
                st.caption("Lascia vuota la data se non c'è nessuna assenza non pagata.")

    # ── 4. altre voci ──
    with st.expander("Assegni, rimborsi, vitto e alloggio, altre trattenute, arrotondamento", expanded=("rimborsi" in sit)):
        a, b, c = st.columns(3)
        if not orario:
            a.number_input("Assegni familiari (CHF)", min_value=0.0, step=10.0, format="%.2f", key=P + "assegni")
        else:
            a.number_input("Assegni familiari (CHF)", min_value=0.0, step=10.0, format="%.2f", key=P + "assegni")
        b.number_input("Vitto e alloggio (CHF)", min_value=0.0, step=10.0, format="%.2f", key=P + "vitto")
        c.number_input("Contributo sindacale / paritetico (CHF)", min_value=0.0, step=1.0, format="%.2f", key=P + "contributo")
        a, b = st.columns(2)
        a.text_input("Altra trattenuta: descrizione", key=P + "altra_nome", placeholder="es. acconto, multa…")
        b.number_input("Altra trattenuta (CHF)", min_value=0.0, step=10.0, format="%.2f", key=P + "altra")
        a, b = st.columns(2)
        a.number_input("Rimborso lavaggio abiti (CHF)", min_value=0.0, step=5.0, format="%.2f", key=P + "lavaggio")
        b.number_input("Rimborsi diversi (CHF, può essere negativo)", step=5.0, format="%.2f", key=P + "rimborsi")
        a, b = st.columns(2)
        a.selectbox("Arrotondamento del netto", ["Nessuno", "A CHF 5", "A CHF 10", "Manuale"], key=P + "arrot_modo")
        if st.session_state[P + "arrot_modo"] == "Manuale":
            b.number_input("Arrotondamento (CHF)", step=0.05, format="%.2f", key=P + "arrot")

    # ── calcolo (prima con le aliquote automatiche, poi mostra i campi LPP / imposta alla fonte) ──
    V = _leggi_V(P, V0, sit, orario)
    try:
        calc = bc.calcola_busta(az, dip, anno, mese, V)
    except Exception as e:      # mai una pagina rotta: si mostra il motivo
        st.error(f"Non riesco a calcolare la busta paga ({type(e).__name__}: {e}). Controlla i dati inseriti.")
        return

    with st.expander("LPP e imposta alla fonte", expanded=True):
        a, b = st.columns(2)
        with a:
            if calc["lpp_sugg"] is not None:
                st.caption(f"LPP calcolata (Piano 1 Basis): CHF {_chf(calc['lpp_sugg'])}")
            st.checkbox("Inserisci l'LPP a mano", key=P + "lpp_man")
            if st.session_state[P + "lpp_man"] or calc["lpp_sugg"] is None:
                st.number_input("LPP (CHF)", min_value=0.0, step=1.0, format="%.2f", key=P + "lpp")
        with b:
            if calc["imposta_sugg"] is not None:
                st.caption(f"Aliquota calcolata: {calc['imposta_sugg']:g}% (tariffa {calc['tariffa_fonte']}) sul salario lordo soggetto IF "
                           f"di CHF {_chf(calc['lordo_if'])}")
            if prec and calc["imposta_sugg"] is not None and abs(prec["calc"].get("imposta_pct", 0) - calc["imposta_sugg"]) > 0.0005:
                st.info(f"L'aliquota cambia: mese precedente {prec['calc'].get('imposta_pct', 0):g}% → {calc['imposta_sugg']:g}% "
                        "(il lordo soggetto IF del mese è diverso).")
            st.checkbox("Inserisci l'aliquota a mano", key=P + "if_man")
            if st.session_state[P + "if_man"] or calc["imposta_sugg"] is None:
                st.number_input("Aliquota imposta alla fonte (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", key=P + "if_pct")
    V = _leggi_V(P, V0, sit, orario)
    calc = bc.calcola_busta(az, dip, anno, mese, V)

    st.date_input("Data di pagamento", key=P + "pagamento", format="DD.MM.YYYY", min_value=MIN_DATA, max_value=MAX_DATA)

    # ── anteprima e salvataggio ──
    st.markdown("#### Conteggio")
    for livello, testo in calc["avvisi"]:
        {"errore": st.error, "avviso": st.warning}.get(livello, st.info)(testo)
    _anteprima(calc)
    g = calc["giorni"]
    st.caption(f"Giorni: lavoro {g['lavoro']} · carenza {g['inf_att'] + g['mal_att']} · indennità assicurazione {g['inf_ass'] + g['mal_ass']} · "
               f"maternità {g['mat']} · non pagati {g['nonpag'] + g['fuori']} (mese di 30 giorni commerciali)")

    mancano_date = [bc.SITUAZIONI[c] for sg, c in (("inf", "infortunio"), ("mal", "malattia"), ("mat", "maternita"))
                    if c in sit and not V.get(f"{sg}_inizio")]
    for nome in mancano_date:
        st.warning(f"{nome}: inserisci il primo giorno dell'assenza, altrimenti non viene conteggiata.")
    bloccato = bool(mancano_date) or any(l == "errore" for l, _ in calc["avvisi"]) or (orario and not float(V["ore"]) and not any(
        (g["inf_att"], g["inf_ass"], g["mal_att"], g["mal_ass"], g["mat"])))
    c1, c2, _ = st.columns([1.4, 1.1, 3])
    with c1:
        with st.container(key="verde_salva_busta"):
            if st.button("Salva busta paga", type="primary", key=P + "salva", disabled=bloccato, width="stretch"):
                pagamento = st.session_state.get(P + "pagamento")
                busta = {"anno": anno, "mese": mese, "input": V, "calc": calc, "data_pagamento": _iso(pagamento)}
                try:
                    pdf = bpdf.busta_pdf(az, dip, busta)
                except Exception as e:
                    st.error(f"Impossibile creare il PDF ({type(e).__name__}: {e}).")
                    return
                db.salva_busta(az["id"], dip["id"], anno, mese, V, calc, pdf, _iso(pagamento))
                st.session_state["msg_bp"] = f"Busta paga di {nome_mese} salvata."
                st.session_state[f"bpver_{dip['id']}_{anno}_{mese}"] = ver + 1
                st.session_state["bp"] = {**st.session_state["bp"], "modo": "vedi"}
                st.rerun()
    with c2:
        if st.button("Annulla", key=P + "annulla", width="stretch"):
            st.session_state[f"bpver_{dip['id']}_{anno}_{mese}"] = ver + 1
            st.session_state["bp"] = {**st.session_state["bp"], "mese": None, "modo": None}
            st.rerun()
    if orario and not float(V["ore"]) and not bloccato:
        pass
    elif bloccato and orario and not float(V["ore"]):
        st.caption("Inserisci le ore lavorate per poter salvare.")


# ══════════════════════════════════════════════════════════════════════════════
# Busta salvata: vista
# ══════════════════════════════════════════════════════════════════════════════
def _vista(az: dict, dip: dict, busta: dict) -> None:
    anno, mese = busta["anno"], busta["mese"]
    st.markdown(f"### Busta paga — {bc.MESI[mese - 1]} {anno}")
    st.caption(f"{dip['cognome']} {dip['nome']} · salvata il {busta.get('aggiornata', '')}")
    _anteprima(busta["calc"])
    for livello, testo in busta["calc"].get("avvisi", []):
        {"errore": st.error, "avviso": st.warning}.get(livello, st.info)(testo)
    c1, c2, c3, _ = st.columns([1.9, 1.3, 1.2, 1])
    with c1:
        st.download_button("Scarica busta paga", data=lambda: buste_ui.pdf_busta(az, dip, busta),
                           file_name=f"Busta_paga_{dip['cognome']}_{dip['nome']}_{anno}-{mese:02d}.pdf".replace(" ", "_"),
                           mime="application/pdf", key=f"bp_dl_{busta['id']}", width="stretch")
    with c2:
        if st.button("Modifica", key=f"bp_edit_{busta['id']}", width="stretch"):
            st.session_state["bp"] = {**st.session_state["bp"], "modo": "modifica"}
            st.rerun()
    with c3:
        if st.button("Elimina", key=f"bp_del_{busta['id']}", width="stretch"):
            st.session_state[f"bp_conf_{busta['id']}"] = True
            st.rerun()
    if st.session_state.get(f"bp_conf_{busta['id']}"):
        st.warning("Eliminare questa busta paga e il suo PDF? L'operazione non si può annullare.")
        d1, d2, _ = st.columns([1.2, 1.2, 3])
        with d1:
            if st.button("Sì, elimina", key=f"bp_del_si_{busta['id']}", width="stretch"):
                db.elimina_busta(az["id"], dip["id"], busta["id"])
                st.session_state.pop(f"bp_conf_{busta['id']}", None)
                st.session_state["bp"] = {**st.session_state["bp"], "mese": None, "modo": None}
                st.session_state["msg_bp"] = "Busta paga eliminata."
                st.rerun()
        with d2:
            if st.button("Annulla", key=f"bp_del_no_{busta['id']}", width="stretch"):
                st.session_state.pop(f"bp_conf_{busta['id']}", None)
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Pagina
# ══════════════════════════════════════════════════════════════════════════════
def render() -> None:
    intestazione(NOME_STUDIO, "Crea busta paga")
    if tasto_home("busta"):
        vai("home")
    st.markdown("# Crea busta paga")
    msg = st.session_state.pop("msg_bp", None)
    if msg:
        st.success(msg)

    ctx = st.session_state.setdefault("bp", {"az": None, "dip": None, "anno": oggi().year, "mese": None, "modo": None})
    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Nessuna azienda in archivio.")
        return
    nomi = {a["id"]: db.nome_azienda(a) for a in aziende}
    if "bp_sel_az" not in st.session_state and ctx.get("az") in nomi:
        st.session_state["bp_sel_az"] = ctx["az"]
    scelta = st.selectbox("Per quale azienda vuoi creare le buste paga?", list(nomi), index=None, format_func=lambda i: nomi[i],
                          placeholder="Scegli un'azienda", key="bp_sel_az")
    if scelta != ctx.get("az"):
        ctx.update(az=scelta, dip=None, mese=None, modo=None)
    if not scelta:
        return
    az = db.get_azienda(scelta)
    dipendenti = db.ordina_dipendenti(az.get("dipendenti", []))
    if not dipendenti:
        st.info("Questa azienda non ha dipendenti. Aggiungili dall'archivio.")
        return

    col_elenco, col_dx = st.columns([1.25, 3.6], gap="large")
    anno_ora = oggi().year
    with col_elenco:
        st.markdown("##### Dipendenti")
        for d in dipendenti:
            fatte = sum(1 for b in d.get("buste_paga", []) if b["anno"] == ctx.get("anno", anno_ora))
            sel = ctx.get("dip") == d["id"]
            etichetta = f"{d['cognome']} {d['nome']}" + (" (licenziato)" if d.get("stato") == "licenziato" else "")
            with st.container(key=f"bp_dip_{'sel' if sel else 'no'}_{d['id']}"):
                if st.button(etichetta, key=f"bp_pick_{d['id']}", type="primary" if sel else "secondary", width="stretch"):
                    ctx.update(dip=d["id"], mese=None, modo=None)
                    st.rerun()
            st.caption(f"{fatte}/12 buste nel {ctx.get('anno', anno_ora)}")

    with col_dx:
        dip = next((d for d in dipendenti if d["id"] == ctx.get("dip")), None)
        if dip is None:
            st.info("Scegli un dipendente a sinistra per vedere le sue buste paga e crearne una nuova.")
            return
        anni = sorted({anno_ora, anno_ora - 1, anno_ora + 1, *bc.anni_con_buste(dip), ctx.get("anno", anno_ora)}, reverse=True)
        c1, c2 = st.columns([3, 1.2], vertical_alignment="bottom")
        c1.markdown(f"#### {dip['cognome']} {dip['nome']}")
        with c2:
            anno = st.selectbox("Anno", anni, index=anni.index(ctx.get("anno", anno_ora)), key="bp_anno")
        if anno != ctx.get("anno"):
            ctx.update(anno=anno, mese=None, modo=None)
        buste = {b["mese"]: b for b in dip.get("buste_paga", []) if b["anno"] == anno}
        ora = oggi()
        for riga in range(3):
            cols = st.columns(4)
            for col, mese in zip(cols, range(riga * 4 + 1, riga * 4 + 5)):
                with col:
                    scelto = ctx.get("mese") == mese
                    with st.container(key=f"bp_carta_{'sel' if scelto else 'no'}_{mese}", border=True):
                        st.markdown(f"**{bc.MESI[mese - 1]}**")
                        b = buste.get(mese)
                        futuro = (anno, mese) > (ora.year, ora.month)
                        if b:
                            st.caption(f"CHF {_chf(b['calc']['netto'])}")
                            if st.button("Apri", key=f"bp_open_{mese}", width="stretch"):
                                ctx.update(mese=mese, modo="vedi")
                                st.rerun()
                        elif futuro:
                            st.caption("—")
                            st.button("＋", key=f"bp_new_{mese}", disabled=True, width="stretch")
                        else:
                            st.caption("Da creare")
                            with st.container(key=f"bp_piu_{mese}"):
                                if st.button("＋", key=f"bp_new_{mese}", width="stretch", help=f"Crea la busta paga di {bc.MESI[mese - 1]} {anno}"):
                                    ctx.update(mese=mese, modo="nuova")
                                    st.rerun()
        with st.expander(f"Riepilogo {anno}", expanded=False):
            buste_ui.tabella_storico(dip, anno)

        mese = ctx.get("mese")
        if mese:
            st.divider()
            esistente = buste.get(mese)
            if esistente and ctx.get("modo") == "vedi":
                _vista(az, dip, esistente)
            else:
                _editor(az, dip, anno, mese, esistente if ctx.get("modo") == "modifica" else None)
