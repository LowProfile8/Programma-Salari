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

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import certificato, db
from core.buste import calcolo as bc
from core.buste import excel as bxl
from core.buste import pdf as bpdf
from core.config import NOME_STUDIO
from core.nav import tasto_home, vai
from core.stile import intestazione
from core.util import a_data, oggi
from modules import buste_ui

MIN_DATA = dt.date(1900, 1, 1)
MAX_DATA = dt.date(oggi().year + 100, 12, 31)
MODI = ["Come il mese precedente", "Ci sono situazioni particolari"]


def _chf(v) -> str:
    return f"{float(v or 0):,.2f}".replace(",", "'")


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, dt.date) else None


# ══════════════════════════════════════════════════════════════════════════════
# Editor di una busta paga
# ══════════════════════════════════════════════════════════════════════════════
CAMPI_NUM = ("salario", "ore", "vac_pct", "fest_pct", "bonus", "ore_supp", "ore_supp_tariffa", "ore_supp_magg", "rif_mensile", "ass_pct",
             "assegni", "vitto", "altra", "contributo", "lavaggio", "rimborsi", "arrot", "lpp", "if_pct")
NOMI_TRED = {"mensile": "13ma nel salario", "annuale": "13ma annuale", "nessuna": "Senza 13ma"}


def _imposta_stato(P: str, V0: dict, forza: bool = False) -> None:
    """Riempie i campi dai valori proposti (una sola volta per visita; con `forza` li riscrive, es. cambio di modo)."""
    s = st.session_state

    def metti(k, v):
        if forza:
            s[P + k] = v
        else:
            s.setdefault(P + k, v)

    for k in CAMPI_NUM:
        metti(k, float(V0.get(k) or 0.0))
    tred = V0.get("tred") or "mensile"
    if V0.get("orario") and tred == "annuale":
        tred = "mensile"
    metti("tred", tred)
    metti("altra_nome", V0.get("altra_nome") or "")
    metti("bonus_nome", V0.get("bonus_nome") or "Indennità extra")
    for cod in bc.PERCENTUALI:
        metti(f"bov_{cod}", cod in (V0.get("basi") or {}))
        metti(f"base_{cod}", float((V0.get("basi") or {}).get(cod) or 0.0))
    metti("contributo_nome", V0.get("contributo_nome") or "Contributo sindacale")
    metti("arrot_modo", V0.get("arrot_modo") or "Nessuno")
    for k in ("inf_attesa", "mal_attesa", "inf_pct", "mal_pct"):
        metti(k, int(V0.get(k) or 0))
    metti("mese_13", int(V0.get("mese_13") or 12))
    for k in ("lpp_man", "if_man"):
        metti(k, bool(V0.get(k)))
    for sigla in ("inf", "mal", "mat", "nonpag"):
        ini, fine = a_data(V0.get(f"{sigla}_inizio")), a_data(V0.get(f"{sigla}_fine"))
        metti(f"{sigla}_inizio", ini)
        metti(f"{sigla}_fine", fine)
        metti(f"{sigla}_aperta", bool(ini and not fine))
    for k in ("entrata", "uscita"):
        metti(k, a_data(V0.get(k)))
        metti(k + "_si", bool(V0.get(k)))
    sit0 = [x for x in (V0.get("situazioni") or []) if x in bc.SITUAZIONI]
    if forza:
        s[P + "sit"] = sit0
    else:
        s.setdefault(P + "sit", sit0)


def _data_assenza(P: str, sigla: str, etichetta: str, con_attesa: bool, az: dict | None = None) -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.date_input(f"{etichetta}: primo giorno", key=P + f"{sigla}_inizio", min_value=MIN_DATA, max_value=MAX_DATA, format="DD.MM.YYYY")
    with c2:
        if not st.session_state.get(P + f"{sigla}_aperta"):
            st.date_input(f"{etichetta}: ultimo giorno", key=P + f"{sigla}_fine", min_value=MIN_DATA, max_value=MAX_DATA, format="DD.MM.YYYY")
        st.checkbox("Ancora in corso (fine non definita)", key=P + f"{sigla}_aperta")
    if con_attesa:
        a, b = st.columns(2)
        a.number_input("Periodo d'attesa (giorni a carico del datore di lavoro)", min_value=0, max_value=730, step=1, key=P + f"{sigla}_attesa",
                       help="Preso dalle Info aziendali: si può cambiare per questo caso.")
        with b:
            pct = st.session_state.get(P + f"{sigla}_pct")
            st.markdown("<div style='font-size:0.85rem;color:#6E6E73;margin-top:1.7rem'>"
                        f"Nel periodo d'attesa il datore di lavoro paga il <b>{pct}%</b> del salario "
                        "(percentuale delle Info aziendali).</div>", unsafe_allow_html=True)


def _leggi_V(P: str, V0: dict, sit: list[str], orario: bool) -> dict:
    s = st.session_state
    V = dict(bc.V_VUOTO)
    for k in CAMPI_NUM:
        V[k] = float(s.get(P + k) or 0.0)
    for k in ("tred", "contributo_nome", "arrot_modo", "lpp_man", "if_man"):
        V[k] = s.get(P + k)
    V["altra_nome"] = s.get(P + "altra_nome") or ""
    for k in ("inf_attesa", "mal_attesa", "inf_pct", "mal_pct", "mese_13"):
        V[k] = int(s.get(P + k) or 0)
    V["orario"] = orario
    V["contratto_id"] = V0.get("contratto_id")
    V["ass_pct"] = float(V0.get("ass_pct") or bc.PCT_INDENNITA)
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
    V["bonus_nome"] = s.get(P + "bonus_nome") or "Indennità extra"
    V["basi"] = {cod: float(s.get(P + f"base_{cod}") or 0.0) for cod in bc.PERCENTUALI if s.get(P + f"bov_{cod}")}
    if "ore_supp" not in sit:
        V["ore_supp"] = 0.0
    V["cong"] = {cod: float(s.get(P + f"cong_{cod}_imp") or 0.0) for cod in bc.CONGUAGLI if s.get(P + f"cong_{cod}_on")}
    V["situazioni"] = list(sit)
    return V


