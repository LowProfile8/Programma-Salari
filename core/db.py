"""core/db.py — accesso ai dati (aziende e dipendenti).

ATTENZIONE: per ora i dati stanno in un file JSON locale (data/archivio.json). Va bene per
sviluppare e provare in locale, MA su Streamlit Cloud il disco si azzera a ogni riavvio.
Prima di inserire dati reali va sostituito con un database esterno (es. Supabase): tutte le
altre parti del programma parlano solo con le funzioni di questo file, quindi basta
riscrivere QUI dentro `_carica()` e `_salva()` (o le singole funzioni) senza toccare il resto.

Struttura:
    {"aziende": [ {id, ragione_sociale, ..., "aliquote": [...], "dipendenti": [ {...} ]} ]}
"""

import copy
import json
from pathlib import Path

from core.util import nuovo_id

PERCORSO = Path(__file__).resolve().parent.parent / "data" / "archivio.json"

# Punto di partenza per le aliquote di una nuova azienda: si modificano liberamente nella
# scheda dell'azienda. I valori vanno verificati ogni anno (e per cassa/assicuratore).
ALIQUOTE_DEFAULT = [
    {"voce": "AVS / AI / IPG", "dipendente": 5.30, "datore": 5.30},
    {"voce": "AD (assicurazione disoccupazione)", "dipendente": 1.10, "datore": 1.10},
    {"voce": "Infortunio professionale", "dipendente": 0.0, "datore": 0.0},
    {"voce": "LINF (infortunio non professionale)", "dipendente": 0.0, "datore": 0.0},
    {"voce": "Indennità giornaliera malattia", "dipendente": 0.0, "datore": 0.0},
    {"voce": "Assegni familiari", "dipendente": 0.0, "datore": 0.0},
]
# L'LPP NON è nella tabella: dipende dal ramo aziendale (vedi modules/archivio.py e core/config.py).

CAMPI_AZIENDA = {
    "ragione_sociale": "",
    "forma_giuridica": "",
    "ramo": "",
    "numero_che": "",
    "multivaluta": "",          # "Sì" / "No" / "" (non ancora indicato)
    "valuta_2": "",
    "valuta_3": "",
    "soci": [],                 # [{"socio": str, "quota": float}]
    "sede_via": "",
    "sede_npa": "",
    "sede_localita": "",
    "persona_contatto": "",
    "telefono": "",
    "email": "",
    "iban": "",
    "cassa_avs": "",
    "cassa_lpp": "",
    "assicuratore_infortuni": "",
    "assicuratore_malattia": "",
    "lpp_modalita": "",         # "piano1_basis" (ristorazione) oppure "manuale" (da inserire nel contratto)
    "revisione": "",            # "Sì" / "No" / ""
    "revisione_tipo": "",       # "Limitata" / "Generale"
    "opting_in": "",            # "Sì" / "No" / ""
    "opting_in_data": None,
    "iva_soggetta": "",         # "Sì" / "No" / ""
    "iva_metodo": "",           # "Effettivo" / "A saldo"
    "iva_criterio": "",
    "iva_periodicita": "",
    "iva_aliquote_saldo": [],   # [{"descrizione": str, "aliquota": float}]
    "note": "",
    "accessi": [],              # [{"descrizione","link","utente","password","note"}]
}

CAMPI_DIPENDENTE = {
    "nome": "",
    "cognome": "",
    "data_nascita": None,
    "numero_avs": "",
    "via": "",
    "npa": "",
    "localita": "",
    "nazionalita": "",
    "stato_civile": "",
    "permesso": "",
    "iban": "",
    "funzione": "",
    "data_assunzione": None,
}


# ── lettura/scrittura del file (da sostituire con il database) ────────────────
def _carica() -> dict:
    if not PERCORSO.exists():
        return {"aziende": []}
    try:
        dati = json.loads(PERCORSO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"aziende": []}
    for azienda in dati.get("aziende", []):
        _migra(azienda)
    return dati


def _migra(azienda: dict) -> None:
    """Porta le aziende salvate con una versione precedente alla struttura attuale."""
    for campo, default in CAMPI_AZIENDA.items():
        azienda.setdefault(campo, copy.deepcopy(default))
    aliquote = []
    for riga in azienda.get("aliquote", []):
        voce = str(riga.get("voce", ""))
        if voce.upper().startswith("LPP"):
            continue  # l'LPP non è più una trattenuta della tabella
        if voce.upper().startswith("AINF NON PROF"):
            riga = {**riga, "voce": "LINF (infortunio non professionale)"}
        aliquote.append(riga)
    if not any("professionale" in str(r.get("voce", "")).lower() and "non prof" not in str(r.get("voce", "")).lower()
               for r in aliquote):
        aliquote.insert(2 if len(aliquote) >= 2 else len(aliquote),
                        {"voce": "Infortunio professionale", "dipendente": 0.0, "datore": 0.0})
    azienda["aliquote"] = aliquote


