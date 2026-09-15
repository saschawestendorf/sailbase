# Deployment auf Railway

Das Repo enthält zwei deploybare Services. Beide bringen ein eigenes `Dockerfile` und eine
`railway.json` mit, Railway braucht also nur das jeweilige Root-Verzeichnis.

| Service | Root Directory | Port | Healthcheck |
|---|---|---|---|
| `sailbase-api` | `apps/api` | `$PORT` (default 8000) | `/health` |
| `sailbase-web` | `apps/web` | `$PORT` (default 3000) | `/` |

Dazu kommt ein Postgres aus dem Railway-Katalog.

## 1. Projekt und Datenbank

1. Neues Railway-Projekt anlegen und dieses GitHub-Repo verbinden.
2. `Add Service → Database → PostgreSQL`. Railway legt `DATABASE_URL` als Variable der
   Datenbank an.

## 2. API-Service

`Add Service → GitHub Repo`, dann in den Service-Settings **Root Directory** auf `apps/api`
setzen. Der Builder wird über `apps/api/railway.json` automatisch auf das Dockerfile gesetzt.

Variablen:

```
DATABASE_URL=${{Postgres.DATABASE_URL}}
ENVIRONMENT=production
SECRET_KEY=<32+ zufällige Bytes>
PUBLIC_WEB_URL=https://<web-domain>
CORS_ORIGINS=https://<web-domain>
PAYMENT_PROVIDER=fake          # auf stripe umstellen, sobald Keys vorhanden
UPLOAD_DIR=/data/uploads
```

`DATABASE_URL` von Railway beginnt mit `postgresql://`; die Anwendung schreibt das intern auf
den psycopg-3-Treiber um, es ist keine manuelle Anpassung nötig.

Beim Containerstart laufen nacheinander `alembic upgrade head` (abschaltbar mit
`RUN_MIGRATIONS=0`) und – falls `SEED_ON_START` gesetzt ist – der Demo-Seed, dann startet
uvicorn. Beide Schritte stehen als eigene Zeilen im Deploy-Log und brechen sichtbar ab, wenn
etwas schiefgeht. Migrationen und Seed sind idempotent, ein Restart oder ein zweiter Replica
ist also unkritisch.

**Volume:** Fotos aus Übergabe und Rücknahme landen unter `UPLOAD_DIR`. Ohne Volume sind sie
nach jedem Deploy weg. In den Service-Settings ein Volume mit Mount Path `/data` anlegen.

**Demo-Daten:** Einmalig `SEED_ON_START=true` setzen, deployen, danach wieder auf `false`.
Der Seed legt den vollständigen Demo-Bestand an (siehe README) und braucht dafür auf einer
frischen Postgres-Datenbank rund zehn Sekunden.

### Wenn der Container mit „Can't locate revision" abbricht

Dann trägt die Datenbank eine Migrationsnummer, die es im Code nicht mehr gibt – in aller
Regel, weil eine bereits ausgerollte Migration ersetzt statt ergänzt wurde. Der Container
startet dann bei jedem Versuch neu und das Deployment scheitert; von außen sieht es aus, als
sei die Datenbank leer und als stimmten die Zugangsdaten nicht.

- **Demo-Datenbank:** `DB_RESET=1` setzen und neu deployen. Das Schema wird verworfen, die
  Migrationen laufen von vorn, der Seed baut den Bestand neu auf. **Danach `DB_RESET` wieder
  auf `0` setzen** – sonst wird bei jedem Deploy alles gelöscht.
- **Echte Daten:** nicht zurücksetzen. Stattdessen eine Migration von Hand schreiben, die von
  der vorhandenen Nummer auf die aktuelle Kette führt, oder die gelöschte Migrationsdatei aus
  der Git-Historie zurückholen.

Damit dieser Fall nicht wieder entsteht, hält `apps/api/tests/test_migrations.py` die Nummer
der ersten Migration fest. Schemaänderungen kommen als zusätzliche Migration obendrauf,
niemals durch Neuerzeugen einer bestehenden.

## 3. Web-Service

Zweiter Service aus demselben Repo, **Root Directory** `apps/web`.

```
API_URL=http://${{sailbase-api.RAILWAY_PRIVATE_DOMAIN}}:8000
```

Der Browser spricht nie direkt mit der API: `/api/*` wird im Web-Service serverseitig
weitergereicht. Dadurch ist `API_URL` eine reine Laufzeitvariable, dasselbe Image läuft in
Staging und Produktion, und die API muss nicht öffentlich erreichbar sein. Wenn die API doch
eine eigene Public Domain bekommen soll (z. B. für `/docs`), dann dort `CORS_ORIGINS` auf die
Web-Domain setzen.

## 4. Reihenfolge

1. Postgres anlegen.
2. API deployen, Domain generieren lassen.
3. Web deployen, `API_URL` auf die private Domain der API setzen.
4. `PUBLIC_WEB_URL` und `CORS_ORIGINS` der API auf die Web-Domain setzen, API neu deployen.

## 5. Stripe

Solange `PAYMENT_PROVIDER=fake` gesetzt ist, bestätigt ein Entwicklungs-Endpunkt Zahlungen
sofort. Der ist in `ENVIRONMENT=production` deaktiviert, dort ist also zwingend Stripe nötig:

```
PAYMENT_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

Im Stripe-Dashboard einen Webhook auf `https://<api-domain>/webhooks/stripe` einrichten
(Events `checkout.session.completed`, `checkout.session.expired`,
`checkout.session.async_payment_failed`).

## Lokal mit Docker

```bash
cp .env.example .env
docker compose up --build        # API :8000, Web :3000, Postgres :5432
```

## Betriebshinweise

- **Health:** `/health` liefert Status, Umgebung und Version.
- **API-Doku:** `/docs` (OpenAPI) am API-Service.
- **Migrationen manuell:** `railway run --service sailbase-api alembic upgrade head`.
- **Skalierung:** Der API-Container ist zustandslos bis auf `UPLOAD_DIR`. Für mehrere Replicas
  Uploads auf Objektspeicher umstellen (`app/api/routes/uploads.py` kapselt das bereits hinter
  einer schmalen Schnittstelle).
