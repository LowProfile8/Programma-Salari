"""modules/buste_ui.py — pezzi grafici delle buste paga usati in più pagine: elenco per anno con le «carte» dei mesi
(archivio e scheda del dipendente) e tabella riassuntiva dell'anno (come la «Scheda salari» degli Excel)."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from core import db
from core.buste import calcolo as bc
from core.buste import pdf as bpdf
from core.nav import vai
from core.util import oggi


def _chf(v) -> str:
    return f"{float(v or 0):,.2f}".replace(",", "'")


def pdf_busta(az: dict, dip: dict, busta: dict) -> bytes:
    """PDF dal cloud; se per qualche motivo manca lo si rifà dai dati salvati."""
    dati = db.leggi_pdf_busta(dip["id"], busta["id"])
    return dati or bpdf.busta_pdf(az, dip, busta)


def _differito_busta(az: dict, dip: dict, busta: dict):
    return lambda: pdf_busta(az, dip, busta)


def _differito_anno(az: dict, dip: dict, anno: int):
    def crea() -> bytes:
        buste = [b for b in bc.buste_dipendente(dip) if b["anno"] == anno]
        return bpdf.unisci_pdf([pdf_busta(az, dip, b) for b in buste])
    return crea


def vai_a_busta(az_id: str, dip_id: str, anno: int, mese: int, modo: str) -> None:
    """Apre la pagina «Crea busta paga» su un dipendente e un mese (modo: 'vedi' oppure 'nuova')."""
    st.session_state["bp"] = {"az": az_id, "dip": dip_id, "anno": anno, "mese": mese, "modo": modo}
    st.session_state["bp_sel_az"] = az_id
    st.session_state.pop("bp_anno", None)
    from core.uscita import PAGINE_PROTETTE
    if st.session_state.get("vista") in PAGINE_PROTETTE:     # dalla scheda del dipendente: chiede se salvare le modifiche
        st.session_state["_nav_richiesta"] = ("busta_paga", {})
        st.rerun()
    vai("busta_paga")


def carte_anno(az: dict, dip: dict, anno: int, chiave: str, con_piu: bool = True) -> None:
    """Le buste di un anno come carte della stessa grandezza, 4 per riga. Sul mese corrente non ancora creato compare un «+»."""
    buste = {b["mese"]: b for b in bc.buste_dipendente(dip) if b["anno"] == anno}
    mesi = sorted(buste)
    ora = oggi()
    if con_piu and anno == ora.year and ora.month not in buste:
        mesi = sorted(mesi + [ora.month])
    if not mesi:
        st.caption("Nessuna busta paga in questo anno.")
        return
    for i in range(0, len(mesi), 4):
        cols = st.columns(4)
        for col, mese in zip(cols, mesi[i:i + 4]):
            with col:
                with st.container(key=f"{chiave}_carta_{anno}_{mese}", border=True):
                    st.markdown(f"**{bc.MESI[mese - 1]}**")
                    b = buste.get(mese)
                    if b is None:
                        st.caption("Da creare")
                        with st.container(key=f"{chiave}_piu_{anno}_{mese}"):
                            if st.button("＋", key=f"{chiave}_nuova_{anno}_{mese}", width="stretch",
                                         help=f"Crea la busta paga di {bc.MESI[mese - 1]} {anno}"):
                                vai_a_busta(az["id"], dip["id"], anno, mese, "nuova")
                    else:
                        st.caption(f"CHF {_chf(b['calc']['netto'])}")
                        st.download_button("Scarica", data=_differito_busta(az, dip, b),
                                           file_name=f"Busta_paga_{dip['cognome']}_{dip['nome']}_{anno}-{mese:02d}.pdf".replace(" ", "_"),
                                           mime="application/pdf", key=f"{chiave}_dl_{b['id']}", width="stretch")
                        if st.button("Modifica", key=f"{chiave}_mod_{b['id']}", width="stretch"):
                            vai_a_busta(az["id"], dip["id"], anno, mese, "vedi")


def buste_dipendente(az: dict, dip: dict, chiave: str, con_piu: bool = True) -> None:
    """Tutte le buste del dipendente divise per anno (dal più recente), con «Scarica l'anno» accanto a ogni anno."""
    anni = bc.anni_con_buste(dip)
    ora = oggi()
    if con_piu and ora.year not in anni:
        anni = [ora.year] + anni
    if not anni:
        st.caption("Nessuna busta paga salvata.")
        return
    for anno in anni:
        c1, c2 = st.columns([1.6, 2.4], vertical_alignment="center")
        c1.markdown(f"##### {anno}")
        if any(b["anno"] == anno for b in dip.get("buste_paga", [])):
            with c2:
                st.download_button("Scarica tutte le buste dell'anno", data=_differito_anno(az, dip, anno),
                                   file_name=f"Buste_paga_{dip['cognome']}_{dip['nome']}_{anno}.pdf".replace(" ", "_"),
                                   mime="application/pdf", key=f"{chiave}_anno_{anno}", width="stretch")
        carte_anno(az, dip, anno, f"{chiave}_{anno}", con_piu)


COLONNE_STORICO = [("stipendio", "Stipendio"), ("carenza", "Carenza"), ("q13", "13ma"), ("bonus", "Bonus"), ("lordo_avs", "Lordo AVS"),
                   ("ind_ass", "Ind. ass."), ("lordo_if", "Lordo IF"), ("avs", "AVS"), ("ad", "AD"), ("igm", "IGM"), ("lainf", "LAINF"),
                   ("lpp", "LPP"), ("imposta", "Imp. fonte"), ("deduzioni", "Deduzioni"), ("netto", "Netto")]


def tabella_storico(dip: dict, anno: int) -> None:
    """Riepilogo dei mesi dell'anno (una riga per mese + totale), come la «Scheda salari»."""
    buste = {b["mese"]: b for b in bc.buste_dipendente(dip) if b["anno"] == anno}
    if not buste:
        st.caption("Nessuna busta paga salvata per questo anno.")
        return
    righe, tot = [], {k: 0.0 for k, _ in COLONNE_STORICO}
    for mese in sorted(buste):
        c = buste[mese]["calc"]
        riga = {"Mese": bc.MESI[mese - 1]}
        for k, et in COLONNE_STORICO:
            v = float(c.get(k) or 0.0)
            riga[et] = v
            tot[k] += v
        righe.append(riga)
    righe.append({"Mese": "Totale", **{et: tot[k] for k, et in COLONNE_STORICO}})
    df = pd.DataFrame(righe)
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={et: st.column_config.NumberColumn(et, format="%.2f") for _, et in COLONNE_STORICO})
