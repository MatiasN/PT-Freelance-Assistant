# PT Tax Assistant

Self-hosted ledger and calculator for a Portugal tax resident who has a full-time job (Categoria A)
and also bills a US client through Stripe as a *trabalhador independente* (Categoria B, Regime
Simplificado, CIRS activity code 1519).

> **Compliance boundary.** This app is an organisational and calculation ledger only. It never
> calls Portal das Finanças, e-Fatura or Segurança Social Direta APIs, never scrapes them, and never
> stores AT/SS credentials. You type the values it prepares into the official portals yourself.
> Estimates are not tax advice. Confirm them with a *contabilista certificado*.

## Features

| Area | What it does |
| --- | --- |
| Dashboard | Freelance gross per ISO week and month, the IRS savings pool (default 25%), estimated IRS and Social Security, expected net, and a warning when the pool is too small |
| Payouts & invoice helper | Record Stripe payouts in USD or EUR with the ECB rate. For each payout it gives copy-ready strings for the Portal das Finanças *Fatura-Recibo* form (VAT exemption article, *"Sem retenção - Não residente sem estabelecimento"*, client details, EUR amounts in PT format) |
| Estimator | IRS: 75% taxable base (CIRS art. 31.º) added to salary, progressive brackets (art. 68.º), and the extra IRS the freelance income causes. Social Security: 70% relevant income, exemption up to 4×IAS when you also have employment, 21.4% on the excess |
| Calendar | Builds the year's fiscal deadlines (SS quarterly declarations and payments, quarterly IVA, e-Fatura, the IRS filing window and payment, a recurring ViaCTT check). Each one has a markdown guide and official links. You can push them to Nextcloud over CalDAV or download them as `.ics` |

Fiscal parameters are versioned per year in `backend/app/fiscal/parameters.py`, with the legal
source next to each value. Only **2026** ships today.

## Run with Docker

```bash
cp .env.example .env           # fill in salary, client details, Nextcloud app password
docker compose up -d --build
open http://localhost:8000
```

The SQLite database lives in the `pt-tax-data` volume. The port is bound to `127.0.0.1`, so put
the app behind your reverse proxy (with TLS and authentication) before you expose it on the LAN.

Push the deadlines from the UI (**Calendar → Push deadlines to Nextcloud**), or from the CLI:

```bash
docker compose exec pt-tax-assistant python -m app.cli sync-calendar --year 2026
```

Event UIDs are stable (`<key>@pt-tax-assistant`), so running the sync again updates the existing
events instead of duplicating them.

### Nextcloud setup

1. Create a dedicated calendar, e.g. `pt-tax`.
2. Create an app password under *Settings → Security → Devices & sessions*.
3. Set `PTTAX_CALDAV_CALENDAR_URL=https://<host>/remote.php/dav/calendars/<user>/pt-tax/`.

## Development

```bash
# backend (Python 3.12, uv)
cd backend
uv sync
uv run uvicorn app.main:app --reload       # http://localhost:8000/docs
uv run pytest && uv run ruff check && uv run mypy app

# frontend (Node 24, Vite + React + TypeScript)
cd frontend
npm install
npm run dev                                # proxies /api to :8000
npm test && npm run lint && npm run build
```

## Layout

```
backend/app/
  fiscal/        pure, unit-tested domain logic (no I/O)
    parameters.py   year-versioned legal constants with sources
    irs.py          simplified-regime base, progressive tax, marginal impact
    social_security.py  quarterly SS for independent workers
    ledger.py       weekly/monthly/quarterly aggregation and the year overview
    invoice_text.py Portal das Finanças copy-paste fields
    deadlines.py    fiscal calendar with guides and links
  calendar_sync.py  iCalendar rendering and CalDAV upsert
  routers/          FastAPI endpoints
frontend/src/       React pages: Dashboard, Payouts, Estimator, Calendar
```

See [TASKS.md](TASKS.md) for the remaining work.
