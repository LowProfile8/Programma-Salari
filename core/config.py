"""core/config.py — nomi e costanti generali. Da qui si cambia il nome dello studio."""

NOME_STUDIO = "Athena Advisory Group"
SOTTOTITOLO = "Gestione salari e dipendenti"
TITOLO_PAGINA = "Athena — salari, contratti e archivio clienti"

# ── Opzioni dei menu a tendina delle Info aziendali ──────────────────────────
FORME_GIURIDICHE = ["Ditta individuale", "Sagl", "SA", "Società in nome collettivo"]

RAMO_RISTORAZIONE = "Ristorazione / alberghiero"
RAMI = [
    RAMO_RISTORAZIONE, "Commercio", "Edilizia e artigianato", "Servizi e consulenza",
    "Sanità e cure", "Industria e produzione", "Trasporti e logistica", "Immobiliare",
]

VALUTE = ["EUR", "USD", "GBP", "CAD", "AUD", "JPY", "CNY", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "AED"]

# Per il ramo ristorazione/alberghiero l'LPP segue il «Piano 1 Basis». Quando avrai il link del
# piano, incollalo qui: comparirà nelle Info aziendali e servirà per la formula nel contratto.
LINK_LPP_PIANO1_BASIS = ""

CRITERI_IVA = ["Fatturato ricevuto (incassato)", "Fatturato emesso (convenuto)"]
