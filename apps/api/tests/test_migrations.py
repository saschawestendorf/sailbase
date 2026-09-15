"""Migrationen dürfen nicht nachträglich ausgetauscht werden.

Hintergrund: Eine bereits ausgerollte Migration wurde im Repo durch eine neu
erzeugte ersetzt. In der Produktionsdatenbank stand danach eine Revisionsnummer,
die es im Code nicht mehr gab. Alembic brach bei jedem Containerstart ab, der
Dienst kam nie hoch – und von außen sah es aus, als sei die Datenbank leer und
als wären die Zugangsdaten falsch.

Die Kette lässt sich hier prüfen, der Zustand einer fremden Datenbank nicht.
Deshalb wird festgehalten, was sich nicht mehr ändern darf: die Nummer der
ersten Migration. Wer sie ändert, strandet jede Datenbank, die sie schon trägt.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

# Die erste ausgerollte Migration. Diese Nummer ist eine Zusage an jede
# Datenbank, die sie bereits trägt: Ändert sie sich, kommt keine davon mehr
# hoch. Neue Schemaänderungen kommen als zusätzliche Migration obendrauf.
ERSTE_REVISION = "b200e3d2fc2d"

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def script_directory() -> ScriptDirectory:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_die_erste_migration_behaelt_ihre_nummer(script_directory):
    bases = script_directory.get_bases()
    assert bases == [ERSTE_REVISION], (
        "Die erste Migration wurde ersetzt oder umbenannt. Jede Datenbank, die "
        f"{ERSTE_REVISION} trägt, kommt damit nicht mehr hoch. Neue Änderungen "
        "gehören in eine zusätzliche Migration."
    )


def test_die_kette_ist_lueckenlos_und_hat_einen_kopf(script_directory):
    """Genau ein Anfang, genau ein Ende, keine fehlenden Zwischenschritte."""
    heads = script_directory.get_heads()
    assert len(heads) == 1, f"Mehrere Köpfe: {heads} – ein Merge fehlt"

    revisions = list(script_directory.walk_revisions())
    bekannt = {r.revision for r in revisions}
    for revision in revisions:
        for vorgaenger in revision._all_down_revisions:
            assert vorgaenger in bekannt, (
                f"Migration {revision.revision} baut auf {vorgaenger} auf, "
                "die es nicht gibt"
            )


def test_jede_migration_laesst_sich_auch_zuruecknehmen(script_directory):
    """Ein downgrade, das nur `pass` ist, hilft im Ernstfall niemandem."""
    ohne_rueckweg = []
    for revision in script_directory.walk_revisions():
        quelle = Path(revision.path).read_text(encoding="utf-8")
        körper = quelle.split("def downgrade()", 1)
        if len(körper) < 2:
            ohne_rueckweg.append(revision.revision)
            continue
        zeilen = [
            zeile.strip()
            for zeile in körper[1].splitlines()[1:]
            if zeile.strip() and not zeile.strip().startswith("#")
        ]
        if zeilen in ([], ["pass"]):
            ohne_rueckweg.append(revision.revision)
    assert not ohne_rueckweg, f"Migrationen ohne downgrade: {ohne_rueckweg}"
