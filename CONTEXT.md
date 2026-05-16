# myTaba — Contesto di Progetto per Handoff Agente

> Leggi questo file per avere tutto il contesto del progetto senza dover rileggere il codice da zero.
> Aggiornato: 2026-05-16

---

## Chi è l'utente

- **Nome**: Daniele
- **Server**: Mac Mini M4 16GB
- **Gateway AI**: OpenClaw su `localhost:18789`
- **Telegram bot**: @serverClaw123bot
- **App in produzione**: `http://serverapp.asuscomm.com:8080`
- **Home Assistant**: `http://192.168.1.142:8123`
- Risponde **sempre in italiano**, è tecnico, vuole risposte concise.

---

## Cos'è myTaba

Sistema di gestione chiusure di cassa con OCR, pensato per un esercizio commerciale (tabaccheria/retail). Permette di fotografare lo scontrino di chiusura cassa, estrarre i dati automaticamente via OCR e tenerli in un dashboard web con funzioni di riconciliazione.

---

## Stack tecnologico

| Layer | Tecnologia |
|-------|-----------|
| Backend | Python 3.11, Django 4.2, Gunicorn |
| OCR | pytesseract + Pillow (lingua italiana) |
| Bot | python-telegram-bot 22.5 |
| Frontend | React 19, Vite 5, Lucide React |
| Database | SQLite3 (persistito su volume Docker) |
| Infra | Docker Compose, Nginx (reverse proxy) |

---

## Struttura del progetto

```
myTaba/
├── cash_manager/           # Config Django (settings, urls, wsgi)
├── reconciliation/         # App Django principale
│   ├── models.py           # CashClosure, CashClosureItem, BankTransaction
│   ├── views.py            # 5 view REST (insert, extract, list, update, delete)
│   ├── urls.py             # Routing API
│   ├── ocr_parser.py       # Parsing OCR con regex (formato italiano: 1.250,00)
│   └── migrations/         # 2 migrazioni
├── dashboard_app/          # Frontend React
│   ├── src/
│   │   ├── App.jsx         # Dashboard principale (tabella chiusure, stats)
│   │   ├── AcquisisciChiusure.jsx  # Caricamento immagine + preview OCR
│   │   └── index.css       # Tema dark, layout responsive
│   ├── nginx.conf          # Proxy Nginx (porta 8080 → backend 8000)
│   ├── vite.config.js      # Proxy dev: /api → http://127.0.0.1:8000
│   └── Dockerfile          # Multi-stage build React
├── bot.py                  # Bot Telegram per invio foto chiusure
├── Dockerfile              # Immagine backend (con tesseract-ocr + ita lang)
├── docker-compose.yml      # Orchestrazione: backend + frontend + volume
├── requirements.txt        # Dipendenze Python
└── mac_mini_setup.md       # Istruzioni deploy su Mac Mini
```

---

## API Endpoints

Base URL produzione: `http://serverapp.asuscomm.com:8080`

| Metodo | Endpoint | Scopo |
|--------|----------|-------|
| POST | `/api/closures/insert/` | Inserisce chiusura via JSON |
| POST | `/api/closures/extract/` | Upload immagine(i), OCR, ritorna dati estratti |
| GET | `/api/closures/list/` | Lista tutte le chiusure con dettagli |
| PUT/POST | `/api/closures/update/<id>/` | Aggiorna chiusura e voci |
| DELETE | `/api/closures/delete/<id>/` | Elimina una chiusura |

**Struttura JSON chiusura:**
```json
{
  "id": 1,
  "date": "2026-05-10",
  "operator": "Mario",
  "summary": {
    "contanti": "100.00",
    "pag_pos": "250.00",
    "cassa_auto": "0.00",
    "reso_cont": "0.00",
    "reso_auto": "0.00",
    "distrib": "0.00",
    "totale": "350.00"
  },
  "items": [
    { "id": 1, "descrizione": "REPARTO 1", "entrate": "200.00", "uscite": "0.00", "saldo": "200.00" }
  ]
}
```

---

## Modelli database

