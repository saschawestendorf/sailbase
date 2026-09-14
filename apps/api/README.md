# Sailbase API

FastAPI backend: dynamic pricing, flexible offers, booking, operations and payouts.

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m app.seed.seed          # demo catalogue (idempotent)
.venv/bin/uvicorn app.main:app --reload    # http://localhost:8000/docs
.venv/bin/python -m pytest -q
```

See `../../docs/deployment.md` for the Railway setup and the full environment variable list.
