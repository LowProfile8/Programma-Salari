"""core/stile.py — stesso stile del programma delle dichiarazioni fiscali (colori, font Inter,
sidebar blu scuro a overlay, card con bordo sottile, pulsanti azzurri). Un solo posto da cui
cambiare l'aspetto di tutta l'app.

Convenzione pulsanti: chiave (key) di un contenitore che inizia per "sec_" -> pulsante grigio
(azioni secondarie: Elimina, Annulla...). "freccia_" -> pulsante circolare «→» delle card.
"""

import streamlit as st

COLORI = {
    "ACCENTO": "#4BA3F7",
    "ACCENTO_SCURO": "#3593EC",
    "ACCENTO_TESTO": "#0A66C2",
    "GRIGIO_BTN": "#E6E7EB",
    "GRIGIO_BTN_HOVER": "#D9DBE1",
    "TESTO": "#1D1D1F",
    "TESTO_SECONDARIO": "#6E6E73",
    "BORDO": "#E5E5E7",
    "BORDO_CAMPO": "#DADDE3",
    "SFONDO_SELEZIONE": "#E4F1FE",
    "SFONDO_HOVER": "#F2F8FE",
    "SFONDO_CARD": "#FFFFFF",
    "SFONDO_PAGINA": "#FBFBFD",
    "SIDEBAR_SFONDO": "#0D2140",
    "SIDEBAR_ATTIVO": "#2862B4",
    "SIDEBAR_TESTO": "#C7D2E6",
    "BLU_HOME": "#2862B4",
    "BLU_HOME_HOVER": "#1F4F98",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background-color: __SFONDO_PAGINA__ !important;
}

