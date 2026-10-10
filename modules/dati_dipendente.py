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

MIN_DATA = dt.date(dt.date.today().year - 100, 1, 1)      # 100 anni nel passato
MAX_DATA = dt.date(dt.date.today().year + 100, 12, 31)    # 100 anni nel futuro

STATI_CIVILI = ["Celibe/Nubile", "Coniugato/a", "Unione domestica registrata", "Divorziato/a", "Vedovo/a"]
STATO_CONIUGATO = "Coniugato/a"
PERMESSO_ALTRO = "Altro"
PERMESSI = [
    "Cittadino svizzero", "Permesso C", "Permesso B", "Permesso G (frontaliere)", "Permesso L",
    "Notifica 90 giorni", PERMESSO_ALTRO,
]

TESTI = ["nome", "cognome", "numero_avs", "n_figli", "cassa_malati", "via", "npa", "localita", "email", "telefono", "ultimo_datore",
         "iban", "banca_nome", "banca_sede"]
DATE = ["data_nascita", "data_entrata_svizzera", "scadenza_permesso", "ultimo_lavoro_data"]
CON_TESTI = ["nome", "cognome", "luogo_nascita", "numero_avs", "via", "npa", "localita"]
CON_SINO = ["assegni", "lavora", "salario_maggiore"]
GENITORI = {"padre": "Padre", "madre": "Madre"}
MAX_FIGLI = 12
PERMESSO_G = "Permesso G (frontaliere)"


def _k(p: str, nome: str) -> str:
    return f"{p}_{nome}"


RICHIESTI_PUBBLICA = ["nome", "cognome", "data_nascita", "nazionalita", "sesso", "stato_civile", "via", "npa", "localita",
                      "permesso", "data_entrata_svizzera", "scadenza_permesso"]
_RICH: set = set()


def _L(etichetta: str, nome: str) -> str:
    """Etichetta con asterisco se il campo è obbligatorio (scheda anagrafica del dipendente)."""
    return f"{etichetta} *" if nome in _RICH else etichetta


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
    s.setdefault(_k(p, "figli_carico"), d.get("figli_a_carico") or None)
    s.setdefault(_k(p, "sesso"), d.get("sesso") or None)
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
    s.setdefault(_k(p, "rientro"), d.get("rientro") or None)
    figli = d.get("figli") or []
    for i in range(MAX_FIGLI):
        f = figli[i] if i < len(figli) else {}
        s.setdefault(_k(p, f"fig{i}_nome"), f.get("nome") or "")
        s.setdefault(_k(p, f"fig{i}_cognome"), f.get("cognome") or "")
        s.setdefault(_k(p, f"fig{i}_data"), a_data(f.get("data_nascita")))
    for rel in GENITORI:
        gen = d.get(rel) or {}
        s.setdefault(_k(p, f"{rel}_nome"), gen.get("nome") or "")
        s.setdefault(_k(p, f"{rel}_cognome"), gen.get("cognome") or "")
        s.setdefault(_k(p, f"{rel}_data_nascita"), a_data(gen.get("data_nascita")))


# ── campi ─────────────────────────────────────────────────────────────────────
def _data(etichetta: str, p: str, nome: str, massimo: dt.date = MAX_DATA) -> None:
    st.date_input(_L(etichetta, nome), value=None, format="DD/MM/YYYY", min_value=MIN_DATA, max_value=massimo, key=_k(p, nome))


def _si_no(etichetta: str, p: str, nome: str, opzioni=("Sì", "No"), disabled: bool = False) -> None:
    st.radio(etichetta, list(opzioni), index=None, horizontal=True, key=_k(p, nome), disabled=disabled)


def _senza_figli(p: str) -> bool:
    return (st.session_state.get(_k(p, "n_figli")) or "").strip() in ("", "0")


