"""modules/scheda_pubblica.py — pagina per il DIPENDENTE: apre il link ricevuto (…/?scheda=CODICE) e compila la scheda anagrafica.

Non richiede la password del programma e non mostra nient'altro. Il codice del link è lungo e casuale; dopo l'invio il link
non è più utilizzabile. I dati arrivano nelle notifiche dello studio, che li importa nel profilo con un clic.
"""

import streamlit as st

from core import db
from core.nav import nuova_entrata, prefisso
from core.stile import applica_stile
from modules import dati_dipendente as dd


def render(token: str) -> None:
    applica_stile()
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], [data-testid='stHeader']"
                "{display:none !important}</style>", unsafe_allow_html=True)
    if st.session_state.get("_scheda_inviata") == token:
        st.markdown("# Scheda anagrafica")
        st.success("Grazie! I tuoi dati sono stati inviati. Puoi chiudere questa pagina.")
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
        st.markdown("# Scheda anagrafica")
        st.success("Grazie, la scheda è già stata inviata. Non devi fare altro.")
        return

    azienda = db.get_azienda(scheda["azienda_id"]) or {}
    dip = db.get_dipendente(scheda["azienda_id"], scheda["dipendente_id"]) or {}
    st.markdown("# Scheda anagrafica")
    st.write(f"Compila i tuoi dati per **{db.nome_azienda(azienda)}**. I campi con * sono obbligatori; "
             "genitori, dati bancari e ultimo impiego sono facoltativi. Controlla tutto prima di inviare.")
    if st.session_state.get("_pub_token") != token:
        nuova_entrata("dip")
        st.session_state["_pub_token"] = token
    p = prefisso("dip", "pubblica")
    # il dipendente parte da un modulo con solo nome e cognome già noti (nient'altro dell'archivio viene mostrato)
    dd.init_stato(p, {"nome": dip.get("nome", ""), "cognome": dip.get("cognome", "")})
    dd.render(p, con_rapporto=False, completo=True, coniuge=True, richiesti=True)
    dati = dd.raccogli(p, con_rapporto=False, completo=True)
    st.write("")
    if st.button("Invia i miei dati", type="primary", key="pub_invia"):
        mancanti = dd.campi_mancanti(p)
        if mancanti:
            st.error("Compila i campi obbligatori: " + ", ".join(mancanti) + ".")
            return
        vuoti = {k: v for k, v in dati.items() if v not in ("", None, {}, [])}
        try:
            ok = db.salva_scheda_ricevuta(token, vuoti)
        except OSError:
            st.error("Il servizio non è raggiungibile in questo momento: riprova tra qualche minuto.")
            return
        if ok:
            st.session_state["_scheda_inviata"] = token
            st.rerun()
        else:
            st.error("Non è stato possibile inviare i dati: il link non è più valido.")
