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
