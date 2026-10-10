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
from core.contratti import costruzione, fonte, minimi
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
    "CCL autorimesse": cal.AUTORIMESSE,
    "CCL pulizie e facility services": cal.PULIZIE,
    "Contratto standard (semplificato)": cal.STANDARD,
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
    st.session_state.pop("ct_msg", None)
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
        igm_u, igm_d = cal.aliquote_da_azienda(az, "Uomo").igm, cal.aliquote_da_azienda(az, "Donna").igm
        st.caption(f"Trattenute a carico del dipendente (da Info aziendali): AVS/AI/IPG {ali.avs:g}% · AD {ali.ad:g}% · "
                   f"malattia uomo {igm_u:g}% / donna {igm_d:g}% (scelta in base al sesso) · LAINF {ali.lainf:g}%")
        if not (az.get("numero_che") and sede):
            st.warning("Nelle Info aziendali mancano numero CHE o sede legale.")


def _cella(etichetta: str, valore: str, colore: str = "#1D1D1F", grande: bool = False) -> str:
    dim = "1.5rem" if grande else "1.1rem"
    return (f"<div style='padding:4px 6px'><div style='font-size:0.72rem;color:#6E6E73'>{etichetta}</div>"
            f"<div style='font-size:{dim};font-weight:700;color:{colore};white-space:nowrap'>{valore}</div></div>")


