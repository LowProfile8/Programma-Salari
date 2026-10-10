"""core/lpp.py — Piano «Uno Basis» di GastroSocial (cassa pensione, ramo ristorazione / alberghiero), anno 2026.

Fonte: «Uno Basis — Deduzione salariale mensile 2026» (MER 1004, GastroSocial), copia in
assets/lpp/uno_basis_2026.pdf. Tutti gli importi sono MENSILI, in franchi.

Calcolo (pagina 2 del documento: GastroSocial calcola sul salario lordo esatto dichiarato):
    salario assicurato = salario lordo - deduzione di coordinamento (CHF 2'205)
                         con minimo CHF 315 e massimo CHF 5'355
    trattenuta al dipendente = salario assicurato x aliquota
        25 - 64/65 anni: 7%   (dichiarato nel documento)
        18 - 24 anni:    0.5% (NON scritto nel documento: ricavato dalla tabella; riproduce tutte
                               le 59 righe, vedi test. Da confermare con GastroSocial.)
    sotto CHF 1'890 al mese: non assicurato (trattenuta 0).

La TABELLA_UFFICIALE serve come controllo e per la regola di arrotondamento del documento
(frazioni fino a 50 franchi: salario inferiore; oltre: superiore). Per la busta paga si usa il calcolo
effettivo (`trattenuta_dipendente`), come fa la cassa.

Da gestire quando faremo il contratto (qui NON ancora coperto): fine dell'assicurazione a 64 anni + 6 mesi
per le donne e 65 per gli uomini, e chi ha meno di 18 anni.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

SOGLIA_ACCESSO_MENSILE = 1890.0
SALARIO_AVS_MASSIMO_MENSILE = 7560.0
DEDUZIONE_COORDINAMENTO_MENSILE = 2205.0
SALARIO_ASSICURATO_MINIMO = 315.0
SALARIO_ASSICURATO_MASSIMO = 5355.0

CATEGORIA_GIOVANI = "18-24"
CATEGORIA_ADULTI = "25-64/65"
ALIQUOTA_DIPENDENTE = {CATEGORIA_ADULTI: Decimal("0.07"), CATEGORIA_GIOVANI: Decimal("0.005")}

# (salario lordo mensile, trattenuta 18-24, trattenuta 25-64/65) — dal PDF ufficiale
TABELLA_UFFICIALE = [
    (1890, 1.60, 22.05),
    (1900, 1.60, 22.05),
    (2000, 1.60, 22.05),
    (2100, 1.60, 22.05),
    (2200, 1.60, 22.05),
    (2300, 1.60, 22.05),
    (2400, 1.60, 22.05),
    (2500, 1.60, 22.05),
    (2600, 2.00, 27.65),
    (2700, 2.50, 34.65),
    (2800, 3.00, 41.65),
    (2900, 3.50, 48.65),
    (3000, 4.00, 55.65),
    (3100, 4.50, 62.65),
    (3200, 5.00, 69.65),
    (3300, 5.50, 76.65),
    (3400, 6.00, 83.65),
    (3500, 6.50, 90.65),
    (3600, 7.00, 97.65),
    (3700, 7.50, 104.65),
    (3800, 8.00, 111.65),
    (3900, 8.50, 118.65),
    (4000, 9.00, 125.65),
    (4100, 9.50, 132.65),
    (4200, 10.00, 139.65),
    (4300, 10.50, 146.65),
    (4400, 11.00, 153.65),
    (4500, 11.50, 160.65),
    (4600, 12.00, 167.65),
    (4700, 12.50, 174.65),
    (4800, 13.00, 181.65),
    (4900, 13.50, 188.65),
    (5000, 14.00, 195.65),
    (5100, 14.50, 202.65),
    (5200, 15.00, 209.65),
    (5300, 15.50, 216.65),
    (5400, 16.00, 223.65),
    (5500, 16.50, 230.65),
    (5600, 17.00, 237.65),
    (5700, 17.50, 244.65),
    (5800, 18.00, 251.65),
    (5900, 18.50, 258.65),
    (6000, 19.00, 265.65),
    (6100, 19.50, 272.65),
    (6200, 20.00, 279.65),
    (6300, 20.50, 286.65),
    (6400, 21.00, 293.65),
    (6500, 21.50, 300.65),
    (6600, 22.00, 307.65),
    (6700, 22.50, 314.65),
    (6800, 23.00, 321.65),
    (6900, 23.50, 328.65),
    (7000, 24.00, 335.65),
    (7100, 24.50, 342.65),
    (7200, 25.00, 349.65),
    (7300, 25.50, 356.65),
    (7400, 26.00, 363.65),
    (7500, 26.50, 370.65),
    (7560, 26.80, 374.85),
]


def categoria_eta(data_nascita: date, anno: int) -> str | None:
    """Categoria per l'anno indicato: dal 1° gennaio successivo al 17° compleanno (18-24) e dal 1° gennaio
    successivo al 24° compleanno (25-64/65). Sotto i 18 anni: None (non assicurato)."""
    eta_nell_anno = anno - data_nascita.year
    if eta_nell_anno < 18:
        return None
    return CATEGORIA_GIOVANI if eta_nell_anno <= 24 else CATEGORIA_ADULTI


def salario_assicurato(lordo_mensile: float) -> float:
    """Salario lordo - coordinamento, tenuto fra 315 e 5'355. 0 se sotto la soglia di accesso."""
    if lordo_mensile < SOGLIA_ACCESSO_MENSILE:
        return 0.0
    return min(max(lordo_mensile - DEDUZIONE_COORDINAMENTO_MENSILE, SALARIO_ASSICURATO_MINIMO), SALARIO_ASSICURATO_MASSIMO)


def trattenuta_dipendente(lordo_mensile: float, categoria: str) -> float:
    """Trattenuta mensile a carico del dipendente (calcolo effettivo, arrotondata al centesimo)."""
    assicurato = Decimal(str(salario_assicurato(lordo_mensile)))
    importo = assicurato * ALIQUOTA_DIPENDENTE[categoria]
    return float(importo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def trattenuta_da_tabella(lordo_mensile: float, categoria: str) -> float:
    """Valore letto dalla tabella ufficiale (con la sua regola di arrotondamento del salario)."""
    if lordo_mensile < SOGLIA_ACCESSO_MENSILE:
        return 0.0
    if lordo_mensile >= SALARIO_AVS_MASSIMO_MENSILE:
        riga = 7560
    elif lordo_mensile < 1900:
        riga = 1890
    else:
        base = int(lordo_mensile // 100 * 100)
        riga = base if lordo_mensile - base <= 50 else base + 100
        riga = min(riga, 7560)
    for lordo, giovani, adulti in TABELLA_UFFICIALE:
        if lordo == riga:
            return giovani if categoria == CATEGORIA_GIOVANI else adulti
    raise ValueError(f"Riga non trovata: {riga}")
