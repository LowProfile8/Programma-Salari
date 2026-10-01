"""core/contratti/calcolo.py — regole e calcoli dei contratti di lavoro.

Tipi di contratto: individuale, CCNL (ristorazione/alberghiero), CCL autotrasporti, CPC parrucchieri.
Durata: indeterminato, determinato, a ore.

Tutto ciò che deriva dai documenti caricati è indicato nei commenti; ciò che è una scelta di calcolo
(ad es. il modo di sommare vacanze e festività) è indicato come tale.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from core.contratti import minimi

INDIVIDUALE, CCNL, AUTOTRASPORTI, CPC = "individuale", "ccnl", "autotrasporti", "cpc"
NOMI_TIPO = {
    INDIVIDUALE: "Contratto individuale",
    CCNL: "CCNL ristorazione / alberghiero",
    AUTOTRASPORTI: "CCL autotrasporti",
    CPC: "CPC parrucchieri e coiffeur",
}
INDETERMINATO, DETERMINATO, ORE = "indeterminato", "determinato", "ore"
NOMI_DURATA = {INDETERMINATO: "Indeterminato", DETERMINATO: "Determinato", ORE: "A ore"}

# ore settimanali a tempo pieno
BASI_ORE_AZIENDA = {"Normale": 42.0, "Stagionale": 43.5, "Piccola": 45.0}   # richiesta del titolare
ORE_PIENO_AUTOTRASPORTI = [45.0, 46.0, 47.0, 47.5, 48.0]                    # CCL art. 14.1 (45-48), base 45
ORE_PIENO_CPC = 43.0                                                         # CCL parrucchieri art. 24.1

ALIQUOTA_13 = 0.0833          # tredicesima 8.33% (art. 6 CCL autotrasporti; art. 12 CCNL; modelli)
ORE_ANNUE_ORARIO = 2160       # per i contratti a ore: salario orario lordo x 2160 (richiesta del titolare)
LIMITE_AD_MENSILE = 12350.0   # salario massimo assicurato AD: CHF 148'200 all'anno / 12


def arrotonda(valore: float, decimali: int = 2) -> float:
    quant = Decimal(1).scaleb(-decimali)
    return float(Decimal(str(valore)).quantize(quant, rounding=ROUND_HALF_UP))


# ── ore settimanali ───────────────────────────────────────────────────────────
def ore_pieno(tipo: str, categoria_azienda: str = "Normale", ore_autotrasporti: float = 45.0) -> float:
    if tipo == AUTOTRASPORTI:
        return ore_autotrasporti
    if tipo == CPC:
        return ORE_PIENO_CPC
    return BASI_ORE_AZIENDA.get(categoria_azienda, 42.0)   # individuale e CCNL


def ore_settimanali(tipo: str, percentuale: float, categoria_azienda: str = "Normale",
                    ore_autotrasporti: float = 45.0) -> float:
    """Ore settimanali = percentuale lavorativa x ore a tempo pieno (42 / 43.5 / 45 per normale / stagionale /
    piccola; 45 autotrasporti; 43 parrucchieri)."""
    return arrotonda(ore_pieno(tipo, categoria_azienda, ore_autotrasporti) * percentuale / 100.0, 2)


# ── vacanze e festività ───────────────────────────────────────────────────────
def eta_anni(data_nascita, riferimento: date | None = None) -> int | None:
    if not data_nascita:
        return None
    r = riferimento or date.today()
    return r.year - data_nascita.year - ((r.month, r.day) < (data_nascita.month, data_nascita.day))


def info_vacanze_festivita(tipo: str, eta: int | None, cinquanta_quindici: bool = False) -> dict:
    """Diritti di legge/contratto. Restituisce testo informativo e percentuali per i contratti a ore."""
    giovane = eta is not None and eta < 20
    if tipo == AUTOTRASPORTI:   # CCL art. 18.1 e 21; percentuali dal foglio di calcolo CPC autotrasporti
        cinque = giovane or cinquanta_quindici
        return {"vacanze": "5 settimane" if cinque else "4 settimane", "vacanze_pct": 10.64 if cinque else 8.33,
                "festivita": "9 festività pagate + 1° maggio (art. 21)", "festivita_pct": 3.58}
    if tipo == CCNL:            # modello CCNL art. 14-15
        return {"vacanze": "5 settimane (35 giorni civili)", "vacanze_pct": 10.65,
                "festivita": "6 festività pagate all'anno (0,5 al mese)", "festivita_pct": 2.27}
    if tipo == CPC:             # CCL parrucchieri art. 28.1
        giorni = "27,5 giorni" if giovane else "22,5 giorni (27,5 dopo 5 anni nella stessa azienda dopo la formazione)"
        return {"vacanze": giorni, "vacanze_pct": None,
                "festivita": "giorni festivi equiparati alle domeniche, senza detrazione (art. 32)", "festivita_pct": None}
    return {"vacanze": "5 settimane fino ai 20 anni, poi 4 (art. 329a CO)" if eta is None else
            ("5 settimane" if giovane else "4 settimane"),
            "vacanze_pct": 10.64 if giovane else 8.33,
            "festivita": "secondo la legislazione cantonale (da definire)", "festivita_pct": None}


# ── aliquote dell'azienda ─────────────────────────────────────────────────────
@dataclass
class Aliquote:
    avs: float = 5.30
    ad: float = 1.10
    igm: float = 0.0
    lainf: float = 0.0


def aliquote_da_azienda(azienda: dict) -> Aliquote:
    """Legge dalla tabella delle aliquote dell'azienda la quota a carico del dipendente."""
    a = Aliquote()
    for r in azienda.get("aliquote", []):
        voce = str(r.get("voce", "")).lower()
        valore = float(r.get("dipendente") or 0.0)
        if "avs" in voce:
            a.avs = valore
        elif voce.startswith("ad ") or voce.startswith("ad(") or "disoccupazione" in voce:
            a.ad = valore
        elif "lainf" in voce or "non professionale" in voce:
            a.lainf = valore
        elif "malattia" in voce or "indennit" in voce:
            a.igm = valore
    return a


