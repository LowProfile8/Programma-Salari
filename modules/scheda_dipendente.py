"""modules/scheda_dipendente.py — scheda del dipendente.

Dati (campi condivisi con «Crea contratto»), contratti, buste paga (in arrivo), allegati e, in fondo,
i tasti «Licenzia dipendente» (arancione) ed «Elimina dipendente» (rosso).
Uscendo con modifiche non salvate compare l'avviso «Vuoi salvare il dipendente?».
"""

import datetime as dt

from core.util import oggi

import streamlit as st

from core import anagrafica, db, info_dipendente, lettera, uscita
from core.config import APP_URL_PREDEFINITO, NOME_STUDIO
from core.contratti.calcolo import NOMI_TIPO as _NOMI_TIPO
from core.nav import nuova_entrata, prefisso, tasto_home, vai
from core.stile import intestazione
from core.util import da_data, data_it, uguali
from modules import dati_dipendente as dd


def _k(p: str, nome: str) -> str:
    return f"{p}_{nome}"


def _dimensione(byte: int) -> str:
    if byte < 1024:
        return f"{byte} B"
    if byte < 1024 ** 2:
        return f"{byte / 1024:.0f} KB"
    return f"{byte / 1024 ** 2:.1f} MB"


CAMPI_CHE_CAMBIANO_IL_CONTRATTO = ("stato_civile", "nazionalita", "permesso", "data_nascita", "sesso", "n_figli", "figli_a_carico",
                                   "coniuge", "data_entrata_svizzera")


def _cambiati(vecchio: dict, nuovo: dict) -> list[str]:
    return [c for c in CAMPI_CHE_CAMBIANO_IL_CONTRATTO if c in nuovo and not uguali({c: nuovo[c]}, vecchio)]


@st.dialog("Dati del dipendente modificati")
def _dialogo_nuovo_contratto(az_id: str, dip_id: str) -> None:
    dip = db.get_dipendente(az_id, dip_id) or {}
    contratti = [c for c in dip.get("contratti", []) if c.get("form")]
    st.markdown("**Vuoi creare un nuovo contratto con i dati appena modificati?**")
    st.caption("Il contratto esistente non viene toccato. Il nuovo parte dal precedente, con imposta alla fonte, LPP e aliquota "
               "malattia ricalcolati sui nuovi dati.")
    if st.button("Sì, crea un nuovo contratto", type="primary", key="nc_si", width="stretch"):
        ultimo = max(contratti, key=lambda c: c.get("data_inizio") or "")
        st.session_state.pop("_nuovo_contratto", None)
        st.session_state["ct_modifica"] = (az_id, dip_id, ultimo["id"], "copia")
        vai("contratto")
    with st.container(key="sec_nc_no"):
        if st.button("No, non creare nessun contratto", key="nc_no", width="stretch"):
            st.session_state.pop("_nuovo_contratto", None)
            st.rerun()


def _scrivi(az_id: str, dip_id: str, dati: dict) -> str | None:
    """Salva e controlla subito, rileggendo dall'archivio, che sia stato scritto tutto."""
    try:
        db.aggiorna_dipendente(az_id, dip_id, dati)
    except OSError as errore:
        return f"Non sono riuscito a scrivere nell'archivio ({errore})."
    if not uguali(dati, db.get_dipendente(az_id, dip_id)):
        return "Il salvataggio non risulta completo: riprova a premere «Salva dipendente»."
    return None


def _salva_dip(az: dict, k: str, dip: dict, dati: dict) -> None:
    if not dati["nome"] or not dati["cognome"]:
        st.error("Nome e cognome sono obbligatori.")
        return
    cambiati = _cambiati(dip, dati)
    errore = _scrivi(az["id"], k, dati)
    if errore:
        st.error(errore)
        return
    st.session_state["msg_dip"] = "Dipendente salvato."
    if cambiati and any(c.get("form") for c in dip.get("contratti", [])):
        st.session_state["_nuovo_contratto"] = (az["id"], k)
    st.rerun()


# ── allegati ──────────────────────────────────────────────────────────────────
def _differito(dip_id: str, allegato_id: str):
    """Funzione che legge il file da Supabase al momento del clic su «Scarica»."""
    def leggi() -> bytes:
        return db.leggi_allegato(dip_id, allegato_id) or b""
    return leggi


