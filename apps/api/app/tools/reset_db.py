"""Schema verwerfen und neu aufbauen – Notausgang für die Demo-Datenbank.

Wozu das nötig ist: wird eine bereits ausgerollte Migration im Repo ersetzt,
steht in der Datenbank eine Revisionsnummer, die es nicht mehr gibt. Alembic
bricht dann bei jedem Start ab ("Can't locate revision"), der Container stirbt,
und von außen sieht es aus, als sei die Datenbank leer – das Portal zeigt nichts
und jede Anmeldung schlägt fehl.

Aus einer Datenbank mit echten Daten führt daraus nur eine von Hand geschriebene
Migration. Für eine Demo-Datenbank ist Wegwerfen und Neuaufbauen richtig, und
genau dafür ist dieses Werkzeug da.

Es läuft nie von selbst. Der Start-Skript ruft es nur auf, wenn `DB_RESET=1`
gesetzt ist, und das ist eine bewusste Handlung: **alle Daten sind danach weg.**

    DB_RESET=1 ./entrypoint.sh      # im Container
    python -m app.tools.reset_db    # von Hand
"""

import logging
import sys

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.core.db import Base, engine

logger = logging.getLogger("sailbase.reset")


def drop_everything() -> list[str]:
    """Entfernt alle Tabellen inklusive `alembic_version`.

    Nicht `Base.metadata.drop_all`: das kennt nur die Tabellen des aktuellen
    Modellstands. Übrig gebliebene Tabellen einer älteren Version blieben liegen
    und die nächste Migration liefe genau darauf auf.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if not tables:
        return []
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            # Ein Rundumschlag, der auch Fremdschlüssel und Reihenfolge erschlägt.
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        else:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(text(f'DROP TABLE IF EXISTS "{table.name}"'))
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    return tables


def main() -> int:
    settings = get_settings()
    logger.warning(
        "Datenbank wird zurückgesetzt (Umgebung: %s). Alle Daten gehen verloren.",
        settings.environment,
    )
    dropped = drop_everything()
    logger.warning("%d Tabellen entfernt: %s", len(dropped), ", ".join(sorted(dropped)) or "keine")
    logger.warning("Weiter mit 'alembic upgrade head' – das übernimmt das Start-Skript.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
