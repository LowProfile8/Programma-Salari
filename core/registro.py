"""core/registro.py — ricerca del numero CHE nel registro di commercio (Zefix, Ufficio federale di giustizia).

Zefix è il registro di commercio federale e comprende anche le aziende del Ticino.
L'interrogazione automatica richiede credenziali GRATUITE: si chiedono per e-mail a zefix@bj.admin.ch
e si mettono nei Secrets dell'app:

    ZEFIX_USER = "..."
    ZEFIX_PASSWORD = "..."

Senza credenziali (o se Zefix non risponde) resta il link al registro di commercio del Ticino, da usare a mano.
NOTA: il codice è scritto sulla documentazione pubblica dell'API ma non è stato provato dal vivo
(servono le credenziali): alla prima prova controlla il risultato.
"""

import re
from urllib.parse import quote

import requests
import streamlit as st

URL_API = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1/company/search"
LINK_REGISTRO = "https://ti.chregister.ch/cr-portal/suche/suche.xhtml"  # registro di commercio del Ticino


def link_ricerca(ragione_sociale: str = "") -> str:
    """Link alla ricerca nel registro di commercio del Ticino (quello da usare a mano se Zefix non risponde)."""
    return LINK_REGISTRO


def formatta_che(uid: str) -> str:
    """'CHE105951817' -> 'CHE-105.951.817'."""
    cifre = re.sub(r"\D", "", uid or "")
    if len(cifre) != 9:
        return uid or ""
    return f"CHE-{cifre[:3]}.{cifre[3:6]}.{cifre[6:]}"


def _normalizza(nome: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (nome or "").casefold())).strip()


def _credenziali() -> tuple[str, str] | None:
    try:
        return str(st.secrets["ZEFIX_USER"]), str(st.secrets["ZEFIX_PASSWORD"])
    except Exception:
        return None


def cerca_che(ragione_sociale: str) -> dict:
    """Cerca la ragione sociale nel registro. Restituisce un dizionario:
        esito     'ok' (trovato con certezza) | 'scelta' (più possibilità: decide l'utente) |
                  'nessuno' | 'errore' | 'manca_nome' | 'no_credenziali'
        messaggio testo da mostrare
        che       numero CHE formattato (solo se esito == 'ok')
        candidati [{'nome', 'che', 'sede'}] (se esito == 'scelta')"""
    nome = (ragione_sociale or "").strip()
    if len(nome) < 3:
        return {"esito": "manca_nome", "messaggio": "Scrivi prima la ragione sociale (almeno 3 caratteri)."}
    credenziali = _credenziali()
    if credenziali is None:
        return {
            "esito": "no_credenziali",
            "messaggio": "Ricerca automatica non attiva: mancano le credenziali Zefix (ZEFIX_USER e ZEFIX_PASSWORD "
                         "nei Secrets). Usa il link qui sopra (registro di commercio del Ticino) e scrivi il numero a mano.",
        }
    try:
        risposta = requests.post(
            URL_API, auth=credenziali, timeout=15,
            json={"name": nome, "languageKey": "it", "maxEntries": 20, "activeOnly": True},
        )
        if risposta.status_code == 401:
            return {"esito": "errore", "messaggio": "Credenziali Zefix non accettate: controlla ZEFIX_USER e ZEFIX_PASSWORD, oppure usa il link qui sopra (registro di commercio del Ticino)."}
        risposta.raise_for_status()
        elementi = risposta.json()
    except (requests.RequestException, ValueError) as errore:
        return {"esito": "errore", "messaggio": f"Il registro di commercio non ha risposto ({errore}). Riprova tra poco oppure usa il link qui sopra (registro di commercio del Ticino)."}

    candidati = [
        {"nome": e.get("name", ""), "che": formatta_che(e.get("uid", "")), "sede": e.get("legalSeat", "")}
        for e in (elementi if isinstance(elementi, list) else []) if e.get("uid")
    ]
    if not candidati:
        return {"esito": "nessuno", "messaggio": "Nessuna azienda attiva trovata con questo nome in Zefix. Prova con il link qui sopra (registro di commercio del Ticino)."}

    identici = [c for c in candidati if _normalizza(c["nome"]) == _normalizza(nome)]
    if len(identici) == 1:
        c = identici[0]
        return {"esito": "ok", "che": c["che"], "messaggio": f"Trovata: {c['nome']} ({c['sede']}) — {c['che']}."}
    return {
        "esito": "scelta", "candidati": identici or candidati,
        "messaggio": "Nessuna corrispondenza esatta e sicura: scegli l'azienda giusta dall'elenco.",
    }
