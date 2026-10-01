"""modules/scheda_dipendente.py — scheda del dipendente.

Dati (campi condivisi con «Crea contratto»), contratti, buste paga (in arrivo), allegati e, in fondo,
i tasti «Licenzia dipendente» (arancione) ed «Elimina dipendente» (rosso).
Uscendo con modifiche non salvate compare l'avviso «Vuoi salvare il dipendente?».
"""

import datetime as dt

import streamlit as st

from core import db, uscita
from core.config import NOME_STUDIO
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


def _scrivi(az_id: str, dip_id: str, dati: dict) -> str | None:
    """Salva e controlla subito, rileggendo dall'archivio, che sia stato scritto tutto."""
    try:
        db.aggiorna_dipendente(az_id, dip_id, dati)
    except OSError as errore:
        return f"Non sono riuscito a scrivere nell'archivio ({errore})."
    if not uguali(dati, db.get_dipendente(az_id, dip_id)):
        return "Il salvataggio non risulta completo: riprova a premere «Salva dipendente»."
    return None


# ── allegati ──────────────────────────────────────────────────────────────────
def _sezione_allegati(az_id: str, dip: dict, p: str) -> None:
    dip_id = dip["id"]
    st.markdown("## Allegati")
    n = st.session_state.get(_k(p, "nup"), 0)
    contratto = st.file_uploader("Contratto di lavoro", key=_k(p, f"up_contratto_{n}"))
    altri = st.file_uploader("Altri allegati (qualsiasi tipo di file)", accept_multiple_files=True,
                             key=_k(p, f"up_altri_{n}"))
    if st.button("Carica gli allegati", key=_k(p, "btn_carica")):
        caricati = 0
        for f, tipo in [(contratto, "contratto")] + [(x, "altro") for x in (altri or [])]:
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
    for titolo, tipo in [("Contratto di lavoro", "contratto"), ("Altri allegati", "altro")]:
        gruppo = [a for a in allegati if a.get("tipo") == tipo]
        if not gruppo:
            continue
        st.markdown(f"**{titolo}**")
        for a in gruppo:
            contenuto = db.leggi_allegato(dip_id, a["id"])
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1.3, 1.1], vertical_alignment="center")
                c1.markdown(a["nome"])
                c1.caption(f"{_dimensione(a.get('dimensione', 0))} · caricato il {data_it(a.get('data'))}")
                with c2:
                    if contenuto is not None:
                        st.download_button("Scarica", data=contenuto, file_name=a["nome"], key=_k(p, f"dl_{a['id']}"))
                    else:
                        st.caption("file non trovato")
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
        data = st.date_input("Data di fine rapporto", value=dt.date.today(), format="DD/MM/YYYY",
                             min_value=dd.MIN_DATA, max_value=dd.MAX_DATA, key=_k(p, "data_licenz"))
        d1, d2, _ = st.columns([1.4, 1, 2])
        with d1:
            with st.container(key="licenzia_si"):
                if st.button("Sì, licenzia", key=_k(p, "licenzia_si")):
                    db.licenzia_dipendente(az_id, dip_id, da_data(data))
                    st.session_state.pop(_k(p, "conf_licenzia"), None)
                    st.session_state["msg_dip"] = "Dipendente licenziato."
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
    c1, c2, _ = st.columns([0.8, 1.6, 3])
    dest = uscita.richiesta_pendente()
    with c1:
        if tasto_home("dip"):
            dest = ("home", {})
    with c2:
        if st.button("← Dipendenti", key="nav_dipendenti_dip", type="primary"):
            dest = ("dipendenti", {})
    st.markdown(f"# {dip['nome']} {dip['cognome']}")
    if dip.get("stato") == "licenziato":
        st.markdown(f"<span style='color:#B42318;font-weight:700'>Licenziato il {data_it(dip.get('data_licenziamento'))}</span>",
                    unsafe_allow_html=True)

    dd.render(p, con_rapporto=True)
    dati = dd.raccogli(p, con_rapporto=True)

    st.write("")
    with st.container(key="verde_salva_dip"):
        salva = st.button("Salva dipendente", key="salva_dip", type="primary")
    if salva:
        if not dati["nome"] or not dati["cognome"]:
            st.error("Nome e cognome sono obbligatori.")
        else:
            errore = _scrivi(az["id"], k, dati)
            if errore:
                st.error(errore)
            else:
                st.session_state["msg_dip"] = "Dipendente salvato."
                st.rerun()
    messaggio = st.session_state.pop("msg_dip", None)
    if messaggio:
        st.success(messaggio)

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
                col_info, col_mod, col_pdf = st.columns([3.4, 1.7, 1.5], vertical_alignment="center")
                col_info.markdown(f"**{NOMI_TIPO.get(c.get('tipo'), c.get('tipo', ''))}** · {NOMI_DURATA.get(c.get('durata'), c.get('durata', ''))}")
                col_info.caption(f"{c.get('funzione') or '—'} · dal {data_it(c.get('data_inizio'))}"
                                 + (f" al {data_it(c.get('data_fine'))}" if c.get("data_fine") else ""))
                contenuto = db.leggi_allegato(k, c["allegato_id"]) if c.get("allegato_id") else None
                with col_mod:
                    with st.container(key=f"giallo_modifica_{c['id']}"):
                        if st.button("Modifica contratto", key=_k(p, f"modct_{c['id']}"), disabled="form" not in c):
                            st.session_state["ct_modifica"] = (az["id"], k, c["id"])
                            vai("contratto")
                with col_pdf:
                    if contenuto:
                        st.download_button("Scarica PDF", data=contenuto, file_name=f"Contratto_{c.get('data_inizio')}.pdf",
                                           mime="application/pdf", key=_k(p, f"ctpdf_{c['id']}"))
                    else:
                        st.caption("PDF non disponibile")
    else:
        st.caption("Nessun contratto registrato.")

    st.markdown("## Buste paga")
    st.info("Le buste paga verranno create in un secondo momento: qui comparirà l'elenco mensile del dipendente.")

    _sezione_allegati(az["id"], dip, p)
    _azioni_finali(az["id"], dip, p)

    # ── uscita con modifiche non salvate ──
    da_salvare = {c: v for c, v in dati.items() if c not in ("nome", "cognome") or v}
    uscita.memorizza("dipendente", id=k, azienda_id=az["id"], dati=da_salvare)
    uscita.gestisci("dipendente", dest, sporco=not uguali(dati, dip))
