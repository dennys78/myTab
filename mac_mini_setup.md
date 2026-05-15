# Istruzioni di Deploy - myTab (Per Sistemista / Coworker)

Questo documento contiene le istruzioni operative per installare, avviare e manutenere l'applicativo **myTab** (Cash Management System) sul server di produzione (Mac Mini).

L'applicativo è containerizzato tramite Docker e si compone di:
1. **Backend**: API Python (Django + Gunicorn)
2. **Frontend**: Dashboard React.js compilata staticamente e servita tramite Nginx (Reverse Proxy)
3. **Database**: SQLite3 montato su un volume persistente (`sqlite_data`)

---

## 1. Primo Setup (Installazione Iniziale)

Assicurati che sul Mac Mini siano installati **Git** e **Docker Desktop** (o Docker Engine + Docker Compose).

1. Apri il terminale e posizionati nella cartella in cui vuoi installare i servizi (es. `/Users/admin/ServerApps/`).
2. Clona il repository:
   ```bash
   git clone https://github.com/dennys78/myTab.git
   cd myTab
   ```
3. Avvia e compila le immagini Docker in modalità "detached" (background):
   ```bash
   docker-compose up -d --build
   ```

A questo punto l'applicativo è in ascolto sulla **porta 8080** del Mac Mini. 
(Se il Mac Mini ha IP `192.168.1.100`, la dashboard sarà visibile dal browser semplicemente visitando `http://192.168.1.100:8080`).

---

## 2. Aggiornamento dell'Applicativo (Release successive)

Quando lo sviluppatore effettua nuove modifiche al codice e le carica su GitHub, per aggiornare il server in produzione senza disservizi o perdita di dati, esegui questi comandi:

1. Entra nella cartella del progetto:
   ```bash
   cd path/to/myTab
   ```
2. Scarica le ultime modifiche dal repository:
   ```bash
   git pull origin main
   ```
3. Ricostruisci i container per applicare le modifiche (il flag `-d` mantiene il servizio in background e riavvia solo ciò che è cambiato):
   ```bash
   docker-compose up -d --build
   ```

---

## 3. Gestione e Persistenza dei Dati

> **ATTENZIONE CRITICA:** Il database dell'applicativo (`db.sqlite3`) risiede **esclusivamente all'interno di un volume Docker denominato `sqlite_data`**.

- **Non cancellare mai i volumi Docker** a meno che tu non voglia azzerare completamente lo storico delle chiusure cassa.
- Il comando `docker-compose down -v` cancella irreversibilmente i volumi. Usa **solo** `docker-compose down` se vuoi spegnere i container senza toccare i dati.
- Se devi fare un backup manuale del file SQLite (consigliato settimanalmente), lo trovi sul file system host di Docker ispezionando il volume:
  ```bash
  docker volume inspect mytab_sqlite_data
  ```

---

## 4. Configurazione Rete (OpenClaw)

L'applicativo espone un endpoint per l'ingestion dei dati tramite OCR (OpenClaw).
Se l'IP del Mac Mini è statico (es. `192.168.1.x`), assicurarsi che l'agente OCR invii i dati a:
`http://<IP_MAC_MINI>:8080/api/closures/insert/`

Non c'è bisogno di specificare la porta 8000. Nginx sulla porta 8080 farà da reverse-proxy intercettando tutto il traffico `/api/` e smistandolo in sicurezza al container Backend.
