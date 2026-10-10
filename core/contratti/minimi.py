"""core/contratti/minimi.py — salari minimi dei contratti collettivi.

Fonti (PDF caricati dal titolare):
  * Autotrasporti: «Salari minimi» dal 1° gennaio 2026 (CCL autotrasporti Ticino 2024-2027).
  * Parrucchieri e coiffeur: CCL Coiffure Suisse, Appendice I «Tabelle del salario di base».
  * CCNL ristorazione/alberghiero: tabella NON ancora caricata -> MINIMI_CCNL vuoto.
  * Individuale: salario minimo cantonale NON ancora caricato -> MINIMO_CANTONALE_ORARIO = None.
Quando arrivano le tabelle mancanti basta compilare i due dizionari qui sotto: il resto del programma
(avvisi gialli, riduzione per il periodo d'introduzione) è già pronto.
"""

SETTIMANE_PER_MESE = 4.33   # CCL autotrasporti: «4.33 = numero fisso, media settimane in un mese»

# ── Autotrasporti 2026: salario orario lordo minimo (anno di servizio 1, anno di servizio 5) ─────────
AUTOTRASPORTI_2026 = {
    "Trasporto cose": {
        "B / BE": (19.00, 20.69),
        "C1 / C1E": (19.42, 21.10),
        "C": (19.54, 21.57),
        "CE, meccanici, capi operai, capi magazzinieri": (20.37, 22.46),
        "Veicoli speciali (autogru)": (23.46, 26.06),
        "Imballatori, magazzinieri, caricatori, manovali": (19.00, 20.07),
        "Disponenti": (24.48, 26.52),
    },
    "Trasporto persone": {
        "B / BE": (21.01, 23.10),
        "D / DE / D1 / D1E": (23.86, 26.20),
        "Disponenti": (24.48, 26.52),
    },
    "Lunga distanza / spedizionieri": {   # nel documento esiste solo il minimo del 1° anno di servizio
        "B / BE": (19.00, None),
        "C1 / C1E": (19.11, None),
        "C": (19.32, None),
        "CE, meccanici, capi operai, capi magazzinieri": (20.26, None),
        "Imballatori, magazzinieri, caricatori, manovali": (19.00, None),
        "Disponenti": (24.48, None),
    },
}
SUPPLEMENTO_AFC_MENSILE = 100.00   # autisti con attestato federale di capacità (AFC)

# ── Parrucchieri: salario di base mensile al 100% (1° anno, 2° anno, dal 3° anno) ────────────────
PARRUCCHIERI = {
    2025: {"Qualificato": (4080, 4080, 4280), "Semi-qualificato": (None, 3750, 4100), "Non qualificato": (3650, 3730, 4025)},
    2026: {"Qualificato": (4160, 4160, 4360), "Semi-qualificato": (None, 3880, 4150), "Non qualificato": (3780, 3830, 4100)},
    2027: {"Qualificato": (4240, 4240, 4460), "Semi-qualificato": (None, 3980, 4200), "Non qualificato": (3880, 3930, 4150)},
}
ANNI_PROFESSIONALI = ["1° anno", "2° anno", "3° anno e seguenti"]

# ── CCNL ristorazione/alberghiero: salari minimi mensili lordi a tempo pieno (art. 10 e 11 CCNL) ──
# Fonti: «Foglio informativo salari minimi CCNL 2026» (GastroSuisse) e brochure CCNL con la tabella 2027.
MINIMI_CCNL_ANNI = {
    2026: {"Ia": 3713.00, "Ib": 3943.00, "II": 4070.00, "IIIa": 4528.00, "IIIb": 4635.00, "IV": 5293.00, "Praticanti": 2390.00},
    2027: {"Ia": 3735.00, "Ib": 3967.00, "II": 4094.00, "IIIa": 4555.00, "IIIb": 4663.00, "IV": 5325.00, "Praticanti": 2404.00},
}
CATEGORIE_CCNL = {
    "Ia": "Cat. Ia — senza apprendistato",
    "Ib": "Cat. Ib — senza apprendistato, formazione Progresso",
    "II": "Cat. II — CFP (2 anni)",
    "IIIa": "Cat. IIIa — AFC",
    "IIIb": "Cat. IIIb — AFC + 6 giorni di perfezionamento",
    "IV": "Cat. IV — esame di professione",
    "Praticanti": "Praticanti (art. 11 CCNL)",
}
# categorie per cui è prevista la riduzione dell'8% nel periodo di introduzione
CATEGORIE_CON_RIDUZIONE = {"Ia", "Ib", "II", "IIIa"}
ORE_MESE_CCNL = {42.0: 182, 43.5: 189, 45.0: 195}   # «ore di lavoro previste al mese» del foglio informativo
MINIMI_CCNL: dict = MINIMI_CCNL_ANNI[2026]           # compatibilità

