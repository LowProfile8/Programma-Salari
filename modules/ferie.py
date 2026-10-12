"""modules/ferie.py — Tabelle vacanze e festività.

Si sceglie l'azienda e l'anno. Vacanze e festività si inseriscono con un pop-up (malattia e infortunio arrivano in automatico dalle buste paga):
«da giorno a giorno» oppure «numero di giorni» di un mese. Il riepilogo mostra i giorni per mese di ogni dipendente
(con cumulati dell'anno prima, usufruiti e residui per le ferie); il calendario mostra mese per mese giorno per giorno.
"""

import datetime as dt
import io

import pandas as pd
import streamlit as st

from core import db, ferie_calc as fc, ferie_pdf
from core.config import NOME_STUDIO
from core.nav import tasto_home, vai
from core.stile import intestazione
from core.util import nuovo_id, oggi

MIN_D, MAX_D = dt.date(1900, 1, 1), dt.date(oggi().year + 100, 12, 31)


def _nome(d: dict) -> str:
    return f"{d['cognome']} {d['nome']}" + (" (licenziato)" if d.get("stato") == "licenziato" else "")


def _salva(az_id: str, anno: int, dati: dict) -> None:
    az = db.get_azienda(az_id) or {}
    tutti = dict(az.get("ferie") or {})
    tutti[str(anno)] = dati
    db.aggiorna_azienda(az_id, {"ferie": tutti})


@st.dialog("Inserisci vacanze o festività")
def _dialogo(az_id: str, anno: int, dips: list[dict], dip_default: str | None, mese_default: int) -> None:
    ids = [d["id"] for d in dips]
    nomi = {d["id"]: _nome(d) for d in dips}
    dip = st.selectbox("Dipendente", ids, format_func=nomi.get, index=ids.index(dip_default) if dip_default in ids else 0, key="fe_dlg_dip")
    tipo = st.radio("Che cosa inserisci?", ["ferie", "festivita"], format_func=lambda t: fc.TIPI[t][0], horizontal=True, key="fe_dlg_tipo")
    g1, g2, _ = st.columns([1, 1, 2])
    with g1:
        with st.container(key="sec_dlg_mal"):
            st.button("Malattia", disabled=True, key="fe_dlg_mal", width="stretch")
    with g2:
        with st.container(key="sec_dlg_inf"):
            st.button("Infortunio", disabled=True, key="fe_dlg_inf", width="stretch")
    st.caption("Malattia e infortunio non si inseriscono qui: si prendono in automatico dalle buste paga.")
    modo = st.radio("Come vuoi indicarlo?", ["Da giorno a giorno", "Numero di giorni"], horizontal=True, key="fe_dlg_modo")
    ev = {"id": nuovo_id(), "dip": dip, "tipo": tipo}
    if modo == "Da giorno a giorno":
        c1, c2 = st.columns(2)
        base = dt.date(anno, mese_default, 1)
        dal = c1.date_input("Primo giorno", value=base, min_value=MIN_D, max_value=MAX_D, format="DD.MM.YYYY", key="fe_dlg_dal")
        al = c2.date_input("Ultimo giorno", value=base, min_value=MIN_D, max_value=MAX_D, format="DD.MM.YYYY", key="fe_dlg_al")
        n = (al - dal).days + 1 if al >= dal else 0
        st.caption(f"{n} giorni (si contano tutti i giorni di calendario, sabato e domenica compresi)." if n else "L'ultimo giorno è prima del primo.")
        ev.update(modo="periodo", dal=dal.isoformat(), al=al.isoformat())
        valido = n > 0
    else:
        c1, c2 = st.columns(2)
        mese = c1.selectbox("Mese", list(range(1, 13)), format_func=lambda m: fc.MESI[m - 1], index=mese_default - 1, key="fe_dlg_mese")
        n = c2.number_input("Numero di giorni", min_value=1, max_value=366, value=1, step=1, key="fe_dlg_n")
        ev.update(modo="numero", mese=int(mese), n=int(n))
        valido = True
    ev["nota"] = st.text_input("Nota (facoltativa)", key="fe_dlg_nota")
    if st.button("Salva", type="primary", key="fe_dlg_salva", disabled=not valido, width="stretch"):
        dati = fc.dati_anno(db.get_azienda(az_id) or {}, anno)
        dati["eventi"].append(ev)
        _salva(az_id, anno, dati)
        st.rerun()