def render(p: str, con_rapporto: bool = True, completo: bool = True, coniuge: bool = True, richiesti: bool = False) -> None:
    global _RICH
    _RICH = set(RICHIESTI_PUBBLICA) if richiesti else set()
    g = lambda n: st.session_state.get(_k(p, n))  # noqa: E731
    oggi = dt.date.today()

    st.markdown("##### Dati personali")
    a, b = st.columns(2)
    a.text_input(_L("Nome", "nome"), key=_k(p, "nome"))
    b.text_input(_L("Cognome", "cognome"), key=_k(p, "cognome"))
    a, b = st.columns(2)
    with a:
        _data("Data di nascita", p, "data_nascita")
    with b:
        st.selectbox(_L("Nazionalità", "nazionalita"), NAZIONALITA, index=None, accept_new_options=True,
                     placeholder="Scegli o scrivi", key=_k(p, "nazionalita"))
    st.radio(_L("Sesso", "sesso"), ["Uomo", "Donna"], index=None, horizontal=True, key=_k(p, "sesso"),
             help="Serve per scegliere l'aliquota malattia corretta (uomo/donna) nei contratti.")
    a, b = st.columns(2)
    a.text_input("Numero AVS", key=_k(p, "numero_avs"), placeholder="756.XXXX.XXXX.XX")
    with b:
        st.selectbox(_L("Stato civile", "stato_civile"), STATI_CIVILI, index=None, placeholder="Scegli", key=_k(p, "stato_civile"))
    a, b = st.columns(2)
    a.text_input("Numero di figli", key=_k(p, "n_figli"))
    b.text_input("Cassa malati", key=_k(p, "cassa_malati"))
    if (g("n_figli") or "").strip() not in ("", "0"):
        st.radio("I figli sono a carico (stesso nucleo familiare)?", ["Sì", "No"], index=None, horizontal=True,
                 key=_k(p, "figli_carico"))
        if completo:
            try:
                n_f = max(0, min(MAX_FIGLI, int((g("n_figli") or "0").strip())))
            except ValueError:
                n_f = 0
            for i in range(n_f):
                a, b, c = st.columns([1.3, 1.3, 1])
                a.text_input(f"Figlio {i + 1}: nome", key=_k(p, f"fig{i}_nome"))
                b.text_input(f"Figlio {i + 1}: cognome", key=_k(p, f"fig{i}_cognome"))
                with c:
                    _data(f"Figlio {i + 1}: data di nascita", p, f"fig{i}_data")

    st.markdown("##### Indirizzo e contatti")
    st.text_input(_L("Via e numero", "via"), key=_k(p, "via"))
    a, b = st.columns([1, 2])
    a.text_input(_L("NPA", "npa"), key=_k(p, "npa"))
    b.text_input(_L("Località", "localita"), key=_k(p, "localita"))
    a, b = st.columns(2)
    a.text_input("E-mail", key=_k(p, "email"))
    b.text_input("Telefono", key=_k(p, "telefono"))

    st.markdown("##### Permesso di soggiorno")
    st.selectbox(_L("Permesso", "permesso"), PERMESSI, index=None, placeholder="Scegli", key=_k(p, "permesso"))
    if g("permesso") == PERMESSO_ALTRO:
        st.text_input("Specifica il permesso", key=_k(p, "permesso_altro"))
    if g("permesso") == PERMESSO_G:
        st.selectbox("Rientro al domicilio in Italia", ["Giornaliero", "Settimanale"], index=None, placeholder="Scegli",
                     key=_k(p, "rientro"), help="Serve per scegliere le tabelle dell'imposta alla fonte (Direttiva punto 2.1).")
    a, b = st.columns(2)
    with a:
        _data("Data di entrata in Svizzera (per i frontalieri: primo impiego in Svizzera)" if g("permesso") == PERMESSO_G
              else "Data di entrata in Svizzera", p, "data_entrata_svizzera")
    if completo:
        with b:
            _data("Scadenza del permesso", p, "scadenza_permesso")

    if con_rapporto:
        st.markdown("##### Rapporto di lavoro")
        a, b = st.columns(2)
        a.text_input("Funzione", key=_k(p, "funzione"))
        with b:
            _data("Data di assunzione", p, "data_assunzione")

    if completo:
        st.markdown("##### Ultimo impiego in Svizzera")
        a, b = st.columns(2)
        with a:
            _data("Ultimo giorno di lavoro", p, "ultimo_lavoro_data")
        b.text_input("Ragione sociale dell'ultimo datore di lavoro", key=_k(p, "ultimo_datore"))

    if coniuge and g("stato_civile") == STATO_CONIUGATO:
        st.markdown("##### Coniuge")
        a, b = st.columns(2)
        a.text_input("Nome", key=_k(p, "con_nome"))
        b.text_input("Cognome", key=_k(p, "con_cognome"))
        a, b = st.columns(2)
        with a:
            _data("Data di nascita", p, "con_data_nascita")
        b.text_input("Luogo di nascita", key=_k(p, "con_luogo_nascita"))
        st.text_input("Numero AVS", key=_k(p, "con_numero_avs"), placeholder="756.XXXX.XXXX.XX")
        st.text_input("Indirizzo di residenza (via e numero)", key=_k(p, "con_via"))
        a, b = st.columns([1, 2])
        a.text_input("CAP", key=_k(p, "con_npa"))
        b.text_input("Comune", key=_k(p, "con_localita"))
        _si_no("Il coniuge percepisce assegni familiari per i figli?", p, "con_assegni", disabled=_senza_figli(p))
        _si_no("Il coniuge lavora?", p, "con_lavora")
        if g("con_lavora") == "Sì":
            _si_no("Dove lavora?", p, "con_lavora_dove", ("Svizzera", "Estero"))
            _si_no("Percepisce un salario maggiore di quello del dipendente?", p, "con_salario_maggiore")

    if completo:
        st.markdown("##### Genitori")
        for rel, etichetta in GENITORI.items():
            st.markdown(f"**{etichetta}**")
            a, b, c = st.columns([1, 1, 1])
            a.text_input("Nome", key=_k(p, f"{rel}_nome"))
            b.text_input("Cognome", key=_k(p, f"{rel}_cognome"))
            with c:
                _data("Data di nascita", p, f"{rel}_data_nascita")

        st.markdown("##### Dati bancari")
        st.text_input("IBAN", key=_k(p, "iban"))
        a, b = st.columns(2)
        a.text_input("Nome della banca", key=_k(p, "banca_nome"))
        b.text_input("Sede della banca", key=_k(p, "banca_sede"))