def _passo_contratto(sel: dict) -> None:
    az = db.get_azienda(sel["azienda_id"])
    if az is None:
        st.session_state.pop("ct_sel", None)
        st.rerun()
        return
    dip = (db.get_dipendente(az["id"], sel["dip_id"]) if sel.get("dip_id") else None) or {}
    salvato = next((c for c in dip.get("contratti", []) if c.get("id") == sel.get("contratto_id")), None) if sel.get("contratto_id") else None
    copia = next((c for c in dip.get("contratti", []) if c.get("id") == sel.get("copia_da")), None) if sel.get("copia_da") else None
    F = dict((salvato or copia or {}).get("form", {}))   # valori già salvati (modifica) o del contratto da cui si riparte
    if copia and not salvato:
        F.update(inizio=None, fine=None, firma=None, senza_data=False)
    tipo = sel["tipo"]
    p = prefisso("ct", "form")
    dd.init_stato(p, dip)
    adesso = oggi()
    ali = cal.aliquote_da_azienda(az)

    st.markdown("# Modifica contratto" if salvato else "# Nuovo contratto")
    if copia and not salvato:
        st.info("Nuovo contratto con i dati aggiornati del dipendente: sono ripartiti dal contratto precedente, che resta invariato.")
    st.markdown(f"**{cal.NOMI_TIPO[tipo]}** · {db.nome_azienda(az)} · "
                + (f"{dip.get('cognome', '')} {dip.get('nome', '')}".strip() if dip else "nuovo dipendente"))
    _riepilogo_azienda(az)

    # ── dati del dipendente (solo ciò che serve al contratto: niente coniuge, genitori, banca...) ──
    st.markdown("## Dati del dipendente")
    dd.render(p, con_rapporto=False, completo=False, coniuge=False)
    dati_dip = dd.raccogli(p, con_rapporto=False, completo=False)
    dip_full = {**dip, **dati_dip}                       # il coniuge resta quello dell'archivio

    # ── condizioni ──
    st.markdown("## Condizioni di lavoro")
    durate = [cal.INDETERMINATO, cal.DETERMINATO] + ([] if tipo == cal.STANDARD else [cal.ORE])
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

    f: dict = {"durata": durata, "inizio": da_data(inizio), "fine": da_data(fine), "funzione": funzione.strip()}
    if not ore_contratto:
        a, b = st.columns(2)
        f["percentuale"] = a.number_input("Percentuale lavorativa (%)", min_value=1.0, max_value=100.0,
                                          value=float(F.get("percentuale", 100.0)), step=5.0, key=_k(p, "pct"))
        if tipo in (cal.INDIVIDUALE, cal.CCNL):
            opz = list(cal.BASI_ORE_AZIENDA)
            f["categoria"] = b.radio("Tipo di azienda", opz, index=_idx(opz, F.get("categoria")), horizontal=True, key=_k(p, "categoria"),
                                     help="Normale 42 ore, stagionale 43,5 ore, piccola 45 ore a tempo pieno.")
        elif tipo == cal.AUTOTRASPORTI:
            f["ore_aut"] = b.selectbox("Ore settimanali a tempo pieno", cal.ORE_PIENO_AUTOTRASPORTI,
                                       index=_idx(cal.ORE_PIENO_AUTOTRASPORTI, F.get("ore_aut")), key=_k(p, "ore_aut"),
                                       help="CCL art. 14.1: da 45 a 48 ore, base 45.")
        elif tipo == cal.AUTORIMESSE:
            f["ore_aut"] = b.selectbox("Ore settimanali a tempo pieno", cal.ORE_PIENO_AUTORIMESSE,
                                       index=_idx(cal.ORE_PIENO_AUTORIMESSE, F.get("ore_aut"), 0), key=_k(p, "ore_aut_ar"),
                                       format_func=lambda o: f"{o:g} ore", help="CCL autorimesse art. 9.1: 41,5, 45 oppure 47 ore.")
        if tipo != cal.STANDARD:
            pre = costruzione.costruisci(az, dip_full, tipo, f, adesso)
            st.info(f"**Ore settimanali: {pre['ore_sett']:g}** ({f['percentuale']:g}% × {pre['pieno']:g} ore a tempo pieno)")
        if tipo != cal.STANDARD and f["percentuale"] < 100:
            opz_az = ["Solo per la nostra azienda", "Anche per un'altra azienda"]
            sc = st.radio("Il dipendente lavora…", opz_az, index=1 if F.get("altra_azienda") else 0, horizontal=True, key=_k(p, "altra_az"),
                          help="Con un'occupazione inferiore al 100% l'aliquota dell'imposta alla fonte si legge sul reddito annuo "
                               "calcolato alla percentuale TOTALE di lavoro (nostra azienda + altro datore).")
            f["altra_azienda"] = sc == opz_az[1]
            if f["altra_azienda"]:
                massimo = max(1.0, 100.0 - f["percentuale"])
                f["pct_altra"] = st.number_input("Percentuale di lavoro presso l'altra azienda (%)", min_value=1.0, max_value=massimo,
                                                 value=min(float(F.get("pct_altra", 20.0)), massimo), step=5.0, key=_k(p, "pct_altra"))
                st.caption(f"Percentuale totale: {f['percentuale'] + f['pct_altra']:g}%. Il reddito annuo determinante per l'imposta alla fonte "
                           f"è il lordo AVS mensile × {(f['percentuale'] + f['pct_altra']) / f['percentuale']:.4g} (totale/nostra percentuale) × mesi.")
    else:
        if tipo == cal.CCNL:
            opz = list(cal.BASI_ORE_AZIENDA)
            f["categoria"] = st.radio("Tipo di azienda (per il calcolo del minimo orario)", opz, index=_idx(opz, F.get("categoria")),
                                      horizontal=True, key=_k(p, "categoria_h"))
        if tipo == cal.AUTORIMESSE:
            f["ore_aut"] = st.selectbox("Ore settimanali a tempo pieno (per il minimo orario)", cal.ORE_PIENO_AUTORIMESSE,
                                        index=_idx(cal.ORE_PIENO_AUTORIMESSE, F.get("ore_aut"), 0), key=_k(p, "ore_aut_ar_h"),
                                        format_func=lambda o: f"{o:g} ore")
        st.info("Contratto a ore: impieghi irregolari, pagati con il salario orario.")

    # classificazione per i minimi
    if tipo == cal.AUTOTRASPORTI:
        a, b = st.columns(2)
        settori = list(minimi.AUTOTRASPORTI_2026)
        f["settore"] = a.selectbox("Settore", settori, index=_idx(settori, F.get("settore")), key=_k(p, "settore"))
        cat_opz = list(minimi.AUTOTRASPORTI_2026[f["settore"]])
        f["categoria_veicolo"] = b.selectbox("Categoria del veicolo / mansione", cat_opz, index=_idx(cat_opz, F.get("categoria_veicolo")),
                                             key=f"{_k(p, 'catveic')}_{f['settore']}")
        a, b = st.columns(2)
        anni_opz = ["1° anno", "5° anno e seguenti"]
        f["anni"] = a.radio("Anni di servizio presso l'azienda", anni_opz, index=_idx(anni_opz, F.get("anni")), horizontal=True, key=_k(p, "anni"))
        f["afc"] = b.checkbox("Autista con attestato federale di capacità (AFC)", value=bool(F.get("afc")), key=_k(p, "afc"))
        f["c1550"] = st.checkbox("50 anni di età e 15 anni di servizio (5 settimane di vacanze)", value=bool(F.get("c1550")), key=_k(p, "c1550"))
    elif tipo == cal.CPC:
        f["c1550"] = st.checkbox("5 anni nella stessa azienda dopo la formazione conclusa (27,5 giorni di vacanza)",
                                 value=bool(F.get("c1550")), key=_k(p, "c1550_cpc"))
        a, b = st.columns(2)
        qual_opz = list(minimi.PARRUCCHIERI[2026])
        f["qualifica"] = a.selectbox("Qualifica", qual_opz, index=_idx(qual_opz, F.get("qualifica")), key=_k(p, "qualifica"))
        f["anno_prof"] = b.selectbox("Anno professionale", list(range(3)), index=int(F.get("anno_prof", 0)),
                                     format_func=lambda i: minimi.ANNI_PROFESSIONALI[i], key=_k(p, "annoprof"))
    elif tipo == cal.AUTORIMESSE:
        cats = list(minimi.AUTORIMESSE_2026)
        f["cat_ccl"] = st.selectbox("Categoria professionale (Appendice 1 CCL autorimesse)", cats, index=_idx(cats, F.get("cat_ccl")),
                                    key=_k(p, "cat_ar"))
        minimi_cat = minimi.AUTORIMESSE_2026[f["cat_ccl"]][0]
        if minimi_cat and len(minimi_cat) > 1:
            f["anno_ccl"] = st.selectbox("Anno dopo il tirocinio", list(range(len(minimi_cat))), index=min(int(F.get("anno_ccl", 0)), len(minimi_cat) - 1),
                                         format_func=lambda i: minimi.ANNI_DOPO_TIROCINIO[i], key=f"{_k(p, 'anno_ar')}_{len(minimi_cat)}")
        else:
            f["anno_ccl"] = 0
        f["c1550"] = False
    elif tipo == cal.PULIZIE:
        cats = list(minimi.PULIZIE_2026)
        f["cat_ccl"] = st.selectbox("Categoria (Appendice 1B CCL pulizie e facility services)", cats, index=_idx(cats, F.get("cat_ccl")),
                                    key=_k(p, "cat_pul"))
    elif tipo == cal.CCNL:
        cats = list(minimi.CATEGORIE_CCNL)
        f["cat_ccnl"] = st.selectbox("Categoria di salario minimo (art. 10 CCNL)", cats, index=_idx(cats, F.get("cat_ccnl")),
                                     format_func=lambda c: minimi.CATEGORIE_CCNL[c], key=_k(p, "catccnl"))
        f["scelta_rid"] = None
        if f["cat_ccnl"] in RIDUZIONI:
            opzioni = RIDUZIONI[f["cat_ccnl"]]
            codici = [o[0] for o in opzioni]
            f["scelta_rid"] = st.radio("Riduzione nel periodo di introduzione", codici, index=_idx(codici, F.get("scelta_rid")),
                                       format_func=lambda c: dict(opzioni)[c], key=f"{_k(p, 'ridu')}_{f['cat_ccnl']}")
        a, b = st.columns(2)
        prove = ["3 mesi", "14 giorni", "Nessuno"]
        f["prova"] = a.selectbox("Periodo di prova", prove, index=_idx(prove, F.get("prova")), key=_k(p, "prova"))
        vkb_default = "99.00" if f.get("percentuale", 100.0) > 50 else "49.50"
        vkb = b.selectbox("Contributo annuo spese di formazione e di esecuzione CCNL (CHF)", list(VKB),
                          index=_idx(VKB, F.get("vkb"), list(VKB).index(vkb_default)), key=f"{_k(p, 'vkb')}_{vkb_default}")
        f["vkb"], f["vkb_testo"] = vkb, VKB[vkb]

    pre = costruzione.costruisci(az, dip_full, tipo, f, adesso)
    if tipo != cal.STANDARD:
        st.caption(f"Vacanze: {pre['vf']['vacanze']} · Festività: {pre['vf']['festivita']}")
    if tipo == cal.INDIVIDUALE:
        with st.expander("Riferimenti del Codice delle obbligazioni (parte salariale)"):
            for riga in cal.RIFERIMENTI_CO:
                st.markdown(f"- {riga}")
            st.caption("Sintesi di riferimento: verifica sempre il testo aggiornato del CO.")

    # ── salario ──
    st.markdown("## Salario")
    etichetta = "Salario orario di base (CHF all'ora)" if ore_contratto else "Salario fisso mensile (CHF)"
    f["salario"] = st.number_input(etichetta, min_value=0.0, value=float(F.get("salario", 0.0)), step=0.05 if ore_contratto else 50.0,
                                   format="%.2f", key=_k(p, "salario"))
    tredicesima_facolt = tipo in (cal.CPC, cal.INDIVIDUALE)      # per questi contratti la tredicesima non è obbligatoria
    if tipo == cal.STANDARD:
        a, b = st.columns(2)
        mens = ["12 mensilità", "13 mensilità"]
        scelta_m = a.radio("Mensilità", mens, index=1 if F.get("tredicesima") == "annuale" else 0, horizontal=True, key=_k(p, "mens_std"))
        f["tredicesima"] = "annuale" if scelta_m.startswith("13") else "nessuna"
        f["bonus"] = b.number_input("Bonus mensile (CHF, facoltativo)", min_value=0.0, value=float(F.get("bonus", 0.0)), step=50.0,
                                    format="%.2f", key=_k(p, "bonus"))
    elif not ore_contratto:
        a, b = st.columns(2)
        opz = ["Mensile", "Annuale"] + (["Nessuna"] if tredicesima_facolt else [])
        scelta_t = a.radio("Tredicesima", opz, index=_idx(opz, (F.get("tredicesima") or "mensile").capitalize()), horizontal=True,
                           key=f"{_k(p, 'tred')}_{len(opz)}")
        f["tredicesima"] = scelta_t.lower()
        f["bonus"] = b.number_input("Bonus mensile (CHF, facoltativo)", min_value=0.0, value=float(F.get("bonus", 0.0)), step=50.0,
                                    format="%.2f", key=_k(p, "bonus"))
    else:
        f["bonus"] = st.number_input("Bonus orario (CHF, facoltativo)", min_value=0.0, value=float(F.get("bonus", 0.0)), step=0.05,
                                     format="%.2f", key=_k(p, "bonus_h"))
        if tredicesima_facolt:
            con13 = st.checkbox("Tredicesima 8,33% (sul solo salario di base)", value=(F.get("tredicesima") or "mensile") != "nessuna",
                                key=_k(p, "tred_h"))
            f["tredicesima"] = "mensile" if con13 else "nessuna"
        else:
            f["tredicesima"] = "mensile"
        a, b = st.columns(2)
        vdef = F.get("vac_pct") or pre["vf"]["vacanze_pct"] or 8.33
        fdef = F.get("fest_pct") if F.get("fest_pct") is not None else (pre["vf"]["festivita_pct"] or 0.0)
        if tipo == cal.PULIZIE and F.get("fest_pct") is None:
            riga_p = minimi.PULIZIE_2026.get(f.get("cat_ccl") or "")
            if riga_p:
                fdef = 1.35 if riga_p[2] else 3.58
        f["vac_pct"] = a.number_input("Indennità vacanze (% sul salario di base)", min_value=0.0, max_value=30.0, value=float(vdef),
                                      step=0.01, format="%.2f", key=f"{_k(p, 'vacpct')}_{vdef}")
        f["fest_pct"] = b.number_input("Indennità festività (%)", min_value=0.0, max_value=30.0, value=float(fdef), step=0.01,
                                       format="%.2f", key=f"{_k(p, 'festpct')}_{fdef}")
        pre_v = costruzione.costruisci(az, dip_full, tipo, f, adesso)["vf"]
        for nome_p, scelto, atteso in (("vacanze", f["vac_pct"], pre_v.get("vacanze_pct")), ("festività", f["fest_pct"], pre_v.get("festivita_pct"))):
            if atteso is None:
                continue
            if scelto < atteso - 0.005:
                st.error(f"Indennità {nome_p} {scelto:.2f}%: inferiore al {atteso:.2f}% previsto da questo contratto ({pre_v[nome_p if nome_p == 'vacanze' else 'festivita']}). "
                         "Correggi la percentuale.")
            elif scelto > atteso + 0.005:
                st.warning(f"Indennità {nome_p} {scelto:.2f}%: superiore al {atteso:.2f}% previsto dal contratto. Verifica che sia voluto.")
        if pre["vf"]["festivita_pct"] is None:
            st.warning("Per questo tipo di contratto la percentuale di festività non è fissata dal documento caricato: inseriscila tu.")
        elif tipo in cal.TIPI_CUMULATIVI:
            st.caption("Calcolo del CCL: festività sul salario di base, vacanze su (base + festività), tredicesima 8,33% sul totale. "
                       "Vacanze 4 settimane 8,33% / 5 settimane 10,64%; festività " +
                       ("3,58%." if tipo == cal.AUTORIMESSE else "1,35% (pulizie ordinarie) o 3,58% (altre categorie)."))
        elif tipo == cal.CPC:
            st.caption("Vacanze: percentuale del CCL (art. 31, nota 13). Festività 3,58%: ricavata dai 9 giorni festivi cantonali, "
                       "non scritta nel CCL parrucchieri: confermala o modificala.")

    pre = costruzione.costruisci(az, dip_full, tipo, f, adesso)
    if f["salario"] > 0 or pre["minimo"].stato == "nd":
        {"sotto": st.warning, "ok": st.success}.get(pre["minimo"].stato, st.info)(pre["minimo"].messaggio)

    # ── salario lordo AVS (sotto salario e tredicesima, sopra le trattenute) ──
    rl = pre["r"]
    parti = [f"salario {'orario ' if ore_contratto else 'fisso '}CHF {cpdf.chf(rl.salario_fisso)}"]
    if rl.bonus:
        parti.append(f"bonus CHF {cpdf.chf(rl.bonus)}")
    if rl.festivita:
        parti.append(f"festività CHF {cpdf.chf(rl.festivita)}")
    if rl.vacanze:
        parti.append(f"vacanze CHF {cpdf.chf(rl.vacanze)}")
    if rl.quota_13:
        parti.append(f"13a mensilità CHF {cpdf.chf(rl.quota_13)}")
    with st.container(key="box_lordo_avs"):
        st.markdown(f"<div class='lordo-box'><div class='lordo-et'>Salario lordo AVS{' (all’ora)' if ore_contratto else ' mensile'}</div>"
                    f"<div class='lordo-val'>CHF {cpdf.chf(rl.lordo_avs)}</div>"
                    f"<div class='lordo-det'>{' + '.join(parti)}</div></div>", unsafe_allow_html=True)

    # ── trattenute ──
    if tipo == cal.STANDARD:
        f.update(lpp_manuale=True, lpp=0.0, if_manuale=True, if_pct=0.0, vitto=0.0, altra=0.0, assegni=0.0, rimborsi=0.0, arrot=0.0)
        st.caption("Contratto standard: si indicano solo i valori lordi, senza trattenute.")
    else:
        st.markdown("## Trattenute")
        ali = pre["ali"]
        st.caption(f"Dalle Info aziendali: AVS/AI/IPG {ali.avs:g}% · AD {ali.ad:g}% · malattia (IGM, "
                   f"{'donna' if (dip_full.get('sesso') or '').lower().startswith('d') else 'uomo'}) {ali.igm:g}% · "
                   f"infortunio non professionale (LAINF) {ali.lainf:g}%.")
        a, b = st.columns(2)
        unita_lpp = " all'ora" if ore_contratto else " al mese"
        with a:
            if ore_contratto:
                st.text_input("LPP", value="Mensile", disabled=True, key=_k(p, "lpp_mensile_txt"))
                st.caption("L'LPP è su base mensile: non si conteggia nel salario orario.")
                f["lpp_manuale"], f["lpp"] = True, 0.0
            elif pre["piano1"] and not ore_contratto:
                lpp_man = st.checkbox("Inserisci l'LPP a mano", value=bool(F.get("lpp_manuale")), key=_k(p, "lpp_man"))
                f["lpp_manuale"] = lpp_man
                val = float(F.get("lpp", pre["lpp_sugg"])) if lpp_man else float(pre["lpp_sugg"])
                f["lpp"] = st.number_input("LPP (CHF)" + unita_lpp, min_value=0.0, value=val, step=1.0, format="%.2f", disabled=not lpp_man,
                                           key=f"{_k(p, 'lpp')}_{lpp_man}_{val}")
                if not lpp_man:
                    f["lpp"] = pre["lpp_sugg"]
                    st.caption(f"Automatico: Piano 1 Basis, {pre['lpp_pct_sugg']:g}% del salario assicurato (in base all'età).")
            else:
                f["lpp_manuale"] = True
                f["lpp"] = st.number_input("LPP (CHF)" + unita_lpp, min_value=0.0, value=float(F.get("lpp", 0.0)), step=1.0,
                                           format="%.2f", key=_k(p, "lpp_libero"))
        if az.get("lpp_link"):
            a.markdown(f"[Tabella / calcolatore della LPP]({az['lpp_link']})")
        with b:
            info = pre["info_if"]
            if pre["esente_if"]:
                st.number_input("Imposta alla fonte (%)", value=0.0, disabled=True, key=_k(p, "if_bloccata"))
                st.caption(info["motivo"])
                f["if_manuale"], f["if_pct"] = False, 0.0
            else:
                st.caption(f"Tariffa **{info['codice']}** — {info['spiegazione']}")
                if pre["nota_front"]:
                    st.caption(pre["nota_front"])
                auto = info["aliquota"]
                man = st.checkbox("Inserisci l'aliquota a mano", value=bool(F.get("if_manuale")) or auto is None,
                                  disabled=auto is None, key=_k(p, "if_man"))
                f["if_manuale"] = man
                val = float(F.get("if_pct", 0.0)) if man else float(auto or 0.0)
                f["if_pct"] = st.number_input("Imposta alla fonte (%)", min_value=0.0, max_value=60.0, value=val, step=0.1, format="%.2f",
                                              disabled=not man, key=f"{_k(p, 'if')}_{man}_{info['codice']}_{val}")
                if not man:
                    f["if_pct"] = float(auto or 0.0)
                    st.caption(f"Automatica dalle tabelle del Cantone Ticino 2026 (reddito annuo determinante CHF {pre['prelim'].lordo_annuo:,.0f}).".replace(",", "'"))
            st.markdown(f"[Calcolatore dell'imposta alla fonte (Ticino)]({fonte.LINK_CALCOLATORE})")
        a, b = st.columns(2)
        f["vitto"] = a.number_input("Vitto e alloggio (CHF)", min_value=0.0, value=float(F.get("vitto", 0.0)), step=10.0, format="%.2f", key=_k(p, "vitto"))
        f["altra"] = b.number_input("Altra trattenuta (CHF)", min_value=0.0, value=float(F.get("altra", 0.0)), step=10.0, format="%.2f", key=_k(p, "altra"))
        if f["vitto"] > 0 and tipo in (cal.CCNL, cal.INDIVIDUALE):
            prest = list(cal.PRESTAZIONI_VITTO_AVS)
            f["vitto_prest"] = st.selectbox("Che cosa copre la trattenuta?", prest, index=_idx(prest, F.get("vitto_prest"), len(prest) - 1),
                                            key=_k(p, "vitto_prest"))
        f["altra_nome"] = st.text_input("Descrizione dell'altra trattenuta (es. cure medico-sanitarie)", value=F.get("altra_nome", ""),
                                        key=_k(p, "altra_nome")) if f["altra"] else ""
        if tipo == cal.AUTOTRASPORTI:
            cm = cal.commissione_paritetica_autotrasporti(f.get("percentuale", 100.0) if not ore_contratto else 100)
            st.caption(f"Commissione paritetica (art. 37 CCL): CHF {cm:.2f} al mese" + (" (non inclusa nel conteggio orario)." if ore_contratto else ", aggiunta in automatico."))

        if tipo == cal.AUTORIMESSE:
            st.caption(f"Contributo paritetico (art. 38.2 CCL): CHF {cal.CONTRIBUTO_PARITETICO_AUTORIMESSE:.2f} al mese"
                       + (" (non incluso nel conteggio orario)." if ore_contratto else ", aggiunto in automatico."))
        elif tipo == cal.PULIZIE:
            st.caption("Contributo paritetico: 0,6% del salario AVS (0,4% applicazione CCL + 0,2% formazione continua), aggiunto in automatico.")

        # ── assegni e rimborsi ──
        st.markdown("## Assegni e rimborsi")
        a, b, c3 = st.columns(3)
        f["assegni"] = a.number_input("Assegni per figli (CHF)", min_value=0.0, value=float(F.get("assegni", 0.0)), step=10.0, format="%.2f", key=_k(p, "assegni"))
        f["rimborsi"] = b.number_input("Altri rimborsi (CHF)", min_value=0.0, value=float(F.get("rimborsi", 0.0)), step=10.0, format="%.2f", key=_k(p, "rimborsi"))
        f["arrot"] = c3.number_input("Arrotondamenti (CHF)", value=float(F.get("arrot", 0.0)), step=0.05, format="%.2f", key=_k(p, "arrot"))
        if tipo == cal.AUTOTRASPORTI:
            opz = list(cal.FORFAIT_TRASFERTA)
            f["trasferta"] = st.radio("Indennità di trasferta forfettaria (non soggetta a trattenute, art. 13.2 CCL)", opz,
                                      index=_idx(opz, F.get("trasferta")), key=_k(p, "trasf"))
        elif tipo == cal.AUTORIMESSE:
            f["trasferta_importo"] = st.number_input("Indennità di trasferta (CHF al mese, non soggetta a trattenute)", min_value=0.0,
                                                     value=float(F.get("trasferta_importo", 0.0)), step=10.0, format="%.2f", key=_k(p, "trasf_ar"))
        elif tipo == cal.PULIZIE:
            f["vestiario_importo"] = st.number_input("Indennità per biancheria e vestiario di lavoro (CHF al mese)", min_value=0.0,
                                                     value=float(F.get("vestiario_importo", 0.0)), step=5.0, format="%.2f", key=_k(p, "vest_pul"))
        elif tipo == cal.CCNL and not ore_contratto:
            st.markdown("**Rimborsi settoriali (non soggetti a trattenute, art. 30 CCNL)**")
            salvati = F.get("ccnl_rimb", [])
            f["ccnl_rimb"] = [st.checkbox(f"{et}: CHF {imp:.2f} al mese", value=bool(salvati[i]) if i < len(salvati) else False,
                                          key=_k(p, f"rimbccnl{i}")) for i, (et, imp) in enumerate(cal.RIMBORSI_CCNL)]
        if ore_contratto and (f["assegni"] or f.get("trasferta", "Nessuno") != "Nessuno" or f.get("trasferta_importo") or f.get("vestiario_importo") or any(f.get("ccnl_rimb", []))):
            st.info("Contratto a ore: assegni per figli e rimborsi settoriali sono importi mensili, pagati a parte; "
                    "non entrano nel salario netto orario.")

    # ── conteggio finale ──
    esito = costruzione.costruisci(az, dip_full, tipo, f, adesso)
    r, controlli = esito["r"], esito["controlli"]
    if tipo == cal.STANDARD:
        controlli = []
    if controlli:
        st.markdown("##### Controlli sul conteggio")
        for livello, testo in controlli:
            (st.error if livello == "errore" else st.warning)(testo)

    if tipo == cal.STANDARD:
        with st.container(key="riepilogo_verde", border=True):
            st.markdown("##### Riepilogo")
            c1_, c2_, _ = st.columns(3)
            c1_.markdown(_cella("Salario lordo AVS mensile", f"CHF {cpdf.chf(r.lordo_avs)}", "#15803D", True), unsafe_allow_html=True)
            c2_.markdown(_cella("Mensilità", str(esito["contratto"]["n_mensilita"])), unsafe_allow_html=True)
    else:
        with st.container(key="riepilogo_verde", border=True):
            st.markdown("##### Riepilogo")
            info = esito["info_if"]
            riga1 = st.columns(3)
            riga1[0].markdown(_cella("Salario lordo AVS", f"CHF {cpdf.chf(r.lordo_avs)}"), unsafe_allow_html=True)
            riga1[1].markdown(_cella("Trattenute totali", f"CHF {cpdf.chf(r.totale_deduzioni)}"), unsafe_allow_html=True)
            riga1[2].markdown(_cella("Salario netto", f"CHF {cpdf.chf(r.netto)}", "#15803D", True), unsafe_allow_html=True)
            riga2 = st.columns(3)
            riga2[0].markdown(_cella("Tariffa imposta alla fonte", info["codice"] if esito["if_pct"] or info["dovuta"] else "—"), unsafe_allow_html=True)
            riga2[1].markdown(_cella("Aliquota imposta alla fonte", f"{r.imposta_fonte_pct:g}%"), unsafe_allow_html=True)
            riga2[2].markdown(_cella("Reddito annuo determinante", f"CHF {cpdf.chf(r.lordo_annuo)}"), unsafe_allow_html=True)
            st.caption("Annuo = lordo × 12 (tredicesima mensile o assente) o × 13 (annuale); contratti a ore: lordo orario × 2160.")

    # ── accordi e segretezza (sotto il riepilogo) ──
    st.markdown("## Accordi e segretezza")
    f["accordi"] = st.text_area("Accordi particolari (facoltativi)", value=F.get("accordi", ""), key=_k(p, "accordi"))
    segr_opz = ["Sì", "No"]
    f["segretezza"] = st.radio("Aggiungere la dichiarazione di segretezza e non concorrenza come ultima pagina?", segr_opz,
                               index=_idx(segr_opz, "Sì" if F.get("segretezza") else "No", 1), horizontal=True, key=_k(p, "segr")) == "Sì"

    # ── data di firma: penultima cosa da inserire ──
    st.markdown("## Data di firma")
    senza = st.checkbox("Non inserire la data di firma (la scrivono a mano il datore di lavoro e il dipendente)",
                        value=bool(F.get("senza_data")), key=_k(p, "senza_data"))
    firma = st.date_input("Data di firma del contratto", value=a_data(F.get("firma")) or adesso, format="DD/MM/YYYY",
                          min_value=dd.MIN_DATA, max_value=dd.MAX_DATA, disabled=senza, key=f"{_k(p, 'firma')}_{senza}")
    f["senza_data"] = senza
    f["firma"] = None if senza else da_data(firma)
    esito = costruzione.costruisci(az, dip_full, tipo, f, adesso)

    contratto = esito["contratto"]
    contratto["dip"] = dip_full
    mancanti = []
    if not dati_dip["nome"] or not dati_dip["cognome"]:
        mancanti.append("nome e cognome del dipendente")
    if f["salario"] <= 0:
        mancanti.append("il salario")
    if durata == cal.DETERMINATO and fine is None:
        mancanti.append("la data di fine")
    # il PDF si crea solo quando serve (clic su «Scarica PDF» o «Salva contratto»), non a ogni modifica del modulo
    errore_pdf = None if cpdf.modello_disponibile(tipo, durata) else "Modello PDF non disponibile per questo contratto."

    def _crea_pdf() -> bytes:
        return cpdf.genera_pdf(contratto)

    # ── pulsanti ──
    st.write("")
    c1, c2, _ = st.columns([1.3, 1.3, 2])
    with c1:
        with st.container(key="verde_salva_contratto"):
            salva = st.button("Salva contratto", key="ct_salva", disabled=bool(mancanti))
    with c2:
        nome_file = f"Contratto_{dati_dip['cognome']}_{dati_dip['nome']}_{f['inizio']}.pdf".replace(" ", "_")
        st.download_button("Scarica PDF", data=_crea_pdf, file_name=nome_file, mime="application/pdf",
                           key="ct_scarica", disabled=bool(mancanti) or bool(errore_pdf))
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
        try:
            pdf_bytes = None if (mancanti or errore_pdf) else _crea_pdf()
        except Exception as e:  # un modello PDF non leggibile non deve bloccare il salvataggio dei dati
            pdf_bytes, errore_pdf = None, f"Impossibile creare il PDF ({type(e).__name__}: {e})"
        allegato_id = db.aggiungi_allegato(az["id"], dip_id, nome_file, pdf_bytes, "contratto") if pdf_bytes else None
        registro = {
            "id": (salvato or {}).get("id") or nuovo_id(), "tipo": tipo, "durata": durata, "funzione": f["funzione"],
            "data_inizio": f["inizio"], "data_fine": f["fine"], "percentuale": f.get("percentuale", 100.0),
            "ore_settimanali": esito["ore_sett"], "salario_fisso": f["salario"], "tredicesima": f.get("tredicesima"),
            "calcolo": dataclasses.asdict(r), "segretezza": f["segretezza"], "allegato_id": allegato_id,
            "creato": da_data(adesso), "form": f, "valori": esito["valori"],
        }
        if salvato:
            db.sostituisci_contratto(az["id"], dip_id, registro["id"], registro, esito["valori"])
        else:
            db.registra_contratto(az["id"], dip_id, registro, esito["valori"])
        # si resta in questa pagina: i salvataggi successivi aggiornano lo stesso contratto
        st.session_state["ct_sel"] = {**sel, "dip_id": dip_id, "contratto_id": registro["id"]}
        st.session_state["ct_msg"] = "Contratto salvato." + ("" if allegato_id else " (PDF non disponibile: salvati solo i dati.)")
        st.session_state["ct_ultimo"] = (az["id"], dip_id)
        st.rerun()

    if st.session_state.get("ct_msg"):
        st.success(st.session_state["ct_msg"])
        az_ult, dip_ult = st.session_state.get("ct_ultimo", (az["id"], sel.get("dip_id")))
        b1, b2, _ = st.columns([1.5, 1.5, 2])
        with b1:
            if st.button("Vai al dipendente", key="ct_vai_dip", type="primary"):
                st.session_state.pop("ct_msg", None)
                st.session_state.pop("ct_sel", None)
                vai("dipendente", azienda_id=az_ult, dipendente_id=dip_ult)
        with b2:
            if st.button("Nuovo contratto", key="ct_nuovo", type="primary"):
                st.session_state.pop("ct_msg", None)
                st.session_state.pop("ct_sel", None)
                nuova_entrata("ct")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════
def render() -> None:
    intestazione(NOME_STUDIO, "Crea contratto")
    sel = st.session_state.get("ct_sel")
    mod = st.session_state.pop("ct_modifica", None)     # arriva dal tasto «Modifica contratto» della scheda dipendente
    if mod and not sel:
        az_id, dip_id, ct_id = mod[:3]
        dip = db.get_dipendente(az_id, dip_id) or {}
        contratto = next((c for c in dip.get("contratti", []) if c.get("id") == ct_id), None)
        if contratto:
            chiave = "copia_da" if (len(mod) > 3 and mod[3] == "copia") else "contratto_id"
            sel = {"azienda_id": az_id, "dip_id": dip_id, "tipo": contratto["tipo"], chiave: ct_id}
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
