"""modules/archivio.py — Archivio clienti.

Viste (tutte in session_state["vista"]):
    archivio        elenco aziende + «Nuova azienda»
    azienda_info    informazioni aziendali (ragione sociale, sede, n. CHE, aliquote...)
    dipendenti      elenco dipendenti dell'azienda + «Nuovo dipendente»
    dipendente      scheda del dipendente (dati di base + buste paga)
"""

import streamlit as st

from core import db
from core.config import NOME_STUDIO
from core.nav import tasto_home, tasto_indietro, vai
from core.stile import intestazione
from core.util import a_data, da_data, data_it



# ══════════════════════════════════════════════════════════════════════
# Elenco aziende
# ══════════════════════════════════════════════════════════════════════
@st.dialog("Nuova azienda")
def _dialog_nuova_azienda() -> None:
    ragione = st.text_input("Ragione sociale", key="nuova_az_ragione")
    if st.button("Crea azienda", type="primary", key="nuova_az_crea"):
        if not ragione.strip():
            st.error("Inserisci la ragione sociale.")
        else:
            az_id = db.nuova_azienda(ragione)
            st.session_state.pop("nuova_az_ragione", None)
            vai("azienda_info", azienda_id=az_id)


def pagina_elenco() -> None:
    intestazione(NOME_STUDIO, "Archivio clienti")
    col_home, _, col_nuova = st.columns([1.2, 3, 1.8])
    with col_home:
        if tasto_home("archivio"):
            vai("home")
    with col_nuova:
        if st.button("+ Nuova azienda", key="nuova_azienda"):
            _dialog_nuova_azienda()

    st.markdown("# Aziende")
    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Nessuna azienda in archivio. Aggiungi la prima con «+ Nuova azienda».")
        return

    nomi = {a["id"]: db.nome_azienda(a) for a in aziende}
    scelta = st.selectbox("Seleziona l'azienda", list(nomi), index=None, format_func=lambda i: nomi[i],
                          placeholder="Scegli un'azienda", key="archivio_azienda")
    if scelta:
        aziende = [a for a in aziende if a["id"] == scelta]

    for az in aziende:
        with st.container(border=True):
            col_info, col_a, col_b = st.columns([3, 1.5, 1.8], vertical_alignment="center")
            with col_info:
                st.markdown(f"**{db.nome_azienda(az)}**")
                sede = " ".join(x for x in [az.get("sede_npa"), az.get("sede_localita")] if x)
                st.caption(" · ".join(x for x in [sede, az.get("numero_che")] if x) or "Informazioni da completare")
            with col_a:
                if st.button("Info aziendali", key=f"info_{az['id']}"):
                    vai("azienda_info", azienda_id=az["id"])
            with col_b:
                if st.button(f"Dipendenti ({len(az.get('dipendenti', []))})", key=f"dip_{az['id']}"):
                    vai("dipendenti", azienda_id=az["id"])


def _azienda_corrente() -> dict | None:
    az = db.get_azienda(st.session_state.get("azienda_id"))
    if az is None:
        vai("archivio")
    return az


# ══════════════════════════════════════════════════════════════════════
# Elenco dipendenti di un'azienda
# ══════════════════════════════════════════════════════════════════════
@st.dialog("Nuovo dipendente")
def _dialog_nuovo_dipendente(azienda_id: str) -> None:
    nome = st.text_input("Nome", key="nuovo_dip_nome")
    cognome = st.text_input("Cognome", key="nuovo_dip_cognome")
    if st.button("Crea dipendente", type="primary", key="nuovo_dip_crea"):
        if not nome.strip() or not cognome.strip():
            st.error("Inserisci nome e cognome.")
        else:
            dip_id = db.nuovo_dipendente(azienda_id, nome, cognome)
            st.session_state.pop("nuovo_dip_nome", None)
            st.session_state.pop("nuovo_dip_cognome", None)
            vai("dipendente", dipendente_id=dip_id)


def pagina_dipendenti() -> None:
    az = _azienda_corrente()
    if az is None:
        return
    intestazione(NOME_STUDIO, "Dipendenti")
    col_a, col_b, _, col_c = st.columns([1.3, 1.6, 1, 1.9])
    with col_a:
        tasto_indietro("← Archivio", "archivio")
    with col_b:
        if st.button("Info aziendali", key="vai_info"):
            vai("azienda_info", azienda_id=az["id"])
    with col_c:
        if st.button("+ Nuovo dipendente", key="nuovo_dipendente"):
            _dialog_nuovo_dipendente(az["id"])

    st.markdown(f"# {db.nome_azienda(az)}")
    dipendenti = db.ordina_dipendenti(az.get("dipendenti", []))
    assunti = sum(1 for d in dipendenti if d.get("stato") != "licenziato")
    licenziati = len(dipendenti) - assunti
    m1, m2, m3 = st.columns(3)
    m1.metric("Assunti", assunti)
    m2.metric("Licenziati", licenziati)
    m3.metric("Totale", len(dipendenti))
    if not dipendenti:
        st.info("Nessun dipendente in questa azienda. Aggiungine uno con «+ Nuovo dipendente» o dalla pagina «Crea contratto».")
        return
    for d in dipendenti:
        fuori = d.get("stato") == "licenziato"
        with st.container(key=f"licenziato_{d['id']}" if fuori else f"assunto_{d['id']}", border=True):
            col_info, col_apri = st.columns([4, 1.2], vertical_alignment="center")
            with col_info:
                st.markdown(f"**{d['cognome']} {d['nome']}**")
                if fuori:
                    st.caption(f"Licenziato il {data_it(d.get('data_licenziamento'))}"
                               + (f" · {d['funzione']}" if d.get("funzione") else ""))
                else:
                    st.caption(" · ".join(x for x in [d.get("funzione"), f"assunto il {data_it(d.get('data_assunzione'))}" if d.get("data_assunzione") else ""] if x) or "Dati da completare")
            with col_apri:
                if st.button("Apri", key=f"apri_dip_{d['id']}"):
                    vai("dipendente", dipendente_id=d["id"])
