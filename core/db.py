"""core/db.py — accesso ai dati (aziende e dipendenti).

ATTENZIONE: per ora i dati stanno in un file JSON locale (data/archivio.json). Va bene per
sviluppare e provare in locale, MA su Streamlit Cloud il disco si azzera a ogni riavvio.
Prima di inserire dati reali va sostituito con un database esterno (es. Supabase): tutte le
altre parti del programma parlano solo con le funzioni di questo file, quindi basta
riscrivere QUI dentro `_carica()` e `_salva()` (o le singole funzioni) senza toccare il resto.

Struttura:
    {"aziende": [ {id, ragione_sociale, ..., "aliquote": [...], "dipendenti": [ {...} ]} ]}
"""

import base64
import copy
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

import requests

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
    {"voce": "Indennità giornaliera malattia — uomo", "dipendente": 0.0, "datore": 0.0},
    {"voce": "Indennità giornaliera malattia — donna", "dipendente": 0.0, "datore": 0.0},
]
# L'LPP NON è nella tabella: dipende dal ramo aziendale (vedi modules/archivio.py e core/config.py).

CAMPI_AZIENDA = {
    "ragione_sociale": "",
    "forma_giuridica": "",
    "amministratore": "",        # solo per le SA
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
    "lpp_link": "",
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
    "sesso": "",                  # "Uomo" / "Donna": serve per l'aliquota malattia
    "n_figli": "",
    "figli_a_carico": "",         # "Sì" / "No": figli nello stesso nucleo (serve per la tariffa dell'imposta alla fonte)
    "luogo_nascita": "",
    "paese_origine": "",
    "data_matrimonio": None,
    "figli": [],                  # [{"cognome","nome","data_nascita"}] (da scheda anagrafica)
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
# ── archivio: Supabase se configurato nei Secrets, altrimenti file locale (solo per provare) ──────────────
# Secrets di Streamlit:  SUPABASE_URL, SUPABASE_KEY (chiave «secret» / service_role), ENCRYPTION_KEY (Fernet).
# Il database è una tabella «archivio» con una riga (id=1) che contiene tutto l'archivio in formato JSON;
# gli allegati stanno nel bucket privato «allegati». Vedi supabase_setup.sql.
BUCKET = "allegati"
_CACHE = {"t": 0.0, "dati": None}
_TTL_LETTURA = 3.0       # secondi: le letture ripetute nella stessa pagina non rifanno la richiesta di rete


def _config() -> tuple[str, str] | None:
    try:
        import streamlit as st
        return str(st.secrets["SUPABASE_URL"]).rstrip("/"), str(st.secrets["SUPABASE_KEY"])
    except Exception:
        return None


def _http(metodo: str, percorso: str, **kw):
    url, chiave = _config()
    intest = {"apikey": chiave, "Authorization": f"Bearer {chiave}", **kw.pop("headers", {})}
    risposta = requests.request(metodo, f"{url}{percorso}", headers=intest, timeout=30, **kw)
    if risposta.status_code >= 400:
        raise OSError(f"Supabase {metodo} {percorso.split('?')[0]}: {risposta.status_code} {risposta.text[:200]}")
    return risposta


_STATO = {"t": 0.0, "v": None}


def stato_cloud() -> tuple[str, str]:
    """('attivo' | 'locale' | 'errore', dettaglio). Con Supabase fa una piccola lettura di prova, al massimo ogni 45 secondi."""
    if not usa_supabase():
        return "locale", ""
    if _STATO["v"] is not None and time.time() - _STATO["t"] < 45:
        return _STATO["v"]
    try:
        _http("GET", "/rest/v1/archivio?id=eq.1&select=id")
        v = ("attivo", "")
    except Exception as e:
        v = ("errore", str(e)[:200])
    _STATO.update(t=time.time(), v=v)
    return v


def usa_supabase() -> bool:
    return _config() is not None


# ── cifratura delle password (campo «accessi») ───────────────────────────────
def _fernet():
    try:
        import streamlit as st
        from cryptography.fernet import Fernet
        return Fernet(str(st.secrets["ENCRYPTION_KEY"]).encode())
    except Exception:
        return None


def _cifra_accessi(dati: dict, cifra: bool) -> dict:
    f = _fernet()
    if f is None:
        return dati
    for azienda in dati.get("aziende", []):
        for riga in azienda.get("accessi", []):
            v = riga.get("password") or ""
            if cifra and v and not v.startswith("enc:"):
                riga["password"] = "enc:" + f.encrypt(v.encode()).decode()
            elif not cifra and v.startswith("enc:"):
                try:
                    riga["password"] = f.decrypt(v[4:].encode()).decode()
                except Exception:
                    riga["password"] = "[non decifrabile]"
    return dati


def _leggi_archivio() -> dict:
    if usa_supabase():
        r = _http("GET", "/rest/v1/archivio?id=eq.1&select=dati")
        righe = r.json()
        return righe[0]["dati"] if righe and righe[0].get("dati") else {"aziende": []}
    if not PERCORSO.exists():
        return {"aziende": []}
    try:
        return json.loads(PERCORSO.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"aziende": []}


def _carica(fresco: bool = False) -> dict:
    """Legge l'archivio. Le scritture usano sempre `fresco=True` (niente cache) per non sovrascrivere modifiche altrui."""
    if not fresco and _CACHE["dati"] is not None and time.time() - _CACHE["t"] < _TTL_LETTURA:
        return copy.deepcopy(_CACHE["dati"])
    try:
        grezzo = _leggi_archivio()
    except OSError:
        if not fresco and _CACHE["dati"] is not None:      # cloud irraggiungibile: per la sola lettura si usa l'ultima copia
            return copy.deepcopy(_CACHE["dati"])
        raise
    dati = _cifra_accessi(grezzo, cifra=False)
    for azienda in dati.get("aziende", []):
        _migra(azienda)
    _CACHE.update(t=time.time(), dati=copy.deepcopy(dati))
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
        if voce.lower().startswith("assegni familiari"):
            continue                      # riga non più prevista
        if voce.upper().startswith("AINF NON PROF"):
            riga = {**riga, "voce": "LAINF (infortunio non professionale)"}
        aliquote.append(riga)
    if not any("professionale" in str(r.get("voce", "")).lower() and "non prof" not in str(r.get("voce", "")).lower()
               for r in aliquote):
        aliquote.insert(2 if len(aliquote) >= 2 else len(aliquote),
                        {"voce": "Infortunio professionale", "dipendente": 0.0, "datore": 0.0})
    nuove = []
    for r in aliquote:
        v = str(r.get("voce", "")).lower()
        if "malattia" in v and "uomo" not in v and "donna" not in v:           # vecchia riga unica -> uomo + donna
            nuove.append({**r, "voce": "Indennità giornaliera malattia — uomo"})
            nuove.append({**r, "voce": "Indennità giornaliera malattia — donna"})
        else:
            nuove.append(r)
    aliquote = nuove
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
    dati = _cifra_accessi(copy.deepcopy(dati), cifra=True)
    if usa_supabase():
        _http("POST", "/rest/v1/archivio", json={"id": 1, "dati": dati},
              headers={"Prefer": "resolution=merge-duplicates", "Content-Type": "application/json"})
    else:
        PERCORSO.parent.mkdir(parents=True, exist_ok=True)
        PERCORSO.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
    _CACHE.update(t=0.0, dati=None)


# ── aziende ───────────────────────────────────────────────────────────────────
def elenco_aziende() -> list[dict]:
    return sorted(_carica()["aziende"], key=lambda a: a.get("ragione_sociale", "").lower())


def get_azienda(azienda_id: str | None) -> dict | None:
    for azienda in _carica()["aziende"]:
        if azienda["id"] == azienda_id:
            return azienda
    return None


def nuova_azienda(ragione_sociale: str) -> str:
    dati = _carica(True)
    azienda = {"id": nuovo_id(), **copy.deepcopy(CAMPI_AZIENDA)}
    azienda["ragione_sociale"] = ragione_sociale.strip()
    azienda["aliquote"] = copy.deepcopy(ALIQUOTE_DEFAULT)
    azienda["dipendenti"] = []
    dati["aziende"].append(azienda)
    _salva(dati)
    return azienda["id"]


def aggiorna_azienda(azienda_id: str, modifiche: dict) -> None:
    dati = _carica(True)
    for azienda in dati["aziende"]:
        if azienda["id"] == azienda_id:
            azienda.update(modifiche)
    _salva(dati)


def elimina_azienda(azienda_id: str) -> None:
    dati = _carica(True)
    for azienda in dati["aziende"]:
        if azienda["id"] == azienda_id:
            for dip in azienda.get("dipendenti", []):
                _cancella_file(dip["id"])
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
    dati = _carica(True)
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
    dati = _carica(True)
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


def elimina_contratto(azienda_id: str, dipendente_id: str, contratto_id: str) -> None:
    """Elimina un contratto (e il suo PDF) e riallinea i valori salariali all'ultimo contratto rimasto."""
    dip = get_dipendente(azienda_id, dipendente_id)
    if dip is None:
        return
    resto = []
    for c in dip.get("contratti", []):
        if c.get("id") == contratto_id:
            if c.get("allegato_id"):
                elimina_allegato(azienda_id, dipendente_id, c["allegato_id"])
        else:
            resto.append(c)
    ultimo = max(resto, key=lambda c: c.get("data_inizio") or "", default=None)
    valori = ultimo.get("valori", {}) if ultimo else {}
    aggiorna_dipendente(azienda_id, dipendente_id, {"contratti": resto, "valori_salariali": valori})


def sostituisci_contratto(azienda_id: str, dipendente_id: str, contratto_id: str, contratto: dict, valori_salariali: dict) -> None:
    """Aggiorna un contratto già salvato (tasto «Modifica contratto»): stesso id, dati nuovi."""
    dip = get_dipendente(azienda_id, dipendente_id)
    if dip is None:
        return
    elenco = [contratto if c.get("id") == contratto_id else c for c in dip.get("contratti", [])]
    aggiorna_dipendente(azienda_id, dipendente_id, {"contratti": elenco, "valori_salariali": valori_salariali})


def elimina_dipendente(azienda_id: str, dipendente_id: str) -> None:
    _cancella_file(dipendente_id)
    dati = _carica(True)
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


# ── file degli allegati: bucket Supabase oppure cartella locale ──
def _scrivi_file(dip_id: str, allegato_id: str, contenuto: bytes) -> None:
    if usa_supabase():
        _http("POST", f"/storage/v1/object/{BUCKET}/{dip_id}/{allegato_id}", data=contenuto,
              headers={"Content-Type": "application/octet-stream", "x-upsert": "true"})
    else:
        DIR_ALLEGATI.joinpath(dip_id).mkdir(parents=True, exist_ok=True)
        (DIR_ALLEGATI / dip_id / allegato_id).write_bytes(contenuto)


def _leggi_file(dip_id: str, allegato_id: str) -> bytes | None:
    if usa_supabase():
        try:
            return _http("GET", f"/storage/v1/object/authenticated/{BUCKET}/{dip_id}/{allegato_id}").content
        except OSError:
            return None
    percorso = DIR_ALLEGATI / dip_id / allegato_id
    return percorso.read_bytes() if percorso.exists() else None


def _cancella_file(dip_id: str, allegato_id: str | None = None) -> None:
    """Cancella un file, oppure tutti i file del dipendente se `allegato_id` è None."""
    if usa_supabase():
        try:
            if allegato_id is None:
                elenco = _http("POST", f"/storage/v1/object/list/{BUCKET}", json={"prefix": dip_id, "limit": 1000}).json()
                percorsi = [f"{dip_id}/{x['name']}" for x in elenco]
            else:
                percorsi = [f"{dip_id}/{allegato_id}"]
            if percorsi:
                _http("DELETE", f"/storage/v1/object/{BUCKET}", json={"prefixes": percorsi})
        except OSError:
            pass
    elif allegato_id is None:
        shutil.rmtree(DIR_ALLEGATI / dip_id, ignore_errors=True)
    else:
        (DIR_ALLEGATI / dip_id / allegato_id).unlink(missing_ok=True)


# ── allegati dei dipendenti (qualsiasi tipo di file) ──────────────────────────
def aggiungi_allegato(azienda_id: str, dipendente_id: str, nome_file: str, contenuto: bytes, tipo: str = "altro") -> str | None:
    """Il file viene salvato con un nome casuale (mai col nome originale: niente rischi di percorsi strani);
    il nome vero resta nell'elenco degli allegati del dipendente."""
    dip = get_dipendente(azienda_id, dipendente_id)
    if dip is None:
        return None
    allegato_id = nuovo_id()
    _scrivi_file(dipendente_id, allegato_id, contenuto)
    nuovo = {"id": allegato_id, "nome": Path(nome_file).name, "tipo": tipo, "dimensione": len(contenuto),
             "data": datetime.now().strftime("%Y-%m-%d")}
    aggiorna_dipendente(azienda_id, dipendente_id, {"allegati": dip.get("allegati", []) + [nuovo]})
    return allegato_id


def leggi_allegato(dipendente_id: str, allegato_id: str) -> bytes | None:
    return _leggi_file(dipendente_id, allegato_id)


def elimina_allegato(azienda_id: str, dipendente_id: str, allegato_id: str) -> None:
    dip = get_dipendente(azienda_id, dipendente_id)
    if dip is None:
        return
    _cancella_file(dipendente_id, allegato_id)
    aggiorna_dipendente(azienda_id, dipendente_id,
                        {"allegati": [a for a in dip.get("allegati", []) if a["id"] != allegato_id]})


# ── schede anagrafiche compilate dal dipendente tramite link ──────────────────
def crea_scheda_link(azienda_id: str, dipendente_id: str) -> str:
    """Crea (o rinnova) il link per far compilare la scheda anagrafica al dipendente. Restituisce il codice del link."""
    dati = _carica(True)
    schede = dati.setdefault("schede", {})
    for token, sc in list(schede.items()):
        if sc.get("dipendente_id") == dipendente_id and not sc.get("ricevuta"):
            del schede[token]                      # un solo link attivo per dipendente
    token = nuovo_id() + nuovo_id() + nuovo_id()
    schede[token] = {"azienda_id": azienda_id, "dipendente_id": dipendente_id, "creato": datetime.now().strftime("%Y-%m-%d %H:%M"),
                     "ricevuta": False, "dati": None}
    _salva(dati)
    return token


def get_scheda(token: str) -> dict | None:
    return (_carica(True).get("schede") or {}).get(token or "")


def scheda_del_dipendente(dipendente_id: str) -> tuple[str, dict] | None:
    for token, sc in (_carica(True).get("schede") or {}).items():
        if sc.get("dipendente_id") == dipendente_id and not sc.get("importata"):
            return token, sc
    return None


def salva_scheda_ricevuta(token: str, dati: dict) -> bool:
    d = _carica(True)
    sc = (d.get("schede") or {}).get(token)
    if not sc or sc.get("ricevuta"):
        return False
    sc.update(dati=dati, ricevuta=True, ricevuta_il=datetime.now().strftime("%Y-%m-%d %H:%M"))
    _salva(d)
    return True


def elimina_scheda(token: str) -> None:
    d = _carica(True)
    (d.get("schede") or {}).pop(token, None)
    _salva(d)


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


def esiste_dipendente(azienda_id: str, nome: str, cognome: str) -> bool:
    """True se nell'azienda c'è già un dipendente con lo stesso nome e cognome (senza distinguere maiuscole)."""
    az = get_azienda(azienda_id) or {}
    n, c = nome.strip().casefold(), cognome.strip().casefold()
    return any((d.get("nome") or "").strip().casefold() == n and (d.get("cognome") or "").strip().casefold() == c
               for d in az.get("dipendenti", []))


def schede_ricevute(solo_da_importare: bool = True) -> list[dict]:
    """Schede anagrafiche inviate dai dipendenti (la «casella» delle notifiche). Più recenti per prime."""
    out = []
    for token, sc in (_carica(True).get("schede") or {}).items():
        if not sc.get("ricevuta"):
            continue
        if solo_da_importare and sc.get("importata"):
            continue
        az = get_azienda(sc.get("azienda_id")) or {}
        dip = get_dipendente(sc.get("azienda_id"), sc.get("dipendente_id")) or {}
        out.append({"token": token, "azienda_id": sc.get("azienda_id"), "dipendente_id": sc.get("dipendente_id"),
                    "azienda": nome_azienda(az) if az else "(azienda eliminata)",
                    "dipendente": f"{dip.get('nome', '')} {dip.get('cognome', '')}".strip() or "(dipendente eliminato)",
                    "ricevuta_il": sc.get("ricevuta_il", ""), "importata": bool(sc.get("importata")), "dati": sc.get("dati") or {}})
    return sorted(out, key=lambda x: x["ricevuta_il"], reverse=True)


def importa_scheda(token: str) -> bool:
    """Importa a mano nel profilo del dipendente i dati inviati; la scheda resta nello storico come «importata»."""
    from core import anagrafica
    d = _carica(True)
    sc = (d.get("schede") or {}).get(token)
    if not sc or not sc.get("ricevuta"):
        return False
    dati = sc.get("dati") or {}
    attuale = get_dipendente(sc["azienda_id"], sc["dipendente_id"])
    if attuale is None:
        return False
    unito = anagrafica.unisci(attuale, dati)
    aggiorna_dipendente(sc["azienda_id"], sc["dipendente_id"], {k: v for k, v in unito.items() if k in dati})
    d = _carica(True)
    d["schede"][token].update(importata=True, importata_il=datetime.now().strftime("%Y-%m-%d %H:%M"))
    _salva(d)
    return True