def _tabella_riepilogo(az: dict, anno: int, dips: list[dict], tipo: str) -> pd.DataFrame:
    righe = []
    for d in dips:
        m = fc.conteggio_mesi(az, anno, d["id"], tipo)
        r = {"Dipendente": _nome(d)}
        if tipo == "ferie":
            ri = fc.riepilogo(az, anno, d["id"])
            r[f"Cumulati {anno - 1}"] = ri["cumulati"]
        for i, v in enumerate(m):
            r[fc.MESI[i][:3]] = v
        if tipo == "ferie":
            r[f"Usufruiti {anno}"] = ri["usufruiti"]
            r["Diritto annuo"] = ri["diritto"]
            r["Residui"] = ri["residui"]
        else:
            r[f"Totale {anno}"] = sum(m)
        righe.append(r)
    return pd.DataFrame(righe)


def _calendario(az: dict, anno: int, mese: int, dips: list[dict]) -> None:
    n = fc.giorni_nel_mese(anno, mese)
    testa = "".join(f"<th style='padding:2px 3px;min-width:22px;{'background:#EEF2F7;' if dt.date(anno, mese, g).weekday() >= 5 else ''}'>"
                    f"{g}<br><span style='font-weight:400;color:#6E6E73'>{fc.GIORNI_SETT[dt.date(anno, mese, g).weekday()]}</span></th>"
                    for g in range(1, n + 1))
    corpo = ""
    for d in dips:
        gr = fc.griglia_mese(az, anno, mese, d["id"])
        celle = ""
        for g in range(1, n + 1):
            weekend = dt.date(anno, mese, g).weekday() >= 5
            L = gr.get(g)
            colore = next((v[2] for v in fc.TIPI.values() if v[1] == L), "#EEF2F7" if weekend else "transparent")
            celle += f"<td style='text-align:center;background:{colore};border:1px solid #E5E9F0;font-weight:700;font-size:0.78rem'>{L or ''}</td>"
        tot = sum(fc.conteggio_mesi(az, anno, d["id"], t)[mese - 1] for t in fc.TIPI)
        corpo += (f"<tr><td style='padding:3px 8px;white-space:nowrap;font-size:0.85rem'>{_nome(d)}</td>{celle}"
                  f"<td style='text-align:center;font-weight:700;padding:0 6px'>{tot}</td></tr>")
    st.markdown(f"<div style='overflow-x:auto'><table style='border-collapse:collapse;font-size:0.78rem'><tr><th style='text-align:left;padding:3px 8px'>"
                f"{fc.MESI[mese - 1]} {anno}</th>{testa}<th style='padding:0 6px'>Tot.</th></tr>{corpo}</table></div>", unsafe_allow_html=True)
    st.caption("  ·  ".join(f"**{v[1]}** = {v[0]}" for v in fc.TIPI.values()) + "  ·  i giorni inseriti come «numero» compaiono solo nel totale  ·  M e I (grigi) arrivano dalle buste paga.")


