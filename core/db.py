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
import shutil
from datetime import datetime
from pathlib import Path

from core.config import CRITERI_IVA
from core.util import nuovo_id

PERCORSO = Path(__file__).resolve().parent.parent / "data" / "archivio.json"
DIR_ALLEGATI = Path(__file__).resolve().parent.parent / "data" / "allegati"   # anche questa cartella si azzera su Streamlit Cloud

# Punto di partenza per le aliquote di una nuova azienda: si modificano liberamente nella
# scheda dell'azienda. I valori vanno verificati ogni anno (e per cassa/assicuratore).
ALIQUOTE_DEFAULT = [
    {"voce": "AVS / AI / IPG", "dipendente": 5.30, "datore": 5.30},
    {"voce": "AD (assicurazione disoccupazione)", "dipendente": 1.10, "datore": 1.10},
    {"voce": "Infortunio professionale", "dipendente": 0.0, "datore": 0.0},
    {"voce": "LAINF (infortunio non professionale)", "dipendente": 0.0, "datore": 0.0},
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
    "contratto_collettivo": "",
    "lpp_modalita": "",         # "piano1_basis" (ristorazione, suggerito) oppure "manuale"
    "lpp_manuale": False,       # ristorazione: True = non usare il Piano 1 Basis ma un piano inserito a mano
    "lpp_piano_nome": "",       # nome del piano manuale (le formule verranno aggiunte in seguito)
    "revisione": "",            # "Sì" / "No" / ""
    "revisione_tipo": "",       # "Limitata" / "Generale"
    "opting_in_data": None,
    "iva_soggetta": "",         # "Sì" / "No" / ""
    "iva_metodo": "",           # "Effettivo" / "A saldo"
    "iva_criterio": "",
    "iva_periodicita": "",
    "iva_aliquote_saldo": [],   # [{"descrizione": str, "aliquota": float}]
    "note": "",
    "accessi": [],              # [{"descrizione","link","utente","password","note"}]
}

CAMPI_CONIUGE = {
    "nome": "", "cognome": "", "data_nascita": None, "luogo_nascita": "", "numero_avs": "",
    "via": "", "npa": "", "localita": "",
    "assegni": "",          # percepisce assegni familiari per i figli: "Sì" / "No" / ""
    "lavora": "",           # "Sì" / "No" / ""
    "lavora_dove": "",      # se lavora: "Svizzera" / "Estero"
    "salario_maggiore": "", # se lavora: percepisce un salario maggiore del dipendente? "Sì" / "No"
}
CAMPI_GENITORE = {"nome": "", "cognome": "", "data_nascita": None}

