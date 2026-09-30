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
from core.nav import tasto_indietro, vai
from core.stile import intestazione
from core.util import a_data, da_data, data_it

STATI_CIVILI = ["", "Celibe/Nubile", "Coniugato/a", "Unione domestica registrata", "Divorziato/a", "Vedovo/a"]
PERMESSI = ["", "Cittadino svizzero", "Permesso C", "Permesso B", "Permesso G (frontaliere)", "Permesso L", "Altro"]


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
        tasto_indietro("← Home", "home")
    with col_nuova:
        if st.button("+ Nuova azienda", key="nuova_azienda"):
            _dialog_nuova_azienda()

    st.markdown("# Aziende")
    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Nessuna azienda in archivio. Aggiungi la prima con «+ Nuova azienda».")
        return

    nomi = {a["id"]: a["ragione_sociale"] for a in aziende}
    scelta = st.selectbox("Seleziona l'azienda", list(nomi), index=None, format_func=lambda i: nomi[i],
                          placeholder="Scegli un'azienda", key="archivio_azienda")
    if scelta:
        aziende = [a for a in aziende if a["id"] == scelta]

    for az in aziende:
        with st.container(border=True):
            col_info, col_a, col_b = st.columns([3, 1.5, 1.8], vertical_alignment="center")
            with col_info:
                st.markdown(f"**{az['ragione_sociale']}**")
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

    st.markdown(f"# {az['ragione_sociale']}")
    dipendenti = sorted(az.get("dipendenti", []), key=lambda d: (d.get("cognome", "").lower(), d.get("nome", "").lower()))
    if not dipendenti:
        st.info("Nessun dipendente in questa azienda. Aggiungine uno con «+ Nuovo dipendente» o dalla pagina «Crea contratto».")
        return
    for d in dipendenti:
        with st.container(border=True):
            col_info, col_apri = st.columns([4, 1.2], vertical_alignment="center")
            with col_info:
                st.markdown(f"**{d['cognome']} {d['nome']}**")
                st.caption(" · ".join(x for x in [d.get("funzione"), f"assunto il {data_it(d.get('data_assunzione'))}" if d.get("data_assunzione") else ""] if x) or "Dati da completare")
            with col_apri:
                if st.button("Apri", key=f"apri_dip_{d['id']}"):
                    vai("dipendente", dipendente_id=d["id"])


# ══════════════════════════════════════════════════════════════════════
# Scheda dipendente
# ══════════════════════════════════════════════════════════════════════
def _indice(opzioni: list[str], valore: str) -> int:
    return opzioni.index(valore) if valore in opzioni else 0


def pagina_dipendente() -> None:
    az = _azienda_corrente()
    if az is None:
        return
    d = db.get_dipendente(az["id"], st.session_state.get("dipendente_id"))
    if d is None:
        vai("dipendenti")
        return
    k = d["id"]
    intestazione(NOME_STUDIO, az["ragione_sociale"])
    tasto_indietro("← Dipendenti", "dipendenti")
    st.markdown(f"# {d['nome']} {d['cognome']}")

    with st.form(f"form_dip_{k}"):
        st.markdown("##### Dati personali")
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome", value=d.get("nome", ""))
        cognome = c2.text_input("Cognome", value=d.get("cognome", ""))
        c3, c4 = st.columns(2)
        nascita = c3.date_input("Data di nascita", value=a_data(d.get("data_nascita")), format="DD/MM/YYYY",
                                min_value=a_data("1930-01-01"), max_value=a_data("2015-12-31"))
        avs = c4.text_input("Numero AVS", value=d.get("numero_avs", ""), placeholder="756.XXXX.XXXX.XX")
        via = st.text_input("Via e numero", value=d.get("via", ""))
        c5, c6 = st.columns([1, 2])
        npa = c5.text_input("NPA", value=d.get("npa", ""))
        localita = c6.text_input("Località", value=d.get("localita", ""))
        c7, c8 = st.columns(2)
        nazionalita = c7.text_input("Nazionalità", value=d.get("nazionalita", ""))
        stato = c8.selectbox("Stato civile", STATI_CIVILI, index=_indice(STATI_CIVILI, d.get("stato_civile", "")))
        permesso = st.selectbox("Permesso di soggiorno / lavoro", PERMESSI, index=_indice(PERMESSI, d.get("permesso", "")))
        iban = st.text_input("IBAN per il pagamento del salario", value=d.get("iban", ""))

        st.markdown("##### Rapporto di lavoro")
        c9, c10 = st.columns(2)
        funzione = c9.text_input("Funzione", value=d.get("funzione", ""))
        assunzione = c10.date_input("Data di assunzione", value=a_data(d.get("data_assunzione")), format="DD/MM/YYYY")
        salva = st.form_submit_button("Salva dipendente", type="primary")

    if salva:
        if not nome.strip() or not cognome.strip():
            st.error("Nome e cognome sono obbligatori.")
        else:
            db.aggiorna_dipendente(az["id"], k, {
                "nome": nome.strip(), "cognome": cognome.strip(), "data_nascita": da_data(nascita),
                "numero_avs": avs, "via": via, "npa": npa, "localita": localita, "nazionalita": nazionalita,
                "stato_civile": stato, "permesso": permesso, "iban": iban, "funzione": funzione,
                "data_assunzione": da_data(assunzione),
            })
            st.success("Dipendente salvato.")

    st.markdown("## Contratti")
    contratti = d.get("contratti", [])
    if contratti:
        for c in contratti:
            st.markdown(f"- **{c.get('funzione', '—')}** · dal {data_it(c.get('data_inizio'))} · {c.get('tipo', '')}")
    else:
        st.caption("Nessun contratto registrato.")

    st.markdown("## Buste paga")
    st.info("Le buste paga verranno create in un secondo momento: qui comparirà l'elenco mensile del dipendente.")

    with st.expander("Elimina dipendente"):
        st.warning("L'operazione non si può annullare.")
        with st.container(key="sec_elimina_dipendente"):
            if st.button("Elimina definitivamente", key=f"elimina_dip_{k}"):
                db.elimina_dipendente(az["id"], k)
                vai("dipendenti", dipendente_id=None)