### CashClosure (tabella principale)
- `date` (DateField)
- `operator` (CharField, nullable)
- `contanti`, `pag_pos`, `cassa_auto`, `reso_cont`, `reso_auto`, `distrib`, `totale` (DecimalField)
- `created_at` (auto)

### CashClosureItem (voci di dettaglio, FK → CashClosure)
- `descrizione`, `entrate`, `uscite`, `saldo`

### BankTransaction (modello presente, non ancora usato)
- `date`, `amount`, `description`
- **Nessun endpoint né UI implementata ancora**

---

## Frontend — Viste principali

| Vista | Componente | Funzionalità |
|-------|-----------|-------------|
| Dashboard | `App.jsx` | Tabella chiusure, espandi dettaglio, modifica inline, elimina, stat mensili |
| Acquisisci | `AcquisisciChiusure.jsx` | Upload foto → OCR → preview editabile → salva su DB |

Navigazione: sidebar desktop + hamburger mobile. Tema dark con CSS custom.

---

## Cosa ha fatto l'agente precedente (cronologia commit)

| Commit | Cosa ha fatto |
|--------|--------------|
| `2c31c79` | Fix: aggiunto tesseract-ocr e pack lingua italiana nel Dockerfile backend |
| `fae4e52` | Fix: struttura JSX rotta in App.jsx (sidebar spariva) |
| `7d961e5` | Feat: aggiunta vista "Acquisisci Chiusure" con upload immagine e preview OCR editabile |
| `25abbfa` | Feat: UI responsive per mobile, modifica nomi reparti abilitata |
| `b5655d1` | Feat: proxy Vite per ambiente di sviluppo |
| `b65684d` | Feat: bottone Elimina nei dettagli espansi |
| `5ab632b` | Fix: porta frontend aggiornata a 8080 in docker-compose |
| `264248d` | Feat: funzionalità eliminazione chiusura cassa |

**Branch**: `main` — clean, 2 commit avanti rispetto a `origin/main`.

---

## Problemi noti / TODO impliciti

### Sicurezza (da risolvere prima di produzione seria)
- `DEBUG = True` in `settings.py` — **da disabilitare**
- `SECRET_KEY` hardcoded in settings
- `CORS_ALLOW_ALL_ORIGINS = True`
- Tutte le view hanno `@csrf_exempt`
- Token Telegram hardcoded in `bot.py` (riga ~72)

### Funzionalità mancanti
- `BankTransaction`: modello Django pronto, ma nessun endpoint/UI
- Nessuna autenticazione utente
- Nessuna paginazione nella lista chiusure
- File di test vuoto (`reconciliation/tests.py`)
- Nessun logging

### OCR
- Parser basato su regex calibrate per un formato specifico di scontrino
- Formato numerico atteso: italiano (`1.250,00`)
- Può fallire su ricevute con layout diverso

---

## Deploy

```bash
# Prima installazione
git clone <repo> && cd myTaba
docker-compose up -d --build

# Aggiornamento
git pull && docker-compose up -d --build
```

- Frontend: `http://<mac-ip>:8080`
- Backend (diretto): `http://<mac-ip>:8000`
- Admin Django: `http://<mac-ip>:8080/admin/`
- Il DB SQLite persiste nel volume Docker `sqlite_data`

---

## Integrazione OpenClaw / Telegram

Il file `SKILL2.md` nella root contiene lo script bash per installare la skill `profilo` in OpenClaw. La skill configura il bot Telegram per:
- Ricevere foto chiusure cassa
- Inviare i dati estratti a `POST /api/closures/insert/`
- Controllare Home Assistant

---

## Prossimi passi ragionevoli

1. **Sicurezza**: spostare SECRET_KEY e token Telegram in variabili d'ambiente (`.env`)
2. **BankTransaction**: aggiungere endpoint e UI per riconciliazione bancaria
3. **Autenticazione**: aggiungere login base (anche solo Django sessions)
4. **OCR migliorato**: gestire layout scontrini diversi, aggiungere fallback
5. **Test**: scrivere almeno test sulle API principali
6. **Push origin**: i 2 commit locali non sono ancora pushati su remote
