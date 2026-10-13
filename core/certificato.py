"""Certificato di salario (modulo ufficiale 11) compilato con i dati delle buste paga di un anno."""
from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject

from core.buste.calcolo import buste_dipendente
from core.util import data_it

MODELLO = Path(__file__).resolve().parent.parent / "assets" / "moduli" / "certificato_salario.pdf"


def _n(x: float) -> str:
    return f"{round(x):,}".replace(",", "'")      # il modulo accetta solo franchi interi


def totali_anno(dip: dict, anno: int) -> dict | None:
    bb = [b for b in buste_dipendente(dip) if b["anno"] == anno]
    if not bb:
        return None
    s = lambda k: sum(float(b.get(k) or 0) for b in bb)
    lordo = s("lordo_avs") + s("ind_ass")
    assegni = s("assegni")
    deduz_avs = s("avs") + s("ad") + s("lainf")
    lpp = s("lpp")
    tot = lordo + assegni
    return {"mesi": [b["mese"] for b in bb], "salario": lordo, "assegni": assegni, "lordo": tot, "avs": deduz_avs,
            "lpp": lpp, "netto": tot - deduz_avs - lpp, "fonte": s("imposta")}


def certificato_pdf(az: dict, dip: dict, anno: int, luogo: str = "", rimborsi: dict | None = None) -> bytes:
    t = totali_anno(dip, anno)
    if t is None:
        raise ValueError("Nessuna busta paga per questo anno.")
    m0, m1 = min(t["mesi"]), max(t["mesi"])
    import calendar
    dal = f"01.{m0:02d}.{anno}"
    al = f"{calendar.monthrange(anno, m1)[1]:02d}.{m1:02d}.{anno}"
    sede = ", ".join(x for x in (az.get("ragione_sociale"), az.get("sede_via"),
                                  " ".join(y for y in (az.get("sede_npa"), az.get("sede_localita")) if y)) if x)
    v = {
        "AHVLinks_C": dip.get("numero_avs") or "",
        "TextLinks_C-GebDatum": data_it(dip.get("data_nascita")) if dip.get("data_nascita") else "",
        "TextLinks_D": str(anno), "TextLinks_E-von": dal, "TextLinks_E-bis": al,
        "TextMehrzeiligLinks_Empfaenger": "\n".join(x for x in (f"{dip.get('nome', '')} {dip.get('cognome', '')}".strip(), dip.get("via") or "",
                                                                 " ".join(y for y in (dip.get("npa"), dip.get("localita")) if y)) if x),
        "DezZahlNull_1": _n(t["salario"]),
        "DezZahlNull_8": _n(t["lordo"]), "DezZahlNull_9": _n(t["avs"]), "DezZahlNull_10_1": _n(t["lpp"]),
        "DezZahlNull_11": _n(t["netto"]),
        "TextMehrzeiligLinks_Bestaetigung": sede,
        "TextLinks_I": f"{luogo or az.get('sede_localita') or ''}, {data_it(__import__('datetime').date.today())}".strip(", "),
    }
    if t["assegni"]:
        v["TextLinks_7-Art"] = "Assegni familiari"
        v["DezZahlNull_7"] = _n(t["assegni"])
    if t["fonte"]:
        v["DezZahlNull_12"] = _n(t["fonte"])
    if az.get("note_certificato"):
        v["TextLinks_15_1"] = az["note_certificato"]
    r = PdfReader(str(MODELLO))
    w = PdfWriter()
    w.append(r)
    w.update_page_form_field_values(w.pages[0], v, auto_regenerate=False)
    for f in w.pages[0].get("/Annots", []):                  # croce su «A» (certificato di salario)
        o = f.get_object()
        if o.get("/T") == "OptionKreuzOhneRahmen_A":
            on = [k for k in o["/AP"]["/N"].keys() if k != "/Off"][0]
            o[NameObject("/V")] = NameObject(on)
            o[NameObject("/AS")] = NameObject(on)
    w._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()