def _sezione_allegati(az_id: str, dip: dict, p: str) -> None:
    dip_id = dip["id"]
    st.markdown("## Allegati")
    n = st.session_state.get(_k(p, "nup"), 0)
    altri = st.file_uploader("Altri allegati (qualsiasi tipo di file)", accept_multiple_files=True,
                             key=_k(p, f"up_altri_{n}"))
    if st.button("Carica gli allegati", key=_k(p, "btn_carica"), disabled=not altri):
        caricati = 0
        for f, tipo in [(x, "altro") for x in (altri or [])]:
            if f is not None:
                db.aggiungi_allegato(az_id, dip_id, f.name, f.getvalue(), tipo)
                caricati += 1
        if caricati:
            st.session_state[_k(p, "nup")] = n + 1
            st.session_state["msg_dip"] = f"Allegati caricati: {caricati}."
            st.rerun()
        else:
            st.warning("Scegli almeno un file da caricare.")

    allegati = dip.get("allegati", [])
    for titolo, tipo in [("Altri allegati", "altro")]:
        gruppo = [a for a in allegati if a.get("tipo") == tipo]
        if not gruppo:
            continue
        st.markdown(f"**{titolo}**")
        for a in gruppo:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1.3, 1.1], vertical_alignment="center")
                c1.markdown(a["nome"])
                c1.caption(f"{_dimensione(a.get('dimensione', 0))} · caricato il {data_it(a.get('data'))}")
                with c2:
                    # il file si scarica da Supabase solo quando si preme «Scarica» (nessun caricamento all'apertura della pagina)
                    st.download_button("Scarica", data=_differito(dip_id, a["id"]), file_name=a["nome"], key=_k(p, f"dl_{a['id']}"))
                with c3:
                    with st.container(key=f"elimina_all_{a['id']}"):
                        if st.button("Elimina", key=_k(p, f"del_{a['id']}")):
                            st.session_state[_k(p, "conf_allegato")] = a["id"]
                            st.rerun()
                if st.session_state.get(_k(p, "conf_allegato")) == a["id"]:
                    st.warning("Eliminare questo allegato? L'operazione non si può annullare.")
                    d1, d2, _ = st.columns([1.2, 1, 2])
                    with d1:
                        with st.container(key=f"elimina_all_si_{a['id']}"):
                            if st.button("Sì, elimina", key=_k(p, f"delsi_{a['id']}")):
                                db.elimina_allegato(az_id, dip_id, a["id"])
                                st.session_state.pop(_k(p, "conf_allegato"), None)
                                st.rerun()
                    with d2:
                        with st.container(key=f"sec_all_no_{a['id']}"):
                            if st.button("Annulla", key=_k(p, f"delno_{a['id']}")):
                                st.session_state.pop(_k(p, "conf_allegato"), None)
                                st.rerun()


