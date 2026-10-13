"""Pagina «Dichiarazioni salariali»: AVS, LPP, imposta alla fonte, LAINF e malattia."""
from __future__ import annotations

import streamlit as st

from core import db, dichiarazioni as dc
from core.config import NOME_STUDIO
from core.nav import tasto_home, vai
from core.stile import intestazione
from core.util import oggi


def _info_assicuratore(titolo: str, nome: str, extra: list[tuple[str, str]] | None = None) -> None:
    if nome:
        st.markdown(f"**{titolo}:** {nome}")
        for k, v in (extra or []):
            if v:
                st.markdown(f"**{k}:** {v}")
        st.caption("Dichiarazione da presentare direttamente all'assicuratore indicato nella scheda dell'azienda.")
    else:
        st.warning(f"Nella scheda dell'azienda non è indicato l'assicuratore ({titolo}). Compila «Informazioni azienda».")


def render() -> None:
    intestazione(NOME_STUDIO, "Dichiarazioni salariali")
    if tasto_home("dichiarazioni"):
        vai("home")
    st.markdown("# Dichiarazioni salariali")
    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Serve almeno un'azienda in archivio.")
        return
    nomi = {a["id"]: db.nome_azienda(a) for a in aziende}
    c1, c2 = st.columns([3, 1])
    az_id = c1.selectbox("Seleziona l'azienda", list(nomi), index=None, format_func=lambda i: nomi[i],
                         placeholder="Scegli un'azienda", key="dich_azienda")
    anni = list(range(oggi().year + 1, oggi().year - 6, -1))
    anno = c2.selectbox("Anno", anni, index=anni.index(oggi().year), key="dich_anno")
    if az_id is None:
        return
    az = db.get_azienda(az_id)
    nome = db.nome_azienda(az)
    st.caption("I dati (salari, giorni, aliquote) vengono presi in automatico dalle buste paga salvate dell'anno.")
    if not dc.dati_anno(az, anno):
        st.warning(f"Per {anno} non ci sono buste paga salvate: i moduli usciranno vuoti.")
    t_avs, t_lpp, t_if, t_inf, t_mal = st.tabs(["AVS", "LPP", "Imposta alla fonte", "LAINF", "Malattia"])
    with t_avs:
        st.markdown(f"Cassa AVS dell'azienda: **{az.get('cassa_avs') or 'non indicata'}**")
        scelta = st.radio("Dichiarazione per", ["IAS (Istituto delle assicurazioni sociali)", "GastroSocial"], horizontal=True, key="dich_avs_tipo")
        if scelta.startswith("IAS"):
            st.download_button("Scarica la dichiarazione dei salari IAS (PDF)", data=lambda: dc.avs_ias_pdf(az, anno),
                               file_name=f"Dichiarazione salari IAS {anno} - {nome}.pdf", mime="application/pdf", key=f"d_ias_{az_id}_{anno}")
        else:
            st.download_button("Scarica la dichiarazione dei salari GastroSocial (PDF)", data=lambda: dc.avs_gastro_pdf(az, anno),
                               file_name=f"Dichiarazione salari AVS GastroSocial {anno} - {nome}.pdf", mime="application/pdf", key=f"d_gs_{az_id}_{anno}")
            st.caption("Il modulo ufficiale GastroSocial per l'AVS non è tra i file forniti: viene generato un elenco equivalente con gli stessi dati.")
    with t_lpp:
        cassa = az.get("cassa_lpp") or ""
        if dc._is_gastro(cassa):
            st.markdown(f"Cassa pensione: **{cassa}**")
            tipo = st.radio("Modulo", ["Annuale", "Trimestrale"], horizontal=True, key="dich_lpp_tipo")
            st.download_button("Scarica la dichiarazione LPP GastroSocial (PDF)", data=lambda: dc.lpp_gastro_pdf(az, anno, tipo == "Trimestrale"),
                               file_name=f"Dichiarazione LPP GastroSocial {anno} - {nome}.pdf", mime="application/pdf", key=f"d_lpp_{az_id}_{anno}_{tipo}")
        else:
            st.info("La cassa pensione di questa azienda non è GastroSocial.")
            _info_assicuratore("Cassa pensione (LPP)", cassa, [("Piano", az.get("lpp_piano_nome")), ("Link", az.get("lpp_link"))])
    with t_if:
        st.download_button("Scarica la dichiarazione imposta alla fonte (PDF, divisa per mesi)", data=lambda: dc.ifonte_pdf(az, anno),
                           file_name=f"Dichiarazione imposta alla fonte {anno} - {nome}.pdf", mime="application/pdf", key=f"d_if_{az_id}_{anno}")
        st.link_button("Sito imposta alla fonte (Ticino)", "https://www4.ti.ch/dfe/dc/sportello/calcolatori-dimposta/iaf2024")
    with t_inf:
        _info_assicuratore("Assicuratore infortuni (LAINF)", az.get("assicuratore_infortuni") or "")
    with t_mal:
        _info_assicuratore("Assicuratore malattia (IGM)", az.get("assicuratore_malattia") or "")