def render() -> None:
    intestazione(NOME_STUDIO, "Tabelle vacanze e festività")
    if tasto_home("ferie"):
        vai("home")
    st.markdown("# Tabelle vacanze e festività")

    aziende = db.elenco_aziende()
    if not aziende:
        st.info("Per vedere la tabella serve almeno un'azienda in archivio.")
        return
    nomi = {a["id"]: db.nome_azienda(a) for a in aziende}
    c1, c2 = st.columns([3, 1])
    az_id = c1.selectbox("Seleziona l'azienda", list(nomi), index=None, format_func=lambda i: nomi[i],
                         placeholder="Scegli un'azienda", key="ferie_azienda")
    anni = list(range(oggi().year + 1, oggi().year - 6, -1))
    anno = c2.selectbox("Anno", anni, index=anni.index(oggi().year), key="ferie_anno")
    if az_id is None:
        return
    az = db.get_azienda(az_id)
    dips = db.ordina_dipendenti(az.get("dipendenti", []))
    if not dips:
        st.info("Questa azienda non ha ancora dipendenti.")
        return
    st.markdown(f"## {db.nome_azienda(az)} — {anno}")
    b1, b2, _ = st.columns([1.6, 2.2, 2])
    with b1:
        if st.button("＋ Inserisci vacanze / festività", key="fe_nuova", type="primary", width="stretch"):
            _dialogo(az_id, anno, dips, st.session_state.get("fe_dip_sel"), st.session_state.get("fe_mese", oggi().month))
    with b2:
        st.download_button("Scarica il PDF (vacanze e festività)", data=lambda: ferie_pdf.riepilogo_pdf(az, anno, dips),
                           file_name=f"Vacanze e festività {anno} - {db.nome_azienda(az)}.pdf",
                           mime="application/pdf", key=f"fe_pdf_{az_id}_{anno}", width="stretch")

    t_riep, t_cal, t_elenco = st.tabs(["Riepilogo annuale", "Calendario del mese", "Vacanze e festività inserite"])
    with t_riep:
        tipo = st.radio("Mostra", list(fc.TIPI), format_func=lambda t: fc.TIPI[t][0], horizontal=True, key="fe_tipo")
        df = _tabella_riepilogo(az, anno, dips, tipo)
        if tipo in fc.DA_BUSTE:
            st.caption(f"{fc.TIPI[tipo][0]}: giorni presi in automatico dalle buste paga salvate. Non si modificano qui: per cambiarli modifica la busta paga.")
            st.dataframe(df.style.set_properties(**{"background-color": "#ECEEF1", "color": "#6E6E73"}), hide_index=True, width="stretch")
        else:
            st.dataframe(df, hide_index=True, width="stretch")
        if tipo == "ferie":
            with st.expander("Cumulati dell'anno precedente e diritto annuo di vacanze"):
                st.caption(f"Giorni di vacanze riportati dal {anno - 1} e diritto dell'anno (di norma 35 giorni civili). Residui = cumulati + diritto − usufruiti.")
                dati = fc.dati_anno(az, anno)
                mod = False
                for d in dips:
                    a, b, _ = st.columns([2.2, 1, 1])
                    a.markdown(f"<div style='padding-top:0.5rem'>{_nome(d)}</div>", unsafe_allow_html=True)
                    cum = b.number_input("Cumulati", value=float(dati["cumulati"].get(d["id"]) or 0.0), step=0.5, key=f"fe_cum_{az_id}_{anno}_{d['id']}",
                                         label_visibility="collapsed")
                    dd = _.number_input("Diritto", value=float(dati["diritto"].get(d["id"]) if dati["diritto"].get(d["id"]) not in (None, "") else fc.DIRITTO_FERIE),
                                        step=0.5, key=f"fe_dir_{az_id}_{anno}_{d['id']}", label_visibility="collapsed")
                    if cum != float(dati["cumulati"].get(d["id"]) or 0.0) or dd != float(dati["diritto"].get(d["id"], fc.DIRITTO_FERIE) or 0.0):
                        dati["cumulati"][d["id"]], dati["diritto"][d["id"]] = cum, dd
                        mod = True
                if mod:
                    _salva(az_id, anno, dati)
                    st.rerun()
    with t_cal:
        mese = st.selectbox("Mese", list(range(1, 13)), index=min(oggi().month, 12) - 1 if anno == oggi().year else 0,
                            format_func=lambda m: fc.MESI[m - 1], key="fe_mese")
        _calendario(az, anno, mese, dips)
    with t_elenco:
        dati = fc.dati_anno(az, anno)
        if not dati["eventi"]:
            st.caption("Nessuna vacanza o festività inserita. Usa «＋ Inserisci vacanze / festività».")
        nomi_d = {d["id"]: _nome(d) for d in dips}
        for ev in sorted([e for e in dati["eventi"] if e.get("tipo") not in fc.DA_BUSTE], key=lambda e: (e.get("dal") or f"{anno}-{int(e.get('mese') or 1):02d}-01")):
            if ev.get("modo") == "numero":
                testo = f"{ev['n']} giorni a {fc.MESI[int(ev['mese']) - 1]}"
            else:
                a, b = fc._d(ev["dal"]), fc._d(ev["al"])
                testo = f"dal {a:%d.%m.%Y} al {b:%d.%m.%Y} ({(b - a).days + 1} giorni)"
            c1, c2, c3 = st.columns([2.3, 3.4, 0.9], vertical_alignment="center")
            c1.markdown(f"**{nomi_d.get(ev['dip'], '—')}**")
            c2.markdown(f"{fc.TIPI[ev['tipo']][0]} · {testo}" + (f" · {ev['nota']}" if ev.get("nota") else ""))
            with c3:
                with st.container(key=f"elimina_{ev['id']}"):
                    if st.button("Elimina", key=f"fe_del_{ev['id']}", width="stretch"):
                        dati["eventi"] = [e for e in dati["eventi"] if e["id"] != ev["id"]]
                        _salva(az_id, anno, dati)
                        st.rerun()
