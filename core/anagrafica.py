"""core/anagrafica.py — legge una «Scheda anagrafica nuove assunzioni» compilata (PDF o testo) e ne ricava i dati
del dipendente. Il modello è quello caricato dal titolare («Scheda anagrafica - Foglio1.pdf»).

NOTA: finora esiste solo il modello VUOTO: la lettura è stata provata su un testo di esempio ma non su una scheda reale
compilata. Prima di applicare i dati, il programma mostra sempre un'anteprima da controllare.
"""

import io
import re

from core.paesi import NAZIONALITA

# etichette del modello, nell'ordine in cui compaiono: (espressione, campo)
_DIP = [
    (r"Cognome", "cognome"), (r"Nome", "nome"), (r"Indirizzo di residenza", "via"), (r"CAP", "npa"), (r"Luogo", "localita"),
    (r"Indirizzo in Ticino", "_via_ti"), (r"CAP", "_npa_ti"), (r"Luogo", "_loc_ti"), (r"Data di nascita", "data_nascita"),
    (r"Luogo di nascita", "luogo_nascita"), (r"N\. ?Telefono", "telefono"), (r"Indirizzo Email", "email"), (r"N° ?AVS", "numero_avs"),
    (r"Impiego", "funzione"), (r"Cognome e Nome Padre", "_padre"), (r"Data di nascita", "_padre_nascita"),
    (r"Cognome e Nome Madre", "_madre"), (r"Data di nascita", "_madre_nascita"), (r"Stato civile", "stato_civile"),
    (r"Data matrimonio", "data_matrimonio"), (r"Permesso di lavoro", "permesso"), (r"Paese d'origine", "paese_origine"),
    (r"Nazionalità", "nazionalita"), (r"Data di entrata in CH", "data_entrata_svizzera"),
    (r"Ultimo datore di lavoro in CH", "ultimo_datore"), (r"Ultimo giorno di lavoro in CH", "ultimo_lavoro_data"),
]
_CON = [
    (r"Cognome", "cognome"), (r"Nome", "nome"), (r"Via N°", "via"), (r"CAP", "npa"), (r"Luogo", "localita"),
    (r"Data di nascita", "data_nascita"), (r"Luogo di nascita", "luogo_nascita"), (r"N° ?AVS", "numero_avs"),
    (r"Lavora in Svizzera\?", "_lavora_ch"), (r"Da che data", "_da_data"), (r"Percepisce un salario maggiore rispetto al dipendente\?", "_salario_maggiore"),
    (r"Lavora all'estero\?", "_lavora_estero"), (r"All'estero percepisce assegni per i figli\?", "assegni"),
]
_BANCA = [(r"Nome Banca", "banca_nome"), (r"Sede", "banca_sede"), (r"N° ?IBAN", "iban")]


def testo_da_file(contenuto: bytes, nome: str) -> str:
    if nome.lower().endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(contenuto)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    return contenuto.decode("utf-8", errors="ignore")


def _sezioni(testo: str) -> dict:
    t = re.sub(r"[ \t]+", " ", testo)
    marcatori = [("dip", r"dati dipendente"), ("con", r"Coniuge o Compagno/?a"), ("figli", r"\nFigli\b"), ("banca", r"\nBanca\b")]
    pos = []
    for chiave, pat in marcatori:
        m = re.search(pat, t, re.I)
        if m:
            pos.append((m.start(), chiave, m.end()))
    pos.sort()
    out = {}
    for i, (inizio, chiave, fine_marcatore) in enumerate(pos):
        fine = pos[i + 1][0] if i + 1 < len(pos) else len(t)
        out[chiave] = t[fine_marcatore:fine]
    return out


def _estrai(blocco: str, schema: list[tuple[str, str]]) -> dict:
    """Scorre le etichette trovate nell'ordine e assegna il testo che le segue."""
    unici = sorted({p for p, _ in schema}, key=len, reverse=True)      # prima le etichette più lunghe («Luogo di nascita» prima di «Luogo»)
    pattern = "|".join(f"(?:{p})\\s*:?" if not p.endswith(r"\?") else f"(?:{p})" for p in unici)
    etichette = list(re.finditer(pattern, blocco, re.I))
    out, puntatore = {}, 0
    for i, m in enumerate(etichette):
        trovato = None
        for j in range(puntatore, len(schema)):
            if re.fullmatch(f"(?:{schema[j][0]})\\s*:?", m.group(0).strip(), re.I) or re.fullmatch(schema[j][0], m.group(0).strip(" :"), re.I):
                trovato = j
                break
        if trovato is None:
            continue
        fine = etichette[i + 1].start() if i + 1 < len(etichette) else len(blocco)
        valore = blocco[m.end():fine].strip(" :\n\t")
        valore = re.sub(r"\s*\n\s*", " ", valore).strip()
        if valore:
            out[schema[trovato][1]] = valore
        puntatore = trovato + 1
    return out


def _data(v: str) -> str | None:
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", v or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None


def _si_no(v: str | None) -> str:
    v = (v or "").strip().lower()
    if not v:
        return ""
    return "Sì" if v[0] in "sx✓v1" or v.startswith("yes") else "No"


