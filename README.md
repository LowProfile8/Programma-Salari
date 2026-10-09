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
Modelli PDF in assets/contratti/. Mancano: salario minimo cantonale per i contratti individuali (vedi minimi.py).

## Collegamento a Supabase (dati permanenti)
1. supabase.com -> progetto (regione europea) -> SQL Editor -> incolla `supabase_setup.sql` -> Run.
2. Project Settings -> API Keys: copia l'URL e la chiave **secret** (service_role). Non la password del database.
3. Genera la chiave di cifratura (comando in `.streamlit/secrets.toml.example`) e conservala in un posto sicuro.
4. Streamlit Cloud -> app -> Settings -> Secrets: incolla SUPABASE_URL, SUPABASE_KEY, ENCRYPTION_KEY, APP_PASSWORD.
Senza questi Secrets l'app usa i file locali (solo per provare). Il codice si può aggiornare quando si vuole: i dati restano su Supabase.

## Tenere attivo Supabase (piano gratuito)
Il file `.github/workflows/keepalive.yml` legge il database ogni 2 giorni, così non va mai in pausa.
Su GitHub: Settings -> Secrets and variables -> Actions -> aggiungi SUPABASE_URL e SUPABASE_KEY (gli stessi dei Secrets di Streamlit).
Per provarlo subito: scheda Actions -> keepalive-supabase -> Run workflow.
Streamlit Community Cloud mette comunque «a dormire» l'app dopo ~12 ore senza visite: al primo accesso basta un clic su «Yes, get this app back up!». I dati non si perdono.

## Imposta alla fonte (Ticino 2026)
Tabelle A, B, C, H, R, S, T, U in assets/fonte/tabelle_2026.json (estratte dal PDF ufficiale); regole in core/contratti/fonte.py.
Il calcolo automatico usa stato civile, attività del coniuge, figli a carico, nazionalità e permesso del dipendente (dati in archivio).

## Link per far compilare la scheda anagrafica al dipendente
Scheda dipendente -> «Scheda anagrafica» -> «Crea il link». Il dipendente apre il link (…/?scheda=CODICE), compila senza password,
e tu importi i dati con un clic. Facoltativo: APP_URL nei Secrets (indirizzo dell'app) per mostrare il link completo.