/* ── Barra laterale: overlay sopra la pagina, il contenuto centrale resta fermo ── */
[data-testid="stSidebar"] {
  background-color: __SIDEBAR_SFONDO__ !important;
  position: fixed !important; top: 0 !important; left: 0 !important; height: 100vh !important;
  z-index: 999999 !important; box-shadow: 4px 0 24px rgba(0,0,0,0.25);
}
[data-testid="stAppViewContainer"] {
  margin-left: 0 !important; padding-left: 0 !important; transform: none !important;
}
section[data-testid="stMain"], div[data-testid="stMain"], .main {
  margin-left: 0 !important; padding-left: 0 !important; left: 0 !important;
  transform: none !important; width: 100% !important; position: relative !important;
}
[data-testid="stSidebarCollapsedControl"] { z-index: 1000000 !important; }
[data-testid="stSidebar"] * { color: __SIDEBAR_TESTO__ !important; text-align: left !important; }
[data-testid="stSidebar"] h3 { color: #FFFFFF !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12) !important; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  color: #8FA3C4 !important; font-weight: 700 !important; letter-spacing: 0.04em;
}
[data-testid="stSidebar"] .stButton > button {
  background-color: transparent !important; border: none !important; color: __SIDEBAR_TESTO__ !important;
  font-weight: 500 !important; padding: 0.5rem 0.7rem !important; border-radius: 8px !important;
  display: flex !important; justify-content: flex-start !important; text-align: left !important;
}
[data-testid="stSidebar"] .stButton > button > div,
[data-testid="stSidebar"] .stButton > button [data-testid="stMarkdownContainer"] {
  display: flex !important; justify-content: flex-start !important; width: 100% !important;
}
[data-testid="stSidebar"] .stButton > button p { color: __SIDEBAR_TESTO__ !important; width: 100%; }
[data-testid="stSidebar"] .stButton > button:hover { background-color: rgba(255,255,255,0.08) !important; }
[data-testid="stSidebar"] .stButton > button:hover p { color: #FFFFFF !important; }
[data-testid="stSidebar"] .st-key-side_attivo .stButton > button { background-color: __SIDEBAR_ATTIVO__ !important; }
[data-testid="stSidebar"] .st-key-side_attivo .stButton > button p { color: #FFFFFF !important; font-weight: 600 !important; }

/* ── Titoli: gerarchia netta, mai blu ── */
h1 { font-weight: 800 !important; font-size: 2.4rem !important; color: __TESTO__ !important;
     letter-spacing: -0.03em; margin-bottom: 0.3rem !important; }
h2 { font-weight: 700 !important; font-size: 1.5rem !important; color: __TESTO__ !important;
     letter-spacing: -0.02em; margin-top: 2.2rem !important; }
h3, h4, h5 { font-weight: 600 !important; color: __TESTO__ !important; }
label, .stMarkdown, .stMarkdown p, .stMarkdown li, .stCaption, p, li { color: __TESTO__ !important; }
.stCaption p, [data-testid="stCaptionContainer"] p { color: __TESTO_SECONDARIO__ !important; }
.testo-hero { font-size: 1.15rem; line-height: 1.6; color: __TESTO_SECONDARIO__; max-width: 640px; margin-bottom: 2.5rem; }

/* ── Intestazione dello studio ── */
.intestazione-studio {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1.1rem 0 1.3rem 0; margin-bottom: 1.4rem; border-bottom: 1px solid __BORDO__;
}
.intestazione-studio .nome-studio { font-size: 0.95rem; font-weight: 800; color: __TESTO__; letter-spacing: -0.01em; }
.intestazione-studio .sottotitolo { font-size: 0.8rem; color: __TESTO_SECONDARIO__; }

/* ── Schede ── */
div[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 16px !important; border: 1px solid __BORDO__ !important;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03); background-color: __SFONDO_CARD__; padding: 0.4rem;
}
[data-testid="stForm"] { border: 1px solid __BORDO__ !important; border-radius: 16px !important; background: __SFONDO_CARD__; }

/* ── Pulsanti: azzurri; grigi se il contenitore ha chiave "sec_..." ── */
.stButton > button, [data-testid="stFormSubmitButton"] > button, .stDownloadButton > button {
  border-radius: 10px; font-weight: 600; padding: 0.5rem 1.3rem;
  background-color: __ACCENTO__ !important; border: 1px solid __ACCENTO__ !important;
  color: #FFFFFF !important; white-space: nowrap;
}
.stButton > button:hover, .stButton > button:focus, .stButton > button:focus-visible, .stButton > button:active,
[data-testid="stFormSubmitButton"] > button:hover, [data-testid="stFormSubmitButton"] > button:focus {
  background-color: __ACCENTO_SCURO__ !important; border-color: __ACCENTO_SCURO__ !important;
  color: #FFFFFF !important; box-shadow: none !important; outline: none !important;
}
.stButton > button p, [data-testid="stFormSubmitButton"] > button p { color: #FFFFFF !important; }
.stButton > button:disabled { opacity: 0.45; }
[class*="st-key-sec_"] .stButton > button {
  background-color: __GRIGIO_BTN__ !important; border-color: __GRIGIO_BTN__ !important; color: #3C3C43 !important;
}
[class*="st-key-sec_"] .stButton > button:hover, [class*="st-key-sec_"] .stButton > button:active {
  background-color: __GRIGIO_BTN_HOVER__ !important; border-color: __GRIGIO_BTN_HOVER__ !important; color: #1D1D1F !important;
}
[class*="st-key-sec_"] .stButton > button p { color: #3C3C43 !important; }
/* tasto «Home»: blu pieno con scritta bianca, uguale in tutte le pagine */
[class*="st-key-btnhome_"] .stButton > button {
  background-color: __BLU_HOME__ !important; border-color: __BLU_HOME__ !important; color: #FFFFFF !important;
}
[class*="st-key-btnhome_"] .stButton > button:hover, [class*="st-key-btnhome_"] .stButton > button:focus {
  background-color: __BLU_HOME_HOVER__ !important; border-color: __BLU_HOME_HOVER__ !important;
}
[class*="st-key-btnhome_"] .stButton > button p { color: #FFFFFF !important; }
/* tasti di eliminazione: rosso, piccoli, bordo rosso scuro e fondo rosso chiaro */
[class*="st-key-elimina_"] .stButton > button {
  background-color: #FEE4E2 !important; border: 1.5px solid #B42318 !important; color: #B42318 !important;
  padding: 0.2rem 0.8rem !important; font-size: 0.82rem !important; min-height: 0 !important;
}
[class*="st-key-elimina_"] .stButton > button:hover, [class*="st-key-elimina_"] .stButton > button:focus {
  background-color: #FECDCA !important; border-color: #912018 !important; color: #912018 !important;
}
[class*="st-key-elimina_"] .stButton > button p { color: inherit !important; font-size: 0.82rem !important; }
/* pop-up «Modifiche non salvate»: compatto */
[data-testid="stDialog"] h2, div[role="dialog"] h2 { font-size: 1.05rem !important; margin: 0 0 0.2rem 0 !important; letter-spacing: 0; }
[data-testid="stDialog"] div[role="dialog"] { padding: 1.2rem 1.4rem !important; }
/* riepiloghi numerici: cifre piccole, mai tagliate */
[data-testid="stMetricValue"], [data-testid="stMetricValue"] > div { font-size: 1.05rem !important; white-space: normal !important; line-height: 1.25; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p { font-size: 0.74rem !important; white-space: normal !important; }
/* tasto giallo «Modifica contratto» */
[class*="st-key-giallo_"] .stButton > button {
  background-color: #FEF9C3 !important; border: 1.5px solid #A16207 !important; color: #A16207 !important;
  padding: 0.2rem 0.8rem !important; font-size: 0.82rem !important; min-height: 0 !important;
}
[class*="st-key-giallo_"] .stButton > button:hover { background-color: #FEF08A !important; border-color: #854D0E !important; color: #854D0E !important; }
[class*="st-key-giallo_"] .stButton > button p { color: inherit !important; font-size: 0.82rem !important; }
.tile-icona-arancio { background: #FFEDD5; }
/* riepilogo del contratto: bordo verde */
.st-key-riepilogo_verde, .st-key-riepilogo_verde > [data-testid="stVerticalBlockBorderWrapper"] {
  border: 2px solid #16A34A !important; border-radius: 16px !important;
}
.lordo-box { background: #EAF4FF; border: 2px solid #4BA3F7; border-radius: 16px; padding: 14px 18px; margin: 6px 0 4px 0; }
.lordo-et { font-size: 0.8rem; font-weight: 600; color: #0D2140; text-transform: uppercase; letter-spacing: .04em; }
.lordo-val { font-size: 1.5rem; font-weight: 800; color: #0D2140; line-height: 1.2; }
.lordo-det { font-size: 0.82rem; color: #4A5568; margin-top: 2px; }
/* niente barre/scheletri di caricamento di Streamlit (capsule azzurre vuote) */
[data-testid="stSkeleton"], [data-testid="stSkeletonElement"], [data-testid="stAppSkeleton"] { display: none !important; }
.st-key-home_archivio_card[data-stale="true"], [data-stale="true"] .st-key-home_archivio_card { display: none !important; }
/* stato del cloud: sempre in basso a sinistra della pagina */
.cloud-fisso { position: fixed; left: 14px; bottom: 12px; z-index: 1000001; display: flex; align-items: center; gap: 8px;
  background: #0D2140; color: #FFFFFF; font-size: 0.8rem; font-weight: 600; padding: 6px 12px; border-radius: 999px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.25); }
/* rettangolo ferie: testo e freccia centrati in verticale */
.st-key-home_ferie_card [data-testid="stHorizontalBlock"] { align-items: center !important; }
.st-key-home_ferie_card [data-testid="stColumn"] { display: flex; flex-direction: column; justify-content: center; }
.st-key-home_ferie_card [data-testid="stElementContainer"], .st-key-home_ferie_card [data-testid="stMarkdownContainer"] { margin: 0 !important; }
.st-key-freccia_ferie [data-testid="stButton"] { display: flex !important; justify-content: flex-end !important; width: 100% !important; }
.st-key-freccia_ferie, .st-key-freccia_ferie [data-testid="stElementContainer"] { width: 100%; display: flex; justify-content: flex-end; }
/* barra laterale: stato del cloud sempre in basso */
.st-key-stato_cloud { margin-top: auto; padding-top: 1.5rem; }
.cloud-riga { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; font-weight: 600; }
.cloud-pallino { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.cloud-verde { background: #22C55E; box-shadow: 0 0 0 3px rgba(34,197,94,0.25); }
.cloud-giallo { background: #FACC15; box-shadow: 0 0 0 3px rgba(250,204,21,0.25); }
/* «Scheda anagrafica»: viola */
[class*="st-key-viola_"] .stButton > button { background-color: #7C3AED !important; border-color: #7C3AED !important; color: #FFFFFF !important; }
[class*="st-key-viola_"] .stButton > button:hover { background-color: #6D28D9 !important; border-color: #6D28D9 !important; }
[class*="st-key-viola_"] .stButton > button p { color: #FFFFFF !important; }
/* Scarica PDF dentro i contratti: stessa grandezza di Modifica ed Elimina, colore azzurro */
[class*="st-key-azzurro_"] .stButton > button, [class*="st-key-azzurro_"] .stDownloadButton > button {
  background-color: #DBEAFE !important; border: 1.5px solid #1D4ED8 !important; color: #1D4ED8 !important;
  padding: 0.2rem 0.8rem !important; font-size: 0.82rem !important; min-height: 0 !important;
}
[class*="st-key-azzurro_"] .stDownloadButton > button:hover { background-color: #BFDBFE !important; border-color: #1E40AF !important; }
[class*="st-key-azzurro_"] .stButton > button p, [class*="st-key-azzurro_"] .stDownloadButton > button p { color: inherit !important; font-size: 0.82rem !important; }
/* tasti di salvataggio verdi: bordo verde scuro, fondo verde chiaro */
[class*="st-key-verde_"] .stButton > button {
  background-color: #DCFCE7 !important; border: 1.5px solid #15803D !important; color: #15803D !important;
}
[class*="st-key-verde_"] .stButton > button:hover, [class*="st-key-verde_"] .stButton > button:focus {
  background-color: #BBF7D0 !important; border-color: #166534 !important; color: #166534 !important;
}
[class*="st-key-verde_"] .stButton > button p { color: inherit !important; }
/* pop-up «Vuoi salvare?»: il testo dei tasti va a capo invece di uscire dal tasto */
[data-testid="stDialog"] .stButton > button, div[role="dialog"] .stButton > button {
  white-space: normal !important; line-height: 1.2 !important; padding: 0.45rem 0.5rem !important;
  min-height: 3rem; font-size: 0.88rem !important; overflow-wrap: anywhere;
}
[data-testid="stDialog"] .stButton > button p, div[role="dialog"] .stButton > button p {
  white-space: normal !important; font-size: 0.88rem !important; text-align: center;
}
/* «Licenzia dipendente»: arancione, stesso formato dei tasti di eliminazione */
[class*="st-key-licenzia_"] .stButton > button {
  background-color: #FFEDD5 !important; border: 1.5px solid #C2410C !important; color: #C2410C !important;
  padding: 0.2rem 0.8rem !important; font-size: 0.82rem !important; min-height: 0 !important;
}
[class*="st-key-licenzia_"] .stButton > button:hover, [class*="st-key-licenzia_"] .stButton > button:focus {
  background-color: #FED7AA !important; border-color: #9A3412 !important; color: #9A3412 !important;
}
[class*="st-key-licenzia_"] .stButton > button p { color: inherit !important; font-size: 0.82rem !important; }
/* dipendente licenziato nell'elenco: bordo rosso */
[class*="st-key-licenziato_"], [class*="st-key-licenziato_"] > [data-testid="stVerticalBlockBorderWrapper"] {
  border: 1.6px solid #D92D20 !important; border-radius: 16px !important;
}
/* pulsante circolare «→» delle card della home */
[class*="st-key-freccia_"] .stButton > button {
  width: 42px !important; height: 42px !important; border-radius: 50% !important;
  padding: 0 !important; font-size: 1.1rem !important; line-height: 1 !important;
}

/* ── Selezioni: blu invece del rosso predefinito ── */
[data-baseweb="tag"] { background-color: __ACCENTO__ !important; color: #FFFFFF !important; }
[data-baseweb="checkbox"] span[aria-checked="true"], label[data-baseweb="checkbox"] > span:first-child {
  background-color: __ACCENTO__ !important; border-color: __ACCENTO__ !important;
}
[data-baseweb="radio"] div[role="radio"][aria-checked="true"] > div { background-color: __ACCENTO__ !important; border-color: __ACCENTO__ !important; }
a, a:hover { color: __ACCENTO_TESTO__ !important; }

/* ── Caselle di inserimento: bianche, un solo bordo sottile e chiaro ── */
div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div {
  background-color: #FFFFFF !important; border: 1px solid __BORDO_CAMPO__ !important;
  border-radius: 10px !important; box-shadow: none !important; outline: none !important; color: __TESTO__ !important;
}
div[data-baseweb="base-input"] { background-color: transparent !important; border: none !important; box-shadow: none !important; }
.stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea {
  background-color: transparent !important; color: __TESTO__ !important; border: none !important; box-shadow: none !important; outline: none !important;
}
div[data-baseweb="input"]:hover, div[data-baseweb="textarea"]:hover, div[data-baseweb="select"]:hover > div { border-color: #C4C9D1 !important; }
div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within, div[data-baseweb="select"]:focus-within > div {
  border-color: __ACCENTO__ !important; box-shadow: 0 0 0 3px rgba(75,163,247,0.16) !important;
}
div[data-baseweb="select"] span, div[data-baseweb="select"] div { color: __TESTO__ !important; }
.stNumberInput button { background-color: transparent !important; color: __TESTO_SECONDARIO__ !important; border: none !important; }

/* ── Menu a tendina: bianco, selezione azzurra ── */
[data-baseweb="popover"] > div, [data-baseweb="popover"] [data-baseweb="menu"], [data-baseweb="popover"] ul {
  background-color: #FFFFFF !important; color: __TESTO__ !important;
}
[data-baseweb="popover"] > div { border: 1px solid __BORDO_CAMPO__ !important; border-radius: 12px !important; box-shadow: 0 10px 30px rgba(0,0,0,0.10) !important; }
li[role="option"] { background-color: #FFFFFF !important; color: __TESTO__ !important; }
li[role="option"] div, li[role="option"] span { background-color: transparent !important; color: inherit !important; }
li[role="option"]:hover, li[role="option"][data-highlighted="true"] { background-color: __SFONDO_HOVER__ !important; color: __ACCENTO_TESTO__ !important; }
li[role="option"][aria-selected="true"] { background-color: __SFONDO_SELEZIONE__ !important; color: __ACCENTO_TESTO__ !important; font-weight: 600; }
[data-baseweb="calendar"], [data-baseweb="calendar"] div { background-color: #FFFFFF; color: __TESTO__; }
[data-baseweb="calendar"] [aria-selected="true"], [data-baseweb="calendar"] [aria-selected="true"] div { background-color: __ACCENTO__ !important; color: #FFFFFF !important; }
[data-testid="InputInstructions"] { display: none !important; }
div[data-testid="stAlertContainer"] { border-radius: 12px; }

/* ── Home: card grande «Archivio» e due riquadri quadrati ── */
.hero-etichetta {
  display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em;
  color: __ACCENTO_TESTO__; background: #FFFFFF; border-radius: 6px; padding: 2px 8px; margin-bottom: 6px;
}
.tile-icona { width: 52px; height: 52px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-bottom: 8px; }
.tile-icona-verde { background: #DCFCE7; }
.tile-icona-blu { background: #DBEAFE; }
.tile-icona-viola { background: #F3E8FF; }
.tile-icona-rosso { background: #FEE2E2; }
.st-key-home_archivio_card, .st-key-home_archivio_card [data-testid="stVerticalBlockBorderWrapper"] {
  background: linear-gradient(135deg, #EAF3FF 0%, #F7FBFF 60%, #FFFFFF 100%) !important;
  border: 1px solid __ACCENTO__ !important; border-radius: 18px !important; padding: 0.9rem 0.6rem !important;
}
.st-key-home_archivio_card h3 { font-size: 1.6rem !important; margin-top: 0; }
.st-key-home_archivio_card .stButton > button { font-size: 1.05rem !important; padding: 0.7rem 1.4rem !important; }
/* i due riquadri sono quadrati: altezza = larghezza */
.st-key-tile_contratto, .st-key-tile_busta, .st-key-tile_nuovo_dip { aspect-ratio: 1 / 1; display: flex; flex-direction: column; justify-content: space-between; }

/* ── Schermata di accesso (per ultima: le sue regole vincono sulle generali) ── */
body:has(.accesso-marcatore) [data-testid="stAppViewContainer"],
body:has(.accesso-marcatore) [data-testid="stMain"],
body:has(.accesso-marcatore) [data-testid="stHeader"],
body:has(.accesso-marcatore) .block-container { background-color: __SIDEBAR_SFONDO__ !important; }
body:has(.accesso-marcatore) [data-testid="stSidebarCollapsedControl"] { display: none !important; }
body:has(.accesso-marcatore) .block-container { padding-top: 18vh !important; }
body:has(.accesso-marcatore) [data-testid="stHorizontalBlock"] { align-items: end !important; }
body:has(.accesso-marcatore) .accesso-titolo, body:has(.accesso-marcatore) [data-testid="stMarkdownContainer"] .accesso-titolo {
  color: #FFFFFF !important; font-weight: 700 !important; font-size: 1rem !important; margin: 0 0 0.35rem 0 !important;
}
body:has(.accesso-marcatore) .accesso-errore, body:has(.accesso-marcatore) [data-testid="stMarkdownContainer"] .accesso-errore {
  color: #FFD9D9 !important; font-size: 0.85rem !important; margin-top: 0.6rem !important;
}
body:has(.accesso-marcatore) .stTextInput input, body:has(.accesso-marcatore) div[data-baseweb="input"] input {
  color: #000000 !important; -webkit-text-fill-color: #000000 !important; caret-color: #000000 !important;
}
body:has(.accesso-marcatore) .stButton > button {
  background-color: __ACCENTO_SCURO__ !important; border: none !important; color: #FFFFFF !important;
  font-weight: 700 !important; font-size: 1.05rem !important; padding: 0.5rem 0 !important; width: 100% !important;
}
body:has(.accesso-marcatore) .stButton > button:hover { background-color: #2678CE !important; }
</style>
"""


def applica_stile() -> None:
    css = _CSS
    for nome, valore in COLORI.items():
        css = css.replace(f"__{nome}__", valore)
    st.markdown(css, unsafe_allow_html=True)


def intestazione(nome_studio: str, sottotitolo: str) -> None:
    st.markdown(
        f"""
        <div class="intestazione-studio">
          <span class="nome-studio">{nome_studio}</span>
          <span class="sottotitolo">{sottotitolo}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def testo_hero(testo: str) -> None:
    st.markdown(f'<p class="testo-hero">{testo}</p>', unsafe_allow_html=True)

