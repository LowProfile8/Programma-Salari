"""modules/contratto.py — Crea contratto, in due passi.

Passo 1 (scelta): azienda -> dipendente nuovo o già esistente -> tipo di contratto.
Passo 2 (contratto): dati del dipendente (precompilati se esistente), dati dell'azienda (dall'archivio),
condizioni, salario con avviso se sotto i minimi, trattenute (dall'azienda), assegni, netto, valori annui,
dichiarazione di segretezza. In fondo: «Salva contratto» e «Scarica PDF».
"""

import dataclasses
import datetime as dt

import streamlit as st

from core import db, lpp
from core.config import NOME_STUDIO, RAMI_PIANO1_BASIS
from core.contratti import calcolo as cal
from core.contratti import minimi
from core.contratti import pdf as cpdf
from core.nav import nuova_entrata, prefisso, tasto_home, vai
from core.stile import intestazione
from core.util import a_data, da_data, data_it, nuovo_id
from modules import dati_dipendente as dd

TIPO_DA_CONTRATTO_AZIENDA = {
    "Contratto individuale": cal.INDIVIDUALE,
    "CCNL ristorazione / alberghiero": cal.CCNL,
    "CCL autotrasporti": cal.AUTOTRASPORTI,
    "CPC parrucchieri e coiffeur": cal.CPC,
}
LIVELLI_RIDUZIONE = {
    "I": [(1, "a) Non ha mai lavorato più di 4 mesi in un'azienda CCNL: −8% per i primi 12 mesi"),
          (2, "b) Ha già lavorato più di 4 mesi in un'azienda CCNL: −8% per i primi 3 mesi"),
          (3, "c) Si rinuncia alla riduzione")],
    "II": [(4, "a) Prima assunzione dopo la formazione o in Svizzera: −8% per i primi 3 mesi"),
           (5, "b) Nessuna riduzione")],
}
LIVELLI_RIDUZIONE["IIIa"] = LIVELLI_RIDUZIONE["II"]
VKB = {"99.00": "         99.00", "49.50": "         49.50"}


def _k(p: str, nome: str) -> str:
    return f"{p}_c_{nome}"


# ══════════════════════════════════════════════════════════════════════
# Passo 1 — scelta
# ══════════════════════════════════════════════════════════════════════
def _passo_scelta() -> None:
    st.markdown("# Nuovo contratto")
    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Per creare un contratto serve almeno un'azienda in archivio.")
        if st.button("Vai all'archivio", key="contratto_vai_archivio"):
            vai("archivio")
        return
    nomi = {a["id"]: db.nome_azienda(a) for a in aziende}
    az_id = st.selectbox("1. Per quale azienda vuoi creare il contratto?", list(nomi), index=None,
                         format_func=lambda i: nomi[i], placeholder="Seleziona un'azienda", key="ct_s_azienda")
    if az_id is None:
        return
    az = db.get_azienda(az_id)

    scelta = st.radio("2. Il contratto è per…", ["Un nuovo dipendente", "Un dipendente già esistente"], index=None,
                      key=f"ct_s_dip_{az_id}")
    dip_id = None
    if scelta == "Un dipendente già esistente":
        assunti = [d for d in db.ordina_dipendenti(az.get("dipendenti", [])) if d.get("stato") != "licenziato"]
        if not assunti:
            st.warning("Questa azienda non ha dipendenti assunti: scegli «Un nuovo dipendente».")
        else:
            etichette = {d["id"]: f"{d['cognome']} {d['nome']}" for d in assunti}
            dip_id = st.selectbox("Quale dipendente?", list(etichette), index=None, format_func=lambda i: etichette[i],
                                  placeholder="Seleziona il dipendente", key=f"ct_s_dipid_{az_id}")

    predefinito = TIPO_DA_CONTRATTO_AZIENDA.get(az.get("contratto_collettivo") or "")
    chiave_tipo = f"ct_s_tipo_{az_id}"
    if predefinito and chiave_tipo not in st.session_state:
        st.session_state[chiave_tipo] = predefinito
    tipo = st.selectbox("3. Che tipo di contratto?", list(cal.NOMI_TIPO), index=None,
                        format_func=lambda t: cal.NOMI_TIPO[t], placeholder="Scegli il tipo di contratto", key=chiave_tipo)
    if predefinito:
        st.caption("Proposto in base al «Contratto seguito» indicato nelle Info aziendali.")

    pronto = bool(scelta and tipo and (scelta == "Un nuovo dipendente" or dip_id))
    if st.button("Avanti →", key="ct_avanti", type="primary", disabled=not pronto):
        st.session_state["ct_sel"] = {"azienda_id": az_id, "dip_id": dip_id, "tipo": tipo}
        nuova_entrata("ct")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════
