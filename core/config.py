"""core/config.py — nomi e costanti generali. Da qui si cambia il nome dello studio."""

NOME_STUDIO = "Athena Advisory Group"
SOTTOTITOLO = "Gestione salari e dipendenti"
TITOLO_PAGINA = "Athena — salari, contratti e archivio clienti"

# ── Opzioni dei menu a tendina delle Info aziendali ──────────────────────────
FORME_GIURIDICHE = ["Ditta individuale", "Sagl", "SA", "Società in nome collettivo"]

RAMO_RISTORAZIONE = "Ristorazione / alberghiero"
RAMO_ALTRO = "Altro"   # apre un campo per scrivere il ramo a mano
RAMI = [
    RAMO_RISTORAZIONE, "Takeaway", "Estetista", "Parrucchiere / barbiere", "Negozio", "E-commerce",
    "Studio di architettura", "Noleggio auto / moto", "Noleggio barche", "Compravendita veicoli",
]

VALUTE = ["EUR", "USD", "GBP", "CAD", "AUD", "JPY", "CNY", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "AED"]

# Metodo di rendiconto IVA
CRITERI_IVA = ["Incassato", "Fatturato"]

# Contratto di lavoro seguito dall'azienda
CONTRATTI_COLLETTIVI = [
    "Contratto individuale", "CCNL ristorazione / alberghiero", "CCL autotrasporti", "CPC parrucchieri e coiffeur",
]
