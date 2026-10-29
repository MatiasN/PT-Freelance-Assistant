# PT Tax Assistant — Remaining Work

These tasks were left open on purpose. Each one should take an AI coding agent several turns
(about 3–5 hours including review). Every task changes behaviour across the backend and the
frontend, or needs legal and domain research before coding.

**Baseline for every task:** `cd backend && uv run pytest && uv run ruff check && uv run mypy app`
and `cd frontend && npm test && npm run lint && npm run build` must stay green. `docker compose build`
must still succeed. Domain logic stays pure in `backend/app/fiscal/` (no I/O). Every legal constant
cites its source the same way `parameters.py` does.

| # | Task | Area |
|---|------|------|
| 1 | ECB exchange-rate auto-lookup | Backend + UI, external API |
| 2 | Stripe payout CSV import | Backend + UI, parsing |
| 3 | Multi-year and regional fiscal parameters | Domain research |
| 4 | Scheduled CalDAV sync with state and stale-event cleanup | Background jobs |
| 5 | Business-day adjustment of deadlines (weekends and holidays) | Domain + calendar |
| 6 | The 15% expense-justification rule of the simplified regime | Domain + UI |
| 7 | Start-of-activity reductions and IRS Jovem | Domain + UI |
| 8 | Annual IRS settlement simulation | Domain + UI |
| 9 | Complete Social Security model | Domain + UI |
| 10 | Invoice lifecycle tracker | Full stack |
| 11 | Settings UI with encrypted secret storage | Full stack, security |
| 12 | Authentication | Security |
| 13 | Database migrations and Nextcloud backups | Ops |
| 14 | Accountant export (CSV/XLSX/PDF) | Full stack |
| 15 | Dashboard charts and year-end projection | Frontend |
| 16 | VAT regime monitor and invoice legal wording review | Domain research |
| 17 | End-to-end tests and CI pipeline | Quality |
| 18 | Portuguese / English internationalisation | Frontend |

---

## 1. ECB exchange-rate auto-lookup

**Description.** Today the user types the USD→EUR rate by hand for every payout. The backend
should fetch the official ECB euro reference rate for the payout date, cache it, and pre-fill it.
The user can still override it.

**Done when**
- `GET /api/exchange-rates?currency=USD&date=YYYY-MM-DD` returns the rate, the date the rate
  actually refers to, and its source.
- Weekends and TARGET holidays fall back to the previous published rate, and the response says so.
- Rates are stored in a new table. A second request for the same date does not touch the network
  (shown by a test).
- If the upstream fails, the endpoint returns 502 with a clear message, and the payout form still
  accepts a manual rate.
- In the payout form, choosing USD and a date auto-fills the rate field and shows where it came
  from. Manual edits are kept.
- Tests use recorded fixtures or a mocked HTTP layer and never call the real network.

**Notes.** Use the ECB Data Portal SDMX API (`data-api.ecb.europa.eu`, series `EXR.D.USD.EUR.SP00.A`)
and check its current documentation. Decide which day's rate applies under the CIVA/CIRS currency
conversion rules and document that choice with a source. Keep `currency_per_eur` in ECB
convention.

**Prompt**
> In this repo (FastAPI backend in `backend/`, React/TS frontend in `frontend/`), add automatic
> ECB reference-rate lookup for foreign-currency payouts. Read the current ECB Data Portal API docs
> first. Add a cached `ExchangeRate` table and a `GET /api/exchange-rates` endpoint. For
> non-publication days, fall back to the previous business day and say so in the response. Map
> upstream failures to 502. Wire it into `frontend/src/pages/Payouts.tsx` so the rate auto-fills
> but stays editable and shows its source and date. Find and cite the Portuguese rule for which
> date's rate applies to invoices in foreign currency. Mock all HTTP in tests. Keep pytest, ruff,
> mypy --strict, vitest, eslint and the build green.

---

## 2. Stripe payout CSV import

**Description.** Instead of typing every weekly payout, import the Stripe Dashboard *Payouts*
CSV export. Show a preview, skip duplicates, and convert currencies.

**Done when**
- `POST /api/payouts/import` accepts a CSV upload and returns a preview: rows to create, rows
  skipped as duplicates, and rows rejected with reasons. Nothing is written until a confirm call
  with the preview token.
- Duplicates are detected by the Stripe payout id (`po_…`), stored in a new unique column.
- Amounts in Stripe's minor units or decimal formats both parse correctly. Non-USD/EUR currencies
  are rejected with a clear reason.