# ── salario ───────────────────────────────────────────────────────────────────
@dataclass
class Parametri:
    tipo: str
    durata: str
    salario_fisso: float                  # al mese (indeterminato/determinato) o all'ora (a ore)
    tredicesima: str = "mensile"          # "mensile" (quota nel salario) / "annuale" (una volta l'anno)
    bonus: float = 0.0
    vacanze_pct: float = 0.0              # solo contratti a ore
    festivita_pct: float = 0.0            # solo contratti a ore
    aliquote: Aliquote = field(default_factory=Aliquote)
    lpp: float = 0.0
    imposta_fonte_pct: float = 0.0
    vitto_alloggio: float = 0.0
    altra_deduzione: float = 0.0
    commissione_paritetica: float = 0.0   # CHF/mese (autotrasporti: art. 37 CCL)
    assegni_figli: float = 0.0
    rimborsi: float = 0.0
    arrotondamenti: float = 0.0


@dataclass
class Risultato:
    orario: bool = False
    salario_fisso: float = 0.0
    quota_13: float = 0.0
    bonus: float = 0.0
    vacanze: float = 0.0
    festivita: float = 0.0
    lordo_avs: float = 0.0
    avs: float = 0.0
    ad: float = 0.0
    igm: float = 0.0
    lainf: float = 0.0
    lpp: float = 0.0
    imposta_fonte: float = 0.0
    imposta_fonte_pct: float = 0.0
    vitto_alloggio: float = 0.0
    altra_deduzione: float = 0.0
    commissione_paritetica: float = 0.0
    totale_deduzioni: float = 0.0
    assegni_figli: float = 0.0
    rimborsi: float = 0.0
    arrotondamenti: float = 0.0
    totale_assegni: float = 0.0
    netto: float = 0.0
    lordo_annuo: float = 0.0
    avs_annuo: float = 0.0


