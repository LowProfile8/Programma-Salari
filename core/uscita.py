"""core/uscita.py — avviso «Vuoi salvare?» quando si lascia una pagina con modifiche non salvate.

Le pagine protette (info azienda, scheda dipendente) a fine pagina:
  1. salvano una «istantanea» di ciò che c'è nei campi (`memorizza`);
  2. se è stata richiesta un'uscita (tasti in alto o barra laterale) chiamano `gestisci`:
     senza modifiche si esce subito, con modifiche compare il pop-up
     «Salva ed esci» / «Continua senza salvare» / «Annulla».
I tasti della barra laterale non possono uscire subito dalla pagina protetta: usano `richiedi_navigazione`.
"""

import streamlit as st

from core import db
from core.nav import vai

PAGINE_PROTETTE = {"azienda_info": "azienda", "dipendente": "dipendente"}
_NOME = {"azienda": "l'azienda", "dipendente": "il dipendente"}


def richiedi_navigazione(vista: str, **contesto) -> None:
    """Per i tasti che portano altrove (barra laterale): da una pagina protetta la pagina stessa decide."""
    if st.session_state.get("vista") in PAGINE_PROTETTE:
        st.session_state["_nav_richiesta"] = (vista, contesto)
    else:
        vai(vista, **contesto)


def richiesta_pendente():
    return st.session_state.pop("_nav_richiesta", None)


def memorizza(tipo: str, **istantanea) -> None:
    st.session_state[f"_snap_{tipo}"] = istantanea


def _salva_istantanea(tipo: str) -> None:
    snap = st.session_state.get(f"_snap_{tipo}") or {}
    if tipo == "azienda":
        db.aggiorna_azienda(snap["id"], snap["dati"])
    else:
        db.aggiorna_dipendente(snap["azienda_id"], snap["id"], snap["dati"])


def _chiudi() -> None:
    """Il pop-up è stato chiuso con la «X»: equivale ad «Annulla»."""
    st.session_state.pop("_uscita_pendente", None)


def _decoratore_dialogo():
    try:
        return st.dialog("Modifiche non salvate", width="large", on_dismiss=_chiudi)
    except TypeError:  # versioni di Streamlit senza on_dismiss
        return st.dialog("Modifiche non salvate", width="large")


@_decoratore_dialogo()
def _dialogo(tipo: str, vista: str, contesto: dict) -> None:
    st.markdown(f"**Vuoi salvare {_NOME[tipo]}?**")
    st.caption("Ci sono modifiche che non hai ancora salvato.")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Salva ed esci", type="primary", key=f"dlg_salva_{tipo}", width="stretch"):
            _salva_istantanea(tipo)
            vai(vista, **contesto)
    with c2:
        with st.container(key=f"sec_dlg_senza_{tipo}"):
            if st.button("Continua senza salvare", key=f"dlg_senza_{tipo}", width="stretch"):
                vai(vista, **contesto)
    with c3:
        with st.container(key=f"sec_dlg_annulla_{tipo}"):
            if st.button("Annulla", key=f"dlg_annulla_{tipo}", width="stretch"):
                _chiudi()
                st.rerun()


def gestisci(tipo: str, destinazione, sporco: bool) -> None:
    """destinazione: (vista, contesto) oppure None. Va chiamata a fine pagina.
    Senza modifiche si esce subito; con modifiche la richiesta resta «in attesa» e il pop-up viene
    mostrato finché non si risponde."""
    if destinazione:
        vista, contesto = destinazione
        if not sporco:
            vai(vista, **contesto)
            return
        st.session_state["_uscita_pendente"] = {"tipo": tipo, "vista": vista, "contesto": contesto}
    pendente = st.session_state.get("_uscita_pendente")
    if pendente and pendente["tipo"] == tipo:
        _dialogo(tipo, pendente["vista"], pendente["contesto"])