- If task 1 is merged, rates come from ECB. Otherwise rows without a rate are flagged.
- The frontend has an upload → preview table → confirm flow that is keyboard accessible.
- Upload size and row count are limited. Malformed CSVs return 422, never 500.
- Tests use realistic fixture CSVs, including BOM, `;` vs `,`, and quoted fields.

**Notes.** Payout gross and fees: decide whether the invoiced amount is the gross charge or the
net payout, and document it. Invoices should normally show the amount billed to the client, not
the amount after Stripe fees. Use the standard `csv` module and Pydantic validation, not a
hand-written parser.

**Prompt**
> Add a Stripe payouts CSV import to PT Tax Assistant. Look up the current column layout of
> Stripe's Payouts export in the Stripe docs. Build a two-step preview/confirm API under
> `/api/payouts/import`, deduplicate on the Stripe payout id (add a unique column), validate every
> row with Pydantic, and enforce size and row limits. Add an accessible upload/preview/confirm UI in
> the Payouts page. Document whether the gross charge or the net payout is the invoice amount and
> why. Cover the edge cases with fixture CSVs. Keep all checks green.

---

## 3. Multi-year and regional fiscal parameters

**Description.** `parameters.py` only has 2026 mainland values. Add 2025, prepare 2027, and
support the Azores and Madeira rate tables. Also add a way to see where each number comes from.

**Done when**
- `FISCAL_PARAMETERS` has 2025 and 2026, each value with a citation to the diploma that set it.
  A 2027 entry is added only if the values are published.
- A `region` (mainland / Açores / Madeira) setting changes the IRS bracket table.
- `GET /api/fiscal-parameters?year=` returns the values together with their sources. The frontend
  shows a "Fiscal parameters" panel with the sources.
- Parametrised tests check at least one official worked example per year, e.g. the AT simulator or
  the official average rate column (*taxa média*) at every bracket boundary.
- Any year without parameters still returns 422 with a helpful message.

**Notes.** IRS rates changed during 2025 (and possibly during 2026), so check which table applies
to *annual settlement* for each income year. Withholding tables are a separate thing. Search
results at the time of writing disagreed on the 2026 values, so use the official CIRS consolidated
text on `info.portaldasfinancas.gov.pt` and *Diário da República*.

**Prompt**
> Extend `backend/app/fiscal/parameters.py` to support several years and the Azores and Madeira
> IRS tables. Research the official values for 2025 and 2026 (CIRS art. 68.º and regional
> diplomas, IAS portarias, art. 25.º specific deduction) only from official sources (Portal das
> Finanças CIRS text, Diário da República). Cite each value. Move sources into structured data
> that the API exposes. Add a region setting and a parameters/sources panel in the frontend.
> Validate each year against the official average-rate column at every bracket boundary with
> parametrised tests.

---

## 4. Scheduled CalDAV sync with state and stale-event cleanup

**Description.** Sync currently only runs from a button or the CLI. Add a scheduled background
sync that records its history, retries on failure, and removes events this app created that are
no longer generated (for example after changing the VAT regime).

**Done when**
- An in-container scheduler (or a separate compose service) syncs on a configurable cron
  (default daily), for the current year and for the next year from 1 December onwards.
- A `calendar_sync_runs` table records start, end, pushed, deleted, failed, and error text.
  `GET /api/calendar/status` returns the last run. The Calendar page shows it.
- Events whose UID ends in `@pt-tax-assistant` but are no longer in the generated set are deleted.
  Events created by anything else are never touched (tested against a fake CalDAV calendar).
- Transient network errors retry with exponential backoff. Auth errors (401/403) do not retry and
  surface clearly.
- Two syncs can't run at the same time, whether triggered by the scheduler or the button.

**Notes.** Prefer a maintained scheduler library (e.g. APScheduler) or a simple supercronic
sidecar over a hand-rolled loop. Use a library for retries (e.g. `tenacity`). caldav 3.x API:
`calendar.search(...)` and `get_object_by_uid`. Check the caldav docs for the version in
`uv.lock`.

**Prompt**
> Implement scheduled, stateful Nextcloud CalDAV sync for PT Tax Assistant. Pick a maintained
> scheduler and retry library, verify their APIs against official docs, and justify the choice.
> Persist sync runs, expose them in `/api/calendar/status` and the Calendar page, prevent
> concurrent runs, and delete stale events this app owns (UID suffix `@pt-tax-assistant`) without
> touching anything else. Write tests against an in-memory fake calendar. Update the Dockerfile or
> compose file if a sidecar is needed.