def _salva(dati: dict) -> None:
    PERCORSO.parent.mkdir(parents=True, exist_ok=True)
    PERCORSO.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")


# ── aziende ───────────────────────────────────────────────────────────────────
def elenco_aziende() -> list[dict]:
    return sorted(_carica()["aziende"], key=lambda a: a.get("ragione_sociale", "").lower())


def get_azienda(azienda_id: str | None) -> dict | None:
    for azienda in _carica()["aziende"]:
        if azienda["id"] == azienda_id:
            return azienda
    return None


def nuova_azienda(ragione_sociale: str) -> str:
    dati = _carica()
    azienda = {"id": nuovo_id(), **copy.deepcopy(CAMPI_AZIENDA)}
    azienda["ragione_sociale"] = ragione_sociale.strip()
    azienda["aliquote"] = copy.deepcopy(ALIQUOTE_DEFAULT)
    azienda["dipendenti"] = []
    dati["aziende"].append(azienda)
    _salva(dati)
    return azienda["id"]


def aggiorna_azienda(azienda_id: str, modifiche: dict) -> None:
    dati = _carica()
    for azienda in dati["aziende"]:
        if azienda["id"] == azienda_id:
            azienda.update(modifiche)
    _salva(dati)


def elimina_azienda(azienda_id: str) -> None:
    dati = _carica()
    dati["aziende"] = [a for a in dati["aziende"] if a["id"] != azienda_id]
    _salva(dati)


# ── dipendenti (annidati dentro l'azienda) ────────────────────────────────────
def get_dipendente(azienda_id: str, dipendente_id: str | None) -> dict | None:
    azienda = get_azienda(azienda_id)
    for dip in (azienda or {}).get("dipendenti", []):
        if dip["id"] == dipendente_id:
            return dip
    return None


def nuovo_dipendente(azienda_id: str, nome: str, cognome: str, extra: dict | None = None) -> str:
    dati = _carica()
    dip_id = nuovo_id()
    for azienda in dati["aziende"]:
        if azienda["id"] == azienda_id:
            dip = {"id": dip_id, **copy.deepcopy(CAMPI_DIPENDENTE), "contratti": [], "buste_paga": []}
            dip["nome"], dip["cognome"] = nome.strip(), cognome.strip()
            dip.update(extra or {})
            azienda["dipendenti"].append(dip)
    _salva(dati)
    return dip_id


def aggiorna_dipendente(azienda_id: str, dipendente_id: str, modifiche: dict) -> None:
    dati = _carica()
    for azienda in dati["aziende"]:
        if azienda["id"] == azienda_id:
            for dip in azienda["dipendenti"]:
                if dip["id"] == dipendente_id:
                    dip.update(modifiche)
    _salva(dati)


def aggiungi_contratto(azienda_id: str, dipendente_id: str, contratto: dict) -> None:
    dip = get_dipendente(azienda_id, dipendente_id)
    if dip is not None:
        aggiorna_dipendente(azienda_id, dipendente_id, {"contratti": dip.get("contratti", []) + [contratto]})


def elimina_dipendente(azienda_id: str, dipendente_id: str) -> None:
    dati = _carica()
    for azienda in dati["aziende"]:
        if azienda["id"] == azienda_id:
            azienda["dipendenti"] = [d for d in azienda["dipendenti"] if d["id"] != dipendente_id]
    _salva(dati)


# ── ricerca (barra di ricerca della home) ─────────────────────────────────────
def cerca(testo: str) -> tuple[list[dict], list[tuple[dict, dict]]]:
    """Cerca aziende (ragione sociale, n. CHE) e dipendenti (nome, cognome).
    Tutte le parole scritte devono comparire; maiuscole/minuscole non contano.
    Restituisce (aziende, [(azienda, dipendente), ...])."""
    parole = [p for p in (testo or "").casefold().split() if p]
    if not parole:
        return [], []
    aziende, dipendenti = [], []
    for az in elenco_aziende():
        testo_az = f"{az.get('ragione_sociale', '')} {az.get('numero_che', '')}".casefold()
        if all(p in testo_az for p in parole):
            aziende.append(az)
        for dip in az.get("dipendenti", []):
            testo_dip = f"{dip.get('nome', '')} {dip.get('cognome', '')}".casefold()
            if all(p in testo_dip for p in parole):
                dipendenti.append((az, dip))
    return aziende, dipendenti