# Passo 2 — contratto
# ══════════════════════════════════════════════════════════════════════
def _riepilogo_azienda(az: dict) -> None:
    ali = cal.aliquote_da_azienda(az)
    with st.container(border=True):
        st.markdown("##### Dati dell'azienda (dall'archivio)")
        c1, c2 = st.columns(2)
        c1.markdown(f"**Ragione sociale**  \n{db.nome_azienda(az)}")
        c2.markdown(f"**Numero CHE**  \n{az.get('numero_che') or '—'}")
        sede = ", ".join(x for x in [az.get("sede_via"), " ".join(y for y in [az.get("sede_npa"), az.get("sede_localita")] if y)] if x)
        c1.markdown(f"**Sede legale**  \n{sede or '—'}")
        c2.markdown(f"**Contratto seguito**  \n{az.get('contratto_collettivo') or '—'}")
        st.caption(f"Trattenute a carico del dipendente (da Info aziendali): AVS/AI/IPG {ali.avs:g}% · AD {ali.ad:g}% · "
                   f"IGM {ali.igm:g}% · LAINF {ali.lainf:g}%")
        if not (az.get("numero_che") and sede):
            st.warning("Nelle Info aziendali mancano numero CHE o sede legale.")


def _si(valore) -> bool:
    return valore == "Sì"