---

## 5. Business-day adjustment of deadlines

**Description.** Deadlines that fall on a weekend or a Portuguese public holiday are generated on
the nominal date. Shift them according to the legal rule for each obligation, and show both dates.

**Done when**
- A pure function computes Portuguese national holidays for any year, including Easter-based ones
  (Good Friday, Corpus Christi).
- Each `Deadline` has `nominal_due` and `effective_due`, with a per-obligation rule saying whether
  it moves to the next business day.
- Calendar events use `effective_due`, and the description mentions the shift.
- Tests cover known years: 2026-01-31 is a Saturday, and so is 2026-10-31.

**Notes.** Prefer the maintained `holidays` package (country `PT`) over hand-rolled Easter maths if
it covers the needed holidays. The legal rule differs by obligation: CPPT art. 20.º and Código Civil
art. 279.º for tax deadlines, and the Segurança Social rules for SS. Research and cite each one.

**Prompt**
> Add business-day adjustment to `backend/app/fiscal/deadlines.py`. Use the `holidays` package
> for Portuguese national holidays (check its docs), find and cite the legal rule for each
> deadline type (CPPT art. 20.º / CC art. 279.º for AT, the relevant rule for Segurança Social),
> and add `nominal_due` and `effective_due`. Update CalDAV rendering and the Calendar page to show
> shifts. Add tests for weekend and holiday cases in 2026 and 2027.

---

## 6. The 15% expense-justification rule

**Description.** Under CIRS art. 31.º n.º 13, the 0.75 coefficient assumes 15% of gross services
income is justified by expenses (the standard €4,104 deduction plus e-Fatura activity expenses and
other listed items). Any shortfall is added to the taxable base. The estimator currently ignores
this, so it can understate IRS.

**Done when**
- A new expense ledger (CRUD API and UI) records activity expenses by category, with the e-Fatura
  activity-expense flag.
- `estimate_irs` takes justified expenses and returns the required amount, the justified amount,
  the shortfall, and the adjusted taxable base.
- The dashboard warns when the year-to-date shortfall is above zero and shows how much more needs
  justifying.
- Tests cover: no shortfall, a partial shortfall, and income low enough that the standard
  deduction covers everything.

**Notes.** Read the current wording of art. 31.º n.os 13–15 carefully: which items count, how
the €4,104 standard deduction interacts, and how mixed-use expenses are capped at 25%. Cite the
paragraph numbers.

**Prompt**
> Implement the CIRS art. 31.º n.º 13 expense-justification rule in PT Tax Assistant. Read the
> official article text first and summarise which items count before coding. Add an `Expense`
> model, CRUD endpoints and a page. Extend `backend/app/fiscal/irs.py` so the simplified-regime
> base includes any shortfall. Surface it on the dashboard and the estimator. Test the boundary
> cases with figures you compute by hand from the law.

---

## 7. Start-of-activity reductions and IRS Jovem

**Description.** Support the reduced coefficient in the first years of activity (CIRS art. 31.º
n.º 10) and the IRS Jovem exemption (art. 12.º-B) as optional profile settings in the estimator.

**Done when**
- The profile records the activity start date, year of birth or first year of work, and whether
  IRS Jovem has already been used.
- `estimate_irs` applies the right reductions per year, and the result lists each one applied.
- The UI explains why a reduction does or doesn't apply.
- Tests cover every year of eligibility and the transitions between them.

**Notes.** IRS Jovem was rewritten in the OE 2025 (age ≤ 35, up to 10 years, an exemption
schedule, and a cap tied to IAS). Check the version in force for each income year.

**Prompt**
> Add start-of-activity coefficient reductions (CIRS art. 31.º n.º 10) and IRS Jovem (art. 12.º-B,
> as in force each year) to PT Tax Assistant. Research the current official text, add profile
> fields (settings or DB), apply the reductions in `backend/app/fiscal/irs.py` with an itemised
> breakdown, expose them in the Estimator page, and write year-by-year eligibility tests.

---

## 8. Annual IRS settlement simulation

**Description.** The estimator stops at gross tax (*coleta*). Simulate the real annual
settlement: salary withholding already paid, deductions from the tax (*deduções à coleta*), the
solidarity surcharge, and the final refund or amount payable.

**Done when**
- The user enters or derives the salary withholding using the official monthly withholding tables
  (Despacho) for their situation.
