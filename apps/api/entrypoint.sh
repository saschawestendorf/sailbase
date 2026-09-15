#!/bin/sh
# Container-Start: Schema auf Stand bringen, Demo-Daten einspielen, dann bedienen.
#
# Migrationen und Seed laufen hier und nicht beim Hochfahren der Anwendung: so
# stehen sie als eigene Schritte im Deploy-Log, scheitern sichtbar, und der
# Healthcheck wartet nicht auf einen Seed, der bei großen Beständen dauert.
set -e

mkdir -p "${UPLOAD_DIR:-/data/uploads}"

if [ "${DB_RESET:-0}" = "1" ]; then
  echo "sailbase: DB_RESET=1 — Schema wird verworfen, ALLE DATEN GEHEN VERLOREN"
  python -m app.tools.reset_db
fi

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "sailbase: Migrationen werden ausgeführt"
  if ! alembic upgrade head 2>&1 | tee /tmp/alembic.log; then
    exit 1
  fi
  # Alembic meldet eine unbekannte Revision mit Exitcode 0 durch die Pipe hindurch,
  # deshalb wird die Ausgabe geprüft. Dieser Fall braucht eine eigene Erklärung:
  # aus der Fehlermeldung allein ist nicht ersichtlich, was zu tun ist.
  if grep -q "Can't locate revision" /tmp/alembic.log; then
    echo "" >&2
    echo "sailbase: Die Datenbank zeigt auf eine Migration, die es im Code nicht gibt." >&2
    echo "  Das passiert, wenn eine bereits ausgerollte Migration ersetzt wurde." >&2
    echo "  Bei einer Demo-Datenbank: DB_RESET=1 setzen, neu deployen, danach wieder auf 0." >&2
    echo "  Bei echten Daten: Migration von Hand schreiben, NICHT zurücksetzen." >&2
    exit 1
  fi
fi

if [ "${SEED_ON_START:-0}" = "1" ] || [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "sailbase: Demo-Bestand wird eingespielt"
  python -m app.seed.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
