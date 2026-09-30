"""modules/info_azienda.py — pagina «Info aziendali».

Niente st.form: i campi cambiano a seconda delle risposte (multivaluta, revisione, IVA, ramo...),
quindi ogni campo ha una chiave `<id azienda>_<nome campo>` in session_state, riempita dai dati
salvati la prima volta che si apre la pagina. «Salva informazioni» (in fondo) o uscire con i tasti
in alto scrivono tutto nell'archivio.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from core import db, lpp, registro
from core.config import (
    CONTRATTI_COLLETTIVI, CRITERI_IVA, FORME_GIURIDICHE, NOME_STUDIO, RAMI, RAMO_ALTRO, RAMO_RISTORAZIONE, VALUTE,
)
from core.nav import vai
from core.stile import intestazione
from core.util import a_data, da_data

PDF_UNO_BASIS = Path(__file__).resolve().parent.parent / "assets" / "lpp" / "uno_basis_2026.pdf"

TESTI = [
    "ragione_sociale", "ramo_altro", "numero_che", "sede_via", "sede_npa", "sede_localita", "persona_contatto",
    "telefono", "email", "iban", "cassa_avs", "cassa_lpp", "assicuratore_infortuni",
    "assicuratore_malattia", "lpp_piano_nome", "note",
]
SELEZIONI = [
    "forma_giuridica", "valuta_2", "valuta_3", "contratto_collettivo", "revisione_tipo", "iva_metodo",
    "iva_criterio", "iva_periodicita",
]
SI_NO = ["multivaluta", "revisione", "iva_soggetta"]


def _k(az_id: str, nome: str) -> str:
    return f"{az_id}_{nome}"


def _init_stato(k: str, az: dict) -> None:
    for n in TESTI:
        st.session_state.setdefault(_k(k, n), az.get(n) or "")
    for n in SELEZIONI + SI_NO:
        st.session_state.setdefault(_k(k, n), az.get(n) or None)
    st.session_state.setdefault(_k(k, "opting_in_data"), a_data(az.get("opting_in_data")))
    st.session_state.setdefault(_k(k, "lpp_manuale"), bool(az.get("lpp_manuale")))
    # ramo: se è uno di quelli in elenco lo selezioniamo; se è scritto a mano compare sotto «Altro»
    ramo = az.get("ramo") or ""
    if ramo in RAMI:
        st.session_state.setdefault(_k(k, "ramo"), ramo)
    elif ramo:
        st.session_state.setdefault(_k(k, "ramo"), RAMO_ALTRO)
        st.session_state[_k(k, "ramo_altro")] = st.session_state[_k(k, "ramo_altro")] or ramo
    else:
        st.session_state.setdefault(_k(k, "ramo"), None)


def _chf(importo: float) -> str:
    return f"{importo:,.0f}".replace(",", "'")


def _ramo_corrente(k: str) -> str:
    ramo = st.session_state.get(_k(k, "ramo"))
    if ramo == RAMO_ALTRO:
        return (st.session_state.get(_k(k, "ramo_altro")) or "").strip() or RAMO_ALTRO
    return ramo or ""


# ── tabelle (data_editor) ─────────────────────────────────────────────────────
def _df(righe: list[dict], colonne: list[str], numeriche: list[str], minimo_righe: int = 0) -> pd.DataFrame:
    righe = list(righe)
    while len(righe) < minimo_righe:
        righe.append({})
    df = pd.DataFrame(righe, columns=colonne)
    for c in colonne:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64") if c in numeriche else df[c].astype("object")
    return df


def _vuoto(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip())


def _righe(df: pd.DataFrame, testi: list[str], numeri: list[str]) -> list[dict]:
    uscita = []
    for r in df.to_dict("records"):
        riga = {c: ("" if _vuoto(r.get(c)) else str(r[c]).strip()) for c in testi}
        riga.update({c: (None if _vuoto(r.get(c)) else float(r[c])) for c in numeri})
        if any(riga[c] for c in testi) or any(riga[c] is not None for c in numeri):
            uscita.append(riga)
    return uscita


# ── ricerca del numero CHE nel registro ───────────────────────────────────────
def _cb_cerca_che(k: str) -> None:
    esito = registro.cerca_che(st.session_state.get(_k(k, "ragione_sociale"), ""))
    st.session_state[_k(k, "esito_che")] = esito
    if esito["esito"] == "ok":
        st.session_state[_k(k, "numero_che")] = esito["che"]


def _cb_usa_che(k: str) -> None:
    esito = st.session_state.get(_k(k, "esito_che")) or {}
    indice = st.session_state.get(_k(k, "scelta_che"))
    candidati = esito.get("candidati", [])
    if indice is not None and 0 <= indice < len(candidati):
        c = candidati[indice]
        st.session_state[_k(k, "numero_che")] = c["che"]
        st.session_state[_k(k, "esito_che")] = {"esito": "ok", "messaggio": f"Inserito: {c['nome']} — {c['che']}."}


def _blocco_che(k: str) -> None:
    st.text_input("Numero CHE (IDI)", key=_k(k, "numero_che"), placeholder="CHE-123.456.789")
    st.markdown(f"[Apri il registro di commercio del Ticino]({registro.link_ricerca()})")
    with st.container(key=f"sec_cerca_che_{k}"):
        st.button("Cerca in Zefix e inserisci il numero CHE", key=_k(k, "btn_che"),
                  on_click=_cb_cerca_che, args=(k,))
    esito = st.session_state.get(_k(k, "esito_che"))
    if not esito:
        return
    if esito["esito"] == "ok":
        st.success(esito["messaggio"])
    elif esito["esito"] == "scelta":
        st.info(esito["messaggio"])
        cand = esito["candidati"]
        st.selectbox("Aziende trovate", list(range(len(cand))), key=_k(k, "scelta_che"),
                     format_func=lambda i: f"{cand[i]['nome']} — {cand[i]['sede']} — {cand[i]['che']}")
        st.button("Usa questo numero", key=_k(k, "btn_usa_che"), on_click=_cb_usa_che, args=(k,))
    else:
        st.warning(esito["messaggio"])


# ── LPP ───────────────────────────────────────────────────────────────────────
def _cb_lpp_alterna(k: str) -> None:
    st.session_state[_k(k, "lpp_manuale")] = not st.session_state.get(_k(k, "lpp_manuale"), False)


def _blocco_lpp(k: str) -> None:
    ramo = _ramo_corrente(k)
    if ramo != RAMO_RISTORAZIONE:
        if ramo:
            st.caption("LPP: per questo ramo non è tra le trattenute della tabella. Si inserirà a mano nel contratto.")
        else:
            st.caption("LPP: scegli il ramo aziendale. Per ristorazione / alberghiero si propone il Piano 1 Basis; "
                       "per gli altri rami l'LPP si inserirà a mano nel contratto.")
        return
    if not st.session_state.get(_k(k, "lpp_manuale")):
        st.info("**LPP: Piano 1 Basis (GastroSocial)**, proposto per il ramo ristorazione / alberghiero. "
                "Le cifre qui sotto vengono usate nel contratto e nel calcolo della busta paga.")
        st.caption(
            "Valori mensili 2026. Trattenuta al dipendente: 7% del salario assicurato (25–64/65 anni) e 0.5% "
            "(18–24 anni, percentuale ricavata dalla tabella). Salario assicurato = salario lordo − "
            f"CHF {_chf(lpp.DEDUZIONE_COORDINAMENTO_MENSILE)}, minimo CHF {_chf(lpp.SALARIO_ASSICURATO_MINIMO)}, "
            f"massimo CHF {_chf(lpp.SALARIO_ASSICURATO_MASSIMO)}. Sotto CHF {_chf(lpp.SOGLIA_ACCESSO_MENSILE)} "
            "al mese non si è assicurati."
        )
        with st.container(key=f"sec_lpp_{k}"):
            c1, c2, _ = st.columns([1.3, 1.5, 1])
            with c1:
                st.button("Modifica piano LPP", key=_k(k, "btn_lpp_modifica"), on_click=_cb_lpp_alterna, args=(k,))
            with c2:
                if PDF_UNO_BASIS.exists():
                    st.download_button("Scarica la tabella (PDF)", data=PDF_UNO_BASIS.read_bytes(),
                                       file_name="Uno_Basis_2026.pdf", mime="application/pdf",
                                       key=_k(k, "dl_uno_basis"))
    else:
        st.warning("**LPP: piano inserito a mano** (non si usa il Piano 1 Basis).")
        st.text_input("Nome del piano LPP", key=_k(k, "lpp_piano_nome"))
        st.caption("Le formule di calcolo di questo piano verranno aggiunte in seguito.")
        with st.container(key=f"sec_lpp_{k}"):
            st.button("Torna al Piano 1 Basis", key=_k(k, "btn_lpp_torna"), on_click=_cb_lpp_alterna, args=(k,))


# ── salvataggio ───────────────────────────────────────────────────────────────
def _salva(k: str, tabelle: dict) -> str | None:
    """Scrive tutto nell'archivio. Restituisce un messaggio d'errore oppure None se è andato bene."""
    def g(nome):
        return st.session_state.get(_k(k, nome))

    if not (g("ragione_sociale") or "").strip():
        return "La ragione sociale non può essere vuota."

    m = {n: (g(n) or "").strip() for n in TESTI}
    m.update({n: g(n) or "" for n in SELEZIONI + SI_NO})
    m.pop("ramo_altro")
    m["ramo"] = _ramo_corrente(k)

    soci = _righe(tabelle["soci"], ["socio"], ["quota"])
    if sum(s["quota"] or 0 for s in soci) > 100.001:
        return "La somma delle quote dei soci supera il 100%."
    m["soci"] = soci

    if m["multivaluta"] != "Sì":
        m["valuta_2"] = m["valuta_3"] = ""
    if m["revisione"] != "Sì":
        m["revisione_tipo"] = ""
    m["opting_in_data"] = da_data(g("opting_in_data")) if m["revisione"] == "Sì" else None
    if m["iva_soggetta"] != "Sì":
        m["iva_metodo"] = m["iva_criterio"] = m["iva_periodicita"] = ""
    saldo = _righe(tabelle["saldo"], ["descrizione"], ["aliquota"]) if "saldo" in tabelle else []
    m["iva_aliquote_saldo"] = saldo if (m["iva_soggetta"] == "Sì" and m["iva_metodo"] == "A saldo") else []

    m["aliquote"] = [
        {"voce": r["voce"], "dipendente": r["dipendente"] or 0.0, "datore": r["datore"] or 0.0}
        for r in _righe(tabelle["aliquote"], ["voce"], ["dipendente", "datore"]) if r["voce"]
    ]
    m["accessi"] = _righe(tabelle["accessi"], ["descrizione", "link", "utente", "password", "note"], [])

    ristorazione = m["ramo"] == RAMO_RISTORAZIONE
    manuale = bool(g("lpp_manuale")) and ristorazione
    m["lpp_manuale"] = manuale
    m["lpp_modalita"] = "" if not m["ramo"] else ("piano1_basis" if (ristorazione and not manuale) else "manuale")
    if not manuale:
        m["lpp_piano_nome"] = ""

    db.aggiorna_azienda(k, m)
    return None


def _pulisci_editor(k: str) -> None:
    """Dopo il salvataggio le tabelle ripartono dai dati appena salvati."""
    for nome in ("ed_soci", "ed_aliquote", "ed_saldo", "ed_accessi"):
        try:
            del st.session_state[_k(k, nome)]
        except KeyError:
            pass


# ── pagina ────────────────────────────────────────────────────────────────────
def pagina_info_azienda() -> None:
    az = db.get_azienda(st.session_state.get("azienda_id"))
    if az is None:
        vai("archivio")
        return
    k = az["id"]
    _init_stato(k, az)
    g = lambda nome: st.session_state.get(_k(k, nome))  # noqa: E731

    intestazione(NOME_STUDIO, "Informazioni aziendali")
    c1, c2, c3, _ = st.columns([0.8, 1.3, 1.6, 2.0])
    dest = None
    with c1:
        with st.container(key="scuro_home"):
            if st.button("Home", key="nav_home", type="primary"):
                dest = ("home", {})
    with c2:
        if st.button("← Aziende", key="nav_aziende", type="primary"):
            dest = ("archivio", {})
    with c3:
        if st.button("Dipendenti →", key="nav_dipendenti", type="primary"):
            dest = ("dipendenti", {"azienda_id": k})
    st.caption("Uscendo con questi tasti le modifiche vengono salvate automaticamente.")

    messaggio = st.session_state.pop("msg_info", None)
    if messaggio:
        st.success(messaggio)
    st.markdown(f"# {az['ragione_sociale']}")

    # ── Dati societari ──
    st.markdown("##### Dati societari")
    st.text_input("Ragione sociale", key=_k(k, "ragione_sociale"))
    a, b = st.columns(2)
    with a:
        st.selectbox("Forma giuridica", FORME_GIURIDICHE, index=None, accept_new_options=True,
                     placeholder="Scegli o scrivi", key=_k(k, "forma_giuridica"))
    with b:
        st.selectbox("Ramo aziendale", RAMI + [RAMO_ALTRO], index=None, placeholder="Scegli il ramo",
                     key=_k(k, "ramo"))
    if g("ramo") == RAMO_ALTRO:
        st.text_input("Specifica il ramo aziendale", key=_k(k, "ramo_altro"))
    _blocco_che(k)

    st.radio("L'attività è multivaluta?", ["Sì", "No"], index=None, horizontal=True, key=_k(k, "multivaluta"))
    if g("multivaluta") == "Sì":
        a, b = st.columns(2)
        with a:
            st.selectbox("Seconda valuta di riferimento", VALUTE, index=None, accept_new_options=True,
                         placeholder="Es. EUR", key=_k(k, "valuta_2"))
        with b:
            st.selectbox("Terza valuta (facoltativa)", VALUTE, index=None, accept_new_options=True,
                         placeholder="Es. USD", key=_k(k, "valuta_3"))

    st.markdown("**Soci e quote**")
    soci = st.data_editor(
        _df(az.get("soci", []), ["socio", "quota"], ["quota"]), num_rows="dynamic", hide_index=True,
        width="stretch", key=_k(k, "ed_soci"),
        column_config={
            "socio": st.column_config.TextColumn("Socio", required=True),
            "quota": st.column_config.NumberColumn("Quota (%)", min_value=0.0, max_value=100.0, format="%.2f"),
        },
    )
    totale = sum(r["quota"] or 0 for r in _righe(soci, ["socio"], ["quota"]))
    if totale:
        (st.caption if abs(totale - 100) < 0.001 else st.warning)(f"Totale quote: {totale:g}%")

    # ── Sede legale ──
    st.markdown("##### Sede legale")
    st.text_input("Via e numero", key=_k(k, "sede_via"))
    a, b = st.columns([1, 2])
    a.text_input("NPA", key=_k(k, "sede_npa"))
    b.text_input("Località", key=_k(k, "sede_localita"))

    # ── Contatti ──
    st.markdown("##### Contatti")
    st.text_input("Persona di contatto", key=_k(k, "persona_contatto"))
    a, b = st.columns(2)
    a.text_input("Telefono", key=_k(k, "telefono"))
    b.text_input("E-mail", key=_k(k, "email"))
    st.text_input("IBAN dell'azienda", key=_k(k, "iban"))

    # ── Assicurazioni sociali e contratto ──
    st.markdown("##### Assicurazioni sociali")
    a, b = st.columns(2)
    a.text_input("Cassa di compensazione AVS", key=_k(k, "cassa_avs"))
    b.text_input("Cassa pensione (LPP)", key=_k(k, "cassa_lpp"),
                 placeholder="GastroSocial" if _ramo_corrente(k) == RAMO_RISTORAZIONE else "")
    a, b = st.columns(2)
    a.text_input("Assicurazione infortuni (LAINF)", key=_k(k, "assicuratore_infortuni"))
    b.text_input("Assicurazione malattia (indennità giornaliera)", key=_k(k, "assicuratore_malattia"))
    st.selectbox("Contratto seguito", CONTRATTI_COLLETTIVI, index=None, placeholder="Scegli il contratto",
                 key=_k(k, "contratto_collettivo"))

    # ── Aliquote e trattenute ──
    st.markdown("##### Aliquote e trattenute")
    st.caption("Percentuali sul salario lordo. Puoi modificare i valori e aggiungere o togliere righe. Verifica le aliquote ogni anno.")
    aliquote = st.data_editor(
        _df(az.get("aliquote", db.ALIQUOTE_DEFAULT), ["voce", "dipendente", "datore"], ["dipendente", "datore"]),
        num_rows="dynamic", hide_index=True, width="stretch", key=_k(k, "ed_aliquote"),
        column_config={
            "voce": st.column_config.TextColumn("Voce", required=True),
            "dipendente": st.column_config.NumberColumn("A carico dipendente (%)", min_value=0.0, max_value=100.0, format="%.3f"),
            "datore": st.column_config.NumberColumn("A carico datore (%)", min_value=0.0, max_value=100.0, format="%.3f"),
        },
    )
    _blocco_lpp(k)

    # ── Revisione ──
    st.markdown("##### Revisione")
    st.radio("La società è soggetta a revisione?", ["Sì", "No"], index=None, horizontal=True, key=_k(k, "revisione"))
    if g("revisione") == "Sì":
        st.radio("Tipo di revisione", ["Limitata", "Generale"], index=None, horizontal=True, key=_k(k, "revisione_tipo"))
        st.date_input("Data dell'opting in", value=None, format="DD/MM/YYYY", key=_k(k, "opting_in_data"))

    # ── IVA ──
    st.markdown("##### IVA")
    st.radio("Contribuente IVA?", ["Sì", "No"], index=None, horizontal=True, key=_k(k, "iva_soggetta"))
    tabella_saldo = None
    if g("iva_soggetta") == "Sì":
        a, b = st.columns(2)
        with a:
            st.selectbox("Metodo", ["Effettivo", "A saldo"], index=None, placeholder="Scegli", key=_k(k, "iva_metodo"))
        with b:
            st.selectbox("Frequenza del rendiconto", ["Trimestrale", "Semestrale", "Annuale"], index=None,
                         placeholder="Scegli", key=_k(k, "iva_periodicita"))
        st.selectbox("Metodo di rendiconto", CRITERI_IVA, index=None, placeholder="Scegli", key=_k(k, "iva_criterio"))
        if g("iva_metodo") == "A saldo":
            st.markdown("**Aliquote a saldo utilizzate**")
            tabella_saldo = st.data_editor(
                _df(az.get("iva_aliquote_saldo", []), ["descrizione", "aliquota"], ["aliquota"], minimo_righe=3),
                num_rows="dynamic", hide_index=True, width="stretch", key=_k(k, "ed_saldo"),
                column_config={
                    "descrizione": st.column_config.TextColumn("Descrizione / attività"),
                    "aliquota": st.column_config.NumberColumn("Aliquota a saldo (%)", min_value=0.0, max_value=100.0, format="%.2f"),
                },
            )

    # ── Note ──
    st.markdown("##### Note")
    st.text_area("Note", key=_k(k, "note"), label_visibility="collapsed")

    # ── Accessi e password ──
    st.markdown("##### Accessi e password")
    accessi = st.data_editor(
        _df(az.get("accessi", []), ["descrizione", "link", "utente", "password", "note"], []),
        num_rows="dynamic", hide_index=True, width="stretch", key=_k(k, "ed_accessi"),
        column_config={
            "descrizione": st.column_config.TextColumn("Descrizione"),
            "link": st.column_config.TextColumn("Link"),
            "utente": st.column_config.TextColumn("Nome utente"),
            "password": st.column_config.TextColumn("Password"),
            "note": st.column_config.TextColumn("Note"),
        },
    )
    st.caption("Attenzione: le password sono salvate come testo semplice e visibili a schermo. "
               "Prima di usare dati reali le cifreremo.")

    st.write("")
    salva = st.button("Salva informazioni", key="salva_basso", type="primary")

    # ── Azioni ──
    tabelle = {"soci": soci, "aliquote": aliquote, "accessi": accessi}
    if tabella_saldo is not None:
        tabelle["saldo"] = tabella_saldo

    if salva or dest:
        errore = _salva(k, tabelle)
        if errore:
            st.error(errore)
        elif dest:
            vai(dest[0], **dest[1])
        else:
            _pulisci_editor(k)
            st.session_state["msg_info"] = "Informazioni salvate."
            st.rerun()

    st.write("")
    with st.expander("Elimina azienda"):
        st.warning("Verranno eliminati anche tutti i dipendenti di questa azienda. L'operazione non si può annullare.")
        with st.container(key="sec_elimina_azienda"):
            if st.button("Elimina definitivamente", key=f"elimina_az_{k}"):
                db.elimina_azienda(k)
                vai("archivio", azienda_id=None)
