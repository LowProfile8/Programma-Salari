"""core/nav.py — navigazione fra le viste (stesso schema del programma delle dichiarazioni:
la vista corrente sta in session_state)."""

import streamlit as st


def vai(vista: str, **contesto) -> None:
    """Cambia pagina. Con contesto si passano azienda_id / dipendente_id."""
    st.session_state["vista"] = vista
    for chiave, valore in contesto.items():
        st.session_state[chiave] = valore
    st.rerun()


def tasto_home(chiave: str = "home") -> bool:
    """Tasto «Home» uguale in tutte le pagine (blu con scritta bianca). Restituisce True se premuto."""
    with st.container(key=f"btnhome_{chiave}"):
        return st.button("Home", key=f"nav_home_{chiave}", type="primary")


def tasto_indietro(etichetta: str, vista: str, **contesto) -> None:
    """Tasto azzurro in alto a sinistra, come «← Home» nel programma di riferimento."""
    if st.button(etichetta, key=f"indietro_{vista}", type="primary"):
        vai(vista, **contesto)
