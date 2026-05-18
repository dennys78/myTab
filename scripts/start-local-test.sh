#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f ".env.local" ]; then
  cp ".env.local.example" ".env.local"
  echo "Creato .env.local da .env.local.example"
fi

if command -v docker >/dev/null 2>&1; then
  echo "Avvio ambiente locale Docker su http://localhost:18080 ..."
  docker compose -f docker-compose.local.yml --env-file .env.local up -d --build

  echo
  echo "Stato container:"
  docker compose -f docker-compose.local.yml --env-file .env.local ps

  echo
  echo "Se il sito non risponde entro pochi secondi, controlla i log con:"
  echo "docker compose -f docker-compose.local.yml --env-file .env.local logs -f"
  exit 0
fi

echo "Docker non trovato: avvio ambiente locale con venv + Vite."

if [ ! -x "venv/bin/python" ]; then
  echo "Errore: venv/bin/python non trovato. Crea il virtualenv o installa Docker."
  exit 1
fi

mkdir -p db_data logs .local-test

set -a
source ".env.local"
set +a

"venv/bin/python" manage.py migrate
"venv/bin/python" manage.py ensure_admin

if lsof -nP -iTCP:18000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Backend gia in ascolto su 18000."
else
  nohup "venv/bin/python" manage.py runserver 127.0.0.1:18000 > logs/local-backend.log 2>&1 &
  echo "$!" > .local-test/backend.pid
fi

if lsof -nP -iTCP:18080 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Frontend gia in ascolto su 18080."
else
  nohup env VITE_API_PROXY_TARGET="http://127.0.0.1:18000" npm --prefix dashboard_app run dev -- --host 127.0.0.1 --port 18080 > logs/local-frontend.log 2>&1 &
  echo "$!" > .local-test/frontend.pid
fi

echo
echo "Ambiente locale avviato: http://localhost:18080"
echo "Log backend:  logs/local-backend.log"
echo "Log frontend: logs/local-frontend.log"