def calcola(p: Parametri) -> Risultato:
    r = Risultato(orario=p.durata == ORE, salario_fisso=p.salario_fisso, bonus=p.bonus)
    base = p.salario_fisso
    if r.orario:
        if p.tipo == CCNL:   # modello CCNL: vacanze e festività sul salario di base, 13a su base+vacanze+festività
            r.festivita = arrotonda(base * p.festivita_pct / 100)
            r.vacanze = arrotonda(base * p.vacanze_pct / 100)
        else:                # esempio CPC autotrasporti: festività sul base, vacanze su (base+festività), 13a sul totale
            r.festivita = arrotonda(base * p.festivita_pct / 100)
            r.vacanze = arrotonda((base + r.festivita) * p.vacanze_pct / 100)
        r.quota_13 = arrotonda((base + r.festivita + r.vacanze) * ALIQUOTA_13)
        r.lordo_avs = arrotonda(base + r.festivita + r.vacanze + r.quota_13 + p.bonus)
        r.lordo_annuo = arrotonda(r.lordo_avs * ORE_ANNUE_ORARIO)
    else:
        r.quota_13 = arrotonda(base * ALIQUOTA_13) if p.tredicesima == "mensile" else 0.0
        r.lordo_avs = arrotonda(base + r.quota_13 + p.bonus)
        r.lordo_annuo = arrotonda(r.lordo_avs * (12 if p.tredicesima == "mensile" else 13))
    r.avs_annuo = r.lordo_annuo      # il salario AVS coincide con il lordo determinante

    base_ad = r.lordo_avs if r.orario else min(r.lordo_avs, LIMITE_AD_MENSILE)
    r.avs = arrotonda(r.lordo_avs * p.aliquote.avs / 100)
    r.ad = arrotonda(base_ad * p.aliquote.ad / 100)
    r.igm = arrotonda(r.lordo_avs * p.aliquote.igm / 100)
    r.lainf = arrotonda(r.lordo_avs * p.aliquote.lainf / 100)
    r.lpp = arrotonda(p.lpp)
    r.imposta_fonte_pct = p.imposta_fonte_pct
    r.imposta_fonte = arrotonda(r.lordo_avs * p.imposta_fonte_pct / 100)
    r.vitto_alloggio = arrotonda(p.vitto_alloggio)
    r.altra_deduzione = arrotonda(p.altra_deduzione)
    r.commissione_paritetica = arrotonda(p.commissione_paritetica)
    r.totale_deduzioni = arrotonda(r.avs + r.ad + r.igm + r.lainf + r.lpp + r.imposta_fonte + r.vitto_alloggio
                                   + r.altra_deduzione + r.commissione_paritetica)
    r.assegni_figli, r.rimborsi, r.arrotondamenti = arrotonda(p.assegni_figli), arrotonda(p.rimborsi), arrotonda(p.arrotondamenti)
    r.totale_assegni = arrotonda(r.assegni_figli + r.rimborsi)
    r.netto = arrotonda(r.lordo_avs - r.totale_deduzioni + r.totale_assegni + r.arrotondamenti)
    return r


def commissione_paritetica_autotrasporti(percentuale: float) -> float:
    """CCL art. 37: CHF 18.00 al mese (9 + 9); con impiego <= 50% CHF 9.00."""
    return 9.00 if percentuale <= 50 else 18.00


# ── verifica dei minimi ───────────────────────────────────────────────────────
@dataclass
class EsitoMinimo:
    stato: str            # "ok" / "sotto" / "nd" (non verificabile)
    messaggio: str
    minimo: float | None = None


def _chf(v: float) -> str:
    return f"{v:,.2f}".replace(",", "'")


