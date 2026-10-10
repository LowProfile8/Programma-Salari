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


def pagina_hub() -> None:
    """Prima pagina dell'archivio: tre grandi tasti (info aziendali, info dipendenti, buste paga)."""
    intestazione(NOME_STUDIO, "Archivio clienti")
    if tasto_home("archivio"):
        vai("home")
    st.markdown("# Archivio clienti")
    st.caption("Scegli che cosa vuoi consultare.")
    schede = [
        ("hub_info", "Info aziendali", "Dati delle aziende clienti: sede, assicurazioni, aliquote, LPP e IVA.", "archivio_aziende"),
        ("hub_dip", "Info dipendenti", "Tutti i dipendenti divisi per azienda, con ricerca per nome.", "archivio_dipendenti"),
        ("hub_buste", "Buste paga", "Archivio delle buste paga per azienda, dipendente e anno.", "archivio_buste"),
    ]
    cols = st.columns(3, gap="large")
    for col, (chiave, titolo, testo, vista) in zip(cols, schede):
        with col:
            with st.container(key=chiave, border=True):
                st.markdown(f"### {titolo}")
                st.caption(testo)
                if st.button("Apri →", key=f"{chiave}_apri", type="primary", width="stretch"):
                    vai(vista)


def pagina_elenco() -> None:
    intestazione(NOME_STUDIO, "Info aziendali")
    col_home, col_ind, _, col_nuova = st.columns([1.2, 1.6, 2, 1.8])
    with col_home:
        if tasto_home("archivio_aziende"):
            vai("home")
    with col_ind:
        tasto_indietro("← Archivio", "archivio")
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
            col_info, col_a, col_b, col_c = st.columns([2.6, 1.4, 1.7, 1.4], vertical_alignment="center")
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
            with col_c:
                if st.button("Buste paga", key=f"bp_{az['id']}"):
                    st.session_state["arch_bp_az"] = az["id"]
                    vai("archivio_buste")


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
        elif db.esiste_dipendente(azienda_id, nome, cognome):
            st.warning(f"⚠️ Il dipendente {nome.strip()} {cognome.strip()} esiste già in questa azienda.")
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
        tasto_indietro("← Aziende", "archivio_aziende")
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


# ══════════════════════════════════════════════════════════════════════
# Info dipendenti: tutti i dipendenti divisi per azienda
# ══════════════════════════════════════════════════════════════════════
def pagina_archivio_dipendenti() -> None:
    intestazione(NOME_STUDIO, "Info dipendenti")
    col_home, col_ind, _ = st.columns([1.2, 1.6, 4])
    with col_home:
        if tasto_home("archivio_dip"):
            vai("home")
    with col_ind:
        tasto_indietro("← Archivio", "archivio")
    st.markdown("# Dipendenti")
    aziende = db.elenco_aziende()
    tutti = [(az, d) for az in aziende for d in db.ordina_dipendenti(az.get("dipendenti", []))]
    if not tutti:
        st.info("Nessun dipendente in archivio.")
        return
    c1, c2 = st.columns(2)
    nomi = {d["id"]: f"{d['cognome']} {d['nome']} — {db.nome_azienda(az)}" for az, d in tutti}
    with c1:
        scelto = st.selectbox("Scegli un dipendente", sorted(nomi, key=lambda i: nomi[i].casefold()), index=None,
                              format_func=lambda i: nomi[i], placeholder="Cerca o scegli dal menu", key="arch_dip_sel")
    with c2:
        testo = st.text_input("Ricerca per nome", key="arch_dip_testo", placeholder="Scrivi nome, cognome o azienda…")
    if scelto:
        az, d = next((a, x) for a, x in tutti if x["id"] == scelto)
        vai("dipendente", azienda_id=az["id"], dipendente_id=d["id"])
        return
    parole = [p for p in (testo or "").casefold().split() if p]
    mostrati = 0
    for az in aziende:
        elenco = [d for d in db.ordina_dipendenti(az.get("dipendenti", []))
                  if all(p in f"{d['nome']} {d['cognome']} {db.nome_azienda(az)}".casefold() for p in parole)]
        if not elenco:
            continue
        mostrati += len(elenco)
        st.markdown(f"##### {db.nome_azienda(az)}")
        for d in elenco:
            fuori = d.get("stato") == "licenziato"
            with st.container(key=f"{'licenziato' if fuori else 'assunto'}_{d['id']}", border=True):
                col_info, col_apri = st.columns([4, 1.2], vertical_alignment="center")
                with col_info:
                    st.markdown(f"**{d['cognome']} {d['nome']}**")
                    st.caption((f"Licenziato il {data_it(d.get('data_licenziamento'))}" if fuori else d.get("funzione") or "Dati da completare"))
                with col_apri:
                    if st.button("Apri", key=f"adip_{d['id']}"):
                        vai("dipendente", azienda_id=az["id"], dipendente_id=d["id"])
    if not mostrati:
        st.caption("Nessun risultato.")


# ══════════════════════════════════════════════════════════════════════
# Archivio delle buste paga
# ══════════════════════════════════════════════════════════════════════
def pagina_archivio_buste() -> None:
    from modules import buste_ui
    intestazione(NOME_STUDIO, "Archivio buste paga")
    col_home, col_ind, _ = st.columns([1.2, 1.6, 4])
    with col_home:
        if tasto_home("archivio_buste"):
            vai("home")
    with col_ind:
        tasto_indietro("← Archivio", "archivio")
    st.markdown("# Buste paga")
    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Nessuna azienda in archivio.")
        return
    nomi = {a["id"]: db.nome_azienda(a) for a in aziende}
    if "arch_bp_az" in st.session_state and st.session_state["arch_bp_az"] not in nomi:
        st.session_state.pop("arch_bp_az")
    scelta = st.selectbox("Di quale azienda vuoi vedere le buste paga?", list(nomi), index=None, format_func=lambda i: nomi[i],
                          placeholder="Scegli un'azienda", key="arch_bp_az")
    if not scelta:
        return
    az = db.get_azienda(scelta)
    dipendenti = sorted(az.get("dipendenti", []), key=lambda d: (d.get("cognome", "").casefold(), d.get("nome", "").casefold()))
    if not dipendenti:
        st.info("Questa azienda non ha dipendenti.")
        return
    st.caption("Apri un dipendente per vedere le sue buste paga, divise per anno.")
    for d in dipendenti:
        n = len(d.get("buste_paga", []))
        etichetta = f"{d['cognome']} {d['nome']}" + (" (licenziato)" if d.get("stato") == "licenziato" else "") + f" — {n} buste"
        with st.expander(etichetta):
            buste_ui.buste_dipendente(az, d, f"arch_{d['id']}")
