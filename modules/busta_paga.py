"""modules/busta_paga.py — Crea busta paga (segnaposto: verrà sviluppata nel passo successivo)."""

import streamlit as st

from core.config import NOME_STUDIO
from core.nav import tasto_indietro
from core.stile import intestazione


def render() -> None:
    intestazione(NOME_STUDIO, "Crea busta paga")
    tasto_indietro("← Home", "home")
    st.markdown("# Nuova busta paga")
    st.info(
        "Sezione in costruzione. Il flusso previsto: scegli l'azienda, scegli il dipendente, inserisci il mese "
        "e le ore/variabili; le aliquote e i dati fissi arrivano dall'archivio."
    )
