"""modules/contratto.py — Crea contratto, in due passi (e «Modifica contratto» per riaprirne uno salvato).

Passo 1 (scelta): azienda -> dipendente nuovo o esistente -> tipo di contratto.
Passo 2 (contratto): dati del dipendente, dati dell'azienda, condizioni, salario con avviso minimi, trattenute,
rimborsi (anche settoriali), riepilogo, segretezza. In fondo «Salva contratto» e «Scarica PDF».
"""

import dataclasses

import streamlit as st

from core import db, lpp
from core.config import NOME_STUDIO, RAMI_PIANO1_BASIS
from core.contratti import calcolo as cal
from core.contratti import minimi
from core.contratti import pdf as cpdf
from core.nav import nuova_entrata, prefisso, tasto_home, vai
from core.stile import intestazione
from core.util import a_data, da_data, nuovo_id, oggi
from modules import dati_dipendente as dd

LINK_IAF = "https://www4.ti.ch/dfe/dc/sportello/calcolatori-dimposta/iaf2024"
TIPO_DA_CONTRATTO_AZIENDA = {
    "Contratto individuale": cal.INDIVIDUALE,
    "CCNL ristorazione / alberghiero": cal.CCNL,
    "CCL autotrasporti": cal.AUTOTRASPORTI,
    "CPC parrucchieri e coiffeur": cal.CPC,
}
RIDUZIONI = {
    "Ia": [(1, "a) Non ha mai lavorato più di 4 mesi in un'azienda CCNL: −8% per i primi 12 mesi"),
           (2, "b) Ha già lavorato più di 4 mesi in un'azienda CCNL: −8% per i primi 3 mesi"),
           (3, "c) Si rinuncia alla riduzione")],
    "II": [(4, "a) Prima assunzione in un'azienda CCNL: −8% per i primi 3 mesi"), (5, "b) Nessuna riduzione")],
}
RIDUZIONI["Ib"] = RIDUZIONI["Ia"]
RIDUZIONI["IIIa"] = RIDUZIONI["II"]
VKB = {"99.00": "         99.00", "49.50": "         49.50"}


def _k(p: str, nome: str) -> str:
    return f"{p}_c_{nome}"


def _idx(opzioni, valore, default=0):
    opzioni = list(opzioni)
    return opzioni.index(valore) if valore in opzioni else default


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