# ── riga del conteggio (stessa struttura della busta paga) ──
COL = [3.0, 1.55, 1.5, 1.6]


def _testo(s: str, grigio: bool = False, destra: bool = False, grassetto: bool = False) -> None:
    colore = "#8A8F98" if grigio else "#1D1D1F"
    st.markdown(f"<div style='font-size:0.92rem;color:{colore};padding-top:0.45rem;text-align:{'right' if destra else 'left'};"
                f"font-weight:{700 if grassetto else 400}'>{s}</div>", unsafe_allow_html=True)


def _totale(v, grassetto: bool = False) -> None:
    _testo(_chf(v), destra=True, grassetto=grassetto)


def _intestazione_tabella() -> None:
    c = st.columns(COL)
    for col, et, dx in zip(c, ["Conteggio paga", "Quota base", "Fattore", "Totale (CHF)"], (False, True, True, True)):
        with col:
            st.markdown(f"<div style='font-size:0.78rem;font-weight:700;color:#6E6E73;text-align:{'right' if dx else 'left'}'>{et}</div>",
                        unsafe_allow_html=True)
    st.markdown("<hr style='margin:0.2rem 0 0.1rem 0;border-color:#0D2140'>", unsafe_allow_html=True)


def _riga_totale(R: dict, cod: str) -> None:
    c = st.columns(COL)
    with c[0]:
        _testo(R[cod][0], grassetto=True)
    with c[3]:
        _totale(R[cod][3], grassetto=True)
    st.markdown("<hr style='margin:0.1rem 0 0.3rem 0;border-color:#4BA3F7'>", unsafe_allow_html=True)


def _segna_base(P: str, cod: str) -> None:
    st.session_state[P + f"bov_{cod}"] = True


def _base(P: str, cod: str, calc: dict) -> None:
    """Importo su cui si applica l'aliquota (quota base): proposto dal programma, modificabile prima del PDF."""
    s = st.session_state
    if not s.get(P + f"bov_{cod}"):
        s[P + f"base_{cod}"] = float(calc["basi_auto"][cod])
    st.number_input(f"Base {cod}", min_value=0.0, step=10.0, format="%.2f", key=P + f"base_{cod}", label_visibility="collapsed",
                    on_change=_segna_base, args=(P, cod), help="Importo su cui si applica l'aliquota. Si può correggere a mano.")


_CTX: dict = {}


