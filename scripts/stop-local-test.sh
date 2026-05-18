#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.local.yml --env-file .env.local down
fi

for name in backend frontend; do
  pid_file=".local-test/${name}.pid"
  if [ -f "$pid_file" ]; then
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid"
      echo "Fermato ${name} (${pid})"
    fi
    rm -f "$pid_file"
  fi
done
