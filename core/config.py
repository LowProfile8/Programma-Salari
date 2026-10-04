"""core/config.py — nomi e costanti generali. Da qui si cambia il nome dello studio."""

NOME_STUDIO = "Athena Advisory Group"
SOTTOTITOLO = "Gestione salari e dipendenti"
TITOLO_PAGINA = "Athena — salari, contratti e archivio clienti"

# ── Opzioni dei menu a tendina delle Info aziendali ──────────────────────────
FORME_GIURIDICHE = ["Ditta individuale", "Sagl", "SA", "Società in nome collettivo"]

RAMO_RISTORAZIONE = "Ristorazione / alberghiero"
RAMO_TAKEAWAY = "Takeaway"
RAMO_ALTRO = "Altro"   # apre un campo per scrivere il ramo a mano
RAMI = [
    RAMO_RISTORAZIONE, RAMO_TAKEAWAY, "Estetista", "Parrucchiere / barbiere", "Negozio", "E-commerce",
    "Studio di architettura", "Noleggio auto / moto", "Noleggio barche", "Compravendita veicoli",
    "Logistica e trasporti", "Servizi e consulenze", "Commerciale",
    "Edilizia e costruzioni", "Industria e produzione", "Sanità e assistenza", "Informatica e tecnologia",
    "Immobiliare", "Agricoltura e giardinaggio",
]

VALUTE = ["EUR", "USD", "GBP", "CAD", "AUD", "JPY", "CNY", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "AED"]

# Rami che seguono il Piano 1 Basis (LPP GastroSocial) come proposta automatica
RAMI_PIANO1_BASIS = {RAMO_RISTORAZIONE, RAMO_TAKEAWAY}

# Metodo di rendiconto IVA
CRITERI_IVA = ["Incassato (prestazioni convenute)", "Fatturato (prestazioni ricevute)"]

# Contratto di lavoro seguito dall'azienda
CONTRATTI_COLLETTIVI = [
    "Contratto individuale", "CCNL ristorazione / alberghiero", "CCL autotrasporti", "CPC parrucchieri e coiffeur",
]