# ── raccolta dei dati ─────────────────────────────────────────────────────────
def raccogli(p: str, con_rapporto: bool = True, completo: bool = True) -> dict:
    """Legge i campi e restituisce il dizionario da salvare nell'archivio. I campi nascosti
    (coniuge se non coniugato, dettagli del lavoro del coniuge se non lavora) vengono svuotati."""
    g = lambda n: st.session_state.get(_k(p, n))  # noqa: E731
    d = {n: (g(n) or "").strip() for n in TESTI}
    d.update({n: da_data(g(n)) for n in DATE})
    d["nazionalita"] = (g("nazionalita") or "").strip()
    d["stato_civile"] = g("stato_civile") or ""
    d["sesso"] = g("sesso") or ""
    d["figli_a_carico"] = (g("figli_carico") or "") if (g("n_figli") or "").strip() not in ("", "0") else ""
    permesso = g("permesso") or ""
    if permesso == PERMESSO_ALTRO:
        permesso = (g("permesso_altro") or "").strip() or PERMESSO_ALTRO
    d["permesso"] = permesso
    d["rientro"] = (g("rientro") or "") if permesso == PERMESSO_G else ""
    if con_rapporto:
        d["funzione"] = (g("funzione") or "").strip()
        d["data_assunzione"] = da_data(g("data_assunzione"))

    if not completo:
        con = None            # nel contratto i dati del coniuge non si toccano
    elif d["stato_civile"] == STATO_CONIUGATO:
        con = {n: (g(f"con_{n}") or "").strip() for n in CON_TESTI}
        con["data_nascita"] = da_data(g("con_data_nascita"))
        con.update({n: g(f"con_{n}") or "" for n in CON_SINO})
        con["lavora_dove"] = g("con_lavora_dove") or ""
        if d["n_figli"] in ("", "0"):
            con["assegni"] = ""
        if con["lavora"] != "Sì":
            con["lavora_dove"] = con["salario_maggiore"] = ""
    else:
        con = copy.deepcopy(db.CAMPI_CONIUGE)
    if con is not None:
        d["coniuge"] = con
    if completo:
        try:
            n_f = max(0, min(MAX_FIGLI, int((d["n_figli"] or "0").strip())))
        except ValueError:
            n_f = 0
        d["figli"] = [{"nome": (g(f"fig{i}_nome") or "").strip(), "cognome": (g(f"fig{i}_cognome") or "").strip(),
                       "data_nascita": da_data(g(f"fig{i}_data"))} for i in range(n_f)]
        for rel in GENITORI:
            d[rel] = {"nome": (g(f"{rel}_nome") or "").strip(), "cognome": (g(f"{rel}_cognome") or "").strip(),
                      "data_nascita": da_data(g(f"{rel}_data_nascita"))}
    else:   # nel contratto questi dati non si chiedono e non si toccano nell'archivio
        for chiave in ("scadenza_permesso", "ultimo_lavoro_data", "ultimo_datore", "iban",
                       "banca_nome", "banca_sede"):
            d.pop(chiave, None)
    return d


def campi_mancanti(p: str) -> list[str]:
    """Etichette dei campi obbligatori ancora vuoti (scheda anagrafica compilata dal dipendente)."""
    g = lambda n: st.session_state.get(_k(p, n))  # noqa: E731
    nomi = {"nome": "Nome", "cognome": "Cognome", "data_nascita": "Data di nascita", "nazionalita": "Nazionalità", "sesso": "Sesso",
            "stato_civile": "Stato civile", "via": "Via e numero", "npa": "NPA", "localita": "Località", "permesso": "Permesso",
            "data_entrata_svizzera": "Data di entrata in Svizzera", "scadenza_permesso": "Scadenza del permesso"}
    mancanti = []
    for n in RICHIESTI_PUBBLICA:
        v = g(n)
        if n == "scadenza_permesso" and g("permesso") in (None, "", "Cittadino svizzero", "Permesso C"):
            continue
        if n == "data_entrata_svizzera" and g("permesso") in (None, "", "Cittadino svizzero"):
            continue
        if v in (None, "") or (isinstance(v, str) and not v.strip()):
            mancanti.append(nomi[n])
    return mancanti
