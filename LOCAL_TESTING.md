# Ambiente di Test Locale

Questo ambiente usa container e dati separati dalla produzione.

- URL app: `http://localhost:18080`
- Database: volume Docker `mytaba_sqlite_local_data`
- Utente iniziale: `admin_test`
- Password iniziale: `test_admin_1234`

## Avvio

Metodo consigliato:

```bash
./scripts/start-local-test.sh
```

Lo script usa Docker se disponibile. Se Docker non e presente, avvia automaticamente:

- backend Django su `http://127.0.0.1:18000`
- frontend Vite su `http://127.0.0.1:18080`

Oppure manualmente:

```bash
docker compose -f docker-compose.local.yml --env-file .env.local up -d --build
```

Poi apri:

```text
http://localhost:18080
```

## Log

Con avvio senza Docker:

```bash
tail -f logs/local-backend.log logs/local-frontend.log
```

Con Docker:

```bash
docker compose -f docker-compose.local.yml --env-file .env.local logs -f
```

## Stop

```bash
./scripts/stop-local-test.sh
```

Oppure manualmente:

```bash
docker compose -f docker-compose.local.yml --env-file .env.local down
```

## Reset completo dati test

Questo elimina solo il volume locale di test.

```bash
docker compose -f docker-compose.local.yml --env-file .env.local down -v
docker compose -f docker-compose.local.yml --env-file .env.local up -d --build
```

## Variabili

Il file `.env.local` e ignorato da Git. Se devi rigenerarlo:

```bash
cp .env.local.example .env.local
```

Per provare l'acquisizione IA, inserisci in `.env.local`:

```text
GROQ_API_KEY=...
```