# ── licenziamento ed eliminazione ─────────────────────────────────────────────
def _azioni_finali(az_id: str, dip: dict, p: str) -> None:
    dip_id = dip["id"]
    licenziato = dip.get("stato") == "licenziato"
    st.write("")
    c1, c2, _ = st.columns([1.5, 1.5, 2])
    with c1:
        if not licenziato:
            with st.container(key="licenzia_dipendente"):
                if st.button("Licenzia dipendente", key=_k(p, "btn_licenzia")):
                    st.session_state[_k(p, "conf_licenzia")] = True
                    st.session_state.pop(_k(p, "conf_elimina"), None)
                    st.rerun()
        else:
            with st.container(key="sec_riassumi"):
                if st.button("Riassumi dipendente", key=_k(p, "btn_riassumi")):
                    db.riassumi_dipendente(az_id, dip_id)
                    st.session_state["msg_dip"] = "Dipendente di nuovo assunto."
                    st.rerun()
    with c2:
        with st.container(key="elimina_dipendente"):
            if st.button("Elimina dipendente", key=_k(p, "btn_elimina")):
                st.session_state[_k(p, "conf_elimina")] = True
                st.session_state.pop(_k(p, "conf_licenzia"), None)
                st.rerun()

    if st.session_state.get(_k(p, "conf_licenzia")):
        st.warning("Licenziare questo dipendente? Resterà in archivio, in fondo all'elenco, segnato in rosso.")
        oggi_ = oggi()
        tipo_lett = st.selectbox("Tipo di lettera", list(lettera.TIPI_LETTERA), format_func=lettera.TIPI_LETTERA.get,
                                 key=_k(p, "tipo_lettera"))
        data = st.date_input("Ultimo giorno di lavoro (fine del rapporto)", value=oggi_, format="DD/MM/YYYY",
                             min_value=dd.MIN_DATA, max_value=dd.MAX_DATA, key=_k(p, "data_licenz"))
        con_lettera = st.radio("Creare la lettera di licenziamento?", ["Sì", "No"], index=0, horizontal=True, key=_k(p, "con_lettera"))
        data_lett = None
        if con_lettera == "Sì":
            data_lett = st.date_input("Data della lettera", value=oggi_, format="DD/MM/YYYY", min_value=dd.MIN_DATA,
                                      max_value=dd.MAX_DATA, key=_k(p, "data_lettera"))
        d1, d2, _ = st.columns([1.4, 1, 2])
        with d1:
            with st.container(key="licenzia_si"):
                if st.button("Sì, licenzia", key=_k(p, "licenzia_si")):
                    db.licenzia_dipendente(az_id, dip_id, da_data(data))
                    st.session_state.pop(_k(p, "conf_licenzia"), None)
                    msg = "Dipendente licenziato."
                    if con_lettera == "Sì":
                        pdf = lettera.lettera_licenziamento(db.get_azienda(az_id) or {}, db.get_dipendente(az_id, dip_id) or {},
                                                            da_data(data_lett), da_data(data), tipo_lett)
                        nome = f"Lettera_licenziamento_{dip.get('cognome', '')}_{dip.get('nome', '')}_{da_data(data_lett)}.pdf".replace(" ", "_")
                        db.aggiungi_allegato(az_id, dip_id, nome, pdf, "altro")
                        msg += " La lettera di licenziamento è tra gli allegati."
                    st.session_state["msg_dip"] = msg
                    st.rerun()
        with d2:
            with st.container(key="sec_licenzia_no"):
                if st.button("Annulla", key=_k(p, "licenzia_no")):
                    st.session_state.pop(_k(p, "conf_licenzia"), None)
                    st.rerun()
    if st.session_state.get(_k(p, "conf_elimina")):
        st.warning("Eliminare definitivamente questo dipendente, con tutti i suoi allegati? "
                   "L'operazione non si può annullare.")
        d1, d2, _ = st.columns([1.4, 1, 2])
        with d1:
            with st.container(key="elimina_dipendente_si"):
                if st.button("Sì, elimina", key=_k(p, "elimina_si")):
                    db.elimina_dipendente(az_id, dip_id)
                    vai("dipendenti", dipendente_id=None)
        with d2:
            with st.container(key="sec_elimina_no"):
                if st.button("Annulla", key=_k(p, "elimina_no")):
                    st.session_state.pop(_k(p, "conf_elimina"), None)
                    st.rerun()


# ── scheda anagrafica (carica un file compilato e riempie i dati) ──
def _url_scheda(token: str) -> str:
    try:
        base = str(st.secrets["APP_URL"]).rstrip("/")
    except Exception:
        base = APP_URL_PREDEFINITO.rstrip("/")
    return f"{base}/?scheda={token}"


@st.dialog("Scheda anagrafica", width="large")
def _dialogo_anagrafica(az_id: str, dip_id: str) -> None:
    t_link, t_file = st.tabs(["Link per il dipendente", "Carica un file"])
    with t_link:
        esistente = db.scheda_del_dipendente(dip_id)
        if esistente and esistente[1].get("ricevuta"):
            token, sc = esistente
            st.success(f"Il dipendente ha compilato la scheda il {sc.get('ricevuta_il')}.")
            dati = sc.get("dati") or {}
            st.caption(f"{len(dati)} dati ricevuti. Controllali e importali: sostituiscono quelli attuali dei campi compilati.")
            if st.button("Importa nel profilo", type="primary", key="anag_importa"):
                db.importa_scheda(token)
                st.session_state["msg_dip"] = "Dati della scheda del dipendente importati."
                nuova_entrata("dip")
                st.rerun()
            if st.button("Scarta e crea un nuovo link", key="anag_scarta"):
                db.elimina_scheda(token)
                st.rerun(scope="fragment")
        else:
            st.caption("Crea un link personale e invialo al dipendente: compila lui i suoi dati (senza vedere altro del programma). "
                       "Quando preme «Invia» ricevi una notifica nella Home: controlli i dati e li importi nel profilo con un clic.")
            if esistente:
                st.text_input("Link da inviare al dipendente (selezionalo e copialo)", value=_url_scheda(esistente[0]),
                              key=f"anag_link_{esistente[0]}")
                st.code(_url_scheda(esistente[0]), language=None)
                st.caption("In attesa della compilazione. Perché il dipendente possa aprirlo senza account, l'app deve essere pubblica: "
                           "Streamlit Cloud → la tua app → Settings → Sharing → «This app is public».")
            if st.button("Crea un nuovo link" if esistente else "Crea il link", type="primary", key="anag_crea"):
                db.crea_scheda_link(az_id, dip_id)
                st.rerun(scope="fragment")      # il popup resta aperto e mostra il link
    with t_file:
        st.caption("Carica la scheda compilata (PDF). La lettura automatica riconosce solo alcuni dati: preferisci il link.")
        file = st.file_uploader("File della scheda", type=["pdf", "txt"], key="anag_file")
        if file is not None:
            try:
                dati = anagrafica.leggi_scheda(anagrafica.testo_da_file(file.getvalue(), file.name))
            except Exception as e:
                st.error(f"Non riesco a leggere il file ({type(e).__name__}).")
                return
            if not dati:
                st.warning("Non ho trovato dati riconoscibili: la scheda potrebbe essere una scansione (immagine) o avere un altro formato.")
                return
            st.dataframe({"Campo": list(dati), "Valore": [str(v) for v in dati.values()]}, hide_index=True, width="stretch")
            if st.button("Applica ai dati del dipendente", type="primary", key="anag_applica"):
                attuale = db.get_dipendente(az_id, dip_id) or {}
                db.aggiorna_dipendente(az_id, dip_id, {k: v for k, v in anagrafica.unisci(attuale, dati).items() if k in dati})
                st.session_state["msg_dip"] = "Dati della scheda anagrafica applicati."
                nuova_entrata("dip")
                st.rerun()


