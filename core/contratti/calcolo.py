"""core/contratti/calcolo.py — regole e calcoli dei contratti di lavoro.

Tipi di contratto: individuale, CCNL (ristorazione/alberghiero), CCL autotrasporti, CPC parrucchieri.
Durata: indeterminato, determinato, a ore.

Tutto ciò che deriva dai documenti caricati è indicato nei commenti; ciò che è una scelta di calcolo
(ad es. il modo di sommare vacanze e festività) è indicato come tale.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from core import lpp
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
        lunghe = giovane or cinquanta_quindici     # 27,5 giorni fino a 20 anni, oppure dopo 5 anni nella stessa azienda dopo la formazione
        return {"vacanze": "27,5 giorni (art. 28 CCL)" if lunghe else "22,5 giorni (art. 28 CCL)",
                "vacanze_pct": 11.83 if lunghe else 9.47,          # nota 13 dell'art. 31 CCL
                "festivita": "giorni festivi cantonali equiparati alle domeniche (art. 32 CCL); per i salari orari 3,58% (9 giorni, da confermare)",
                "festivita_pct": 3.58}
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
    rimborsi_sett: float = 0.0            # rimborsi settoriali non soggetti a trattenute (forfait trasferta, lavaggio abiti...)


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
    rimborsi_sett: float = 0.0
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
        r.quota_13 = arrotonda(base * ALIQUOTA_13) if p.tredicesima != "nessuna" else 0.0   # 8.33% sul solo salario di base
        r.lordo_avs = arrotonda(base + r.festivita + r.vacanze + r.quota_13 + p.bonus)
        r.lordo_annuo = arrotonda(r.lordo_avs * ORE_ANNUE_ORARIO)
    else:
        r.quota_13 = arrotonda(base * ALIQUOTA_13) if p.tredicesima == "mensile" else 0.0
        r.lordo_avs = arrotonda(base + r.quota_13 + p.bonus)
        r.lordo_annuo = arrotonda(r.lordo_avs * (13 if p.tredicesima == "annuale" else 12))
    r.avs_annuo = r.lordo_annuo      # il salario AVS coincide con il lordo determinante

    base_ad = r.lordo_avs if r.orario else min(r.lordo_avs, LIMITE_AD_MENSILE)
    r.avs = arrotonda(r.lordo_avs * p.aliquote.avs / 100)
    r.ad = arrotonda(base_ad * p.aliquote.ad / 100)
    r.igm = arrotonda(r.lordo_avs * p.aliquote.igm / 100)
    r.lainf = arrotonda(r.lordo_avs * p.aliquote.lainf / 100)
    r.lpp = arrotonda(p.lpp)
    r.imposta_fonte_pct = p.imposta_fonte_pct
    base_if = r.lordo_avs + (0.0 if r.orario else p.assegni_figli + p.rimborsi + p.rimborsi_sett)   # Direttiva 2.2.3
    r.imposta_fonte = arrotonda(base_if * p.imposta_fonte_pct / 100)
    r.vitto_alloggio = arrotonda(p.vitto_alloggio)
    r.altra_deduzione = arrotonda(p.altra_deduzione)
    r.commissione_paritetica = arrotonda(p.commissione_paritetica)
    r.totale_deduzioni = arrotonda(r.avs + r.ad + r.igm + r.lainf + r.lpp + r.imposta_fonte + r.vitto_alloggio
                                   + r.altra_deduzione + r.commissione_paritetica)
    r.assegni_figli, r.rimborsi, r.arrotondamenti = arrotonda(p.assegni_figli), arrotonda(p.rimborsi), arrotonda(p.arrotondamenti)
    r.rimborsi_sett = arrotonda(p.rimborsi_sett)
    if r.orario:    # importi mensili: si pagano a parte, non fanno parte del netto orario
        r.totale_assegni = arrotonda(r.rimborsi)
    else:
        r.totale_assegni = arrotonda(r.assegni_figli + r.rimborsi + r.rimborsi_sett)
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
        if durata == ORE:
            minimo, unita = arrotonda(mensile100 / 185), "all'ora (CCL art. 38: salario mensile diviso 185)"
        else:
            minimo, unita = arrotonda(mensile100 * percentuale / 100), "al mese"
        base_txt = f"minimo CCL parrucchieri {anno_t} ({qualifica}, {minimi.ANNI_PROFESSIONALI[anno_prof]}){'' if durata == ORE else f' al {percentuale:g}%'}: CHF {_chf(minimo)} {unita}"
    elif tipo == CCNL:
        tabella = minimi.MINIMI_CCNL_ANNI.get(min(max(anno, 2026), 2027), {})
        valore = tabella.get(livello_ccnl)
        if valore is None:
            return EsitoMinimo("nd", "Scegli la categoria CCNL per verificare il salario minimo.")
        mensile = valore * (1 - riduzione_introduzione)
        if durata == ORE:
            ore_mese = minimi.ORE_MESE_CCNL.get(float(ore_pieno_sett), 182)
            minimo = arrotonda(mensile / ore_mese)
            unita = "all'ora (senza supplementi)"
        else:
            minimo = arrotonda(mensile * percentuale / 100)
            unita = "al mese"
        rid_txt = f", ridotto dell'{riduzione_introduzione * 100:g}% (periodo di introduzione)" if riduzione_introduzione else ""
        base_txt = f"minimo CCNL {anno if anno in (2026, 2027) else 2026}, categoria {minimi.CATEGORIE_CCNL[livello_ccnl]}{rid_txt}: CHF {_chf(minimo)} {unita}"
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


# ── rimborsi settoriali (non soggetti a trattenute) ───────────────────────────
# autotrasporti: CCL art. 13.2 (forfait mensile di trasferta); CCNL: art. 30 (lavaggio vestiario e grembiuli)
FORFAIT_TRASFERTA = {"Nessuno": 0.0, "Rientra la sera (CHF 300 al mese)": 300.0, "Non rientra la sera (CHF 800 al mese)": 800.0}
RIMBORSI_CCNL = [("Lavaggio e stiro di giacche / vestiario (art. 30 CCNL)", 50.0),
                 ("Lavaggio e stiro dei grembiuli (art. 30 CCNL)", 20.0)]


PRESTAZIONI_VITTO_AVS = {   # importi minimi AVS (art. 11 cpv. 2 OAVS), citati nel commento al CCNL art. 29: (al giorno, al mese)
    "Alloggio": (11.50, 345.0), "Colazione": (3.50, 105.0), "Pranzo": (10.0, 300.0), "Cena": (8.0, 240.0),
    "Pensione completa (vitto)": (21.50, 645.0), "Pensione completa con alloggio": (33.0, 990.0),
}


def avviso_vitto_alloggio(tipo: str, importo: float, prestazione: str | None = None) -> list[tuple[str, str]]:
    """Elenco (livello, testo): «errore» = importo troppo alto, «avviso» = da controllare."""
    if importo <= 0:
        return []
    out: list[tuple[str, str]] = []
    if tipo == AUTOTRASPORTI:
        out.append(("avviso", "Il CCL autotrasporti non prevede trattenute per vitto e alloggio: le indennità spettano al dipendente "
                              "(art. 13). Verifica che la trattenuta sia concordata per iscritto."))
        return out
    if tipo == CPC:
        out.append(("avviso", "CCL parrucchieri: verifica nel CCL l'eventuale regolamentazione di vitto e alloggio prima di trattenere."))
        return out
    riferimento = "CCNL art. 29" if tipo == CCNL else "contratto individuale (art. 13 del modello)"
    out.append(("avviso", f"{riferimento}: serve un accordo scritto; senza accordo valgono le tariffe minime AVS per le prestazioni "
                          "effettivamente ricevute (solo i pasti consumati; in caso di vacanze o malattia l'importo si riduce)."))
    if prestazione in PRESTAZIONI_VITTO_AVS:
        giorno, mese = PRESTAZIONI_VITTO_AVS[prestazione]
        if importo > mese + 0.005:
            out.append(("errore", f"Trattenuta per vitto/alloggio troppo alta: CHF {importo:,.2f} al mese per «{prestazione}», "
                                  f"mentre il valore AVS è CHF {giorno:.2f} al giorno (CHF {mese:,.0f} al mese)."))
        elif importo < mese - 0.005:
            out.append(("avviso", f"Importo sotto il valore AVS di CHF {mese:,.0f} al mese per «{prestazione}»: la differenza "
                                  "rientra nel salario AVS determinante."))
    elif importo > 990:
        out.append(("errore", f"Trattenuta per vitto e alloggio troppo alta: CHF {importo:,.2f} al mese; il massimo AVS (pensione "
                              "completa con alloggio) è CHF 990."))
    return out


# ── Codice delle obbligazioni: regole salariali per il contratto individuale (da verificare) ─────────────────
RIFERIMENTI_CO = [
    "Art. 322: il datore di lavoro paga il salario convenuto o d'uso; la tredicesima è dovuta solo se pattuita (art. 322d).",
    "Art. 323: salario pagato alla fine di ogni mese, salvo diverso accordo scritto (il modello prevede il 6 del mese successivo).",
    "Art. 323b: il datore di lavoro consegna un conteggio salariale; le trattenute devono essere legittime e concordate.",
    "Art. 324a: salario in caso di malattia/infortunio per un tempo limitato (3 settimane nel 1° anno, poi secondo scala), "
    "salvo assicurazione equivalente (IGM).",
    "Art. 329a: vacanze di almeno 4 settimane all'anno (5 fino ai 20 anni compiuti); non si possono sostituire con denaro (art. 329d). "
    "Per impieghi irregolari l'indennità del 8,33% (4 sett.) / 10,64% (5 sett.) va indicata separatamente.",
    "Art. 321c: ore supplementari compensate con tempo libero di pari durata o pagate con supplemento del 25%, salvo accordo scritto.",
    "Art. 327a: il datore di lavoro rimborsa tutte le spese necessarie all'esecuzione del lavoro.",
    "Art. 335b-335c: periodo di prova di 1 mese (massimo 3 mesi se pattuito); disdetta: 1 mese nel 1° anno, 2 mesi dal 2° al 9°, 3 mesi dopo.",
    "Art. 340-340c: il divieto di concorrenza dopo la fine del rapporto richiede la forma scritta e al massimo 3 anni.",
    "Nei contratti individuali non esiste un salario minimo nel CO: vale il salario minimo cantonale, se previsto.",
]


# ── controlli: trattenute troppo alte, non dovute o salario troppo basso ──────
def controlla_conteggio(*, tipo: str, durata: str, r: "Risultato", par: "Parametri", eta: int | None, anno_inizio: int,
                        anno_nascita: int | None, ore_sett: float, percentuale: float, esente_if: bool,
                        lpp_max: float | None, minimo: "EsitoMinimo") -> list[tuple[str, str]]:
    """Elenco di (livello, messaggio). Livello «errore» = molto probabile sbaglio, «avviso» = da controllare."""
    out: list[tuple[str, str]] = []
    unita = "all'ora" if r.orario else "al mese"
    lordo = r.lordo_avs
    if par.salario_fisso <= 0:
        return out
    if minimo.stato == "sotto":
        out.append(("errore", "Salario troppo basso: " + minimo.messaggio))
    if r.netto <= 0:
        out.append(("errore", f"Il salario netto è zero o negativo (CHF {r.netto:,.2f} {unita}): le trattenute superano il lordo."))
    elif lordo > 0 and r.totale_deduzioni / lordo > 0.35:
        out.append(("avviso", f"Trattenute molto alte: {r.totale_deduzioni / lordo * 100:.1f}% del lordo AVS "
                              f"(CHF {r.totale_deduzioni:,.2f} su {lordo:,.2f}). Controlla importi e percentuali."))
    # AVS / AD
    if par.aliquote.avs > 5.3 + 1e-9:
        out.append(("errore", f"AVS/AI/IPG al {par.aliquote.avs:g}%: la quota del dipendente è del 5,3%. Controlla le Info aziendali."))
    if par.aliquote.ad > 1.1 + 1e-9:
        out.append(("errore", f"AD al {par.aliquote.ad:g}%: la quota del dipendente è dell'1,1% (fino a CHF 12'350 al mese)."))
    if anno_nascita is not None and anno_inizio < anno_nascita + 18 and (r.avs or r.ad):
        out.append(("avviso", "Dipendente sotto i 18 anni: i contributi AVS/AD si pagano dal 1° gennaio dopo il 17° compleanno; "
                              "controlla se le trattenute AVS e AD sono dovute."))
    if eta is not None and eta >= 65 and (r.avs or r.ad):
        out.append(("avviso", "Dipendente in età AVS: l'AD non è più dovuta e l'AVS ha una franchigia di CHF 1'400 al mese per datore "
                              "di lavoro (da verificare)."))
    # LPP
    if r.lpp > 0 and not r.orario and lordo < lpp.SOGLIA_ACCESSO_MENSILE:
        out.append(("errore", f"LPP non dovuta: il salario (CHF {lordo:,.2f}) è sotto la soglia di accesso di "
                              f"CHF {lpp.SOGLIA_ACCESSO_MENSILE:,.0f} al mese."))
    if r.lpp > 0 and anno_nascita is not None and anno_inizio < anno_nascita + 18:
        out.append(("errore", "LPP non dovuta: sotto i 18 anni non si è assicurati."))
    if lpp_max is not None and r.lpp > lpp_max + 0.005:
        out.append(("avviso", f"LPP troppo alta rispetto al Piano 1 Basis (CHF {r.lpp:,.2f} invece di CHF {lpp_max:,.2f})."))
    # LAINF: assicurazione infortuni non professionali solo da 8 ore settimanali
    if r.lainf > 0 and not r.orario and ore_sett < 8:
        out.append(("errore", f"LAINF non dovuta: con {ore_sett:g} ore settimanali (meno di 8) non si è assicurati contro gli infortuni "
                              "non professionali."))
    # imposta alla fonte
    if esente_if and par.imposta_fonte_pct:
        out.append(("errore", "Imposta alla fonte non dovuta: cittadino svizzero o permesso C."))
    elif par.imposta_fonte_pct > 25:
        out.append(("avviso", f"Imposta alla fonte molto alta ({par.imposta_fonte_pct:g}%): controlla con il calcolatore del Ticino."))
    elif r.orario and par.imposta_fonte_pct == 0 and not esente_if:
        pass
    # vitto/alloggio e altre trattenute
    if lordo > 0 and (r.vitto_alloggio + r.altra_deduzione) / lordo > 0.25:
        out.append(("avviso", "Vitto, alloggio e altre trattenute superano il 25% del salario lordo."))
    if r.vitto_alloggio > 990 and not r.orario:
        out.append(("avviso", f"Vitto e alloggio CHF {r.vitto_alloggio:,.2f}: sopra il valore massimo AVS (circa CHF 990 al mese)."))
    # commissione paritetica autotrasporti
    if tipo == AUTOTRASPORTI and not r.orario:
        att = commissione_paritetica_autotrasporti(percentuale)
        if abs(r.commissione_paritetica - att) > 0.005:
            out.append(("avviso", f"Commissione paritetica: per il {percentuale:g}% di impiego sono dovuti CHF {att:.2f} al mese."))
    return out