- Deductions supported: general family expenses, health, education, rent, VAT on invoices, with
  their legal caps. The overall cap by income level (art. 78.º n.º 7) is applied.
- The solidarity surcharge (art. 68.º-A) is applied above its thresholds.
- The result shows liquidated tax, credits, and refund or payment. Results are within ±1 € of the
  AT simulator for 3 documented scenarios, saved as test fixtures.

**Notes.** Withholding tables are formula-based since 2023 (marginal rate and amount to subtract).
Model them as data per year. Keep this separate from the "freelance impact" figure on the
dashboard.

**Prompt**
> Build an annual IRS settlement simulator into PT Tax Assistant. Using official sources only
> (CIRS arts. 68.º-A, 78.º–78.º-E, 99.º-C and the year's withholding Despacho), model withholding
> on salary, deductions with caps, the solidarity surcharge, and the final refund or amount due.
> Add an endpoint and an Estimator sub-section. Write three scenario tests whose expected values
> you derive step by step in the test docstrings.

---

## 9. Complete Social Security model

**Description.** The SS estimator handles the 4×IAS exemption for people who also have
employment. It does not handle the 12-month exemption at the start of activity, the optional
±25% adjustment of relevant income, the minimum contribution, or the income-date basis. It also
doesn't give the monthly values to type into the quarterly declaration.

**Done when**
- The profile records the activity start date. Contributions are zero during the initial
  exemption, as defined in the code.
- The user can pick an adjustment from −25% to +25% in 5% steps, and it is applied to the base.
- The quarterly declaration helper lists each month's services income exactly as SS Direta asks
  for it, with copy buttons.
- The dashboard shows a monthly payment schedule (amount, due date) for the year.
- Tests check each rule against worked examples from the official SS practical guide.

**Notes.** Verify against the current Código Contributivo (arts. 157.º, 162.º–168.º) and the
official *Guia Prático — Trabalhadores Independentes*. Also verify the assumption in
`social_security.py` that only the excess over 4×IAS is charged.

**Prompt**
> Complete the Segurança Social model in `backend/app/fiscal/social_security.py`. Using the
> current Código Contributivo and the official ISS practical guide, verify the existing 4×IAS
> logic and add the first-12-months exemption, the ±25% adjustment, the minimum contribution if
> applicable, a per-month declaration helper (with copy fields in the UI), and a monthly payment
> schedule on the dashboard. Cite articles and test against the guide's examples.

---

## 10. Invoice lifecycle tracker

**Description.** Payouts store an optional invoice number, but nothing enforces that every payout
was invoiced on time. Track the invoice lifecycle and flag gaps.

**Done when**
- Payouts can be edited in the UI (the `PUT` endpoint already exists), including the invoice
  number and issue date, through an "I issued this invoice" flow from the invoice helper.
- Invoice numbers are validated against the Portal format (`FR <series>/<n>`). Gaps and duplicates
  in the sequence are reported.
- The dashboard shows a "not yet invoiced" count with how overdue each one is, based on the legal
  issuing deadline.
- Optionally, each un-invoiced payout gets a CalDAV reminder (reusing `calendar_sync.py`).
- Backend and frontend tests cover the state transitions.

**Notes.** Find the legal deadline for issuing a fatura-recibo (CIVA art. 36.º and the rules for
*recibos verdes*). Don't guess it.

**Prompt**
> Add an invoice lifecycle to PT Tax Assistant: payout editing in the UI, a "mark as invoiced"
> flow from the invoice helper, invoice-number validation, gap and duplicate detection, and
> overdue alerts on the dashboard based on the legal issuing deadline (research CIVA art. 36.º
> and cite it). Optionally push reminders through `backend/app/calendar_sync.py`. Test the state
> machine on both sides.

---

## 11. Settings UI with encrypted secret storage

**Description.** All configuration, including the Nextcloud password, comes from environment
variables, so changing the client address means editing `.env` and restarting. Move the
user-editable settings into the database with a settings page, and encrypt the CalDAV secret at
rest.

**Done when**
- A settings table holds profile, client and invoice strings, and CalDAV settings. Env vars are
  used only as the first-boot defaults.
- The CalDAV password is encrypted with a key from a Docker secret or env var (e.g. Fernet from
  `cryptography`). It is never returned by any endpoint, only "set / not set".
- A "Test connection" button validates the URL and credentials and lists available calendars.
- All inputs are validated (URLs must be https unless explicitly allowed, length limits).
- The estimator, invoice helper and sync read the DB settings. Tests cover precedence and the
  rule that secrets never leak.

**Notes.** Changing the settings source touches `get_settings()` usages everywhere. Find all of
them first.

**Prompt**
> Replace env-only configuration in PT Tax Assistant with DB-backed settings editable from a new
> Settings page. Use env vars only as first-boot defaults. Encrypt the CalDAV password at rest
> with `cryptography` Fernet and a key from a Docker secret, never return it from the API, and
> add a "Test connection" endpoint that lists the user's Nextcloud calendars. Update every
> consumer of `get_settings()`, validate all inputs, and test secret non-disclosure.

---

## 12. Authentication

**Description.** The app has no authentication and relies on binding to localhost. Add
single-user auth, preferably sign-in with the user's Nextcloud account over OpenID Connect, with a
local password as a fallback.

**Done when**
- Every `/api` route except `/api/health` requires a session. The SPA redirects to login.
- The OIDC login works against Nextcloud's OIDC provider app. A local argon2-hashed password works
  when OIDC isn't configured.
- Session cookies are `HttpOnly`, `Secure` (behind TLS), and `SameSite=Lax`. State-changing
  requests are CSRF-protected.
- Tests cover unauthenticated access, login, logout, and CSRF rejection.

**Notes.** Use maintained libraries (e.g. Authlib for OIDC, argon2-cffi), not custom crypto. Check
which OIDC app the user's Nextcloud version supports.

**Prompt**
> Add authentication to PT Tax Assistant. Implement OIDC login against Nextcloud (verify which
> Nextcloud OIDC provider app and endpoints to use from official docs) using Authlib, with a local
> argon2 password fallback. Protect all `/api` routes except health, add CSRF protection for
> mutations, set secure cookie attributes, and add a login screen to the React app. Test the auth
> flows, including negative cases.

---

## 13. Database migrations and Nextcloud backups

**Description.** The schema is created with `SQLModel.metadata.create_all`, so any model change
from the other tasks breaks existing databases. Introduce migrations and automated backups to
Nextcloud over WebDAV.

**Done when**
- Alembic is configured with an initial migration matching the current models. The container runs
  `alembic upgrade head` on start.
- A test checks that migrations produce exactly the same schema as the models.
- A scheduled (or CLI-triggered) job makes a consistent SQLite backup with the online backup API
  and uploads it to a configurable Nextcloud folder, keeping the last N copies.
- The README documents a tested restore procedure.

**Notes.** Use `sqlite3.Connection.backup`, not a file copy, while the app is running.

**Prompt**
> Introduce Alembic migrations to PT Tax Assistant's backend (replace `init_db`'s `create_all`),
> run them on container start, and add a test that migrations match the SQLModel metadata. Then
> add a backup command that takes a consistent SQLite backup and uploads it to Nextcloud over
> WebDAV with N-copy retention. Document and test the restore procedure.