def _passo_contratto(sel: dict) -> None:
    az = db.get_azienda(sel["azienda_id"])
    if az is None:
        st.session_state.pop("ct_sel", None)
        st.rerun()
        return
    dip = (db.get_dipendente(az["id"], sel["dip_id"]) if sel.get("dip_id") else None) or {}
    salvato = next((c for c in dip.get("contratti", []) if c.get("id") == sel.get("contratto_id")), None) if sel.get("contratto_id") else None
    F = (salvato or {}).get("form", {})                  # valori già salvati (modifica contratto)
    tipo = sel["tipo"]
    p = prefisso("ct", "form")
    dd.init_stato(p, dip)
    ali = cal.aliquote_da_azienda(az)
    adesso = oggi()

    st.markdown("# Modifica contratto" if salvato else "# Nuovo contratto")
    st.markdown(f"**{cal.NOMI_TIPO[tipo]}** · {db.nome_azienda(az)} · "
                + (f"{dip.get('cognome', '')} {dip.get('nome', '')}".strip() if dip else "nuovo dipendente"))
    _riepilogo_azienda(az)
    # ── dati del dipendente (solo ciò che serve al contratto) ──
    st.markdown("## Dati del dipendente")
    dd.render(p, con_rapporto=False, completo=False)

    # ── condizioni ──
    st.markdown("## Condizioni di lavoro")
    durate = [cal.INDETERMINATO, cal.DETERMINATO] + ([] if tipo == cal.CPC else [cal.ORE])
    durata = st.radio("Tipo di contratto", durate, index=_idx(durate, F.get("durata")), format_func=lambda d: cal.NOMI_DURATA[d],
                      horizontal=True, key=_k(p, "durata"))
    ore_contratto = durata == cal.ORE
    c1, c2 = st.columns(2)
    inizio = c1.date_input("Data di inizio", value=a_data(F.get("inizio")) or adesso, format="DD/MM/YYYY",
                           min_value=dd.MIN_DATA, max_value=dd.MAX_DATA, key=_k(p, "inizio"))
    fine = None
    if durata == cal.DETERMINATO:
        fine = c2.date_input("Data di fine", value=a_data(F.get("fine")), format="DD/MM/YYYY", min_value=dd.MIN_DATA,
                             max_value=dd.MAX_DATA, key=_k(p, "fine"))
    funzione = st.text_input("Funzione", value=F.get("funzione") or dip.get("funzione") or "", key=_k(p, "funzione"))

    percentuale, categoria, ore_pieno_aut = 100.0, "Normale", 45.0
    if not ore_contratto:
        a, b = st.columns(2)
        percentuale = a.number_input("Percentuale lavorativa (%)", min_value=1.0, max_value=100.0,
                                     value=float(F.get("percentuale", 100.0)), step=5.0, key=_k(p, "pct"))
        if tipo in (cal.INDIVIDUALE, cal.CCNL):
            opz = list(cal.BASI_ORE_AZIENDA)
            categoria = b.radio("Tipo di azienda", opz, index=_idx(opz, F.get("categoria")), horizontal=True, key=_k(p, "categoria"),
                                help="Normale 42 ore, stagionale 43,5 ore, piccola 45 ore a tempo pieno.")
        elif tipo == cal.AUTOTRASPORTI:
            ore_pieno_aut = b.selectbox("Ore settimanali a tempo pieno", cal.ORE_PIENO_AUTOTRASPORTI,
                                        index=_idx(cal.ORE_PIENO_AUTOTRASPORTI, F.get("ore_aut")), key=_k(p, "ore_aut"),
                                        help="CCL art. 14.1: da 45 a 48 ore, base 45.")
        ore_sett = cal.ore_settimanali(tipo, percentuale, categoria, ore_pieno_aut)
        pieno = cal.ore_pieno(tipo, categoria, ore_pieno_aut)
        st.info(f"**Ore settimanali: {ore_sett:g}** ({percentuale:g}% × {pieno:g} ore a tempo pieno)")
    else:
        ore_sett = 0.0
        if tipo == cal.CCNL:
            opz = list(cal.BASI_ORE_AZIENDA)
            categoria = st.radio("Tipo di azienda (per il calcolo del minimo orario)", opz, index=_idx(opz, F.get("categoria")),
                                 horizontal=True, key=_k(p, "categoria_h"))
        pieno = cal.ore_pieno(tipo, categoria, 45.0)
        st.info("Contratto a ore: impieghi irregolari, pagati con il salario orario.")

    # classificazione per i minimi, secondo il tipo di contratto
    cls: dict = {}
    anni_servizio_15 = False
    ccnl_extra, settore, categoria_v, anni, afc, qualifica, anno_prof, cat_ccnl, scelta_rid, prova, vkb = {}, None, None, None, False, None, 0, None, None, "3 mesi", "99.00"
    if tipo == cal.AUTOTRASPORTI:
        a, b = st.columns(2)
        settori = list(minimi.AUTOTRASPORTI_2026)
        settore = a.selectbox("Settore", settori, index=_idx(settori, F.get("settore")), key=_k(p, "settore"))
        cat_opz = list(minimi.AUTOTRASPORTI_2026[settore])
        categoria_v = b.selectbox("Categoria del veicolo / mansione", cat_opz, index=_idx(cat_opz, F.get("categoria_veicolo")),
                                  key=f"{_k(p, 'catveic')}_{settore}")
        a, b = st.columns(2)
        anni_opz = ["1° anno", "5° anno e seguenti"]
        anni = a.radio("Anni di servizio presso l'azienda", anni_opz, index=_idx(anni_opz, F.get("anni")), horizontal=True, key=_k(p, "anni"))
        afc = b.checkbox("Autista con attestato federale di capacità (AFC)", value=bool(F.get("afc")), key=_k(p, "afc"))
        anni_servizio_15 = st.checkbox("50 anni di età e 15 anni di servizio (5 settimane di vacanze)", value=bool(F.get("c1550")), key=_k(p, "c1550"))
        cls = dict(settore=settore, categoria=categoria_v, anni_servizio=5 if anni.startswith("5") else 1, afc=afc)
    elif tipo == cal.CPC:
        a, b = st.columns(2)
        qual_opz = list(minimi.PARRUCCHIERI[2026])
        qualifica = a.selectbox("Qualifica", qual_opz, index=_idx(qual_opz, F.get("qualifica")), key=_k(p, "qualifica"))
        anno_prof = b.selectbox("Anno professionale", list(range(3)), index=int(F.get("anno_prof", 0)),
                                format_func=lambda i: minimi.ANNI_PROFESSIONALI[i], key=_k(p, "annoprof"))
        cls = dict(qualifica=qualifica, anno_prof=anno_prof)
    elif tipo == cal.CCNL:
        cats = list(minimi.CATEGORIE_CCNL)
        cat_ccnl = st.selectbox("Categoria di salario minimo (art. 10 CCNL)", cats, index=_idx(cats, F.get("cat_ccnl")),
                                format_func=lambda c: minimi.CATEGORIE_CCNL[c], key=_k(p, "catccnl"))
        scelta_rid = None
        if cat_ccnl in RIDUZIONI:
            opzioni = RIDUZIONI[cat_ccnl]
            codici = [o[0] for o in opzioni]
            scelta_rid = st.radio("Riduzione nel periodo di introduzione", codici, index=_idx(codici, F.get("scelta_rid")),
                                  format_func=lambda c: dict(opzioni)[c], key=f"{_k(p, 'ridu')}_{cat_ccnl}")
        a, b = st.columns(2)
        prove = ["3 mesi", "14 giorni", "Nessuno"]
        prova = a.selectbox("Periodo di prova", prove, index=_idx(prove, F.get("prova")), key=_k(p, "prova"))
        vkb_default = "99.00" if percentuale > 50 else "49.50"
        vkb = b.selectbox("Contributo annuo spese di formazione e di esecuzione CCNL (CHF)", list(VKB),
                          index=_idx(VKB, F.get("vkb"), list(VKB).index(vkb_default)), key=f"{_k(p, 'vkb')}_{vkb_default}")
        cls = dict(livello_ccnl=cat_ccnl, riduzione_introduzione=0.08 if scelta_rid in (1, 2, 4) else 0.0)
        ccnl_extra = {"livello": cat_ccnl, "riduzione": scelta_rid, "prova": prova, "vkb": VKB[vkb]}

    nascita = a_data(da_data(st.session_state.get(f"{p}_data_nascita")))
    eta = cal.eta_anni(nascita, inizio)
    vf = cal.info_vacanze_festivita(tipo, eta, anni_servizio_15)
    st.caption(f"Vacanze: {vf['vacanze']} · Festività: {vf['festivita']}")
    if tipo == cal.INDIVIDUALE:
        with st.expander("Riferimenti del Codice delle obbligazioni (parte salariale)"):
            for riga in cal.RIFERIMENTI_CO:
                st.markdown(f"- {riga}")
            st.caption("Sintesi di riferimento: verifica sempre il testo aggiornato del CO.")

    # ── salario ──
    st.markdown("## Salario")
    etichetta = "Salario orario di base (CHF all'ora)" if ore_contratto else "Salario fisso mensile (CHF)"
    salario = st.number_input(etichetta, min_value=0.0, value=float(F.get("salario", 0.0)), step=0.05 if ore_contratto else 50.0,
                              format="%.2f", key=_k(p, "salario"))
    tredicesima, bonus, vac_pct, fest_pct = "mensile", 0.0, 0.0, 0.0
    if not ore_contratto:
        a, b = st.columns(2)
        tred_opz = ["Mensile", "Annuale"]
        tredicesima = "mensile" if a.radio("Tredicesima", tred_opz, index=_idx(tred_opz, (F.get("tredicesima") or "mensile").capitalize()),
                                           horizontal=True, key=_k(p, "tred")) == "Mensile" else "annuale"
        bonus = b.number_input("Bonus mensile (CHF, facoltativo)", min_value=0.0, value=float(F.get("bonus", 0.0)), step=50.0,
                               format="%.2f", key=_k(p, "bonus"))
    else:
        bonus = st.number_input("Bonus orario (CHF, facoltativo)", min_value=0.0, value=float(F.get("bonus", 0.0)), step=0.05,
                                format="%.2f", key=_k(p, "bonus_h"))
        a, b = st.columns(2)
        vdef = F.get("vac_pct") or vf["vacanze_pct"] or 8.33
        fdef = F.get("fest_pct") if F.get("fest_pct") is not None else (vf["festivita_pct"] or 0.0)
        vac_pct = a.number_input("Indennità vacanze (% sul salario di base)", min_value=0.0, max_value=30.0, value=float(vdef),
                                 step=0.01, format="%.2f", key=f"{_k(p, 'vacpct')}_{vdef}")
        fest_pct = b.number_input("Indennità festività (%)", min_value=0.0, max_value=30.0, value=float(fdef), step=0.01,
                                  format="%.2f", key=f"{_k(p, 'festpct')}_{fdef}")
        st.caption("La tredicesima (8,33%) si calcola solo sul salario di base.")
        if vf["festivita_pct"] is None:
            st.warning("Per questo tipo di contratto la percentuale di festività non è fissata dal documento caricato: inseriscila tu.")

    minimo = cal.verifica_minimo(tipo=tipo, durata=durata, salario_fisso=salario, percentuale=percentuale,
                                 ore_sett=ore_sett, ore_pieno_sett=pieno, anno=inizio.year, **cls)
    if salario > 0 or minimo.stato == "nd":
        {"sotto": st.warning, "ok": st.success}.get(minimo.stato, st.info)(minimo.messaggio)

    lordo_prelim = cal.calcola(cal.Parametri(tipo, durata, salario, tredicesima, bonus, vac_pct, fest_pct, ali))
    st.caption(f"Salario lordo AVS {'(all’ora)' if ore_contratto else '(al mese)'}: CHF {cpdf.chf(lordo_prelim.lordo_avs)}")

    # ── trattenute ──
    st.markdown("## Trattenute")
    st.caption(f"Dalle Info aziendali: AVS/AI/IPG {ali.avs:g}% · AD {ali.ad:g}% · malattia (IGM) {ali.igm:g}% · "
               f"infortunio non professionale (LAINF) {ali.lainf:g}%.")
    lpp_sugg, lpp_pct_sugg = 0.0, None
    piano1 = az.get("lpp_modalita") == "piano1_basis" and az.get("ramo") in RAMI_PIANO1_BASIS
    if piano1 and not ore_contratto:
        categoria_lpp = (lpp.categoria_eta(nascita, inizio.year) if nascita else lpp.CATEGORIA_ADULTI) or lpp.CATEGORIA_ADULTI
        lpp_sugg = lpp.trattenuta_dipendente(lordo_prelim.lordo_avs, categoria_lpp)
        lpp_pct_sugg = float(lpp.ALIQUOTA_DIPENDENTE[categoria_lpp] * 100)
    a, b = st.columns(2)
    lpp_importo = a.number_input("LPP (CHF)" + (" all'ora" if ore_contratto else " al mese"), min_value=0.0,
                                 value=float(F.get("lpp", lpp_sugg)), step=1.0, format="%.2f", key=f"{_k(p, 'lpp')}_{lpp_sugg}")
    if piano1 and not ore_contratto:
        a.caption(f"Suggerito dal Piano 1 Basis ({lpp_pct_sugg:g}% del salario assicurato): modificabile.")
    nazion = st.session_state.get(f"{p}_nazionalita") or ""
    perm = st.session_state.get(f"{p}_permesso") or ""
    esente_if = nazion == "Svizzera" or perm in ("Cittadino svizzero", "Permesso C")
    if esente_if:
        b.number_input("Imposta alla fonte (%)", value=0.0, disabled=True, key=_k(p, "if_bloccata"),
                       help="Cittadini svizzeri e titolari del permesso C non sono soggetti all'imposta alla fonte.")
        b.caption("Non dovuta: cittadino svizzero o permesso C.")
        if_pct = 0.0
    else:
        if_pct = b.number_input("Imposta alla fonte (%)", min_value=0.0, max_value=60.0, value=float(F.get("if_pct", 0.0)),
                                step=0.1, format="%.2f", key=_k(p, "if"))
        b.markdown(f"[Calcolatore dell'imposta alla fonte (Ticino)]({LINK_IAF})")
    a, b = st.columns(2)
    vitto = a.number_input("Vitto e alloggio (CHF)", min_value=0.0, value=float(F.get("vitto", 0.0)), step=10.0, format="%.2f", key=_k(p, "vitto"))
    altra = b.number_input("Altra trattenuta (CHF)", min_value=0.0, value=float(F.get("altra", 0.0)), step=10.0, format="%.2f", key=_k(p, "altra"))
    avviso = cal.avviso_vitto_alloggio(tipo, vitto)
    if avviso:
        st.warning(avviso[1])
    altra_nome = st.text_input("Descrizione dell'altra trattenuta (es. cure medico-sanitarie)", value=F.get("altra_nome", ""),
                               key=_k(p, "altra_nome")) if altra else ""
    comm, comm_mensile = 0.0, 0.0
    if tipo == cal.AUTOTRASPORTI:
        comm_mensile = cal.commissione_paritetica_autotrasporti(percentuale if not ore_contratto else 100)
        if ore_contratto:
            st.caption(f"Commissione paritetica: CHF {comm_mensile:.2f} al mese (non inclusa nel conteggio orario).")
        else:
            comm = comm_mensile
            st.caption(f"Commissione paritetica (art. 37 CCL): CHF {comm:.2f} al mese, aggiunta in automatico.")

    # ── assegni e rimborsi ──
    st.markdown("## Assegni e rimborsi")
    a, b, c3 = st.columns(3)
    assegni = a.number_input("Assegni per figli (CHF)", min_value=0.0, value=float(F.get("assegni", 0.0)), step=10.0, format="%.2f", key=_k(p, "assegni"))
    rimborsi = b.number_input("Altri rimborsi (CHF)", min_value=0.0, value=float(F.get("rimborsi", 0.0)), step=10.0, format="%.2f", key=_k(p, "rimborsi"))
    arrot = c3.number_input("Arrotondamenti (CHF)", value=float(F.get("arrot", 0.0)), step=0.05, format="%.2f", key=_k(p, "arrot"))

    rimb_sett, trasferta, ccnl_rimb = 0.0, None, []
    if tipo == cal.AUTOTRASPORTI:
        opz = list(cal.FORFAIT_TRASFERTA)
        trasferta = st.radio("Indennità di trasferta forfettaria (non soggetta a trattenute, art. 13.2 CCL)", opz,
                             index=_idx(opz, F.get("trasferta")), key=_k(p, "trasf"))
        rimb_sett = cal.FORFAIT_TRASFERTA[trasferta]
    elif tipo == cal.CCNL:
        st.markdown("**Rimborsi settoriali (non soggetti a trattenute, art. 30 CCNL)**")
        salvati = F.get("ccnl_rimb", [])
        for i, (etichetta_r, importo_r) in enumerate(cal.RIMBORSI_CCNL):
            if st.checkbox(f"{etichetta_r}: CHF {importo_r:.2f} al mese", value=bool(salvati[i]) if i < len(salvati) else False,
                           key=_k(p, f"rimbccnl{i}")):
                rimb_sett += importo_r
                ccnl_rimb.append(True)
            else:
                ccnl_rimb.append(False)
    if rimb_sett:
        st.caption(f"Rimborsi settoriali: CHF {rimb_sett:.2f} al mese.")
    if ore_contratto and (assegni or rimb_sett):
        st.info("Contratto a ore: assegni per figli e rimborsi settoriali sono importi mensili, pagati a parte; "
                "non entrano nel salario netto orario.")

    par = cal.Parametri(tipo, durata, salario, tredicesima, bonus, vac_pct, fest_pct, ali, lpp_importo, if_pct, vitto, altra,
                        comm, assegni, rimborsi, arrot, rimb_sett)
    r = cal.calcola(par)

    nasc_anno = nascita.year if nascita else None
    lpp_max_val = lpp_sugg if (piano1 and not ore_contratto) else None
    controlli = cal.controlla_conteggio(tipo=tipo, durata=durata, r=r, par=par, eta=eta, anno_inizio=inizio.year,
                                        anno_nascita=nasc_anno, ore_sett=ore_sett, percentuale=percentuale,
                                        esente_if=esente_if, lpp_max=lpp_max_val, minimo=minimo)
    if controlli:
        st.markdown("##### Controlli sul conteggio")
        for livello, testo in controlli:
            (st.error if livello == "errore" else st.warning)(testo)

    with st.container(border=True):
        st.markdown("##### Riepilogo")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Lordo AVS", f"CHF {cpdf.chf(r.lordo_avs)}")
        m2.metric("Trattenute", f"CHF {cpdf.chf(r.totale_deduzioni)}")
        m3.metric("Netto", f"CHF {cpdf.chf(r.netto)}")
        m4.metric("Imposta alla fonte", f"{r.imposta_fonte_pct:g}%")
        m5, m6 = st.columns(2)
        m5.metric("Lordo annuo determinante", f"CHF {cpdf.chf(r.lordo_annuo)}")
        m6.metric("Salario AVS annuo", f"CHF {cpdf.chf(r.avs_annuo)}")
        st.caption("Annuo = lordo × 12 (tredicesima mensile) o × 13 (annuale); contratti a ore: lordo orario × 2160.")

    st.markdown("## Accordi e dichiarazione di segretezza")
    accordi = st.text_area("Accordi particolari (facoltativi)", value=F.get("accordi", ""), key=_k(p, "accordi"))
    segr_opz = ["Sì", "No"]
    segretezza = st.radio("Aggiungere la dichiarazione di segretezza e non concorrenza come ultima pagina?", segr_opz,
                          index=_idx(segr_opz, "Sì" if F.get("segretezza") else "No", 1), horizontal=True, key=_k(p, "segr"))

    # ── dati per il PDF e per l'archivio ──
    dati_dip = dd.raccogli(p, con_rapporto=False, completo=False)
    dati_dip["funzione"] = funzione.strip()
    dati_dip["data_assunzione"] = da_data(inizio)
    form = {
        "durata": durata, "inizio": da_data(inizio), "fine": da_data(fine), "funzione": funzione.strip(),
        "percentuale": percentuale, "categoria": categoria, "ore_aut": ore_pieno_aut, "settore": settore,
        "categoria_veicolo": categoria_v, "anni": anni, "afc": afc, "c1550": anni_servizio_15, "qualifica": qualifica,
        "anno_prof": anno_prof, "cat_ccnl": cat_ccnl, "scelta_rid": scelta_rid, "prova": prova, "vkb": vkb,
        "salario": salario, "tredicesima": tredicesima, "bonus": bonus, "vac_pct": vac_pct, "fest_pct": fest_pct,
        "lpp": lpp_importo, "if_pct": if_pct, "vitto": vitto, "altra": altra, "altra_nome": altra_nome,
        "assegni": assegni, "rimborsi": rimborsi, "arrot": arrot, "trasferta": trasferta, "ccnl_rimb": ccnl_rimb,
        "accordi": accordi, "segretezza": segretezza == "Sì",
    }
    contratto = {
        "tipo": tipo, "durata": durata,
        "azienda": {"nome": db.nome_azienda(az), "sede_via": az.get("sede_via"), "sede_npa": az.get("sede_npa"),
                    "sede_localita": az.get("sede_localita"), "numero_che": az.get("numero_che")},
        "dip": dati_dip, "funzione": funzione.strip(), "data_inizio": da_data(inizio), "data_fine": da_data(fine),
        "percentuale": percentuale, "ore_sett": ore_sett, "categoria_azienda": categoria,
        "calc": dataclasses.asdict(r),
        "aliq": {"avs": ali.avs, "ad": ali.ad, "igm": ali.igm, "lainf": ali.lainf},
        "lpp_pct": lpp_pct_sugg if (piano1 and abs(lpp_importo - lpp_sugg) < 0.005) else None,
        "vacanze_pct": vac_pct if ore_contratto else None, "festivita_pct": fest_pct if ore_contratto else None,
        "accordi": accordi, "segretezza": segretezza == "Sì", "data_firma": da_data(adesso),
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
        if salvato and salvato.get("allegato_id"):
            db.elimina_allegato(az["id"], dip_id, salvato["allegato_id"])
        allegato_id = db.aggiungi_allegato(az["id"], dip_id, nome_file, pdf_bytes, "contratto") if pdf_bytes else None
        registro = {
            "id": (salvato or {}).get("id") or nuovo_id(), "tipo": tipo, "durata": durata, "funzione": funzione.strip(),
            "data_inizio": da_data(inizio), "data_fine": da_data(fine), "percentuale": percentuale, "ore_settimanali": ore_sett,
            "salario_fisso": salario, "tredicesima": tredicesima, "calcolo": dataclasses.asdict(r),
            "segretezza": segretezza == "Sì", "allegato_id": allegato_id, "creato": da_data(adesso), "form": form,
        }
        valori = {"data_contratto": da_data(inizio), "tipo": tipo, "durata": durata, "orario": ore_contratto,
                  "salario_lordo": r.lordo_avs, "salario_netto": r.netto, "imposta_fonte_pct": r.imposta_fonte_pct,
                  "lordo_annuo": r.lordo_annuo, "avs_annuo": r.avs_annuo}
        if salvato:
            db.sostituisci_contratto(az["id"], dip_id, registro["id"], registro, valori)
        else:
            db.registra_contratto(az["id"], dip_id, registro, valori)
        st.session_state.pop("ct_sel", None)
        st.session_state["msg_dip"] = "Contratto salvato." + ("" if allegato_id else " (PDF non disponibile: salvati solo i dati.)")
        vai("dipendente", azienda_id=az["id"], dipendente_id=dip_id)


# ══════════════════════════════════════════════════════════════════════
def render() -> None:
    intestazione(NOME_STUDIO, "Crea contratto")
    sel = st.session_state.get("ct_sel")
    mod = st.session_state.pop("ct_modifica", None)     # arriva dal tasto «Modifica contratto» della scheda dipendente
    if mod and not sel:
        az_id, dip_id, ct_id = mod
        dip = db.get_dipendente(az_id, dip_id) or {}
        contratto = next((c for c in dip.get("contratti", []) if c.get("id") == ct_id), None)
        if contratto:
            sel = {"azienda_id": az_id, "dip_id": dip_id, "tipo": contratto["tipo"], "contratto_id": ct_id}
            st.session_state["ct_sel"] = sel
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
