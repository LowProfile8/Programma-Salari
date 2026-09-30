"""modules/contratto.py — Crea contratto.

1. Si sceglie l'azienda da un menu a tendina: i dati aziendali vengono letti dall'archivio
   (collegamento diretto, sola lettura: per cambiarli si modificano le Info aziendali).
2. Si inseriscono a mano i dati del dipendente e le condizioni di lavoro.
3. «Salva nell'archivio» crea il dipendente (o lo aggiorna) e registra il contratto.
La generazione del documento (PDF/Word) verrà aggiunta nel passo successivo.
"""

import datetime as dt

import streamlit as st

from core import db
from core.config import NOME_STUDIO
from core.nav import tasto_home, vai
from core.stile import intestazione
from core.util import da_data, nuovo_id
from modules.archivio import PERMESSI, STATI_CIVILI

TIPI_CONTRATTO = ["A tempo indeterminato", "A tempo determinato"]


def _riepilogo_azienda(az: dict) -> None:
    """Dati presi automaticamente dalle Info aziendali."""
    sede = ", ".join(x for x in [az.get("sede_via"), " ".join(y for y in [az.get("sede_npa"), az.get("sede_localita")] if y)] if x)
    with st.container(border=True):
        st.markdown("##### Dati dell'azienda (dall'archivio)")
        c1, c2 = st.columns(2)
        c1.markdown(f"**Ragione sociale**  \n{az['ragione_sociale']}")
        c2.markdown(f"**Numero CHE**  \n{az.get('numero_che') or '—'}")
        c1.markdown(f"**Sede legale**  \n{sede or '—'}")
        c2.markdown(f"**Persona di contatto**  \n{az.get('persona_contatto') or '—'}")
        mancano = [n for n, v in [("numero CHE", az.get("numero_che")), ("sede legale", sede)] if not v]
        if mancano:
            st.warning("Nelle Info aziendali mancano: " + ", ".join(mancano) + ".")
            if st.button("Completa le info aziendali", key="completa_info"):
                vai("azienda_info", azienda_id=az["id"])


def render() -> None:
    intestazione(NOME_STUDIO, "Crea contratto")
    if tasto_home("contratto"):
        vai("home")
    st.markdown("# Nuovo contratto")

    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Per creare un contratto serve almeno un'azienda in archivio.")
        if st.button("Vai all'archivio", key="contratto_vai_archivio"):
            vai("archivio")
        return

    nomi = {a["id"]: a["ragione_sociale"] for a in aziende}
    az_id = st.selectbox(
        "Per quale azienda lavorerà il dipendente?", list(nomi), index=None,
        format_func=lambda i: nomi[i], placeholder="Seleziona un'azienda", key="contratto_azienda",
    )
    if az_id is None:
        return
    az = db.get_azienda(az_id)
    _riepilogo_azienda(az)

    st.markdown("## Dati del dipendente")
    c1, c2 = st.columns(2)
    nome = c1.text_input("Nome", key="ct_nome")
    cognome = c2.text_input("Cognome", key="ct_cognome")
    c3, c4 = st.columns(2)
    nascita = c3.date_input("Data di nascita", value=None, format="DD/MM/YYYY", key="ct_nascita",
                            min_value=dt.date(1930, 1, 1), max_value=dt.date(2015, 12, 31))
    avs = c4.text_input("Numero AVS", key="ct_avs", placeholder="756.XXXX.XXXX.XX")
    via = st.text_input("Via e numero", key="ct_via")
    c5, c6 = st.columns([1, 2])
    npa = c5.text_input("NPA", key="ct_npa")
    localita = c6.text_input("Località", key="ct_localita")
    c7, c8 = st.columns(2)
    nazionalita = c7.text_input("Nazionalità", key="ct_nazionalita")
    stato = c8.selectbox("Stato civile", STATI_CIVILI, key="ct_stato")
    permesso = st.selectbox("Permesso di soggiorno / lavoro", PERMESSI, key="ct_permesso")
    iban = st.text_input("IBAN per il pagamento del salario", key="ct_iban")

    st.markdown("## Condizioni di lavoro")
    funzione = st.text_input("Funzione", key="ct_funzione")
    c9, c10 = st.columns(2)
    tipo = c9.selectbox("Tipo di contratto", TIPI_CONTRATTO, key="ct_tipo")
    inizio = c10.date_input("Data di inizio", value=dt.date.today(), format="DD/MM/YYYY", key="ct_inizio")
    fine = None
    if tipo == TIPI_CONTRATTO[1]:
        fine = st.date_input("Data di fine", value=None, format="DD/MM/YYYY", key="ct_fine")
    c11, c12 = st.columns(2)
    grado = c11.number_input("Grado di occupazione (%)", min_value=0, max_value=100, value=100, step=5, key="ct_grado")
    ore = c12.number_input("Ore settimanali", min_value=0.0, max_value=60.0, value=42.0, step=0.5, key="ct_ore")
    c13, c14 = st.columns(2)
    salario = c13.number_input("Salario lordo mensile (CHF)", min_value=0.0, value=0.0, step=100.0, format="%.2f", key="ct_salario")
    tredicesima = c14.checkbox("13ª mensilità", value=True, key="ct_13")
    c15, c16 = st.columns(2)
    vacanze = c15.number_input("Vacanze (settimane/anno)", min_value=0.0, max_value=10.0, value=4.0, step=0.5, key="ct_vacanze")
    prova = c16.number_input("Periodo di prova (mesi)", min_value=0, max_value=3, value=3, key="ct_prova")
    note = st.text_area("Note / clausole particolari", key="ct_note")

    st.write("")
    col_salva, col_genera = st.columns(2)
    with col_salva:
        salva = st.button("Salva nell'archivio", type="primary", key="ct_salva")
    with col_genera:
        st.button("Genera contratto (in arrivo)", key="ct_genera", disabled=True)

    if salva:
        if not nome.strip() or not cognome.strip():
            st.error("Inserisci almeno nome e cognome del dipendente.")
            return
        if tipo == TIPI_CONTRATTO[1] and fine is None:
            st.error("Per un contratto a tempo determinato serve la data di fine.")
            return
        contratto = {
            "id": nuovo_id(), "tipo": tipo, "funzione": funzione, "data_inizio": da_data(inizio),
            "data_fine": da_data(fine), "grado_occupazione": grado, "ore_settimanali": ore,
            "salario_lordo_mensile": salario, "tredicesima": tredicesima, "vacanze_settimane": vacanze,
            "periodo_prova_mesi": prova, "note": note,
        }
        dati_persona = {
            "data_nascita": da_data(nascita), "numero_avs": avs, "via": via, "npa": npa, "localita": localita,
            "nazionalita": nazionalita, "stato_civile": stato, "permesso": permesso, "iban": iban,
            "funzione": funzione, "data_assunzione": da_data(inizio),
        }
        dip_id = db.nuovo_dipendente(az_id, nome, cognome, dati_persona)
        db.aggiungi_contratto(az_id, dip_id, contratto)
        for chiave in [k for k in st.session_state if k.startswith("ct_")]:
            del st.session_state[chiave]
        st.session_state["contratto_salvato"] = f"{cognome} {nome}"
        vai("dipendente", azienda_id=az_id, dipendente_id=dip_id)