---

## 14. Accountant export

**Description.** At year end the accountant needs a summary: payouts with invoice numbers and
rates, quarterly totals, SS declarations, and the IRS estimate. Generate it as CSV, XLSX and a
one-page PDF.

**Done when**
- `GET /api/exports/{year}.csv|.xlsx|.pdf` returns correct files with PT number formatting in the
  human-readable outputs.
- The XLSX has sheets for payouts, monthly totals, quarterly SS, and the IRS summary, using real
  numeric cells (not text).
- The PDF includes the compliance disclaimer and the fiscal parameter sources.
- Download buttons on the Dashboard. Tests open the generated files and check their contents.

**Notes.** Use maintained libraries (e.g. openpyxl, a PDF library such as WeasyPrint or ReportLab).
Note the image-size impact in the Dockerfile.

**Prompt**
> Add yearly accountant exports (CSV, XLSX, PDF) to PT Tax Assistant using maintained libraries.
> Reuse `build_year_overview` from `backend/app/fiscal/ledger.py`. Store numbers as numeric cells,
> include parameter sources and the disclaimer, add download buttons on the Dashboard, and test by
> parsing the generated files. Keep the Docker image building.

---

## 15. Dashboard charts and year-end projection

**Description.** The dashboard is all tables. Add accessible charts and a year-end projection
that warns when the projected income crosses into a higher IRS bracket or an SS threshold.

**Done when**
- A monthly bar chart of gross vs savings target, and a cumulative line of obligations vs savings
  pool.
- The projection uses year-to-date run-rate (and optionally a user-entered expected income), and
  shows the projected IRS impact, the marginal bracket, and the quarters where SS kicks in.
