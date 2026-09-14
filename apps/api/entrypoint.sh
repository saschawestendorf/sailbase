#!/bin/sh
# Container start: bring the schema to head, then serve.
# Migrations are idempotent, so a restart or a scaled replica is safe.
set -e

mkdir -p "${UPLOAD_DIR:-/data/uploads}"

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "sailbase: running database migrations"
  alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
