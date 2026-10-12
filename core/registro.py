"""core/registro.py — numero CHE dal registro di commercio.

* Link manuale: Zefix, con la ragione sociale già inserita nella ricerca.
* Ricerca automatica: portale del registro di commercio del Cantone Ticino (ti.chregister.ch).

ATTENZIONE: il portale del Ticino è una pagina a moduli (JSF), non un servizio pensato per i programmi, e
non è stato possibile provarlo dal vivo durante lo sviluppo. La lettura è quindi «adattiva»: scarica la
pagina di ricerca, riconosce il campo del nome e il tasto di ricerca, invia la richiesta e cerca i numeri CHE
nel risultato. Se il portale cambia, chiede un controllo anti-robot (captcha) o risponde in modo
inatteso, la funzione non inventa nulla: restituisce un errore con il motivo e il numero si scrive a mano.
"""

import re
from urllib.parse import quote, unquote, urljoin

import requests
from bs4 import BeautifulSoup

URL_TICINO = "https://ti.chregister.ch/cr-portal/suche/suche.xhtml"
URL_ZEFIX = "https://www.zefix.admin.ch/it/search/entity/welcome"

_RE_CHE = re.compile(r"CHE[-\s]?(\d{3})[.\s]?(\d{3})[.\s]?(\d{3})", re.I)
_PAROLE_NOME = ("firma", "ditta", "name", "nome", "bezeichnung", "denominazione", "suche", "ricerca", "cerca")
_PAROLE_NO = ("uid", "che", "plz", "npa", "cap", "sitz", "sede", "ort", "luogo", "comune", "gemeinde", "canton")
_PAROLE_INVIO = ("cerca", "ricerca", "suche", "recherche", "search", "avvia", "trova")
_INTESTAZIONI = {"User-Agent": "Mozilla/5.0 (compatible; FiduciariaApp/1.0)", "Accept-Language": "it,de;q=0.8,en;q=0.5"}
_MANUALE = f"Puoi cercarlo a mano nel [registro di commercio del Ticino]({URL_TICINO})."


class _ErroreLettura(Exception):
    """Il portale non si è lasciato leggere come previsto."""


def link_ricerca(ragione_sociale: str = "") -> str:
    """Link a Zefix con la ragione sociale già inserita nella ricerca."""
    nome = (ragione_sociale or "").strip()
    if not nome:
        return URL_ZEFIX
    return f"https://www.zefix.admin.ch/it/search/entity/list?name={quote(nome)}"


def formatta_che(testo: str) -> str:
    """'CHE105951817' -> 'CHE-105.951.817'. Se non riconosce un CHE restituisce il testo com'è."""
    m = _RE_CHE.search(testo or "")
    return f"CHE-{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else (testo or "")


def _normalizza(nome: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (nome or "").casefold())).strip()


# ── lettura della pagina di ricerca ───────────────────────────────────────────
def _identificatori(campo, soup) -> str:
    testo = " ".join(str(campo.get(a) or "") for a in ("id", "name", "placeholder", "title", "aria-label"))
    if campo.get("id"):
        for et in soup.find_all("label", attrs={"for": campo["id"]}):
            testo += " " + et.get_text(" ", strip=True)
    return testo.casefold()


def _campi_testo(modulo) -> list:
    return [i for i in modulo.find_all("input")
            if (i.get("type") or "text").lower() in ("text", "search")
            and not i.has_attr("disabled") and not i.has_attr("readonly")]


def _trova_modulo(soup):
    moduli = [f for f in soup.find_all("form") if _campi_testo(f)]
    if not moduli:
        return None
    con_stato = [f for f in moduli if f.find("input", attrs={"name": re.compile(r"faces\.ViewState", re.I)})]
    return (con_stato or moduli)[0]


def _campo_nome(modulo, soup):
    campi = _campi_testo(modulo)
    if not campi:
        raise _ErroreLettura("nella pagina di ricerca non c'è un campo di testo")

    def punteggio(campo) -> int:
        ident = _identificatori(campo, soup)
        return sum(p in ident for p in _PAROLE_NOME) - 5 * sum(p in ident for p in _PAROLE_NO)

    return max(campi, key=punteggio)  # a parità vince il primo


def _pulsante_invio(modulo):
    candidati = modulo.find_all("input", attrs={"type": re.compile("^(submit|image)$", re.I)})
    candidati += [b for b in modulo.find_all("button") if (b.get("type") or "submit").lower() == "submit"]
    if not candidati:
        return None

    def punteggio(el) -> int:
        testo = f"{el.get('value') or ''} {el.get_text(' ', strip=True)} {el.get('id') or ''} {el.get('title') or ''}".casefold()
        return sum(p in testo for p in _PAROLE_INVIO)

    return max(candidati, key=punteggio)


