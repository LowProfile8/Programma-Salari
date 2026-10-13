"""core/contratti/ricalcolo.py — ricalcolo automatico dei contratti quando cambiano i dati del dipendente.

Se in un secondo momento si modifica età, nazionalità, permesso, stato civile, figli o dati del coniuge, per ogni contratto
salvato (modificabile) si ricalcolano LPP automatica e imposta alla fonte automatica, si rifà il PDF e si aggiornano i
valori salariali. Importi inseriti a mano (LPP o aliquota «manuale») restano com'erano.
"""

from core import db
from core.contratti import costruzione
from core.contratti import pdf as cpdf
from core.util import oggi


def ricalcola_dipendente(azienda_id: str, dipendente_id: str) -> int:
    """Restituisce quanti contratti sono stati aggiornati."""
    az = db.get_azienda(azienda_id)
    dip = db.get_dipendente(azienda_id, dipendente_id)
    if az is None or dip is None:
        return 0
    cambiati, nuovi = 0, []
    for c in dip.get("contratti", []):
        form = c.get("form")
        if not form:
            nuovi.append(c)
            continue
        esito = costruisci_contratto(az, dip, c["tipo"], form)
        r, valori = esito["r"], esito["valori"]
        if abs(r.netto - (c.get("calcolo") or {}).get("netto", -1)) < 0.005 and \
                abs(r.imposta_fonte_pct - (c.get("calcolo") or {}).get("imposta_fonte_pct", -1)) < 0.0005 and \
                abs(r.lpp - (c.get("calcolo") or {}).get("lpp", -1)) < 0.005:
            nuovi.append(c)
            continue
        c = {**c, "calcolo": dict(esito["contratto"]["calc"]), "valori": valori}
        try:
            pdf_bytes = cpdf.genera_pdf(esito["contratto"])
            if c.get("allegato_id"):
                db.elimina_allegato(azienda_id, dipendente_id, c["allegato_id"])
            nome = f"Contratto_{dip.get('cognome', '')}_{dip.get('nome', '')}_{c.get('data_inizio')}.pdf".replace(" ", "_")
            c["allegato_id"] = db.aggiungi_allegato(azienda_id, dipendente_id, nome, pdf_bytes, "contratto")
        except Exception:      # il PDF non deve bloccare l'aggiornamento dei dati
            pass
        nuovi.append(c)
        cambiati += 1
        # dopo aver modificato gli allegati l'elenco va riletto per non perdere le modifiche
        dip = db.get_dipendente(azienda_id, dipendente_id)
    if cambiati:
        ultimo = max(nuovi, key=lambda x: x.get("data_inizio") or "")
        valori = ultimo.get("valori") or dip.get("valori_salariali") or {}
        db.aggiorna_dipendente(azienda_id, dipendente_id, {"contratti": nuovi, "valori_salariali": valori})
    return cambiati


def costruisci_contratto(az: dict, dip: dict, tipo: str, form: dict) -> dict:
    """Come in «Crea contratto», con i dati ATTUALI del dipendente."""
    return costruzione.costruisci(az, dip, tipo, form, oggi())
