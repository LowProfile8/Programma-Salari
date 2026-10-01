"""modules/dati_dipendente.py — i campi dei dati del dipendente, usati sia nella scheda del dipendente
sia in «Crea contratto» (così le due pagine raccolgono sempre le stesse informazioni).

Ordine: prima i dati personali, poi indirizzo e contatti, permesso, rapporto di lavoro, ultimo impiego in
Svizzera, coniuge (solo se coniugato), genitori e dati bancari.

Ogni campo ha una chiave `<prefisso>_<campo>` in session_state. Il prefisso viene da `core.nav.prefisso`
e cambia a ogni visita della pagina: i campi ripartono sempre dai dati salvati.
"""

import copy
import datetime as dt

import streamlit as st

from core import db
from core.paesi import NAZIONALITA
from core.util import a_data, da_data

MIN_DATA = dt.date(1900, 1, 1)
MAX_DATA = dt.date(2100, 12, 31)

STATI_CIVILI = ["Celibe/Nubile", "Coniugato/a", "Unione domestica registrata", "Divorziato/a", "Vedovo/a"]
STATO_CONIUGATO = "Coniugato/a"
PERMESSO_ALTRO = "Altro"
PERMESSI = [
    "Cittadino svizzero", "Permesso C", "Permesso B", "Permesso G (frontaliere)", "Permesso L",
    "Notifica 90 giorni", PERMESSO_ALTRO,
]

TESTI = ["nome", "cognome", "numero_avs", "via", "npa", "localita", "email", "telefono", "ultimo_datore",
         "iban", "banca_nome", "banca_sede"]
DATE = ["data_nascita", "data_entrata_svizzera", "scadenza_permesso", "ultimo_lavoro_data"]
CON_TESTI = ["nome", "cognome", "luogo_nascita", "numero_avs", "via", "npa", "localita"]
CON_SINO = ["assegni", "lavora", "salario_maggiore"]
GENITORI = {"padre": "Padre", "madre": "Madre"}


def _k(p: str, nome: str) -> str:
    return f"{p}_{nome}"


# ── stato iniziale ────────────────────────────────────────────────────────────
def init_stato(p: str, d: dict) -> None:
    """Riempie i campi con i dati salvati `d` (dizionario vuoto per un dipendente nuovo)."""
    s = st.session_state
    for n in TESTI:
        s.setdefault(_k(p, n), d.get(n) or "")
    for n in DATE:
        s.setdefault(_k(p, n), a_data(d.get(n)))
    s.setdefault(_k(p, "nazionalita"), d.get("nazionalita") or None)
    s.setdefault(_k(p, "stato_civile"), d.get("stato_civile") or None)
    s.setdefault(_k(p, "funzione"), d.get("funzione") or "")
    s.setdefault(_k(p, "data_assunzione"), a_data(d.get("data_assunzione")))
    # permesso: se non è fra quelli in elenco compare sotto «Altro», nel campo di testo
    permesso = d.get("permesso") or ""
    if permesso in PERMESSI:
        s.setdefault(_k(p, "permesso"), permesso)
        s.setdefault(_k(p, "permesso_altro"), "")
    elif permesso:
        s.setdefault(_k(p, "permesso"), PERMESSO_ALTRO)
        s.setdefault(_k(p, "permesso_altro"), permesso)
    else:
        s.setdefault(_k(p, "permesso"), None)
        s.setdefault(_k(p, "permesso_altro"), "")
    con = d.get("coniuge") or {}
    for n in CON_TESTI:
        s.setdefault(_k(p, f"con_{n}"), con.get(n) or "")
    s.setdefault(_k(p, "con_data_nascita"), a_data(con.get("data_nascita")))
    for n in CON_SINO + ["lavora_dove"]:
        s.setdefault(_k(p, f"con_{n}"), con.get(n) or None)
    for rel in GENITORI:
        gen = d.get(rel) or {}
        s.setdefault(_k(p, f"{rel}_nome"), gen.get("nome") or "")
        s.setdefault(_k(p, f"{rel}_cognome"), gen.get("cognome") or "")
        s.setdefault(_k(p, f"{rel}_data_nascita"), a_data(gen.get("data_nascita")))


# ── campi ─────────────────────────────────────────────────────────────────────
def _data(etichetta: str, p: str, nome: str, massimo: dt.date = MAX_DATA) -> None:
    st.date_input(etichetta, value=None, format="DD/MM/YYYY", min_value=MIN_DATA, max_value=massimo, key=_k(p, nome))


def _si_no(etichetta: str, p: str, nome: str, opzioni=("Sì", "No")) -> None:
    st.radio(etichetta, list(opzioni), index=None, horizontal=True, key=_k(p, nome))