# ── pagina ────────────────────────────────────────────────────────────────────
def pagina_dipendente() -> None:
    az = db.get_azienda(st.session_state.get("azienda_id"))
    if az is None:
        vai("archivio")
        return
    dip = db.get_dipendente(az["id"], st.session_state.get("dipendente_id"))
    if dip is None:
        vai("dipendenti")
        return
    k = dip["id"]
    if st.session_state.get("_dip_corrente") != k:
        nuova_entrata("dip")
        st.session_state["_dip_corrente"] = k
    p = prefisso("dip", k)
    dd.init_stato(p, dip)

    intestazione(NOME_STUDIO, db.nome_azienda(az))
    c1, c2, c3, _ = st.columns([0.8, 1.6, 1.5, 1.6])
    dest = uscita.richiesta_pendente()
    with c1:
        if tasto_home("dip"):
            dest = ("home", {})
    with c2:
        if st.button("← Dipendenti", key="nav_dipendenti_dip", type="primary"):
            dest = ("dipendenti", {})
    with c3:
        with st.container(key="viola_anagrafica"):
            if st.button("Scheda anagrafica", key="btn_anagrafica", type="primary"):
                _dialogo_anagrafica(az["id"], k)
    st.markdown(f"# {dip['nome']} {dip['cognome']}")
    if dip.get("stato") == "licenziato":
        st.markdown(f"<span style='color:#B42318;font-weight:700'>Licenziato il {data_it(dip.get('data_licenziamento'))}</span>",
                    unsafe_allow_html=True)

    dd.render(p, con_rapporto=True)
    dati = dd.raccogli(p, con_rapporto=True)

    st.write("")
    with st.container(key="verde_salva_dip"):
        salva = st.button("Salva dipendente", key="salva_dip", type="primary")
    salva = salva or st.session_state.pop("_salva_basso", False)
    if salva:
        _salva_dip(az, k, dip, dati)
    messaggio = st.session_state.pop("msg_dip", None)
    if messaggio:
        st.success(messaggio)
    if st.session_state.get("_nuovo_contratto") == (az["id"], k):
        _dialogo_nuovo_contratto(az["id"], k)

    # ── valori salariali dall'ultimo contratto (calcolati automaticamente) ──
    v = dip.get("valori_salariali") or {}
    st.markdown("## Dati salariali")
    if v:
        orario = v.get("orario")
        st.caption(f"Dall'ultimo contratto, in vigore dal {data_it(v.get('data_contratto'))}"
                   + (" · contratto a ore: importi per ora" if orario else ""))
        m1, m2, m3 = st.columns(3)
        m1.metric("Salario lordo" + (" (all'ora)" if orario else " (al mese)"), f"CHF {v.get('salario_lordo', 0):,.2f}".replace(",", "'"))
        m2.metric("Salario netto" + (" (all'ora)" if orario else " (al mese)"), f"CHF {v.get('salario_netto', 0):,.2f}".replace(",", "'"))
        m3.metric("Imposta alla fonte", f"{v.get('imposta_fonte_pct', 0):g}%")
        m4, m5, _ = st.columns(3)
        m4.metric("Salario lordo annuo determinante", f"CHF {v.get('lordo_annuo', 0):,.2f}".replace(",", "'"))
        m5.metric("Salario AVS annuo", f"CHF {v.get('avs_annuo', 0):,.2f}".replace(",", "'"))
    else:
        st.caption("Compaiono qui dopo aver salvato un contratto per questo dipendente (da «Crea contratto»).")

    st.markdown("## Contratti")
    contratti = dip.get("contratti", [])
    if contratti:
        from core.contratti.calcolo import NOMI_DURATA, NOMI_TIPO
        for c in contratti:
            with st.container(border=True):
                col_info, col_mod, col_del, col_pdf = st.columns([3.2, 1.3, 1.3, 1.3], vertical_alignment="center")
                col_info.markdown(f"**{NOMI_TIPO.get(c.get('tipo'), c.get('tipo', ''))}** · {NOMI_DURATA.get(c.get('durata'), c.get('durata', ''))}")
                col_info.caption(f"{c.get('funzione') or '—'} · dal {data_it(c.get('data_inizio'))}"
                                 + (f" al {data_it(c.get('data_fine'))}" if c.get("data_fine") else ""))
                with col_mod:
                    with st.container(key=f"giallo_modifica_{c['id']}"):
                        if st.button("Modifica", key=_k(p, f"modct_{c['id']}"), disabled="form" not in c, width="stretch"):
                            st.session_state["ct_modifica"] = (az["id"], k, c["id"])
                            vai("contratto")
                with col_del:
                    with st.container(key=f"elimina_contratto_{c['id']}"):
                        if st.button("Elimina", key=_k(p, f"delct_{c['id']}"), width="stretch"):
                            st.session_state[_k(p, "conf_contratto")] = c["id"]
                            st.rerun()
                with col_pdf:
                    with st.container(key=f"azzurro_pdf_{c['id']}"):
                        if c.get("allegato_id"):
                            st.download_button("Scarica PDF", data=_differito(k, c["allegato_id"]), file_name=f"Contratto_{c.get('data_inizio')}.pdf",
                                               mime="application/pdf", key=_k(p, f"ctpdf_{c['id']}"), width="stretch")
                        else:
                            st.button("Scarica PDF", key=_k(p, f"ctpdf_no_{c['id']}"), disabled=True, width="stretch")
                if st.session_state.get(_k(p, "conf_contratto")) == c["id"]:
                    st.warning("Eliminare questo contratto e il suo PDF? L'operazione non si può annullare.")
                    d1, d2, _ = st.columns([1.3, 1.3, 2])
                    with d1:
                        with st.container(key=f"elimina_contratto_si_{c['id']}"):
                            if st.button("Sì, elimina", key=_k(p, f"delctsi_{c['id']}"), width="stretch"):
                                db.elimina_contratto(az["id"], k, c["id"])
                                st.session_state.pop(_k(p, "conf_contratto"), None)
                                st.session_state["msg_dip"] = "Contratto eliminato."
                                st.rerun()
                    with d2:
                        with st.container(key=f"sec_contratto_no_{c['id']}"):
                            if st.button("Annulla", key=_k(p, f"delctno_{c['id']}"), width="stretch"):
                                st.session_state.pop(_k(p, "conf_contratto"), None)
                                st.rerun()
    else:
        st.caption("Nessun contratto registrato.")

    st.markdown("## Buste paga")
    st.info("Le buste paga verranno create in un secondo momento: qui comparirà l'elenco mensile del dipendente.")

    _sezione_allegati(az["id"], dip, p)
    st.write("")
    b1, b2, _ = st.columns([1.2, 1.6, 2.4])
    with b1:
        with st.container(key="verde_salva_dip_basso"):
            if st.button("Salva dipendente", key="salva_dip_basso", type="primary"):
                _salva_dip(az, k, dip, dati)
    with b2:
        with st.container(key="azzurro_info_dip"):
            st.download_button("Scarica info dipendente", data=lambda: info_dipendente.scheda_pdf(db.nome_azienda(az), {**dip, **dati}),
                               file_name=f"Info_{dip.get('cognome', '')}_{dip.get('nome', '')}.pdf".replace(" ", "_"),
                               mime="application/pdf", key="scarica_info_dip")
    _azioni_finali(az["id"], dip, p)

    # ── uscita con modifiche non salvate ──
    da_salvare = {c: v for c, v in dati.items() if c not in ("nome", "cognome") or v}
    uscita.memorizza("dipendente", id=k, azienda_id=az["id"], dati=da_salvare)
    uscita.gestisci("dipendente", dest, sporco=not uguali(dati, dip))