def _dati_modulo(modulo, campo_nome, nome: str, pulsante) -> list[tuple[str, str]]:
    dati: list[tuple[str, str]] = []
    for el in modulo.find_all(["input", "select", "textarea"]):
        chiave = el.get("name")
        if not chiave or el.has_attr("disabled"):
            continue
        if el.name == "input":
            tipo = (el.get("type") or "text").lower()
            if tipo in ("submit", "button", "image", "reset", "file"):
                continue
            if tipo in ("checkbox", "radio") and not el.has_attr("checked"):
                continue
            valore = el.get("value", "on" if tipo in ("checkbox", "radio") else "")
        elif el.name == "select":
            opzioni = el.find_all("option")
            scelta = next((o for o in opzioni if o.has_attr("selected")), opzioni[0] if opzioni else None)
            valore = (scelta.get("value", scelta.get_text(strip=True)) if scelta else "")
        else:
            valore = el.get_text()
        dati.append((chiave, valore))
    dati = [(k, v) for k, v in dati if k != campo_nome.get("name")]
    dati.append((campo_nome["name"], nome))
    if pulsante is not None and pulsante.get("name"):
        dati.append((pulsante["name"], pulsante.get("value") or ""))
    return dati


# ── lettura dei risultati ─────────────────────────────────────────────────────
def _estrai_candidati(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    trovati: dict[str, dict] = {}

    def aggiungi(che: str, nome: str, sede: str = "") -> None:
        attuale = trovati.setdefault(che, {"nome": "", "che": che, "sede": ""})
        attuale["nome"] = attuale["nome"] or nome
        attuale["sede"] = attuale["sede"] or sede

    for riga in soup.find_all("tr"):
        celle = [c.get_text(" ", strip=True) for c in riga.find_all(["td", "th"])]
        blocco = " ".join(celle) + " " + " ".join(unquote(a["href"]) for a in riga.find_all("a", href=True))
        m = _RE_CHE.search(blocco)
        if not m:
            continue
        altre = [c for c in celle if c and not _RE_CHE.search(c) and not re.fullmatch(r"[\d\s.,-]+", c)]
        aggiungi(formatta_che(m.group(0)), altre[0] if altre else "", ", ".join(altre[1:3]))
    for a in soup.find_all("a", href=True):
        m = _RE_CHE.search(unquote(a["href"]))
        if m:
            aggiungi(formatta_che(m.group(0)), a.get_text(" ", strip=True))
    return list(trovati.values())


# ── ricerca ───────────────────────────────────────────────────────────────────
def _cerca_nel_portale(nome: str) -> list[dict]:
    with requests.Session() as sessione:
        sessione.headers.update(_INTESTAZIONI)
        pagina = sessione.get(URL_TICINO, timeout=20)
        pagina.raise_for_status()
        if re.search(r"captcha", pagina.text, re.I):
            raise _ErroreLettura("il portale chiede un controllo anti-robot (captcha)")
        soup = BeautifulSoup(pagina.text, "html.parser")
        modulo = _trova_modulo(soup)
        if modulo is None:
            raise _ErroreLettura("nella pagina non ho trovato il modulo di ricerca")
        campo = _campo_nome(modulo, soup)
        dati = _dati_modulo(modulo, campo, nome, _pulsante_invio(modulo))
        indirizzo = urljoin(pagina.url, modulo.get("action") or pagina.url)
        risposta = sessione.post(indirizzo, data=dati, timeout=25, headers={"Referer": pagina.url})
        risposta.raise_for_status()
        if re.search(r"captcha", risposta.text, re.I):
            raise _ErroreLettura("il portale chiede un controllo anti-robot (captcha)")
        return _estrai_candidati(risposta.text)


def cerca_che(ragione_sociale: str) -> dict:
    """Cerca la ragione sociale nel registro di commercio del Ticino. Restituisce un dizionario:
        esito     'ok' (trovato con certezza) | 'scelta' (più possibilità: decide l'utente) |
                  'nessuno' | 'errore' | 'manca_nome'
        messaggio testo da mostrare (può contenere un link in formato markdown)
        che       numero CHE formattato (solo se esito == 'ok')
        candidati [{'nome', 'che', 'sede'}] (se esito == 'scelta')"""
    nome = (ragione_sociale or "").strip()
    if len(nome) < 3:
        return {"esito": "manca_nome", "messaggio": "Scrivi prima la ragione sociale (almeno 3 caratteri)."}
    try:
        candidati = _cerca_nel_portale(nome)
    except _ErroreLettura as errore:
        return {"esito": "errore", "messaggio": f"Non riesco a leggere il registro di commercio del Ticino: {errore}. {_MANUALE}"}
    except requests.RequestException as errore:
        return {"esito": "errore", "messaggio": f"Il registro di commercio del Ticino non ha risposto ({errore}). {_MANUALE}"}
    except Exception as errore:  # il portale può cambiare in modi imprevedibili: niente crash, solo un messaggio
        return {"esito": "errore", "messaggio": f"Risposta del portale non interpretabile ({type(errore).__name__}). {_MANUALE}"}

    if not candidati:
        return {"esito": "nessuno", "messaggio": f"Nessun numero CHE trovato nella risposta del registro. {_MANUALE}"}
    identici = [c for c in candidati if _normalizza(c["nome"]) == _normalizza(nome)]
    if len(identici) == 1:
        c = identici[0]
        return {"esito": "ok", "che": c["che"], "messaggio": f"Trovata: {c['nome']} — {c['che']}."}
    return {
        "esito": "scelta", "candidati": identici or candidati,
        "messaggio": "Nessuna corrispondenza esatta e sicura: scegli l'azienda giusta dall'elenco.",
    }