CAMPI_DIPENDENTE = {
    "nome": "",
    "cognome": "",
    "data_nascita": None,
    "nazionalita": "",
    "numero_avs": "",
    "stato_civile": "",
    "n_figli": "",
    "cassa_malati": "",
    "via": "",
    "npa": "",
    "localita": "",
    "email": "",
    "telefono": "",
    "permesso": "",
    "data_entrata_svizzera": None,
    "scadenza_permesso": None,
    "funzione": "",
    "data_assunzione": None,
    "ultimo_lavoro_data": None,   # ultimo giorno di lavoro precedente in Svizzera
    "ultimo_datore": "",          # ragione sociale dell'ultimo datore di lavoro
    "coniuge": CAMPI_CONIUGE,
    "padre": CAMPI_GENITORE,
    "madre": CAMPI_GENITORE,
    "iban": "",
    "banca_nome": "",
    "banca_sede": "",
    "valori_salariali": {},       # dall'ultimo contratto: salario lordo/netto, % imposta alla fonte, lordo annuo...
    "stato": "assunto",           # "assunto" / "licenziato"
    "data_licenziamento": None,
    "allegati": [],               # [{"id","nome","tipo": "contratto"|"altro","dimensione","data"}]
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


def _riempi(dest: dict, modello: dict) -> None:
    """Aggiunge a `dest` i campi mancanti del `modello` (anche dentro i dizionari annidati)."""
    for campo, default in modello.items():
        if campo not in dest:
            dest[campo] = copy.deepcopy(default)
        elif isinstance(default, dict) and isinstance(dest[campo], dict):
            _riempi(dest[campo], default)


def nome_azienda(azienda: dict) -> str:
    """Nome da mostrare: la ragione sociale, oppure un segnaposto se è vuota."""
    return (azienda.get("ragione_sociale") or "").strip() or "(senza ragione sociale)"


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
            riga = {**riga, "voce": "LAINF (infortunio non professionale)"}
        aliquote.append(riga)
    if not any("professionale" in str(r.get("voce", "")).lower() and "non prof" not in str(r.get("voce", "")).lower()
               for r in aliquote):
        aliquote.insert(2 if len(aliquote) >= 2 else len(aliquote),
                        {"voce": "Infortunio professionale", "dipendente": 0.0, "datore": 0.0})
    azienda["aliquote"] = aliquote
    for dip in azienda.get("dipendenti", []):
        _riempi(dip, CAMPI_DIPENDENTE)
        dip.setdefault("contratti", [])
        dip.setdefault("buste_paga", [])
    criterio = str(azienda.get("iva_criterio", "")).lower()
    if criterio and criterio not in [c.lower() for c in CRITERI_IVA]:
        if "incass" in criterio or "ricevuto" in criterio:
            azienda["iva_criterio"] = CRITERI_IVA[0]
        elif "fattur" in criterio or "emesso" in criterio:
            azienda["iva_criterio"] = CRITERI_IVA[1]


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
    for azienda in dati["aziende"]:
        if azienda["id"] == azienda_id:
            for dip in azienda.get("dipendenti", []):
                shutil.rmtree(DIR_ALLEGATI / dip["id"], ignore_errors=True)
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


def registra_contratto(azienda_id: str, dipendente_id: str, contratto: dict, valori_salariali: dict) -> None:
    """Aggiunge il contratto all'elenco del dipendente e aggiorna i suoi valori salariali."""
    dip = get_dipendente(azienda_id, dipendente_id)
    if dip is not None:
        aggiorna_dipendente(azienda_id, dipendente_id,
                            {"contratti": dip.get("contratti", []) + [contratto], "valori_salariali": valori_salariali})


def elimina_dipendente(azienda_id: str, dipendente_id: str) -> None:
    shutil.rmtree(DIR_ALLEGATI / dipendente_id, ignore_errors=True)
    dati = _carica()
    for azienda in dati["aziende"]:
        if azienda["id"] == azienda_id:
            azienda["dipendenti"] = [d for d in azienda["dipendenti"] if d["id"] != dipendente_id]
    _salva(dati)


def licenzia_dipendente(azienda_id: str, dipendente_id: str, data_iso: str | None) -> None:
    aggiorna_dipendente(azienda_id, dipendente_id, {"stato": "licenziato", "data_licenziamento": data_iso})


def riassumi_dipendente(azienda_id: str, dipendente_id: str) -> None:
    aggiorna_dipendente(azienda_id, dipendente_id, {"stato": "assunto", "data_licenziamento": None})


def ordina_dipendenti(dipendenti: list[dict]) -> list[dict]:
    """Prima gli assunti, poi i licenziati; in ciascun gruppo per cognome e nome."""
    return sorted(dipendenti, key=lambda d: (d.get("stato") == "licenziato", d.get("cognome", "").casefold(),
                                             d.get("nome", "").casefold()))


# ── allegati dei dipendenti (qualsiasi tipo di file) ──────────────────────────
def aggiungi_allegato(azienda_id: str, dipendente_id: str, nome_file: str, contenuto: bytes, tipo: str = "altro") -> str | None:
    """Il file viene salvato con un nome casuale (mai col nome originale: niente rischi di percorsi strani);
    il nome vero resta nell'elenco degli allegati del dipendente."""
    dip = get_dipendente(azienda_id, dipendente_id)
    if dip is None:
        return None
    allegato_id = nuovo_id()
    DIR_ALLEGATI.joinpath(dipendente_id).mkdir(parents=True, exist_ok=True)
    (DIR_ALLEGATI / dipendente_id / allegato_id).write_bytes(contenuto)
    nuovo = {"id": allegato_id, "nome": Path(nome_file).name, "tipo": tipo, "dimensione": len(contenuto),
             "data": datetime.now().strftime("%Y-%m-%d")}
    aggiorna_dipendente(azienda_id, dipendente_id, {"allegati": dip.get("allegati", []) + [nuovo]})
    return allegato_id


def leggi_allegato(dipendente_id: str, allegato_id: str) -> bytes | None:
    percorso = DIR_ALLEGATI / dipendente_id / allegato_id
    return percorso.read_bytes() if percorso.exists() else None


def elimina_allegato(azienda_id: str, dipendente_id: str, allegato_id: str) -> None:
    dip = get_dipendente(azienda_id, dipendente_id)
    if dip is None:
        return
    (DIR_ALLEGATI / dipendente_id / allegato_id).unlink(missing_ok=True)
    aggiorna_dipendente(azienda_id, dipendente_id,
                        {"allegati": [a for a in dip.get("allegati", []) if a["id"] != allegato_id]})


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