# ── Individuale: salario minimo cantonale (franchi all'ora) ──
MINIMO_CANTONALE_ORARIO = None


# ── Autorimesse (CCL Ticino, Appendice 1, salari minimi 2026): salario mensile minimo per anno dopo il tirocinio ──
# valore: (lista dei minimi per anno, giovani lavoratori riducibili all'80%/90%: non per le categorie con tirocinio di 4 anni)
AUTORIMESSE_2026 = {
    "Meccatronico / meccanico d'automobili / elettricista elettronico per autoveicoli (AFC 4 anni)": ([3854, 4495, 4790, 4834, 5497], False),
    "Meccanico di manutenzione / riparatore d'automobili (AFC 3 anni)": ([3584, 4279, 4514], True),
    "Assistente di manutenzione per automobili (CFP 2 anni)": ([3492], True),
    "Aiuto meccanico": ([4016], True),
    "Addetto al lavaggio, pulizia e preparazione estetica dei veicoli / addetto pneumatici": ([3977], True),
    "Impiegato del commercio al dettaglio AFC / commesso vendita pezzi di ricambio": ([3675, 3988, 4165, 4532, 4797], True),
    "Assistente del commercio al dettaglio CFP / magazziniere": ([3491, 3988, 4352], True),
    "Addetto alla vendita di carburanti": ([4061, 4269], True),
    "Impiegato di commercio generico o CFP": ([3612], True),
    "Impiegato di commercio operativo o AFC": ([3907], True),
    "Impiegato di commercio responsabile": ([4435], True),
    "Maestro meccanico / dipl. economia aziendale / coordinatore d'officina / capo meccanico / meccanico diagnostico (accordo individuale)": ([5914], True),
    "Consulente servizio clienti / ricezionista (accordo individuale, escluse provvigioni)": ([4752], True),
    "Carrozziere / fabbro di veicoli (si applica il CCL carrozzerie)": (None, False),
}
ANNI_DOPO_TIROCINIO = ["1° anno", "2° anno", "3° anno", "4° anno", "5° anno"]
DIVISORE_ORARIO_AUTORIMESSE = {41.5: 180, 45.0: 195, 47.0: 203}   # 180 e 203 dal CCL art. 13.2; 195 = 45 x 4,33 (non scritto nel CCL)

# ── Pulizie e facility services (CCL Ticino, Appendice 1B, 2026-2027) ──
# valore: (salario orario minimo, salario mensile minimo a tempo pieno, pulizie ordinarie -> festivi 1,35% invece di 3,58%)
PULIZIE_2026 = {
    "Pulizie ordinarie I": (18.50, 3367.00, True),
    "Pulizie ordinarie II (con formazione)": (19.00, 3458.00, True),
    "Resp. pulizie immobile / capo oggetto (accordo individuale, minimo cat. II)": (19.00, 3458.00, True),
    "Pulizie speciali I": (19.00, 3458.00, False),
    "Pulizie speciali II (con formazione)": (19.70, 3585.40, False),
    "Caposquadra (accordo individuale, minimo cat. II)": (19.70, 3585.40, False),
    "Pulizie ospedali I": (19.00, 3458.00, False),
    "Pulizie ospedali II (con formazione)": (19.70, 3585.40, False),
    "Resp. pulizie ospedali / capo oggetto (accordo individuale, minimo cat. II)": (19.70, 3585.40, False),
    "Pulizie veicoli I": (19.00, 3458.00, False),
    "Pulizie veicoli II (con formazione)": (19.70, 3585.40, False),
    "Operatore pulizia ordinaria con CFP (2 anni)": (20.00, 3640.00, True),
    "Operatore pulizia ordinaria con AFC (3 anni)": (21.20, 3858.40, True),
    "Giovane diplomato CFP (fino a 25 anni) — 1° anno dopo il diploma": (17.00, 3094.00, True),
    "Giovane diplomato CFP (fino a 25 anni) — 2° anno dopo il diploma": (18.00, 3276.00, True),
    "Giovane diplomato CFP (fino a 25 anni) — 3° anno dopo il diploma": (19.00, 3458.00, True),
    "Giovane diplomato AFC (fino a 25 anni) — 1° anno dopo il diploma": (18.02, 3279.65, True),
    "Giovane diplomato AFC (fino a 25 anni) — 2° anno dopo il diploma": (19.08, 3472.55, True),
    "Giovane diplomato AFC (fino a 25 anni) — 3° anno dopo il diploma": (20.14, 3665.50, True),
    "Personale amministrativo — impiegato generico": (19.18, 3490.80, False),
    "Personale amministrativo — impiegato operativo": (20.73, 3772.50, False),
    "Personale amministrativo — supervisore": (23.49, 4275.50, False),
}