def _conguaglio(P: str, cod: str, calc: dict) -> None:
    """Sotto un onere sociale: «＋ Conguaglio». Si indica la nuova aliquota (o il nuovo importo LPP) e da quale mese vale: il programma
    calcola la differenza sulle buste già salvate dell'anno e la mette in questa busta (importo modificabile)."""
    s = st.session_state
    nome = bc.CONGUAGLI[cod]
    on = P + f"cong_{cod}_on"
    if not s.get(on):
        c = st.columns(COL)
        with c[0]:
            with st.container(key=f"sec_cong_{P}{cod}"):
                if st.button(f"＋ Conguaglio {nome}", key=P + f"cong_{cod}_add", width="stretch"):
                    s[on] = True
                    st.rerun()
        return
    anno, mese, dip = _CTX["anno"], _CTX["mese"], _CTX["dip"]
    if cod == "lpp":
        attuale = float(calc["lpp"])
    elif cod == "imposta":
        attuale = float(calc.get("imposta_pct") or 0.0)
    else:
        attuale = float(next((x[3] for x in calc["righe"] if x[0] == cod), 0.0) or 0.0)
    s.setdefault(P + f"cong_{cod}_nuova", attuale)
    s.setdefault(P + f"cong_{cod}_dal", 1)
    with st.container(border=True):
        st.markdown(f"**Conguaglio {nome}**")
        c = st.columns(COL)
        with c[0]:
            if mese == 1:
                st.caption("Nessuna busta precedente nell'anno: non c'è nulla da conguagliare.")
            else:
                st.selectbox("Vale dal mese", list(range(1, mese)), format_func=lambda m: bc.MESI[m - 1], key=P + f"cong_{cod}_dal")
        if cod == "imposta" and mese > 1:
            # lordo annuo effettivo calcolato in automatico dalle buste dell'anno; l'aliquota corretta segue la tariffa del dipendente
            from core.contratti import fonte as _fonte
            ka, kp = P + "cong_imposta_annuo", P + "cong_imposta_nuova"
            if not s.get(ka + "_man"):
                s[ka] = float(bc.lordo_annuo_effettivo(dip, anno, mese, calc.get("lordo_if")))
            tar = calc.get("tariffa_fonte")
            auto_pct = _fonte.aliquota(tar, float(s.get(ka) or 0.0)) if tar and tar != "—" else None
            if auto_pct is not None and not s.get(kp + "_man"):
                s[kp] = float(auto_pct)
            a1, a2 = st.columns([1, 1])
            with a1:
                st.number_input("Salario lordo annuo effettivo (CHF)", min_value=0.0, step=100.0, format="%.2f", key=ka,
                                on_change=lambda: s.__setitem__(ka + "_man", True),
                                help="Calcolato in automatico: lordi soggetti IF dei mesi già salvati + questo mese + mesi mancanti al lordo regolare. Si può modificare.")
            with a2:
                st.caption(f"Tariffa {tar or '—'}: aliquota corretta {auto_pct:g}% (dalla tabella)" if auto_pct is not None else "Aliquota non calcolabile: inseriscila a mano.")
            if s.get(ka + "_man") or s.get(kp + "_man"):
                with st.container(key=f"sec_ripr_{P}"):
                    if st.button("Ripristina i valori automatici", key=P + "cong_imposta_ripr"):
                        s[ka + "_man"] = False
                        s[kp + "_man"] = False
                        st.rerun()
        with c[1]:
            if cod == "lpp":
                st.number_input("Nuovo importo LPP al mese (CHF)", min_value=0.0, step=1.0, format="%.2f", key=P + f"cong_{cod}_nuova")
            else:
                st.number_input("Nuova aliquota (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.3f", key=P + f"cong_{cod}_nuova",
                                on_change=(lambda: s.__setitem__(P + "cong_imposta_nuova_man", True)) if cod == "imposta" else None)
        with c[2]:
            st.write("")
            with st.container(key=f"rosso_togli_{P}{cod}"):
                if st.button("Togli", key=P + f"cong_{cod}_del", width="stretch"):
                    s[on] = False
                    for suff in ("nuova", "dal", "imp", "sig", "annuo", "annuo_man", "pct_man"):
                        s.pop(P + f"cong_{cod}_{suff}", None)
                    st.rerun()
        firma = (s.get(P + f"cong_{cod}_nuova"), s.get(P + f"cong_{cod}_dal"))
        if s.get(P + f"cong_{cod}_sig") != firma:
            sugg, n = bc.conguaglio_suggerito(dip, anno, mese, cod, float(firma[0] or 0.0), int(firma[1] or 1))
            s[P + f"cong_{cod}_imp"] = sugg
            s[P + f"cong_{cod}_sig"] = firma
            s[P + f"cong_{cod}_n"] = n
            st.rerun()          # il conteggio sopra si ricalcola con il nuovo conguaglio
        with c[3]:
            st.number_input("Importo del conguaglio (CHF)", step=1.0, format="%.2f", key=P + f"cong_{cod}_imp",
                            help="Calcolato in automatico sulle buste già salvate; puoi correggerlo. Positivo = si trattiene, negativo = si restituisce.")
        st.caption(f"Calcolato su {s.get(P + f'cong_{cod}_n', 0)} buste già salvate del {_CTX['anno']}: nuovo dovuto meno quanto già trattenuto.")
        if cod == "imposta":
            st.link_button("Apri il calcolatore dell'imposta alla fonte (Repubblica e Cantone Ticino)", "https://www4.ti.ch/dfe/dc/sportello/calcolatori-dimposta/iaf2024")


