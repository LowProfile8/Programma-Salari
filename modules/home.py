"""modules/home.py — homepage: un grande tasto «Archivio» e due riquadri quadrati,
«Crea contratto» e «Crea busta paga» (stessa impostazione della home del programma di riferimento)."""

import streamlit as st

from core import db
from core.config import NOME_STUDIO, SOTTOTITOLO
from core.nav import vai
from core.stile import intestazione

# Icone minimali a contorno (niente emoji, per un aspetto sobrio)
_SVG = (
    '<svg width="{d}" height="{d}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">{p}</svg>'
)
ICONA_CARTELLA = _SVG.format(
    d=32, c="#9333EA",
    p='<path d="M3 6.5a1 1 0 0 1 1-1h4.5l2 2H20a1 1 0 0 1 1 1V18a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>',
)
ICONA_CONTRATTO = _SVG.format(
    d=26, c="#2563EB",
    p='<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M9.5 12.5h5M9.5 15.5h5M9.5 9.5h2"/>',
)
ICONA_CALENDARIO = _SVG.format(
    d=26, c="#DC2626",
    p='<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18"/><path d="M8 3v4M16 3v4"/>'
      '<path d="M8 14h2M12 14h2M16 14h.01M8 17.5h2M12 17.5h2"/>',
)
ICONA_BUSTA = _SVG.format(
    d=26, c="#16A34A",
    p='<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 9h18"/><path d="M7 14h4"/>',
)


def _riquadro(chiave: str, titolo: str, descrizione: str, icona: str, colore: str, vista: str) -> None:
    with st.container(key=f"tile_{chiave}", border=True):
        st.markdown(f"<div class='tile-icona tile-icona-{colore}'>{icona}</div>", unsafe_allow_html=True)
        st.markdown(f"**{titolo}**")
        st.caption(descrizione)
        with st.container(key=f"freccia_{chiave}"):
            if st.button("→", key=f"home_{chiave}"):
                vai(vista)


def _ricerca() -> None:
    """Barra di ricerca in alto: trova aziende (ragione sociale, CHE) e dipendenti (nome, cognome)."""
    testo = st.text_input("Cerca", key="home_cerca", label_visibility="collapsed",
                          placeholder="Cerca un'azienda o un dipendente…")
    if not testo.strip():
        return
    aziende, dipendenti = db.cerca(testo)
    if not aziende and not dipendenti:
        st.caption("Nessun risultato.")
        return
    with st.container(border=True):
        for az in aziende[:8]:
            col_info, col_apri = st.columns([4, 1.2], vertical_alignment="center")
            with col_info:
                st.markdown(f"**{db.nome_azienda(az)}**")
                st.caption("Azienda" + (f" · {az['numero_che']}" if az.get("numero_che") else ""))
            with col_apri:
                if st.button("Apri", key=f"cerca_az_{az['id']}"):
                    vai("azienda_info", azienda_id=az["id"])
        for az, dip in dipendenti[:8]:
            col_info, col_apri = st.columns([4, 1.2], vertical_alignment="center")
            with col_info:
                st.markdown(f"**{dip['cognome']} {dip['nome']}**")
                st.caption(f"Dipendente · {db.nome_azienda(az)}")
            with col_apri:
                if st.button("Apri", key=f"cerca_dip_{dip['id']}"):
                    vai("dipendente", azienda_id=az["id"], dipendente_id=dip["id"])
        if len(aziende) > 8 or len(dipendenti) > 8:
            st.caption("Ci sono altri risultati: scrivi di più per restringere la ricerca.")


def render() -> None:
    intestazione(NOME_STUDIO, SOTTOTITOLO)
    _ricerca()
    st.write("")

    n_aziende = len(db.elenco_aziende())
    with st.container(key="home_archivio_card", border=True):
        col_testo, col_icona = st.columns([5, 1], vertical_alignment="center")
        with col_testo:
            st.markdown("<div class='hero-etichetta'>ARCHIVIO</div>", unsafe_allow_html=True)
            st.markdown("### Archivio clienti")
            st.write(
                "Aziende clienti, informazioni aziendali, dipendenti e buste paga. "
                f"Aziende in archivio: **{n_aziende}**."
            )
            if st.button("Apri l'archivio →", key="home_archivio", type="primary"):
                vai("archivio")
        with col_icona:
            st.markdown(
                "<div class='tile-icona tile-icona-viola' style='width:64px;height:64px;margin:0 auto;'>"
                f"{ICONA_CARTELLA}</div>",
                unsafe_allow_html=True,
            )

    st.write("")
    col1, col2, col3 = st.columns(3)
    with col1:
        _riquadro("contratto", "Crea contratto", "Nuovo contratto di lavoro.", ICONA_CONTRATTO, "blu", "contratto")
    with col2:
        _riquadro("busta", "Crea busta paga", "Busta paga mensile. In arrivo.", ICONA_BUSTA, "verde", "busta_paga")
    with col3:
        _riquadro("ferie", "Tabelle ferie e festività", "Ferie e festività per dipendente e mese.",
                  ICONA_CALENDARIO, "rosso", "ferie")