def _stato(v: str) -> str:
    v = (v or "").lower()
    for chiave, nome in (("unione", "Unione domestica registrata"), ("coniug", "Coniugato/a"), ("spos", "Coniugato/a"),
                         ("celib", "Celibe/Nubile"), ("nubil", "Celibe/Nubile"), ("divorz", "Divorziato/a"), ("vedov", "Vedovo/a")):
        if chiave in v:
            return nome
    return ""


def _permesso(v: str) -> str:
    v = (v or "").strip()
    m = re.search(r"\b([BCGL])\b", v, re.I)
    if "svizz" in v.lower():
        return "Cittadino svizzero"
    if "90" in v or "notifica" in v.lower():
        return "Notifica 90 giorni"
    if m:
        return {"B": "Permesso B", "C": "Permesso C", "G": "Permesso G (frontaliere)", "L": "Permesso L"}[m.group(1).upper()]
    return v


def _nazione(v: str) -> str:
    v = (v or "").strip()
    for n in NAZIONALITA:
        if n.lower() == v.lower():
            return n
    agg = {"italian": "Italia", "svizzer": "Svizzera", "frances": "Francia", "tedesc": "Germania", "spagnol": "Spagna", "portoghes": "Portogallo"}
    for k, n in agg.items():
        if v.lower().startswith(k):
            return n
    return v


def _nome_cognome(v: str) -> tuple[str, str]:
    parti = (v or "").split()
    return (parti[0], " ".join(parti[1:])) if parti else ("", "")


def leggi_scheda(testo: str) -> dict:
    """Restituisce i dati nel formato dell'archivio (solo i campi trovati)."""
    sez = _sezioni(testo)
    d = _estrai(sez.get("dip", testo), _DIP)
    dati: dict = {}
    for campo in ("cognome", "nome", "via", "npa", "localita", "luogo_nascita", "telefono", "email", "numero_avs", "funzione",
                  "paese_origine", "ultimo_datore", "iban", "banca_nome", "banca_sede"):
        if d.get(campo):
            dati[campo] = d[campo]
    for campo in ("data_nascita", "data_matrimonio", "data_entrata_svizzera", "ultimo_lavoro_data"):
        if _data(d.get(campo)):
            dati[campo] = _data(d[campo])
    if d.get("stato_civile"):
        dati["stato_civile"] = _stato(d["stato_civile"])
    if d.get("permesso"):
        dati["permesso"] = _permesso(d["permesso"])
    if d.get("nazionalita"):
        dati["nazionalita"] = _nazione(d["nazionalita"])
    for rel in ("padre", "madre"):
        if d.get(f"_{rel}"):
            cognome, nome = _nome_cognome(d[f"_{rel}"])
            dati[rel] = {"cognome": cognome, "nome": nome, "data_nascita": _data(d.get(f"_{rel}_nascita"))}
    if "con" in sez:
        c = _estrai(sez["con"], _CON)
        con = {k: c[k] for k in ("cognome", "nome", "via", "npa", "localita", "luogo_nascita", "numero_avs") if c.get(k)}
        if _data(c.get("data_nascita")):
            con["data_nascita"] = _data(c["data_nascita"])
        ch, estero = _si_no(c.get("_lavora_ch")), _si_no(c.get("_lavora_estero"))
        if ch or estero:
            con["lavora"] = "Sì" if "Sì" in (ch, estero) else "No"
            if con["lavora"] == "Sì":
                con["lavora_dove"] = "Svizzera" if ch == "Sì" else "Estero"
                con["salario_maggiore"] = _si_no(c.get("_salario_maggiore")) or ""
        if c.get("assegni"):
            con["assegni"] = _si_no(c["assegni"])
        if con:
            dati["coniuge"] = con
    if "figli" in sez:
        figli = []
        for cognome, nome, nascita in re.findall(r"Cognome:?\s*(\S*)\s*Nome:?\s*(\S*)\s*Data di nascita:?\s*([\d./-]*)", sez["figli"]):
            if cognome or nome:
                figli.append({"cognome": cognome, "nome": nome, "data_nascita": _data(nascita)})
        if figli:
            dati["figli"], dati["n_figli"] = figli, str(len(figli))
        m = re.search(r"figli sono a tuo carico\?\s*(\S+)", sez["figli"], re.I)
        if m:
            dati["figli_a_carico"] = _si_no(m.group(1))
    if "banca" in sez:
        b = _estrai(sez["banca"], _BANCA)
        for k in ("banca_nome", "banca_sede", "iban"):
            if b.get(k):
                dati[k] = b[k]
    return dati


def unisci(esistente: dict, nuovi: dict) -> dict:
    """Aggiorna `esistente` con i dati letti, senza cancellare nulla (i dizionari annidati si fondono)."""
    risultato = dict(esistente)
    for k, v in nuovi.items():
        if isinstance(v, dict):
            base = dict(risultato.get(k) or {})
            base.update({a: b for a, b in v.items() if b not in (None, "")})
            risultato[k] = base
        else:
            risultato[k] = v
    return risultato