- Charts work in light and dark mode, have text alternatives or data-table fallbacks, and work by
  keyboard.
- Tests cover the projection maths (backend) and render the charts (frontend).

**Notes.** Prefer a maintained chart library (e.g. Recharts). Put the projection logic in
`backend/app/fiscal/`, not in React.

**Prompt**
> Upgrade the PT Tax Assistant dashboard with accessible charts (pick a maintained React chart
> library and justify it) and a year-end projection computed in a new pure backend function next
> to `ledger.py`. Warn when the projection crosses an IRS bracket or the 4×IAS SS threshold.
> Support light and dark themes and provide table fallbacks. Test both layers.

---

## 16. VAT regime monitor and invoice legal wording review

**Description.** The VAT exemption reason defaults to the user-provided "Artigo 6.º, n.º 7, al.
a) do CIVA" with code `M99`. For B2B services to a non-EU business, the usual basis is art. 6.º
n.º 6 al. a) *a contrario*. Confirm the right wording and code for each client type, and track
the Art. 53.º small-business threshold.

**Done when**
- The client profile has a type (business or consumer, and location). The invoice helper picks
  the legally correct exemption wording and SAF-T exemption code for each, with citations.
- A VAT monitor computes year-to-date turnover relevant to Art. 53.º and warns at 75% and 100%
  of the threshold. Deadlines switch regime when the user confirms.
- `PTTAX_VAT_REGIME` defaults are reviewed. The quarterly IVA deadline guides are checked against
  the current CIVA art. 41.º.
- Tests for each client type and the threshold transitions.

**Notes.** This is a research-heavy task. Use the official CIVA text and AT's list of exemption
codes (*Códigos de motivo de isenção*). Include a note recommending the user confirm with a
*contabilista certificado*.

**Prompt**
> Review and fix VAT handling in PT Tax Assistant. Using the official CIVA text (arts. 6.º, 41.º,
> 53.º) and AT's list of VAT exemption reason codes, decide the correct invoice wording and code
> for B2B and B2C clients outside the EU, add a client-type setting, and make
> `backend/app/fiscal/invoice_text.py` choose accordingly. Add an Art. 53.º threshold monitor
> with warnings and regime-dependent deadlines. Cite every rule and test each branch.

---

## 17. End-to-end tests and CI pipeline

**Description.** Only unit and API tests exist, and nothing runs them automatically. Add
browser end-to-end tests and a CI pipeline that also builds the Docker image.

**Done when**
- Playwright tests run against the built container and cover: adding a USD payout → the dashboard
  totals update → the invoice helper shows PT-formatted values → the `.ics` download works.
- CI (GitHub Actions) runs backend lint, type checks and tests, then frontend lint, tests and
  build, then the Docker build and E2E, with dependency caching.
- CI includes a dependency vulnerability scan and fails on high-severity issues.
- The README shows how to run E2E locally.

**Notes.** Use a fake CalDAV server (e.g. Radicale in a service container) to E2E-test the push
button.

**Prompt**
> Add Playwright end-to-end tests and a GitHub Actions pipeline to PT Tax Assistant. E2E must run
> against the Docker image and include a Radicale service container to test the CalDAV push.
> Cover the payout → dashboard → invoice helper → calendar flows. The pipeline runs all existing
> checks, the Docker build, E2E and a dependency vulnerability scan, with caching. Check current
> action versions against official docs.

---

## 18. Portuguese / English internationalisation

**Description.** The UI mixes English labels with Portuguese legal terms. Add full PT-PT and EN
translations. Legal strings that are pasted into the Portal stay in Portuguese whatever the
language.

**Done when**
- All UI strings come from translation catalogues. A language switcher remembers the choice.
- Number and date formatting follows the selected locale. Portal copy fields always use PT
  formatting.
- Calendar event guides can be generated in either language (a setting).
- A test fails if any catalogue key is missing in either language.

**Notes.** Use a maintained i18n library (e.g. react-i18next) on the frontend. On the backend, keep
guide texts as data, not inline f-strings.

**Prompt**
> Internationalise PT Tax Assistant into PT-PT and EN using a maintained i18n library. Move all
> UI strings into catalogues, add a persisted language switcher, keep Portal copy-paste fields in
> Portuguese with PT formatting, and make the CalDAV guide texts in
> `backend/app/fiscal/deadlines.py` available in both languages via a setting. Add a
> catalogue-completeness test.
