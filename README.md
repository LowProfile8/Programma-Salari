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

Ricerca automatica del numero CHE (Zefix): servono credenziali gratuite (zefix@bj.admin.ch) nei Secrets
(ZEFIX_USER, ZEFIX_PASSWORD). Senza, resta il link al registro.
LPP ristorazione: Piano 1 Basis GastroSocial 2026 in core/lpp.py (tabella e formule dal PDF in assets/lpp/).
Registro di commercio del Ticino: link in core/registro.py.
