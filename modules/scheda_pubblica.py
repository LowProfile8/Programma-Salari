"""modules/scheda_pubblica.py — pagina per il DIPENDENTE: apre il link ricevuto (…/?scheda=CODICE) e compila la scheda anagrafica.

Non richiede la password del programma e non mostra nient'altro. Il codice del link è lungo e casuale; dopo l'invio il link
non è più utilizzabile. I dati vengono salvati direttamente nel profilo del dipendente e il link viene eliminato.
"""

import streamlit as st

from core import db
from core.config import NOME_STUDIO
from core.nav import nuova_entrata, prefisso
from core.stile import applica_stile, intestazione
from modules import dati_dipendente as dd


def render(token: str) -> None:
    applica_stile()
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl']{display:none !important}</style>",
                unsafe_allow_html=True)
    intestazione(NOME_STUDIO, "Scheda anagrafica")
    if st.session_state.get("_scheda_inviata") == token:
        st.success("Grazie! I tuoi dati sono stati inviati e salvati. Puoi chiudere questa pagina.")
        return
    try:
        scheda = db.get_scheda(token)
    except OSError:
        st.warning("Il servizio non è raggiungibile in questo momento. Riprova tra qualche minuto.")
        return
    if not scheda:
        st.error("Questo link non è valido o non è più attivo. Chiedi un nuovo link.")
        return
    if scheda.get("ricevuta"):
        st.success("Grazie, la scheda è già stata inviata. Non devi fare altro.")
        return
    if st.session_state.get("_scheda_inviata") == token:
        st.success("Grazie! I tuoi dati sono stati inviati. Puoi chiudere questa pagina.")
        return

    azienda = db.get_azienda(scheda["azienda_id"]) or {}
    dip = db.get_dipendente(scheda["azienda_id"], scheda["dipendente_id"]) or {}
    st.markdown("# Scheda anagrafica")
    st.write(f"Compila i tuoi dati per **{db.nome_azienda(azienda)}**. Controlla tutto prima di inviare.")
    if st.session_state.get("_pub_token") != token:
        nuova_entrata("dip")
        st.session_state["_pub_token"] = token
    p = prefisso("dip", "pubblica")
    # il dipendente parte da un modulo con solo nome e cognome già noti (nient'altro dell'archivio viene mostrato)
    dd.init_stato(p, {"nome": dip.get("nome", ""), "cognome": dip.get("cognome", "")})
    dd.render(p, con_rapporto=False, completo=True, coniuge=True)
    dati = dd.raccogli(p, con_rapporto=False, completo=True)
    st.write("")
    if st.button("Invia i miei dati", type="primary", key="pub_invia"):
        if not dati["nome"] or not dati["cognome"]:
            st.error("Nome e cognome sono obbligatori.")
        else:
            vuoti = {k: v for k, v in dati.items() if v not in ("", None, {}, [])}
            try:
                ok = db.registra_scheda_nel_profilo(token, vuoti)
            except OSError:
                ok = False
                st.error("Il servizio non è raggiungibile in questo momento: riprova tra qualche minuto.")
            if ok:
                st.session_state["_scheda_inviata"] = token
                st.rerun()
            elif not st.session_state.get("_scheda_errore_rete"):
                pass
            else:
                st.error("Non è stato possibile inviare i dati: il link non è più valido.")
