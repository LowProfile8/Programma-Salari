"""modules/ferie.py — Tabelle ferie e festività.

Si sceglie un'azienda dal menu a tendina e compare una tabella: una riga per ogni dipendente, una colonna per
ogni mese. Per ora la tabella è vuota (la struttura): i contenuti li approfondiamo in un secondo momento.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from core import db
from core.config import NOME_STUDIO
from core.nav import tasto_home, vai
from core.stile import intestazione

MESI = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]


def render() -> None:
    intestazione(NOME_STUDIO, "Tabelle ferie e festività")
    if tasto_home("ferie"):
        vai("home")
    st.markdown("# Tabelle ferie e festività")

    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Per vedere la tabella serve almeno un'azienda in archivio.")
        return
    nomi = {a["id"]: db.nome_azienda(a) for a in aziende}
    az_id = st.selectbox("Seleziona l'azienda", list(nomi), index=None, format_func=lambda i: nomi[i],
                         placeholder="Scegli un'azienda", key="ferie_azienda")
    if az_id is None:
        return

    az = db.get_azienda(az_id)
    dipendenti = db.ordina_dipendenti(az.get("dipendenti", []))
    st.markdown(f"## {db.nome_azienda(az)} — {dt.date.today().year}")
    if not dipendenti:
        st.info("Questa azienda non ha ancora dipendenti.")
        return
    righe = [f"{d['cognome']} {d['nome']}" + (" (licenziato)" if d.get("stato") == "licenziato" else "") for d in dipendenti]
    tabella = pd.DataFrame("", index=pd.Index(righe, name="Dipendente"), columns=MESI)
    st.dataframe(tabella, width="stretch")
    st.caption("Tabella in costruzione: i valori di ferie e festività verranno aggiunti in seguito.")