def verifica_minimo(*, tipo: str, durata: str, salario_fisso: float, percentuale: float, ore_sett: float,
                    ore_pieno_sett: float, anno: int, settore: str = "", categoria: str = "", anni_servizio: int = 1,
                    afc: bool = False, qualifica: str = "", anno_prof: int = 0, livello_ccnl: str = "",
                    riduzione_introduzione: float = 0.0) -> EsitoMinimo:
    """Confronta il salario fisso con il minimo contrattuale, in proporzione alla percentuale lavorativa."""
    if tipo == AUTOTRASPORTI:
        riga = minimi.AUTOTRASPORTI_2026.get(settore, {}).get(categoria)
        if not riga:
            return EsitoMinimo("nd", "Scegli settore e categoria del veicolo per verificare il salario minimo.")
        orario = riga[1] if (anni_servizio >= 5 and riga[1]) else riga[0]
        if durata == ORE:
            minimo = orario + (minimi.SUPPLEMENTO_AFC_MENSILE / (ore_pieno_sett * minimi.SETTIMANE_PER_MESE) if afc else 0)
            minimo = arrotonda(minimo)
            unita = "all'ora"
        else:
            minimo = orario * ore_sett * minimi.SETTIMANE_PER_MESE
            if afc:
                minimo += minimi.SUPPLEMENTO_AFC_MENSILE * percentuale / 100
            minimo = arrotonda(minimo)
            unita = "al mese"
        base_txt = (f"minimo CCL autotrasporti 2026 ({settore}, {categoria}, "
                    f"{'dal 5° anno' if anni_servizio >= 5 else '1° anno di servizio'}"
                    f"{', con supplemento AFC' if afc else ''}): CHF {_chf(minimo)} {unita}")
    elif tipo == CPC:
        anno_t = min(max(anno, 2025), 2027)
        valori = minimi.PARRUCCHIERI[anno_t].get(qualifica)
        if not valori:
            return EsitoMinimo("nd", "Scegli la qualifica per verificare il salario minimo.")
        mensile100 = valori[min(max(anno_prof, 0), 2)]
        if mensile100 is None:
            return EsitoMinimo("nd", f"Per {qualifica.lower()} al 1° anno professionale il CCL non fissa un salario minimo.")
        minimo = arrotonda(mensile100 * percentuale / 100)
        unita = "al mese"
        base_txt = f"minimo CCL parrucchieri {anno_t} ({qualifica}, {minimi.ANNI_PROFESSIONALI[anno_prof]}) al {percentuale:g}%: CHF {_chf(minimo)} al mese"
    elif tipo == CCNL:
        valore = minimi.MINIMI_CCNL.get(livello_ccnl.split(" ")[0]) if livello_ccnl else None
        if valore is None:
            return EsitoMinimo("nd", "Tabella dei salari minimi CCNL non ancora caricata: il controllo del minimo non è possibile.")
        minimo = arrotonda(valore * (1 - riduzione_introduzione) * (percentuale / 100 if durata != ORE else 1))
        unita = "al mese"
        base_txt = f"minimo CCNL livello {livello_ccnl}: CHF {_chf(minimo)}"
    else:
        if minimi.MINIMO_CANTONALE_ORARIO is None:
            return EsitoMinimo("nd", "Per il contratto individuale il salario minimo cantonale non è ancora caricato: nessun controllo.")
        orario = minimi.MINIMO_CANTONALE_ORARIO
        minimo = arrotonda(orario if durata == ORE else orario * ore_sett * minimi.SETTIMANE_PER_MESE)
        unita = "all'ora" if durata == ORE else "al mese"
        base_txt = f"salario minimo cantonale: CHF {_chf(minimo)} {unita}"

    if salario_fisso + 0.005 < minimo:
        return EsitoMinimo("sotto", f"Salario sotto il minimo: {base_txt}. Hai inserito CHF {_chf(salario_fisso)}.", minimo)
    return EsitoMinimo("ok", f"Salario nei minimi: {base_txt}.", minimo)