def render(p: str, con_rapporto: bool = True) -> None:
    g = lambda n: st.session_state.get(_k(p, n))  # noqa: E731
    oggi = dt.date.today()

    st.markdown("##### Dati personali")
    a, b = st.columns(2)
    a.text_input("Nome", key=_k(p, "nome"))
    b.text_input("Cognome", key=_k(p, "cognome"))
    a, b = st.columns(2)
    with a:
        _data("Data di nascita", p, "data_nascita", oggi)
    with b:
        st.selectbox("Nazionalità", NAZIONALITA, index=None, accept_new_options=True,
                     placeholder="Scegli o scrivi", key=_k(p, "nazionalita"))
    a, b = st.columns(2)
    a.text_input("Numero AVS", key=_k(p, "numero_avs"), placeholder="756.XXXX.XXXX.XX")
    with b:
        st.selectbox("Stato civile", STATI_CIVILI, index=None, placeholder="Scegli", key=_k(p, "stato_civile"))

    st.markdown("##### Indirizzo e contatti")
    st.text_input("Via e numero", key=_k(p, "via"))
    a, b = st.columns([1, 2])
    a.text_input("NPA", key=_k(p, "npa"))
    b.text_input("Località", key=_k(p, "localita"))
    a, b = st.columns(2)
    a.text_input("E-mail", key=_k(p, "email"))
    b.text_input("Telefono", key=_k(p, "telefono"))

    st.markdown("##### Permesso di soggiorno")
    st.selectbox("Permesso", PERMESSI, index=None, placeholder="Scegli", key=_k(p, "permesso"))
    if g("permesso") == PERMESSO_ALTRO:
        st.text_input("Specifica il permesso", key=_k(p, "permesso_altro"))
    a, b = st.columns(2)
    with a:
        _data("Data di entrata in Svizzera", p, "data_entrata_svizzera")
    with b:
        _data("Scadenza del permesso", p, "scadenza_permesso")

    if con_rapporto:
        st.markdown("##### Rapporto di lavoro")
        a, b = st.columns(2)
        a.text_input("Funzione", key=_k(p, "funzione"))
        with b:
            _data("Data di assunzione", p, "data_assunzione")

    st.markdown("##### Ultimo impiego in Svizzera")
    a, b = st.columns(2)
    with a:
        _data("Ultimo giorno di lavoro", p, "ultimo_lavoro_data")
    b.text_input("Ragione sociale dell'ultimo datore di lavoro", key=_k(p, "ultimo_datore"))

    if g("stato_civile") == STATO_CONIUGATO:
        st.markdown("##### Coniuge")
        a, b = st.columns(2)
        a.text_input("Nome", key=_k(p, "con_nome"))
        b.text_input("Cognome", key=_k(p, "con_cognome"))
        a, b = st.columns(2)
        with a:
            _data("Data di nascita", p, "con_data_nascita", oggi)
        b.text_input("Luogo di nascita", key=_k(p, "con_luogo_nascita"))
        st.text_input("Numero AVS", key=_k(p, "con_numero_avs"), placeholder="756.XXXX.XXXX.XX")
        st.text_input("Indirizzo di residenza (via e numero)", key=_k(p, "con_via"))
        a, b = st.columns([1, 2])
        a.text_input("CAP", key=_k(p, "con_npa"))
        b.text_input("Comune", key=_k(p, "con_localita"))
        _si_no("Il coniuge percepisce assegni familiari per i figli?", p, "con_assegni")
        _si_no("Il coniuge lavora?", p, "con_lavora")
        if g("con_lavora") == "Sì":
            _si_no("Dove lavora?", p, "con_lavora_dove", ("Svizzera", "Estero"))
            _si_no("Percepisce un salario maggiore di quello del dipendente?", p, "con_salario_maggiore")

    st.markdown("##### Genitori")
    for rel, etichetta in GENITORI.items():
        st.markdown(f"**{etichetta}**")
        a, b, c = st.columns([1, 1, 1])
        a.text_input("Nome", key=_k(p, f"{rel}_nome"))
        b.text_input("Cognome", key=_k(p, f"{rel}_cognome"))
        with c:
            _data("Data di nascita", p, f"{rel}_data_nascita", oggi)

    st.markdown("##### Dati bancari")
    st.text_input("IBAN", key=_k(p, "iban"))
    a, b = st.columns(2)
    a.text_input("Nome della banca", key=_k(p, "banca_nome"))
    b.text_input("Sede della banca", key=_k(p, "banca_sede"))


# ── raccolta dei dati ─────────────────────────────────────────────────────────
def raccogli(p: str, con_rapporto: bool = True) -> dict:
    """Legge i campi e restituisce il dizionario da salvare nell'archivio. I campi nascosti
    (coniuge se non coniugato, dettagli del lavoro del coniuge se non lavora) vengono svuotati."""
    g = lambda n: st.session_state.get(_k(p, n))  # noqa: E731
    d = {n: (g(n) or "").strip() for n in TESTI}
    d.update({n: da_data(g(n)) for n in DATE})
    d["nazionalita"] = (g("nazionalita") or "").strip()
    d["stato_civile"] = g("stato_civile") or ""
    permesso = g("permesso") or ""
    if permesso == PERMESSO_ALTRO:
        permesso = (g("permesso_altro") or "").strip() or PERMESSO_ALTRO
    d["permesso"] = permesso
    if con_rapporto:
        d["funzione"] = (g("funzione") or "").strip()
        d["data_assunzione"] = da_data(g("data_assunzione"))

    if d["stato_civile"] == STATO_CONIUGATO:
        con = {n: (g(f"con_{n}") or "").strip() for n in CON_TESTI}
        con["data_nascita"] = da_data(g("con_data_nascita"))
        con.update({n: g(f"con_{n}") or "" for n in CON_SINO})
        con["lavora_dove"] = g("con_lavora_dove") or ""
        if con["lavora"] != "Sì":
            con["lavora_dove"] = con["salario_maggiore"] = ""
    else:
        con = copy.deepcopy(db.CAMPI_CONIUGE)
    d["coniuge"] = con
    for rel in GENITORI:
        d[rel] = {"nome": (g(f"{rel}_nome") or "").strip(), "cognome": (g(f"{rel}_cognome") or "").strip(),
                  "data_nascita": da_data(g(f"{rel}_data_nascita"))}
    return d