def _passo_contratto(sel: dict) -> None:
    az = db.get_azienda(sel["azienda_id"])
    if az is None:
        st.session_state.pop("ct_sel", None)
        st.rerun()
        return
    dip = (db.get_dipendente(az["id"], sel["dip_id"]) if sel.get("dip_id") else None) or {}
    tipo = sel["tipo"]
    p = prefisso("ct", "form")
    dd.init_stato(p, dip)
    ali = cal.aliquote_da_azienda(az)
    oggi = dt.date.today()

    st.markdown("# Nuovo contratto")
    st.markdown(f"**{cal.NOMI_TIPO[tipo]}** · {db.nome_azienda(az)} · "
                + (f"{dip.get('cognome', '')} {dip.get('nome', '')}".strip() if dip else "nuovo dipendente"))
    _riepilogo_azienda(az)
    if tipo == cal.CPC:
        st.warning("Il modello PDF per il contratto CPC parrucchieri non è ancora disponibile: puoi compilare e salvare "
                   "il contratto e controllare i minimi, ma «Scarica PDF» resterà disattivato finché non lo carichi.")

    # ── dati del dipendente ──
    st.markdown("## Dati del dipendente")
    dd.render(p, con_rapporto=False)

    # ── condizioni ──
    st.markdown("## Condizioni di lavoro")
    durate = [cal.INDETERMINATO, cal.DETERMINATO] + ([] if tipo == cal.CPC else [cal.ORE])
    durata = st.radio("Tipo di contratto", durate, format_func=lambda d: cal.NOMI_DURATA[d], horizontal=True,
                      key=_k(p, "durata"))
    ore_contratto = durata == cal.ORE
    c1, c2 = st.columns(2)
    inizio = c1.date_input("Data di inizio", value=oggi, format="DD/MM/YYYY", min_value=dd.MIN_DATA, max_value=dd.MAX_DATA,
                           key=_k(p, "inizio"))
    fine = None
    if durata == cal.DETERMINATO:
        fine = c2.date_input("Data di fine", value=None, format="DD/MM/YYYY", min_value=dd.MIN_DATA,
                             max_value=dd.MAX_DATA, key=_k(p, "fine"))
    funzione = st.text_input("Funzione", value=dip.get("funzione") or "", key=_k(p, "funzione"))

    percentuale, categoria, ore_pieno_aut = 100.0, "Normale", 45.0
    if not ore_contratto:
        a, b = st.columns(2)
        percentuale = a.number_input("Percentuale lavorativa (%)", min_value=1.0, max_value=100.0, value=100.0, step=5.0,
                                     key=_k(p, "pct"))
        if tipo in (cal.INDIVIDUALE, cal.CCNL):
            categoria = b.radio("Tipo di azienda", list(cal.BASI_ORE_AZIENDA), horizontal=True, key=_k(p, "categoria"),
                                help="Normale 42 ore, stagionale 43,5 ore, piccola 45 ore a tempo pieno.")
        elif tipo == cal.AUTOTRASPORTI:
            ore_pieno_aut = b.selectbox("Ore settimanali a tempo pieno", cal.ORE_PIENO_AUTOTRASPORTI, index=0,
                                        key=_k(p, "ore_aut"), help="CCL art. 14.1: da 45 a 48 ore, base 45.")
        ore_sett = cal.ore_settimanali(tipo, percentuale, categoria, ore_pieno_aut)
        pieno = cal.ore_pieno(tipo, categoria, ore_pieno_aut)
        st.info(f"**Ore settimanali: {ore_sett:g}** ({percentuale:g}% × {pieno:g} ore a tempo pieno)")
    else:
        ore_sett = 0.0
        pieno = cal.ore_pieno(tipo, "Normale", 45.0)
        st.info("Contratto a ore: impieghi irregolari, pagati con il salario orario.")

    # classificazione per i minimi, secondo il tipo di contratto
    cls: dict = {}
    anni_servizio_15 = False
    if tipo == cal.AUTOTRASPORTI:
        a, b = st.columns(2)
        settore = a.selectbox("Settore", list(minimi.AUTOTRASPORTI_2026), key=_k(p, "settore"))
        categoria_v = b.selectbox("Categoria del veicolo / mansione", list(minimi.AUTOTRASPORTI_2026[settore]),
                                  key=f"{_k(p, 'catveic')}_{settore}")
        a, b = st.columns(2)
        anni = a.radio("Anni di servizio presso l'azienda", ["1° anno", "5° anno e seguenti"], horizontal=True, key=_k(p, "anni"))
        afc = b.checkbox("Autista con attestato federale di capacità (AFC)", key=_k(p, "afc"))
        anni_servizio_15 = st.checkbox("50 anni di età e 15 anni di servizio (5 settimane di vacanze)", key=_k(p, "c1550"))
        cls = dict(settore=settore, categoria=categoria_v, anni_servizio=5 if anni.startswith("5") else 1, afc=afc)
    elif tipo == cal.CPC:
        a, b = st.columns(2)
        qualifica = a.selectbox("Qualifica", list(minimi.PARRUCCHIERI[2026]), key=_k(p, "qualifica"))
        anno_prof = b.selectbox("Anno professionale", list(range(3)), format_func=lambda i: minimi.ANNI_PROFESSIONALI[i],
                                key=_k(p, "annoprof"))
        cls = dict(qualifica=qualifica, anno_prof=anno_prof)
    elif tipo == cal.CCNL:
        a, b = st.columns(2)
        livello = a.selectbox("Livello di salario minimo", ["I (senza formazione)", "II (CFP)", "IIIa (AFC)"],
                              key=_k(p, "livello"))
        chiave_liv = livello.split(" ")[0]
        opzioni = LIVELLI_RIDUZIONE[chiave_liv]
        scelta_rid = st.radio("Riduzione nel periodo di introduzione (art. 10 CCNL)", [o[0] for o in opzioni],
                              format_func=lambda c: dict(opzioni)[c], key=f"{_k(p, 'ridu')}_{chiave_liv}")
        a, b = st.columns(2)
        prova = a.selectbox("Periodo di prova", ["3 mesi", "14 giorni", "Nessuno"], key=_k(p, "prova"))
        vkb_default = "99.00" if percentuale > 50 else "49.50"
        vkb = b.selectbox("Contributo annuo spese di formazione e di esecuzione CCNL (CHF)", list(VKB),
                          index=list(VKB).index(vkb_default), key=f"{_k(p, 'vkb')}_{vkb_default}")
        cls = dict(livello_ccnl=livello, riduzione_introduzione=0.08 if scelta_rid in (1, 2, 4) else 0.0)
        ccnl_extra = {"livello": livello, "riduzione": scelta_rid, "prova": prova, "vkb": VKB[vkb]}

    eta = cal.eta_anni(a_data(da_data(st.session_state.get(f"{p}_data_nascita"))), inizio)
    vf = cal.info_vacanze_festivita(tipo, eta, anni_servizio_15)
    st.caption(f"Vacanze: {vf['vacanze']} · Festività: {vf['festivita']}")

    # ── salario ──
    st.markdown("## Salario")
    etichetta = "Salario orario di base (CHF all'ora)" if ore_contratto else "Salario fisso mensile (CHF)"
    salario = st.number_input(etichetta, min_value=0.0, value=0.0, step=0.05 if ore_contratto else 50.0, format="%.2f",
                              key=_k(p, "salario"))
    tredicesima, bonus, vac_pct, fest_pct = "mensile", 0.0, 0.0, 0.0
    if not ore_contratto:
        a, b = st.columns(2)
        tredicesima = "mensile" if a.radio("Tredicesima", ["Mensile", "Annuale"], horizontal=True, key=_k(p, "tred")) == "Mensile" else "annuale"
        bonus = b.number_input("Bonus mensile (CHF, facoltativo)", min_value=0.0, value=0.0, step=50.0, format="%.2f", key=_k(p, "bonus"))
    else:
        bonus = st.number_input("Bonus orario (CHF, facoltativo)", min_value=0.0, value=0.0, step=0.05, format="%.2f", key=_k(p, "bonus_h"))
        a, b = st.columns(2)
        vdef = vf["vacanze_pct"] or 8.33
        fdef = vf["festivita_pct"] or 0.0
        vac_pct = a.number_input("Indennità vacanze (% sul salario di base)", min_value=0.0, max_value=30.0, value=float(vdef),
                                 step=0.01, format="%.2f", key=f"{_k(p, 'vacpct')}_{vdef}")
        fest_pct = b.number_input("Indennità festività (%)", min_value=0.0, max_value=30.0, value=float(fdef), step=0.01,
                                  format="%.2f", key=f"{_k(p, 'festpct')}_{fdef}")
        if vf["festivita_pct"] is None:
            st.warning("Per questo tipo di contratto la percentuale di festività non è fissata dal documento caricato: "
                       "inseriscila tu.")

    minimo = cal.verifica_minimo(tipo=tipo, durata=durata, salario_fisso=salario, percentuale=percentuale,
                                 ore_sett=ore_sett, ore_pieno_sett=pieno, anno=inizio.year, **cls)
    if salario > 0 or minimo.stato == "nd":
        if minimo.stato == "sotto":
            st.warning(minimo.messaggio)
        elif minimo.stato == "ok":
            st.success(minimo.messaggio)
        else:
            st.info(minimo.messaggio)

    base = cal.Parametri(tipo, durata, salario, tredicesima, bonus, vac_pct, fest_pct, ali)
    lordo_prelim = cal.calcola(base)
    st.metric("Salario lordo AVS " + ("(all'ora)" if ore_contratto else "(al mese)"), f"CHF {cpdf.chf(lordo_prelim.lordo_avs)}")

    # ── trattenute ──
    st.markdown("## Trattenute")
    st.caption(f"Dalle Info aziendali: AVS/AI/IPG {ali.avs:g}% · AD {ali.ad:g}% · malattia (IGM) {ali.igm:g}% · "
               f"infortunio non professionale (LAINF) {ali.lainf:g}%.")
    lpp_sugg, lpp_pct_sugg = 0.0, None
    piano1 = az.get("lpp_modalita") == "piano1_basis" and az.get("ramo") in RAMI_PIANO1_BASIS
    if piano1 and not ore_contratto:
        data_nasc = st.session_state.get(f"{p}_data_nascita")
        categoria_lpp = (lpp.categoria_eta(data_nasc, inizio.year) if data_nasc else lpp.CATEGORIA_ADULTI) or lpp.CATEGORIA_ADULTI
        lpp_sugg = lpp.trattenuta_dipendente(lordo_prelim.lordo_avs, categoria_lpp)
        lpp_pct_sugg = float(lpp.ALIQUOTA_DIPENDENTE[categoria_lpp] * 100)
    a, b = st.columns(2)
    lpp_importo = a.number_input("LPP (CHF)" + (" all'ora" if ore_contratto else " al mese"), min_value=0.0, value=float(lpp_sugg),
                                 step=1.0, format="%.2f", key=f"{_k(p, 'lpp')}_{lpp_sugg}")
    if piano1 and not ore_contratto:
        a.caption(f"Suggerito dal Piano 1 Basis ({lpp_pct_sugg:g}% del salario assicurato): modificabile.")
    if_pct = b.number_input("Imposta alla fonte (%)", min_value=0.0, max_value=60.0, value=0.0, step=0.1, format="%.2f",
                            key=_k(p, "if"))
    a, b = st.columns(2)
    vitto = a.number_input("Vitto e alloggio (CHF)", min_value=0.0, value=0.0, step=10.0, format="%.2f", key=_k(p, "vitto"))
    altra = b.number_input("Altra trattenuta (CHF)", min_value=0.0, value=0.0, step=10.0, format="%.2f", key=_k(p, "altra"))
    altra_nome = st.text_input("Descrizione dell'altra trattenuta (es. cure medico-sanitarie)", key=_k(p, "altra_nome")) if altra else ""
    comm = 0.0
    comm_mensile = 0.0
    if tipo == cal.AUTOTRASPORTI:
        comm_mensile = cal.commissione_paritetica_autotrasporti(percentuale if not ore_contratto else 100)
        if ore_contratto:
            st.caption(f"Commissione paritetica: CHF {comm_mensile:.2f} al mese (non inclusa nel conteggio orario).")
        else:
            comm = comm_mensile
            st.caption(f"Commissione paritetica (art. 37 CCL): CHF {comm:.2f} al mese, aggiunta in automatico.")

    # ── assegni ──
    st.markdown("## Assegni e rimborsi")
    a, b, c3 = st.columns(3)
    assegni = a.number_input("Assegni per figli (CHF)", min_value=0.0, value=0.0, step=10.0, format="%.2f", key=_k(p, "assegni"))
    rimborsi = b.number_input("Rimborsi (CHF)", min_value=0.0, value=0.0, step=10.0, format="%.2f", key=_k(p, "rimborsi"))
    arrot = c3.number_input("Arrotondamenti (CHF)", value=0.0, step=0.05, format="%.2f", key=_k(p, "arrot"))

    par = cal.Parametri(tipo, durata, salario, tredicesima, bonus, vac_pct, fest_pct, ali, lpp_importo, if_pct, vitto, altra,
                        comm, assegni, rimborsi, arrot)
    r = cal.calcola(par)

    with st.container(border=True):
        st.markdown("##### Riepilogo")
        m1, m2, m3 = st.columns(3)
        m1.metric("Salario lordo AVS", f"CHF {cpdf.chf(r.lordo_avs)}")
        m2.metric("Totale trattenute", f"CHF {cpdf.chf(r.totale_deduzioni)}")
        m3.metric("Salario netto", f"CHF {cpdf.chf(r.netto)}")
        m4, m5, m6 = st.columns(3)
        m4.metric("Imposta alla fonte", f"{r.imposta_fonte_pct:g}%")
        m5.metric("Salario lordo annuo determinante", f"CHF {cpdf.chf(r.lordo_annuo)}")
        m6.metric("Salario AVS annuo", f"CHF {cpdf.chf(r.avs_annuo)}")
        st.caption("Annuo = lordo × 12 (tredicesima mensile) o × 13 (tredicesima annuale); nei contratti a ore lordo orario × 2160.")

    st.markdown("## Accordi e dichiarazione di segretezza")
    accordi = st.text_area("Accordi particolari (facoltativi)", key=_k(p, "accordi"))
    segretezza = st.radio("Aggiungere la dichiarazione di segretezza e non concorrenza come ultima pagina?",
                          ["Sì", "No"], index=1, horizontal=True, key=_k(p, "segr"))

    # ── dati per il PDF e per l'archivio ──
    dati_dip = dd.raccogli(p, con_rapporto=False)
    dati_dip["funzione"] = funzione.strip()
    dati_dip["data_assunzione"] = da_data(inizio)
    contratto = {
        "tipo": tipo, "durata": durata,
        "azienda": {"nome": db.nome_azienda(az), "sede_via": az.get("sede_via"), "sede_npa": az.get("sede_npa"),
                    "sede_localita": az.get("sede_localita"), "numero_che": az.get("numero_che")},
        "dip": dati_dip, "funzione": funzione.strip(), "data_inizio": da_data(inizio), "data_fine": da_data(fine),
        "percentuale": percentuale, "ore_sett": ore_sett, "categoria_azienda": categoria,
        "calc": dataclasses.asdict(r), "aliq": {"igm": ali.igm, "lainf": ali.lainf},
        "lpp_pct": lpp_pct_sugg if (piano1 and abs(lpp_importo - lpp_sugg) < 0.005) else None,
        "vacanze_pct": vac_pct if ore_contratto else None, "festivita_pct": fest_pct if ore_contratto else None,
        "accordi": accordi, "segretezza": _si(segretezza), "data_firma": da_data(oggi),
        "altra_deduzione_nome": altra_nome, "comm_mensile": comm_mensile if ore_contratto else None,
    }
    if tipo == cal.CCNL:
        contratto["ccnl"] = ccnl_extra

    mancanti = []
    if not dati_dip["nome"] or not dati_dip["cognome"]:
        mancanti.append("nome e cognome del dipendente")
    if salario <= 0:
        mancanti.append("il salario")
    if durata == cal.DETERMINATO and fine is None:
        mancanti.append("la data di fine")
    pdf_bytes, errore_pdf = None, None
    if not mancanti:
        try:
            pdf_bytes = cpdf.genera_pdf(contratto)
        except cpdf.ModelloMancante as e:
            errore_pdf = str(e)
        except Exception as e:  # un modello PDF non leggibile non deve bloccare il salvataggio dei dati
            errore_pdf = f"Impossibile creare il PDF ({type(e).__name__}: {e})"

    # ── pulsanti ──
    st.write("")
    c1, c2, _ = st.columns([1.3, 1.3, 2])
    with c1:
        with st.container(key="verde_salva_contratto"):
            salva = st.button("Salva contratto", key="ct_salva", disabled=bool(mancanti))
    with c2:
        nome_file = f"Contratto_{dati_dip['cognome']}_{dati_dip['nome']}_{da_data(inizio)}.pdf".replace(" ", "_")
        st.download_button("Scarica PDF", data=pdf_bytes or b"", file_name=nome_file, mime="application/pdf",
                           key="ct_scarica", disabled=pdf_bytes is None)
    if mancanti:
        st.caption("Per salvare o scaricare inserisci: " + ", ".join(mancanti) + ".")
    elif errore_pdf:
        st.warning(errore_pdf)

    if salva:
        if sel.get("dip_id"):
            db.aggiorna_dipendente(az["id"], sel["dip_id"], dati_dip)
            dip_id = sel["dip_id"]
        else:
            dip_id = db.nuovo_dipendente(az["id"], dati_dip["nome"], dati_dip["cognome"], dati_dip)
        allegato_id = None
        if pdf_bytes:
            allegato_id = db.aggiungi_allegato(az["id"], dip_id, nome_file, pdf_bytes, "contratto")
        registro = {
            "id": nuovo_id(), "tipo": tipo, "durata": durata, "funzione": funzione.strip(), "data_inizio": da_data(inizio),
            "data_fine": da_data(fine), "percentuale": percentuale, "ore_settimanali": ore_sett,
            "salario_fisso": salario, "tredicesima": tredicesima, "calcolo": dataclasses.asdict(r),
            "segretezza": _si(segretezza), "allegato_id": allegato_id, "creato": da_data(oggi),
        }
        valori = {"data_contratto": da_data(inizio), "tipo": tipo, "durata": durata, "orario": ore_contratto,
                  "salario_lordo": r.lordo_avs, "salario_netto": r.netto, "imposta_fonte_pct": r.imposta_fonte_pct,
                  "lordo_annuo": r.lordo_annuo, "avs_annuo": r.avs_annuo}
        db.registra_contratto(az["id"], dip_id, registro, valori)
        st.session_state.pop("ct_sel", None)
        st.session_state["msg_dip"] = "Contratto salvato." + ("" if allegato_id else " (PDF non disponibile: salvati solo i dati.)")
        vai("dipendente", azienda_id=az["id"], dipendente_id=dip_id)


# ══════════════════════════════════════════════════════════════════════
def render() -> None:
    intestazione(NOME_STUDIO, "Crea contratto")
    sel = st.session_state.get("ct_sel")
    c1, c2, _ = st.columns([0.8, 1.8, 3])
    with c1:
        if tasto_home("contratto"):
            vai("home")
    if sel:
        with c2:
            if st.button("← Cambia selezione", key="ct_indietro", type="primary"):
                st.session_state.pop("ct_sel", None)
                nuova_entrata("ct")
                st.rerun()
        _passo_contratto(sel)
    else:
        _passo_scelta()
