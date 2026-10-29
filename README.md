# PT Tax Assistant

Self-hosted ledger and calculator for a Portugal tax resident who has a full-time job (Categoria A)
and also bills a US client through Stripe as a *trabalhador independente* (Categoria B, Regime
Simplificado, CIRS activity code 1519).

> **Compliance boundary.** This app is an organisational and calculation ledger only. It never
> calls Portal das Finanças, e-Fatura or Segurança Social Direta APIs, never scrapes them, and never
> stores AT/SS credentials. You type the values it prepares into the official portals yourself.
> Estimates are not tax advice. Confirm them with a *contabilista certificado*.
>
> The only outbound connection is to the public **ECB Data Portal** to fetch euro reference
> exchange rates (currency code and date range only, no personal data). Rates are cached in the
> local database.

## Features

| Area | What it does |
| --- | --- |
| Dashboard | Freelance gross per ISO week and month, the IRS savings pool (default 25%), estimated IRS and Social Security, expected net, and a warning when the pool is too small |
| Payouts & invoice helper | Record Stripe payouts in USD or EUR. The ECB reference rate is looked up automatically (cached locally, editable, with the source and rate day shown; non-publication days fall back to the previous business day with an explanation). Each payout stores two EUR amounts when they differ: the *Fatura-Recibo* amount (CIVA day) and the IRS income (payment day). For each payout it gives copy-ready strings for the Portal das Finanças *Fatura-Recibo* form (VAT exemption article, *"Sem retenção - Não residente sem estabelecimento"*, client details, EUR amounts in PT format) |
| Estimator | IRS: 75% taxable base (CIRS art. 31.º) added to salary, progressive brackets (art. 68.º), and the extra IRS the freelance income causes. Social Security: 70% relevant income, exemption up to 4×IAS when you also have employment, 21.4% on the excess |
| Calendar | Builds the year's fiscal deadlines (SS quarterly declarations and payments, quarterly IVA, e-Fatura, the IRS filing window and payment, a recurring ViaCTT check). Each one has a markdown guide and official links. You can push them to Nextcloud over CalDAV or download them as `.ics` |

Fiscal parameters are versioned per year in `backend/app/fiscal/parameters.py`, with the legal
source next to each value. Only **2026** ships today.

### Exchange rates (ECB)

`GET /api/exchange-rates?currency=USD&date=2026-03-06[&invoice_issued_on=2026-03-02]` (`payout_date=` is accepted too)
returns the ECB euro foreign exchange reference rate (units of currency per 1 EUR) from the
[ECB Data Portal API](https://data.ecb.europa.eu/help/api/overview), dataflow `EXR`, series
`D.USD.EUR.SP00.A` (`detail=dataonly&format=csvdata`, an 8-column CRLF CSV). Published rates
are cached in the `exchange_rate` table, so each business day is fetched at most once.

The ECB only publishes on TARGET business days (around 16:00 CET). For a weekend, a TARGET
closing day (New Year's Day, Good Friday, Easter Monday, 1 May, 25 and 26 December), or a day
whose rate is not out yet, the response carries the latest previous business day with
`is_fallback: true`, a `fallback_reason` (`weekend`, `target_holiday`, `not_yet_published`,
`no_rate_published`) and a human-readable `note`. Days before the first euro reference rates
(1999-01-04) are rejected with **422** without contacting the ECB. If the ECB cannot be reached
or answers with an error or an unreadable payload, the endpoint responds **502** and the UI
lets you type the rate yourself.

**Which day's rate applies.** The response carries two rates: the top-level one for the
*Fatura-Recibo* amount (`requested_date`, `conversion_basis`, `conversion_note`) and `irs` for
the IRS income; `rates_differ` tells whether they are different days. The rule lives in
`backend/app/fiscal/currency_conversion.py`. Confirm with your *contabilista certificado* and
check the current wording on the AT pages linked below.

* **The Fatura-Recibo amount — [CIVA art. 49.º](https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/civa_rep/Pages/iva49.aspx)
  n.º 1**: foreign-currency amounts are converted at the selling rate published by Banco de
  Portugal (which republishes the ECB reference rates) for the day the tax becomes
  chargeable; n.º 2 allows opting for the rate of the first business day of that month instead
  (not implemented). That day is fixed by
  **[CIVA art. 8.º](https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/civa_rep/Pages/iva8.aspx)
  n.º 1**: al. c) — payment received before the invoice is issued → the day of receipt;
  al. a) — invoice issued first, within the deadline of art. 36.º n.º 1 → the invoice date.
