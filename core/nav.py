"""core/nav.py — navigazione fra le viste (la vista corrente sta in session_state).

Campi che ripartono puliti a ogni ingresso: ogni pagina con un modulo (info azienda, scheda dipendente,
crea contratto) usa chiavi con un «numero di visita» (vedi `prefisso`). Entrando nella pagina il numero
sale e i campi vengono riempiti di nuovo dai dati salvati. Così non restano mai valori «vecchi» o vuoti
dalla visita precedente (era la causa dei menu IVA che tornavano vuoti).
"""

import streamlit as st

# vista -> tipo di modulo che ha chiavi versionate
_TIPI_PAGINA = {"azienda_info": "az", "dipendente": "dip", "contratto": "ct"}


def nuova_entrata(tipo: str) -> None:
    """Segna una nuova visita del modulo `tipo` e butta le chiavi della visita precedente."""
    vecchia = st.session_state.get(f"_ver_{tipo}", 0)
    inizio = f"{tipo}{vecchia}_"
    for chiave in [c for c in st.session_state if isinstance(c, str) and c.startswith(inizio)]:
        try:
            del st.session_state[chiave]
        except KeyError:
            pass
    st.session_state[f"_ver_{tipo}"] = vecchia + 1


def prefisso(tipo: str, oggetto: str) -> str:
    """Prefisso delle chiavi dei campi di un modulo, valido per la visita in corso."""
    return f"{tipo}{st.session_state.get(f'_ver_{tipo}', 0)}_{oggetto}"


def vai(vista: str, **contesto) -> None:
    """Cambia pagina. Con contesto si passano azienda_id / dipendente_id."""
    tipo = _TIPI_PAGINA.get(vista)
    if tipo:
        nuova_entrata(tipo)
    if vista == "contratto":
        st.session_state.pop("ct_sel", None)
    st.session_state.pop("_nav_richiesta", None)
    st.session_state.pop("_uscita_pendente", None)
    st.session_state["vista"] = vista
    for chiave, valore in contesto.items():
        st.session_state[chiave] = valore
    st.rerun()


def tasto_home(chiave: str = "home") -> bool:
    """Tasto «Home» uguale in tutte le pagine (blu con scritta bianca). Restituisce True se premuto."""
    with st.container(key=f"btnhome_{chiave}"):
        return st.button("Home", key=f"nav_home_{chiave}", type="primary")


def tasto_indietro(etichetta: str, vista: str, **contesto) -> None:
    """Tasto azzurro in alto a sinistra."""
    if st.button(etichetta, key=f"indietro_{vista}", type="primary"):
        vai(vista, **contesto)
