# Fiduciaria — gestione salari, contratti e archivio clienti

Avvio locale:
    pip install -r requirements.txt
    cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # poi cambia la password
    streamlit run app.py

Pubblicazione: repository GitHub PRIVATO -> share.streamlit.io -> "Create app" -> main file `app.py`;
password nei Secrets dell'app (APP_PASSWORD).

IMPORTANTE: i dati sono in `data/archivio.json`, che su Streamlit Cloud si azzera a ogni riavvio.
Prima di usare dati reali sostituire `core/db.py` con un database esterno (es. Supabase).

Struttura: app.py (navigazione) · core/ (stile, dati, utilità) · modules/ (pagine)

Numero CHE: il tasto automatico legge il registro di commercio del Ticino (core/registro.py, non provato dal vivo);
il link manuale porta a Zefix con la ragione sociale già inserita.
LPP ristorazione: Piano 1 Basis GastroSocial 2026 in core/lpp.py (tabella e formule dal PDF in assets/lpp/).
Registro di commercio del Ticino: link in core/registro.py.

Pagine: home (Archivio, Crea contratto, Crea busta paga, Tabelle ferie e festività) · archivio · info azienda ·
dipendenti · scheda dipendente (allegati in data/allegati/, anch'essi da spostare su un archivio esterno).
Modifiche non salvate: pop-up «Vuoi salvare?» (core/uscita.py). Campi che ripartono puliti a ogni ingresso: core/nav.py.

Contratti: core/contratti/ (calcolo.py regole e calcoli, minimi.py tabelle dei salari minimi, pdf.py compilazione dei modelli).
Modelli PDF in assets/contratti/. Mancano: tabella minimi CCNL, minimo cantonale, modello CPC parrucchieri (vedi minimi.py).
