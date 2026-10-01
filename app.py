"""app.py — punto d'ingresso. Avvio locale:  streamlit run app.py

Viste (st.session_state["vista"]):
    home          tre tasti: Archivio (grande), Crea contratto, Crea busta paga
    archivio      elenco aziende clienti
    azienda_info  informazioni aziendali
    dipendenti    dipendenti di un'azienda
    dipendente    scheda dipendente
    contratto     crea contratto
    busta_paga    crea busta paga
"""

import streamlit as st

from core import db
from core.config import NOME_STUDIO, TITOLO_PAGINA
from core.nav import vai
from core.uscita import richiedi_navigazione
from core.stile import applica_stile
from modules import archivio, busta_paga, contratto, ferie, home, info_azienda, scheda_dipendente

VISTE = {
    "home": home.render,
    "archivio": archivio.pagina_elenco,
    "azienda_info": info_azienda.pagina_info_azienda,
    "dipendenti": archivio.pagina_dipendenti,
    "dipendente": scheda_dipendente.pagina_dipendente,
    "contratto": contratto.render,
    "busta_paga": busta_paga.render,
    "ferie": ferie.render,
}
# A quale voce del menu laterale appartiene ogni vista
VOCE_MENU = {
    "home": "home", "archivio": "archivio", "azienda_info": "archivio", "dipendenti": "archivio",
    "dipendente": "archivio", "contratto": "contratto", "busta_paga": "busta_paga",
    "ferie": "ferie",
}


def _accesso_consentito() -> bool:
    """Schermata di accesso a schermo intero. La password sta nei secrets di Streamlit
    (APP_PASSWORD). Se manca, per lo sviluppo locale vale 'Athena': su Streamlit Cloud
    imposta SEMPRE APP_PASSWORD nei Secrets."""
    if st.session_state.get("_autenticato"):
        return True
    try:
        password_attesa = str(st.secrets["APP_PASSWORD"])
    except Exception:
        password_attesa = "Athena"

    st.markdown("<span class='accesso-marcatore'></span>", unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.3, 1])
    with centro:
        st.markdown("<p class='accesso-titolo'>Password</p>", unsafe_allow_html=True)
        col_campo, col_tasto = st.columns([4, 1], gap="small", vertical_alignment="bottom")
        with col_campo:
            codice = st.text_input("Password", key="campo_password", type="password", label_visibility="collapsed")
        with col_tasto:
            st.button("→", key="invia_password")
        if codice and codice != password_attesa:
            st.markdown("<p class='accesso-errore'>Codice non corretto.</p>", unsafe_allow_html=True)
    if codice and codice == password_attesa:
        st.session_state["_autenticato"] = True
        st.session_state.pop("campo_password", None)
        st.rerun()
    return False


def _voce_menu(etichetta: str, vista: str) -> None:
    attiva = VOCE_MENU.get(st.session_state.get("vista", "home")) == vista
    chiave = "side_attivo" if attiva else f"side_{vista}"
    with st.container(key=chiave):
        if st.button(etichetta, key=f"menu_{vista}", width="stretch"):
            richiedi_navigazione(vista)


def _barra_laterale() -> None:
    with st.sidebar:
        st.markdown(f"### {NOME_STUDIO}")
        st.divider()
        _voce_menu("Home", "home")
        st.write("")
        _voce_menu("Archivio", "archivio")
        _voce_menu("Crea contratto", "contratto")
        _voce_menu("Crea busta paga", "busta_paga")
        _voce_menu("Tabelle ferie e festività", "ferie")
        st.divider()
        st.caption("● Archivio permanente (Supabase)" if db.usa_supabase() else "● ATTENZIONE: archivio locale, si azzera")


def main() -> None:
    st.set_page_config(page_title=TITOLO_PAGINA, layout="centered", initial_sidebar_state="collapsed")
    applica_stile()
    if not _accesso_consentito():
        return
    _barra_laterale()
    vista = st.session_state.get("vista", "home")
    if vista not in VISTE:
        vai("home")
        return
    VISTE[vista]()


if __name__ == "__main__":
    main()
