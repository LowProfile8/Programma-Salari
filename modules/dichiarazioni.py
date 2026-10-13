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


VOCI = [("dich_avs", "Dichiarazione AVS"), ("dich_lpp", "Dichiarazione LPP"), ("dich_if", "Dichiarazione imposta alla fonte")]


def cerchi(prefisso: str) -> None:
    """Tre pulsanti circolari con bordo blu (usati in home e nella pagina Dichiarazioni salariali)."""
    cols = st.columns([1, 1, 1, 3.2])
    for col, (vista, et) in zip(cols, VOCI):
        with col:
            with st.container(key=f"cerchio_{prefisso}_{vista}"):
                if st.button(et, key=f"{prefisso}_{vista}"):
                    vai(vista)


def render() -> None:
    intestazione(NOME_STUDIO, "Dichiarazioni salariali")
    if tasto_home("dichiarazioni"):
        vai("home")
    st.markdown("# Dichiarazioni salariali")
    st.caption("Scegli la dichiarazione da preparare.")
    cerchi("hub")


def _scelta(titolo: str, chiave: str):
    intestazione(NOME_STUDIO, titolo)
    if tasto_home(chiave):
        vai("home")
    st.markdown(f"# {titolo}")
    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Serve almeno un'azienda in archivio.")
        return None
    nomi = {a["id"]: db.nome_azienda(a) for a in aziende}
    c1, c2 = st.columns([3, 1])
    az_id = c1.selectbox("Seleziona l'azienda", list(nomi), index=None, format_func=lambda i: nomi[i],
                         placeholder="Scegli un'azienda", key="dich_azienda")
    anni = list(range(oggi().year + 1, oggi().year - 6, -1))
    anno = c2.selectbox("Anno", anni, index=anni.index(oggi().year), key="dich_anno")
    if az_id is None:
        return None
    az = db.get_azienda(az_id)
    st.caption("I dati (salari, giorni, aliquote) vengono presi in automatico dalle buste paga salvate dell'anno.")
    if not dc.dati_anno(az, anno):
        st.warning(f"Per {anno} non ci sono buste paga salvate: i moduli usciranno vuoti.")
    return az_id, az, anno, db.nome_azienda(az)


def render_avs() -> None:
    r = _scelta("Dichiarazione AVS", "dich_avs")
    if not r:
        return
    az_id, az, anno, nome = r
    st.markdown(f"Cassa AVS dell'azienda: **{az.get('cassa_avs') or 'non indicata'}**")
    scelta = st.radio("Dichiarazione per", ["IAS (Istituto delle assicurazioni sociali)", "GastroSocial"], horizontal=True, key="dich_avs_tipo")
    if scelta.startswith("IAS"):
        st.download_button("Scarica la dichiarazione dei salari IAS (PDF)", data=lambda: dc.avs_ias_pdf(az, anno),
                           file_name=f"Dichiarazione salari IAS {anno} - {nome}.pdf", mime="application/pdf", key=f"d_ias_{az_id}_{anno}")
    else:
        st.download_button("Scarica la dichiarazione dei salari GastroSocial (PDF)", data=lambda: dc.avs_gastro_pdf(az, anno),
                           file_name=f"Dichiarazione salari AVS GastroSocial {anno} - {nome}.pdf", mime="application/pdf", key=f"d_gs_{az_id}_{anno}")
        st.caption("Il modulo ufficiale GastroSocial per l'AVS non è tra i file forniti: viene generato un elenco equivalente con gli stessi dati.")


def render_lpp() -> None:
    r = _scelta("Dichiarazione LPP", "dich_lpp")
    if not r:
        return
    az_id, az, anno, nome = r
    cassa = az.get("cassa_lpp") or ""
    if dc._is_gastro(cassa):
        st.markdown(f"Cassa pensione: **{cassa}**")
        tipo = st.radio("Modulo", ["Annuale", "Trimestrale"], horizontal=True, key="dich_lpp_tipo")
        st.download_button("Scarica la dichiarazione LPP GastroSocial (PDF)", data=lambda: dc.lpp_gastro_pdf(az, anno, tipo == "Trimestrale"),
                           file_name=f"Dichiarazione LPP GastroSocial {anno} - {nome}.pdf", mime="application/pdf", key=f"d_lpp_{az_id}_{anno}_{tipo}")
    else:
        st.info("La cassa pensione di questa azienda non è GastroSocial.")
        _info_assicuratore("Cassa pensione (LPP)", cassa, [("Piano", az.get("lpp_piano_nome")), ("Link", az.get("lpp_link"))])


def render_if() -> None:
    r = _scelta("Dichiarazione imposta alla fonte", "dich_if")
    if not r:
        return
    az_id, az, anno, nome = r
    st.download_button("Scarica la dichiarazione imposta alla fonte (PDF, divisa per mesi)", data=lambda: dc.ifonte_pdf(az, anno),
                       file_name=f"Dichiarazione imposta alla fonte {anno} - {nome}.pdf", mime="application/pdf", key=f"d_if_{az_id}_{anno}")
    st.link_button("Sito imposta alla fonte (Ticino)", "https://www4.ti.ch/dfe/dc/sportello/calcolatori-dimposta/iaf2024")