* **The IRS income — [CIRS art. 23.º](https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/cirs_rep/Pages/irs23.aspx)
  n.º 1 al. b)**: *"tratando-se de rendimentos provenientes do exterior, aplica-se o câmbio de
  compra na data em que aqueles foram pagos ou postos à disposição do sujeito passivo"*; n.º 3:
  when no quotation exists for that day, the last previous quotation applies (the fallback
  above).

| Order of events | Day used | Why |
| --- | --- | --- |
| Payout received, then Fatura-Recibo issued (the Stripe flow) | **payout date** | CIVA art. 8.º n.º 1 al. c) and CIRS art. 23.º n.º 1 al. b) agree |
| Fatura issued first, paid later | **invoice date** for the document, **payout date** for IRS | CIVA art. 8.º n.º 1 al. a) + art. 49.º n.º 1 vs. CIRS art. 23.º n.º 1 al. b) |

A payout therefore stores two pairs: `currency_per_eur`/`eur_amount` (+ `rate_date`) for the
*Fatura-Recibo* — what the invoice helper prints — and `irs_currency_per_eur`/`irs_eur_amount`
(+ `irs_rate_date`) for the income. The dashboard and the IRS/Social Security estimates use the
IRS amount. When the invoice precedes the payout the form shows both rates and both EUR amounts
(each editable) and the payouts table shows the IRS amount next to the document amount. Note
that the quarterly Social Security declaration is pre-filled by AT from the invoices issued,
i.e. the document amounts; the difference is normally a few cents, but mention it to your
accountant if it is not.

Each stored rate also carries its **provenance** (`rate_provenance` / `irs_rate_provenance`):
whether it was taken from the ECB as-is or typed manually, and either way what the ECB said for
that day (`ecb_rate_date`, `ecb_currency_per_eur`, `is_fallback`, `fallback_reason`,
`fetched_at`), or nulls when the lookup had failed. It lives in its own table
(`payout_rate_provenance`, one row per pair), so adding it never touched the `payout` table:
payouts recorded before it existed simply read as `null`. The payouts table in the UI shows it
("ECB rate of 06/03/2026 (fallback for 07/03/2026)", "manual (ECB was 1.0817 on 06/03/2026)").

Existing databases are upgraded at start-up (`app/db.py`, `init_db`): missing tables are
created, and the columns the IRS pair needed on `payout` are added and backfilled from the
document pair (`upgrade_schema`).

Settings: `PTTAX_ECB_API_BASE_URL` (default `https://data-api.ecb.europa.eu/service`) and
`PTTAX_ECB_TIMEOUT_SECONDS` (default `10`).

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
    currency_conversion.py  which day's rate converts a payout (CIVA art. 8.º/49.º, CIRS art. 23.º)
  calendar_sync.py  iCalendar rendering and CalDAV upsert
  ecb.py            ECB Data Portal client (EXR dataflow, CSV) and TARGET calendar
  exchange_rates.py cached reference-rate lookup with business-day fallback
  routers/          FastAPI endpoints
frontend/src/       React pages: Dashboard, Payouts, Estimator, Calendar
```

## Roadmap

Planned work, grouped into milestones with acceptance criteria for each item, is in
[ROADMAP.md](ROADMAP.md). Open an issue before starting on an item.

## License

[MIT](LICENSE) © 2026 MatiasN. The software is provided "as is", without warranty of any kind;
see the compliance boundary above. It is not tax advice.