def _tabella_conteggio(P: str, V: dict, calc: dict, orario: bool, sit: list[str], ali) -> None:
    s = st.session_state
    R = {cod: (et, qb, fat, tot) for cod, et, qb, fat, tot in calc["righe"]}
    g = calc["giorni"]
    _intestazione_tabella()

    # stipendio
    c = st.columns(COL)
    with c[0]:
        _testo("Salario orario lordo" if orario else "Stipendio lordo")
    with c[1]:
        st.number_input("Quota base", min_value=0.0, step=0.05 if orario else 10.0, format="%.2f", key=P + "salario", label_visibility="collapsed")
    with c[2]:
        if orario:
            st.number_input("Ore", min_value=0.0, step=0.5, format="%.2f", key=P + "ore", label_visibility="collapsed")
        else:
            _testo(f"{g['lavoro']} gg", destra=True)
    with c[3]:
        _totale(R["stipendio"][3])
    if orario and (g["inf_att"] or g["inf_ass"] or g["mal_att"] or g["mal_ass"] or g["mat"]):
        c = st.columns(COL)
        with c[0]:
            _testo("Media mensile dei lordi dei 12 mesi precedenti (per le assenze)", grigio=True)
        with c[1]:
            st.number_input("Riferimento", min_value=0.0, step=10.0, format="%.2f", key=P + "rif_mensile", label_visibility="collapsed")
    if R["carenza"][3]:
        c = st.columns(COL)
        with c[0]:
            _testo("Stipendio lordo periodo di carenza")
        with c[1]:
            _testo(_chf(R["carenza"][1]), True, True)
        with c[2]:
            _testo(f"{R['carenza'][2]:g} gg", True, True)
        with c[3]:
            _totale(R["carenza"][3])
    if orario:
        for cod, chiave, et in (("vac", "vac_pct", "Supplemento vacanze (%)"), ("fest", "fest_pct", "Supplemento festività (%)")):
            c = st.columns(COL)
            with c[0]:
                _testo(et)
            with c[1]:
                st.number_input(et, min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=P + chiave, label_visibility="collapsed")
            with c[3]:
                _totale(R[cod][3])
    # tredicesima
    c = st.columns(COL)
    with c[0]:
        opzioni = ["mensile", "nessuna"] if orario else ["mensile", "annuale", "nessuna"]
        st.selectbox("Tredicesima", opzioni, format_func=lambda x: NOMI_TRED[x], key=P + "tred", label_visibility="collapsed")
    with c[1]:
        if s.get(P + "tred") == "annuale":
            st.selectbox("Mese 13ma", list(range(1, 13)), format_func=lambda m: bc.MESI_BREVI[m - 1], key=P + "mese_13", label_visibility="collapsed")
    with c[3]:
        _totale(R["q13"][3])
    for cod in ("ore_supp", "mat"):
        if R[cod][3]:
            c = st.columns(COL)
            with c[0]:
                _testo(R[cod][0])
            with c[1]:
                if R[cod][1] is not None:
                    _testo(_chf(R[cod][1]), True, True)
            with c[2]:
                if R[cod][2] is not None:
                    _testo(f"{R[cod][2]:g}", True, True)
            with c[3]:
                _totale(R[cod][3])
    # indennità extra (bonus): disponibile in ogni mese
    c = st.columns(COL)
    with c[0]:
        if s.get(P + "bonus_nome") not in ("Bonus", "Indennità extra"):
            s[P + "bonus_nome"] = "Indennità extra"
        st.selectbox("Tipo", ["Bonus", "Indennità extra"], key=P + "bonus_nome", label_visibility="collapsed")
    with c[3]:
        st.number_input("Indennità extra", min_value=0.0, step=10.0, format="%.2f", key=P + "bonus", label_visibility="collapsed")
    _riga_totale(R, "lordo_avs")

    # assegni e indennità dell'assicurazione → lordo soggetto all'imposta alla fonte
    c = st.columns(COL)
    with c[0]:
        _testo("Assegni familiari")
    with c[3]:
        st.number_input("Assegni familiari", min_value=0.0, step=10.0, format="%.2f", key=P + "assegni", label_visibility="collapsed")
    if R["ind_ass"][3]:
        c = st.columns(COL)
        with c[0]:
            _testo("Indennità Assicurazione")
        with c[1]:
            _testo(_chf(R["ind_ass"][1]) + " /gg", True, True)
        with c[2]:
            _testo(f"{R['ind_ass'][2]:g} gg", True, True)
        with c[3]:
            _totale(R["ind_ass"][3])
    _riga_totale(R, "lordo_if")

    # trattenute: AVS, AD, IGM, LAINF (grigie, dal contratto / Info aziendali), LPP e imposta alla fonte
    for cod in ("avs", "ad", "igm", "lainf"):
        if cod in ("igm", "lainf") and not R[cod][2]:
            continue
        c = st.columns(COL)
        with c[0]:
            _testo(R[cod][0], grigio=True)
        with c[1]:
            _base(P, cod, calc)
        with c[2]:
            _testo(f"{R[cod][2]:g} %", True, True)
        with c[3]:
            _testo(_chf(R[cod][3]), True, True)
        if cod in bc.CONGUAGLI:
            _conguaglio(P, cod, calc)
    # LPP
    c = st.columns(COL)
    with c[0]:
        _testo("Trattenuta LPP")
    with c[1]:
        if s.get(P + "lpp_man") or calc["lpp_sugg"] is None:
            st.number_input("LPP", min_value=0.0, step=1.0, format="%.2f", key=P + "lpp", label_visibility="collapsed")
        else:
            _testo("automatica", True, True)
    with c[2]:
        if calc["lpp_sugg"] is not None:
            st.checkbox("A mano", key=P + "lpp_man")
    with c[3]:
        _totale(calc["lpp"])
    _conguaglio(P, "lpp", calc)
    # imposta alla fonte: quota base = lordo soggetto IF, fattore = aliquota
    c = st.columns(COL)
    with c[0]:
        _testo("Trattenuta Imposta alla fonte" + (f" (tariffa {calc['tariffa_fonte']})" if calc.get("tariffa_fonte") else ""))
        if calc["imposta_sugg"] is not None:
            st.checkbox("Aliquota a mano", key=P + "if_man")
    with c[1]:
        _base(P, "imposta", calc)
    with c[2]:
        if s.get(P + "if_man") or calc["imposta_sugg"] is None:
            st.number_input("Aliquota", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", key=P + "if_pct", label_visibility="collapsed")
        else:
            _testo(f"{calc['imposta_sugg']:g} %", False, True)
    with c[3]:
        _totale(calc["imposta"])
    if calc.get("imposta_bloccata") and not s.get(P + "if_man"):
        st.caption("Malattia/infortunio: aliquota uguale al mese precedente (non si abbassa); il conguaglio si fa a fine anno.")
    _conguaglio(P, "imposta", calc)
    # altre trattenute
    for chiave, et in (("vitto", "Vitto e alloggio"), ("contributo", None), ("altra", None)):
        c = st.columns(COL)
        with c[0]:
            if chiave == "vitto":
                _testo(et)
            elif chiave == "contributo":
                st.text_input("Contributo", key=P + "contributo_nome", label_visibility="collapsed", placeholder="Contributo sindacale / paritetico")
            else:
                st.text_input("Altra trattenuta", key=P + "altra_nome", label_visibility="collapsed", placeholder="Altra trattenuta (descrizione)")
        with c[3]:
            st.number_input(chiave, min_value=0.0, step=5.0, format="%.2f", key=P + chiave, label_visibility="collapsed")
    _riga_totale(R, "deduzioni")
    if any(s.get(P + f"bov_{c_}") for c_ in bc.PERCENTUALI):
        with st.container(key="sec_ripristina_basi_" + P):
            if st.button("Ripristina le basi di calcolo automatiche", key=P + "ripr_basi"):
                for c_ in bc.PERCENTUALI:
                    s[P + f"bov_{c_}"] = False
                st.rerun()

    # rimborsi e arrotondamento
    for chiave, et in (("lavaggio", "Rimborso lavaggio abiti"), ("rimborsi", "Rimborsi diversi")):
        c = st.columns(COL)
        with c[0]:
            _testo(et)
        with c[3]:
            st.number_input(et, step=5.0, format="%.2f", key=P + chiave, label_visibility="collapsed")
    c = st.columns(COL)
    with c[0]:
        st.selectbox("Arrotondamento", ["Nessuno", "A CHF 5", "A CHF 10", "Manuale"], key=P + "arrot_modo", label_visibility="collapsed",
                     format_func=lambda x: "Arrotondamento: " + x.lower() if x != "Nessuno" else "Arrotondamento: nessuno")
    with c[1]:
        if s.get(P + "arrot_modo") == "Manuale":
            st.number_input("Arrotondamento", step=0.05, format="%.2f", key=P + "arrot", label_visibility="collapsed")
    with c[3]:
        _totale(calc["arrot"])
    _riga_totale(R, "netto")


def _editor(az: dict, dip: dict, anno: int, mese: int, esistente: dict | None) -> None:
    ver = st.session_state.get(f"bpver_{dip['id']}_{anno}_{mese}", 0)
    P = f"bp{ver}_{dip['id']}_{anno}_{mese}_"
    prec = bc.busta_precedente(dip, anno, mese)
    nuovo_ct = None if esistente else bc.nuovo_contratto(dip, anno, mese, prec)
    nome_mese = f"{bc.MESI[mese - 1]} {anno}"
    if P + "init" not in st.session_state:
        V0 = dict(esistente["input"]) if esistente else bc.valori_proposti(az, dip, anno, mese, prec)
        lic = a_data(dip.get("data_licenziamento"))
        if not esistente and lic and (lic.year, lic.month) == (anno, mese) and lic < dt.date(anno, mese, bc.giorni_mese(anno, mese)):
            V0["uscita"] = lic.isoformat()
            V0["situazioni"] = list(V0.get("situazioni") or []) + ["giorni"]
        st.session_state[P + "V0"] = V0
        st.session_state[P + "V0c"] = bc.valori_proposti(az, dip, anno, mese, None, dal_contratto=True)
        st.session_state[P + "base"] = "prec"
        _imposta_stato(P, V0)
        st.session_state[P + "init"] = True
        st.session_state.setdefault(P + "pagamento", a_data(esistente.get("data_pagamento")) if esistente and esistente.get("data_pagamento")
                                    else dt.date(anno, mese, bc.giorni_mese(anno, mese)))
    # modi di partenza
    if prec:
        modi = [MODI[0], MODI[1]]
    else:
        modi = ["Dal contratto (prima busta paga)", MODI[1]]
    if nuovo_ct and prec:
        ini = a_data(nuovo_ct.get("data_inizio"))
        modi.append(f"Secondo il nuovo contratto (dal {ini.strftime('%d.%m.%Y') if ini else '—'})")
    if P + "modo" not in st.session_state or st.session_state[P + "modo"] not in modi:
        st.session_state[P + "modo"] = modi[0] if not esistente else modi[1]
    V0 = st.session_state[P + "V0"]
    # il modo «nuovo contratto» riparte dai valori del contratto
    modo_corrente = st.session_state[P + "modo"]
    base = "contr" if modo_corrente.startswith("Secondo il nuovo contratto") else "prec"
    if base != st.session_state[P + "base"]:
        V0 = st.session_state[P + "V0c"] if base == "contr" else st.session_state[P + "V0"]
        _imposta_stato(P, V0, forza=True)
        st.session_state[P + "base"] = base
    V0 = st.session_state[P + "V0c"] if base == "contr" else st.session_state[P + "V0"]
    orario = bool(V0.get("orario"))
    _imposta_stato(P, V0)        # Streamlit toglie lo stato dei campi non mostrati in un giro: li ripristina (evita i KeyError)

    st.markdown(f"### {'Modifica' if esistente else 'Nuova'} busta paga — {nome_mese}")
    st.caption(f"{dip['cognome']} {dip['nome']} · {db.nome_azienda(az)}")
    if prec:
        st.caption(f"Mese precedente: {bc.MESI[prec['mese'] - 1]} {prec['anno']} · lordo AVS CHF {_chf(prec['calc']['lordo_avs'])} · "
                   f"netto CHF {_chf(prec['calc']['netto'])}")
    else:
        st.caption("Prima busta paga del dipendente: parto dai dati del contratto.")
    if nuovo_ct:
        ini = a_data(nuovo_ct.get("data_inizio"))
        st.info(f"C'è un contratto che inizia il {ini.strftime('%d.%m.%Y') if ini else '—'}"
                + (" (diverso da quello della busta precedente)" if prec else "") + ". "
                + ("Scegli «Secondo il nuovo contratto» per prendere salario, aliquote e imposta alla fonte da lì." if prec else ""))

    # ── 1. come procedere ──
    if not esistente:
        st.radio("Come vuoi creare questa busta paga?", modi, key=P + "modo", horizontal=False)
        particolare = st.session_state[P + "modo"] == MODI[1]
    else:
        particolare = True
    if particolare:
        st.multiselect("Situazioni particolari del mese", list(bc.SITUAZIONI), format_func=lambda k: bc.SITUAZIONI[k], key=P + "sit",
                       placeholder="Scegli una o più situazioni (infortunio, malattia, maternità, bonus, ore supplementari…)")
        sit = list(st.session_state[P + "sit"])
    else:
        sit = list(st.session_state.get(P + "sit") or [])
        if sit:
            st.info("Dal mese precedente proseguono: " + ", ".join(bc.SITUAZIONI[x].lower() for x in sit) +
                    ". Per cambiarle scegli «Ci sono situazioni particolari».")
    if mese == int(st.session_state.get(P + "mese_13") or 12) and st.session_state.get(P + "tred") == "annuale":
        st.info("In questo mese si paga la 13a mensilità (13a «annuale» del contratto).")

    # ── 2. situazioni particolari ──
    if "infortunio" in sit:
        with st.container(border=True):
            st.markdown("**Infortunio**")
            _data_assenza(P, "inf", "Infortunio", True)
    if "malattia" in sit:
        with st.container(border=True):
            st.markdown("**Malattia**")
            _data_assenza(P, "mal", "Malattia", True)
    if "maternita" in sit:
        with st.container(border=True):
            st.markdown("**Maternità / paternità**")
            _data_assenza(P, "mat", "Congedo", False)
            st.caption("Indennità: 80 % del salario medio giornaliero, massimo CHF 220 al giorno.")
    if "ore_supp" in sit:
        with st.container(border=True):
            st.markdown("**Ore supplementari**")
            a, b, c = st.columns(3)
            a.number_input("Ore supplementari", min_value=0.0, step=0.5, format="%.2f", key=P + "ore_supp")
            b.number_input("Importo per ora (CHF)", min_value=0.0, step=0.5, format="%.2f", key=P + "ore_supp_tariffa",
                           help="Per i salari mensili: salario mensile × 12 / (ore settimanali × 52).")
            c.number_input("Maggiorazione (%)", min_value=0.0, max_value=200.0, step=5.0, key=P + "ore_supp_magg")
    if "giorni" in sit:
        with st.container(border=True):
            st.markdown("**Entrata, uscita o assenza non pagata**")
            a, b = st.columns(2)
            with a:
                st.checkbox("Entrato durante questo mese", key=P + "entrata_si")
                if st.session_state.get(P + "entrata_si"):
                    st.date_input("Primo giorno di lavoro", key=P + "entrata", min_value=MIN_DATA, max_value=MAX_DATA, format="DD.MM.YYYY")
            with b:
                st.checkbox("Uscito durante questo mese", key=P + "uscita_si")
                if st.session_state.get(P + "uscita_si"):
                    st.date_input("Ultimo giorno di lavoro", key=P + "uscita", min_value=MIN_DATA, max_value=MAX_DATA, format="DD.MM.YYYY")
            st.markdown("Assenza non pagata")
            _data_assenza(P, "nonpag", "Assenza", False)
            st.caption("Lascia vuota la data se non c'è nessuna assenza non pagata.")
    if "rimborsi" in sit:
        st.info("Rimborsi, vitto e alloggio e altre trattenute si inseriscono nel conteggio qui sotto.")
    if "salario" in sit:
        st.info("Cambia il salario o le aliquote direttamente nel conteggio qui sotto.")

    # ── 3. conteggio ──
    V = _leggi_V(P, V0, sit, orario)
    try:
        calc = bc.calcola_busta(az, dip, anno, mese, V)
    except Exception as e:      # mai una pagina rotta: si mostra il motivo
        st.error(f"Non riesco a calcolare la busta paga ({type(e).__name__}: {e}). Controlla i dati inseriti.")
        return
    st.markdown("#### Conteggio")
    _CTX.update(anno=anno, mese=mese, dip=dip)
    _tabella_conteggio(P, V, calc, orario, sit, None)
    V = _leggi_V(P, V0, sit, orario)
    calc = bc.calcola_busta(az, dip, anno, mese, V)

    st.session_state.setdefault(P + "contanti", bool(esistente and esistente.get("contanti")))
    st.session_state.setdefault(P + "pagamento", a_data(esistente.get("data_pagamento")) if esistente and esistente.get("data_pagamento")
                                else dt.date(anno, mese, bc.giorni_mese(anno, mese)))
    st.checkbox("Pagato in contanti", key=P + "contanti", help="Solo in questo caso sul PDF compaiono «Pagato in contanti» e la data.")
    if st.session_state.get(P + "contanti"):
        st.date_input("Data del pagamento in contanti", key=P + "pagamento", format="DD.MM.YYYY", min_value=MIN_DATA, max_value=MAX_DATA)
    if calc.get("dettagli"):
        with st.container(border=True):
            st.markdown("**Come sono stati calcolati i giorni di assenza**")
            for riga in calc["dettagli"]:
                st.caption(riga)
    if prec and calc["imposta_sugg"] is not None and abs(prec["calc"].get("imposta_pct", 0) - calc["imposta_sugg"]) > 0.0005 and not V["if_man"]:
        st.info(f"L'aliquota dell'imposta alla fonte cambia: mese precedente {prec['calc'].get('imposta_pct', 0):g}% → "
                f"{calc['imposta_sugg']:g}% (il lordo soggetto IF del mese è diverso).")
    for livello, testo in calc["avvisi"]:
        {"errore": st.error, "avviso": st.warning}.get(livello, st.info)(testo)
    g = calc["giorni"]
    st.caption(f"Giorni: lavoro {g['lavoro']} · carenza {g['inf_att'] + g['mal_att']} · indennità assicurazione {g['inf_ass'] + g['mal_ass']} · "
               f"maternità {g['mat']} · non pagati {g['nonpag'] + g['fuori']} (mese di 30 giorni commerciali)")

    s = st.session_state
    mancano = []
    for sg, c_, nome in (("inf", "infortunio", "Infortunio"), ("mal", "malattia", "Malattia"), ("mat", "maternita", "Maternità")):
        if c_ in sit:
            if not V.get(f"{sg}_inizio"):
                mancano.append(f"{nome}: inserisci il primo giorno dell'assenza, altrimenti non viene conteggiata.")
            elif not s.get(P + f"{sg}_aperta") and not s.get(P + f"{sg}_fine"):
                mancano.append(f"{nome}: inserisci l'ultimo giorno oppure spunta «Ancora in corso».")
    for testo in mancano:
        st.warning(testo)
    senza_ore = orario and not float(V["ore"]) and not any((g["inf_att"], g["inf_ass"], g["mal_att"], g["mal_ass"], g["mat"]))
    bloccato = bool(mancano) or senza_ore or any(l == "errore" for l, _ in calc["avvisi"])
    if senza_ore:
        st.caption("Inserisci le ore lavorate per poter salvare.")
    c1, c2, _ = st.columns([1.4, 1.4, 3])
    with c1:
        with st.container(key="verde_salva_busta"):
            if st.button("Salva", type="primary", key=P + "salva", disabled=bloccato, width="stretch"):
                contanti = bool(st.session_state.get(P + "contanti"))
                pagamento = st.session_state.get(P + "pagamento") if contanti else None
                busta = {"anno": anno, "mese": mese, "input": V, "calc": calc, "data_pagamento": _iso(pagamento), "contanti": contanti}
                try:
                    pdf = bpdf.busta_pdf(az, dip, busta)
                except Exception as e:
                    st.error(f"Impossibile creare il PDF ({type(e).__name__}: {e}).")
                    return
                db.salva_busta(az["id"], dip["id"], anno, mese, V, calc, pdf, _iso(pagamento), contanti)
                st.session_state["msg_bp"] = f"Busta paga di {nome_mese} salvata."
                st.session_state[f"bpver_{dip['id']}_{anno}_{mese}"] = ver + 1
                st.session_state["bp"] = {**st.session_state["bp"], "modo": "vedi"}
                st.rerun()
    with c2:
        with st.container(key="rosso_annulla_busta"):
            if st.button("Annulla", key=P + "annulla", width="stretch"):
                st.session_state[f"bpver_{dip['id']}_{anno}_{mese}"] = ver + 1
                st.session_state["bp"] = {**st.session_state["bp"], "mese": None, "modo": None}
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Busta salvata: vista
# ══════════════════════════════════════════════════════════════════════════════
def _anteprima(calc: dict) -> None:
    """Conteggio di una busta salvata, in sola lettura (stesse righe del PDF)."""
    righe = ""
    uguali = abs(float(calc.get("lordo_if") or 0) - float(calc.get("lordo_avs") or 0)) < 0.005
    for cod, et, qb, fat, tot in bpdf.righe_normali(calc):
        if cod not in bpdf.FISSE and not tot:
            continue
        if cod == "lordo_if" and uguali:
            continue
        forte = cod in bpdf.TOTALI
        stile = "font-weight:700;border-top:1px solid #4BA3F7;background:#F2F8FF;" if forte else ""
        qbs = (f"{qb:g}%" if cod in ("vac", "fest") else _chf(qb)) if qb not in (None, "") and not forte else ""
        fats = (f"{fat:g} %" if cod in bpdf.PERC else f"{fat:g}") if fat not in (None, "") and not forte else ""
        righe += (f"<tr style='{stile}'><td style='padding:3px 6px'>{et}</td><td style='text-align:right'>{qbs}</td>"
                  f"<td style='text-align:right'>{fats}</td><td style='text-align:right;padding-right:6px'>{_chf(tot)}</td></tr>")
    st.markdown("<table style='width:100%;font-size:0.92rem;border-collapse:collapse'>"
                "<tr style='font-size:0.78rem;color:#6E6E73'><th style='text-align:left;padding:3px 6px'>Conteggio paga</th>"
                "<th style='text-align:right'>Quota base</th><th style='text-align:right'>Fattore</th><th style='text-align:right;padding-right:6px'>Totale (CHF)</th></tr>"
                f"{righe}</table>", unsafe_allow_html=True)


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
            st.session_state["bp"] = {**st.session_state["bp"], "modo": "modifica", "scroll": True}
            st.rerun()
    with c3:
        with st.container(key=f"rosso_bp_del_{busta['id']}"):
            if st.button("Elimina", key=f"bp_del_{busta['id']}", width="stretch"):
                st.session_state[f"bp_conf_{busta['id']}"] = True
                st.rerun()
    if st.session_state.get(f"bp_conf_{busta['id']}"):
        st.warning("Eliminare questa busta paga e il suo PDF? L'operazione non si può annullare.")
        d1, d2, _ = st.columns([1.2, 1.2, 3])
        with d1:
            with st.container(key=f"rosso_bp_del_si_{busta['id']}"):
                if st.button("Sì, elimina", key=f"bp_del_si_{busta['id']}", width="stretch"):
                    db.elimina_busta(az["id"], dip["id"], busta["id"])
                    st.session_state.pop(f"bp_conf_{busta['id']}", None)
                    st.session_state["bp"] = {**st.session_state["bp"], "mese": None, "modo": None}
                    st.session_state["msg_bp"] = "Busta paga eliminata."
                    st.rerun()
        with d2:
            with st.container(key=f"rosso_bp_del_no_{busta['id']}"):
                if st.button("Annulla", key=f"bp_del_no_{busta['id']}", width="stretch"):
                    st.session_state.pop(f"bp_conf_{busta['id']}", None)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Pagina
# ══════════════════════════════════════════════════════════════════════════════
TOTALI = "__totali__"


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
        st.write("")
        with st.container(key="bp_totali_" + ("sel" if ctx.get("dip") == TOTALI else "no")):
            if st.button("Salari totali", key="bp_pick_totali", type="primary" if ctx.get("dip") == TOTALI else "secondary", width="stretch"):
                ctx.update(dip=TOTALI, mese=None, modo=None)
                st.rerun()
        st.caption("Riepilogo di tutti i dipendenti")

    with col_dx:
        if ctx.get("dip") == TOTALI:
            buste_ui.salari_totali(az, f"bp_{az['id']}")
            return
        dip = next((d for d in dipendenti if d["id"] == ctx.get("dip")), None)
        if dip is None:
            st.info("Scegli un dipendente a sinistra per vedere le sue buste paga e crearne una nuova.")
            return
        anni = sorted({anno_ora, anno_ora - 1, anno_ora + 1, *bc.anni_con_buste(dip), ctx.get("anno", anno_ora)}, reverse=True)
        c1, c2, c3 = st.columns([2.3, 1.7, 1.2], vertical_alignment="bottom")
        c1.markdown(f"#### {dip['cognome']} {dip['nome']}")
        with c2:
            if st.button("Info dipendente →", key=f"bp_info_{dip['id']}", width="stretch"):
                vai("dipendente", azienda_id=az["id"], dipendente_id=dip["id"])
        with c3:
            anno = st.selectbox("Anno", anni, index=anni.index(ctx.get("anno", anno_ora)), key="bp_anno")
        if anno != ctx.get("anno"):
            ctx.update(anno=anno, mese=None, modo=None)
        buste = {b["mese"]: b for b in dip.get("buste_paga", []) if b["anno"] == anno}
        ora = oggi()
        mese_cert = buste_ui.licenziato_con_ultima_busta(dip, anno)
        for riga in range(4):
            cols = st.columns(3)
            for col, mese in zip(cols, range(riga * 3 + 1, riga * 3 + 4)):
                with col:
                    scelto = ctx.get("mese") == mese
                    with st.container(key=f"bp_carta_{'sel' if scelto else 'no'}_{mese}", border=True):
                        st.markdown(f"**{bc.MESI[mese - 1]}**")
                        b = buste.get(mese)
                        futuro = (anno, mese) > (ora.year, ora.month)
                        if mese_cert and not b and mese == mese_cert + 1:
                            st.caption("Rapporto concluso")
                            st.download_button("Scarica certificato di salario", data=lambda: certificato.certificato_pdf(az, dip, anno),
                                               file_name=f"Certificato di salario {anno} - {dip['cognome']} {dip['nome']}.pdf",
                                               mime="application/pdf", key=f"bp_cert_{mese}", width="stretch")
                        elif mese_cert and not b and mese > mese_cert:
                            st.caption("—")
                            st.button("＋", key=f"bp_new_{mese}", disabled=True, width="stretch")
                        elif b:
                            st.caption(f"Lordo AVS: CHF {_chf(b['calc']['lordo_avs'])}")
                            st.caption(f"Netto: CHF {_chf(b['calc']['netto'])}")
                            if st.button("Apri", key=f"bp_open_{mese}", width="stretch"):
                                ctx.update(mese=mese, modo="vedi", scroll=True)
                                st.rerun()
                        elif futuro:
                            st.caption("—")
                            st.button("＋", key=f"bp_new_{mese}", disabled=True, width="stretch")
                        else:
                            st.caption("Da creare")
                            with st.container(key=f"bp_piu_{mese}"):
                                if st.button("＋", key=f"bp_new_{mese}", width="stretch", help=f"Crea la busta paga di {bc.MESI[mese - 1]} {anno}"):
                                    ctx.update(mese=mese, modo="nuova", scroll=True)
                                    st.rerun()
        with st.expander(f"Riepilogo {anno}", expanded=False):
            buste_ui.tabella_storico(dip, anno, az)
        with st.expander(f"Conguaglio imposta alla fonte {anno} (fine anno)", expanded=False):
            buste_ui.conguaglio_if_ui(dip, anno)

        mese = ctx.get("mese")
        if mese:
            st.divider()
            esistente = buste.get(mese)
            with st.container(key="bp_editor"):
                if esistente and ctx.get("modo") == "vedi":
                    _vista(az, dip, esistente)
                else:
                    _editor(az, dip, anno, mese, esistente if ctx.get("modo") == "modifica" else None)
            if ctx.pop("scroll", False):     # appena scelto un mese: la pagina scende da sola sulla busta da compilare
                components.html("<script>setTimeout(function(){var e=window.parent.document.querySelector('.st-key-bp_editor');"
                                "if(e){e.scrollIntoView({behavior:'smooth',block:'start'});var m=window.parent.document.querySelector('[data-testid=stMain]');if(m){setTimeout(function(){m.scrollBy({top:-90,behavior:'smooth'});},400);}}},450);</script>", height=0)
