"""core/contratti/fonte.py — imposta alla fonte, Cantone Ticino, tabelle 2026.

Fonti (PDF caricati): «Aliquote di imposta alla fonte, edizione 2026» (tabelle A, B, C, H, R, S, T, U) e
«Direttiva cantonale in ambito imposte alla fonte» (valida dal 1.1.2026).

Regole applicate (Direttiva punti 2.1 e 2.3):
  A  persone sole (celibi/nubili, divorziati, separati, vedovi) senza figli a carico nello stesso nucleo
  B  coniugati con coniuge senza attività lucrativa            (numero = figli a carico)
  C  coniugati con coniuge con attività lucrativa              (numero = figli a carico)
  H  persone sole che vivono con figli a carico                (da H1)
  R S T U = come A B C H per i «nuovi frontalieri fiscali»
  Stato civile non noto: A0; coniugato senza dati sul coniuge: C0.
  Cittadini svizzeri e permesso C: nessuna imposta alla fonte. Assoggettamento dal 1° gennaio dell'anno dei 18 anni.
  L'aliquota si legge sul reddito annuo lordo determinante (es. lordo mensile x 13) e si applica al lordo del mese.
"""

import json
from functools import lru_cache
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent.parent / "assets" / "fonte" / "tabelle_2026.json"
LINK_CALCOLATORE = "https://www4.ti.ch/dfe/dc/sportello/calcolatori-dimposta/iaf2024"
REDDITO_MASSIMO = 1_200_000
DATA_NUOVI_FRONTALIERI = "2023-07-17"   # accordo Svizzera-Italia sui frontalieri, in vigore dal 17 luglio 2023 (da verificare nella Direttiva)
NUOVO_FRONTALIERE = {"A": "R", "B": "S", "C": "T", "H": "U"}


@lru_cache(maxsize=1)
def _tabelle() -> dict:
    return json.loads(FILE.read_text(encoding="utf-8"))


def esente(nazionalita: str | None, permesso: str | None) -> bool:
    """Cittadini svizzeri e titolari del permesso C non pagano l'imposta alla fonte."""
    return (nazionalita or "") == "Svizzera" or (permesso or "") in ("Cittadino svizzero", "Permesso C")


def nuovo_frontaliere(permesso, data_entrata, data_inizio_contratto) -> tuple[bool, str]:
    """I titolari di permesso G che iniziano a lavorare dal 17.7.2023 sono «nuovi frontalieri» (tabelle R, S, T, U).
    Si usa la data di entrata in Svizzera dell'anagrafica; se manca, la data di inizio del contratto."""
    if (permesso or "") != "Permesso G (frontaliere)":
        return False, ""
    riferimento = data_entrata or data_inizio_contratto
    nuovo = bool(riferimento) and str(riferimento)[:10] >= DATA_NUOVI_FRONTALIERI
    origine = "data di entrata in Svizzera" if data_entrata else "data di inizio del contratto (manca la data di entrata in anagrafica)"
    return nuovo, f"Permesso G: {'nuovo' if nuovo else 'vecchio'} frontaliere in base alla {origine}."


def _figli(v) -> int:
    try:
        return max(0, min(9, int(str(v).strip())))
    except (ValueError, TypeError):
        return 0


def codice_tariffa(stato_civile, coniuge_lavora, n_figli, figli_a_carico, nuovo_frontaliere: bool = False) -> tuple[str, str]:
    """(codice, spiegazione), ad es. ('B1', 'coniugato, coniuge senza attività lucrativa, 1 figlio a carico')."""
    figli = _figli(n_figli) if figli_a_carico != "No" else 0
    coniugato = stato_civile in ("Coniugato/a", "Unione domestica registrata")
    if coniugato:
        if coniuge_lavora == "No":
            lettera, spieg = "B", "coniugato, coniuge senza attività lucrativa"
        elif coniuge_lavora == "Sì":
            lettera, spieg = "C", "coniugato, coniuge con attività lucrativa"
        else:
            lettera, spieg, figli = "C", "coniugato, attività del coniuge non indicata (C0 come da Direttiva)", 0
    elif stato_civile and figli > 0 and figli_a_carico == "Sì":
        lettera, spieg = "H", "persona sola con figli a carico nello stesso nucleo"
    else:
        lettera = "A"
        spieg = "persona sola" if stato_civile else "stato civile non indicato (A0 come da Direttiva)"
        if figli > 0 and figli_a_carico != "Sì":
            spieg += ": figli non indicati come «a carico» (nello stesso nucleo)"
        figli = 0
    if nuovo_frontaliere:
        lettera = NUOVO_FRONTALIERE[lettera]
    if lettera in ("H", "U") and figli == 0:
        figli = 1
    if figli and lettera in ("B", "C", "S", "T", "H", "U"):
        spieg += f", {figli} figli a carico" if figli > 1 else ", 1 figlio a carico"
    return f"{lettera}{figli}", spieg


def aliquota(codice: str, reddito_annuo: float) -> float | None:
    """Aliquota in % dalla tabella; None se il reddito supera CHF 1'200'000 o il codice non esiste."""
    t = _tabelle().get(codice[0])
    if not t or reddito_annuo is None or reddito_annuo > REDDITO_MASSIMO:
        return None
    r = max(1, int(reddito_annuo))
    colonna = int(codice[1:])
    for a, b, valori in t:
        if a <= r <= b:
            return valori[colonna]
    return None


def valuta(*, nazionalita, permesso, stato_civile, coniuge_lavora, n_figli, figli_a_carico, reddito_annuo: float,
           anno_nascita: int | None = None, anno: int | None = None, nuovo_frontaliere: bool = False) -> dict:
    """Risultato completo: {'dovuta': bool, 'codice', 'spiegazione', 'aliquota' (%), 'motivo'}."""
    if esente(nazionalita, permesso):
        return {"dovuta": False, "codice": "—", "spiegazione": "", "aliquota": 0.0,
                "motivo": "Cittadino svizzero o permesso C: imposta alla fonte non dovuta."}
    if anno_nascita and anno and anno < anno_nascita + 18:
        return {"dovuta": False, "codice": "—", "spiegazione": "", "aliquota": 0.0,
                "motivo": "Sotto i 18 anni: l'assoggettamento inizia il 1° gennaio dell'anno dei 18 anni."}
    codice, spieg = codice_tariffa(stato_civile, coniuge_lavora, n_figli, figli_a_carico, nuovo_frontaliere)
    return {"dovuta": True, "codice": codice, "spiegazione": spieg, "aliquota": aliquota(codice, reddito_annuo), "motivo": ""}
