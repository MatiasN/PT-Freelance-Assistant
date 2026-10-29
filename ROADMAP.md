# Roadmap

Where PT Tax Assistant is heading, what is already done, and what "done" means for each item.

> [!NOTE]
> This roadmap is a plan, not a promise. Order and scope can change as Portuguese tax law
> changes or as research turns up something unexpected. Nothing here is tax advice. Confirm
> every figure with a *contabilista certificado*.

**Last updated:** 2026-10-29

## Contents

- [Status at a glance](#status-at-a-glance)
- [Milestones](#milestones)
- [Definition of done](#definition-of-done)
- [How to contribute to an item](#how-to-contribute-to-an-item)
- [Items](#items)
  - [M1 · Foundations](#m1--foundations)
  - [M2 · Payouts and invoicing](#m2--payouts-and-invoicing)
  - [M3 · Tax accuracy](#m3--tax-accuracy)
  - [M4 · Reporting and experience](#m4--reporting-and-experience)

## Status at a glance

| Status | Meaning |
| --- | --- |
| ✅ Done | Merged on `main` and documented in the README |
| 🚧 In progress | Someone is working on it (linked issue or PR) |
| 📋 Planned | Specified below, nobody is working on it yet |
| 🔬 Research | Needs legal or domain research before any code |

| ID | Item | Milestone | Area | Status | Depends on |
| --- | --- | --- | --- | --- | --- |
| 1 | [ECB exchange-rate auto-lookup](#1-ecb-exchange-rate-auto-lookup) | M2 | Backend + UI, external API | ✅ Done | — |
| 2 | [Stripe payout CSV import](#2-stripe-payout-csv-import) | M2 | Backend + UI, parsing | 📋 Planned | 1 ✅ |
| 3 | [Multi-year and regional fiscal parameters](#3-multi-year-and-regional-fiscal-parameters) | M3 | Domain research | 🔬 Research | — |
| 4 | [Scheduled CalDAV sync with state and stale-event cleanup](#4-scheduled-caldav-sync-with-state-and-stale-event-cleanup) | M4 | Background jobs | 📋 Planned | 13 |
| 5 | [Business-day adjustment of deadlines](#5-business-day-adjustment-of-deadlines) | M3 | Domain + calendar | 🔬 Research | — |
| 6 | [The 15% expense-justification rule](#6-the-15-expense-justification-rule) | M3 | Domain + UI | 🔬 Research | 13 |
| 7 | [Start-of-activity reductions and IRS Jovem](#7-start-of-activity-reductions-and-irs-jovem) | M3 | Domain + UI | 🔬 Research | 3 |
| 8 | [Annual IRS settlement simulation](#8-annual-irs-settlement-simulation) | M3 | Domain + UI | 🔬 Research | 3 |
| 9 | [Complete Social Security model](#9-complete-social-security-model) | M3 | Domain + UI | 🔬 Research | — |
| 10 | [Invoice lifecycle tracker](#10-invoice-lifecycle-tracker) | M2 | Full stack | 📋 Planned | 13 |
| 11 | [Settings UI with encrypted secret storage](#11-settings-ui-with-encrypted-secret-storage) | M1 | Full stack, security | 📋 Planned | 13 |
| 12 | [Authentication](#12-authentication) | M1 | Security | 📋 Planned | — |
| 13 | [Database migrations and Nextcloud backups](#13-database-migrations-and-nextcloud-backups) | M1 | Ops | 📋 Planned | — |
| 14 | [Accountant export (CSV/XLSX/PDF)](#14-accountant-export) | M4 | Full stack | 📋 Planned | — |
| 15 | [Dashboard charts and year-end projection](#15-dashboard-charts-and-year-end-projection) | M4 | Frontend | 📋 Planned | — |
| 16 | [VAT regime monitor and invoice legal wording review](#16-vat-regime-monitor-and-invoice-legal-wording-review) | M2 | Domain research | 🔬 Research | — |
| 17 | [End-to-end tests and CI pipeline](#17-end-to-end-tests-and-ci-pipeline) | M1 | Quality | 📋 Planned | — |
| 18 | [Portuguese / English internationalisation](#18-portuguese--english-internationalisation) | M4 | Frontend | 📋 Planned | — |

**Progress:** 1 of 18 items done.

Item IDs are stable. Refer to them as "roadmap item 7" in issues and pull requests, not "#7",
because GitHub turns `#7` into a link to issue or PR number 7.

## Milestones

Milestones group items that make sense together. They are a suggested order, not a hard
sequence: items without dependencies can be picked up at any time.

| Milestone | Goal | Items |
| --- | --- | --- |
| **M1 · Foundations** | Safe to change the schema, safe to expose beyond localhost, checked on every push | 13, 17, 11, 12 |
| **M2 · Payouts and invoicing** | Getting money in and invoiced correctly takes minutes, not an evening | 1 ✅, 2, 10, 16 |
| **M3 · Tax accuracy** | Estimates match what AT and Segurança Social will actually charge | 3, 5, 6, 7, 8, 9 |
| **M4 · Reporting and experience** | The year is easy to read, hand over and keep in sync | 4, 14, 15, 18 |

Why this order:

- **13 (migrations) comes first** for every item that changes the database. Until then,
  `backend/app/db.py` only knows how to *add* columns (`upgrade_schema`), which is a stopgap.
- **17 (CI)** should land early so every later item is checked automatically.
- **12 (authentication)** is required before the app is reachable from anywhere other than
  localhost.
- **3 (fiscal parameters)** unblocks the other tax items that need more than one year of values.

## Definition of done

Every item, on top of its own acceptance criteria:

- [ ] Backend checks pass: `cd backend && uv run pytest && uv run ruff check && uv run mypy app`
- [ ] Frontend checks pass: `cd frontend && npm test && npm run lint && npm run build`
- [ ] `docker compose build` succeeds
- [ ] Domain logic stays pure in `backend/app/fiscal/` (no I/O)
- [ ] Every legal constant or rule cites its source the same way `parameters.py` does
- [ ] Tests never call a real external service (use recorded fixtures or a mocked HTTP layer)
- [ ] The README documents any new behaviour, setting or endpoint
- [ ] This roadmap is updated: status, checked criteria, and anything that changed in scope

## How to contribute to an item

1. **Open an issue** for the item (or comment on the existing one) before starting, so work isn't
   duplicated. Title it `Roadmap 7: Start-of-activity reductions and IRS Jovem`.
2. For 🔬 items, **post the research first** in the issue: the articles, diplomas and official
   pages you will rely on, and a short summary of the rule. Code review is much easier once the
   rule is agreed.
3. **Keep pull requests small.** One item can be several PRs (for example domain logic, then API,
   then UI).
4. In the PR, **tick the acceptance criteria** you covered and link the roadmap item.
5. When the item is merged, **update its status here** and add a short "Delivered" note.

Each item below also has an *agent prompt*: a ready-made brief for an AI coding assistant. Items
are sized at roughly 3–5 hours of agent work including review.

---

## Items

### M1 · Foundations

#### 13. Database migrations and Nextcloud backups

**Status:** 📋 Planned · **Area:** Ops · **Depends on:** —

**Goal.** The schema is created with `SQLModel.metadata.create_all`, plus a small
`upgrade_schema` step in `backend/app/db.py` that can only add columns. Any other model change
from the items below would break existing databases. Introduce real migrations and automated
backups to Nextcloud over WebDAV.

**Acceptance criteria**

- [ ] Alembic is configured with an initial migration matching the current models (including
  `exchange_rate`, `payout_rate_provenance` and the IRS columns on `payout`). The container runs
  `alembic upgrade head` on start.
- [ ] `upgrade_schema` is replaced by migrations, and databases already upgraded by it migrate
  cleanly.
- [ ] A test checks that migrations produce exactly the same schema as the models.
- [ ] A scheduled (or CLI-triggered) job makes a consistent SQLite backup with the online backup
  API and uploads it to a configurable Nextcloud folder, keeping the last N copies.
- [ ] The README documents a tested restore procedure.

**Notes.** Use `sqlite3.Connection.backup`, not a file copy, while the app is running.

<details>
<summary>Agent prompt</summary>

> Introduce Alembic migrations to PT Tax Assistant's backend (replace `init_db`'s `create_all`
> and `upgrade_schema`), run them on container start, and add a test that migrations match the
> SQLModel metadata. Then add a backup command that takes a consistent SQLite backup and uploads
> it to Nextcloud over WebDAV with N-copy retention. Document and test the restore procedure.

</details>

#### 17. End-to-end tests and CI pipeline

**Status:** 📋 Planned · **Area:** Quality · **Depends on:** —

**Goal.** Only unit and API tests exist, and nothing runs them automatically. Add browser
end-to-end tests and a CI pipeline that also builds the Docker image.

**Acceptance criteria**

- [ ] Playwright tests run against the built container and cover: adding a USD payout (with the
  ECB rate auto-filled from a stubbed upstream) → the dashboard totals update → the invoice
  helper shows PT-formatted values → the `.ics` download works.
- [ ] CI (GitHub Actions) runs backend lint, type checks and tests, then frontend lint, tests and
  build, then the Docker build and E2E, with dependency caching.
- [ ] CI includes a dependency vulnerability scan and fails on high-severity issues.
- [ ] The README shows how to run E2E locally.

**Notes.** Use a fake CalDAV server (e.g. Radicale in a service container) to E2E-test the push
button. Point `PTTAX_ECB_API_BASE_URL` at a stub so E2E never calls the real ECB.

<details>
<summary>Agent prompt</summary>

> Add Playwright end-to-end tests and a GitHub Actions pipeline to PT Tax Assistant. E2E must run
> against the Docker image and include a Radicale service container to test the CalDAV push.
> Cover the payout → dashboard → invoice helper → calendar flows. The pipeline runs all existing
> checks, the Docker build, E2E and a dependency vulnerability scan, with caching. Check current
> action versions against official docs.

</details>

#### 11. Settings UI with encrypted secret storage

**Status:** 📋 Planned · **Area:** Full stack, security · **Depends on:** 13

**Goal.** All configuration, including the Nextcloud password, comes from environment
variables, so changing the client address means editing `.env` and restarting. Move the
user-editable settings into the database with a settings page, and encrypt the CalDAV secret at
rest.

**Acceptance criteria**

- [ ] A settings table holds profile, client and invoice strings, and CalDAV settings. Env vars
  are used only as the first-boot defaults.
- [ ] The CalDAV password is encrypted with a key from a Docker secret or env var (e.g. Fernet
  from `cryptography`). It is never returned by any endpoint, only "set / not set".
- [ ] A "Test connection" button validates the URL and credentials and lists available calendars.
- [ ] All inputs are validated (URLs must be https unless explicitly allowed, length limits).
- [ ] The estimator, invoice helper and sync read the DB settings. Tests cover precedence and
  the rule that secrets never leak.

**Notes.** Changing the settings source touches `get_settings()` usages everywhere. Find all of
them first. The ECB settings (`PTTAX_ECB_*`) are operational, not user profile, and can stay
env-only.

<details>
<summary>Agent prompt</summary>

> Replace env-only configuration in PT Tax Assistant with DB-backed settings editable from a new
> Settings page. Use env vars only as first-boot defaults. Encrypt the CalDAV password at rest
> with `cryptography` Fernet and a key from a Docker secret, never return it from the API, and
> add a "Test connection" endpoint that lists the user's Nextcloud calendars. Update every
> consumer of `get_settings()`, validate all inputs, and test secret non-disclosure.

</details>

#### 12. Authentication

**Status:** 📋 Planned · **Area:** Security · **Depends on:** —

**Goal.** The app has no authentication and relies on binding to localhost. Add single-user
auth, preferably sign-in with the user's Nextcloud account over OpenID Connect, with a local
password as a fallback.

**Acceptance criteria**

- [ ] Every `/api` route except `/api/health` requires a session. The SPA redirects to login.
- [ ] The OIDC login works against Nextcloud's OIDC provider app. A local argon2-hashed password
  works when OIDC isn't configured.
- [ ] Session cookies are `HttpOnly`, `Secure` (behind TLS), and `SameSite=Lax`. State-changing
  requests are CSRF-protected.
- [ ] Tests cover unauthenticated access, login, logout, and CSRF rejection.

**Notes.** Use maintained libraries (e.g. Authlib for OIDC, argon2-cffi), not custom crypto.
Check which OIDC app the user's Nextcloud version supports.

<details>
<summary>Agent prompt</summary>

> Add authentication to PT Tax Assistant. Implement OIDC login against Nextcloud (verify which
> Nextcloud OIDC provider app and endpoints to use from official docs) using Authlib, with a local
> argon2 password fallback. Protect all `/api` routes except health, add CSRF protection for
> mutations, set secure cookie attributes, and add a login screen to the React app. Test the auth
> flows, including negative cases.

</details>

---

### M2 · Payouts and invoicing

#### 1. ECB exchange-rate auto-lookup

**Status:** ✅ Done · **Area:** Backend + UI, external API · **Depends on:** —

**Goal.** Stop typing the USD→EUR rate by hand for every payout: fetch the official ECB euro
reference rate for the right day, cache it, pre-fill it, and keep it editable.

**Acceptance criteria**

- [x] `GET /api/exchange-rates?currency=USD&date=YYYY-MM-DD` returns the rate, the date the rate
  actually refers to, and its source. (`payout_date=` is accepted too.)
- [x] Weekends and TARGET holidays fall back to the previous published rate, and the response
  says so.
- [x] Rates are stored in a new table. A second request for the same date does not touch the
  network (shown by a test).
- [x] If the upstream fails, the endpoint returns 502 with a clear message, and the payout form
  still accepts a manual rate.
- [x] In the payout form, choosing USD and a date auto-fills the rate field and shows where it
  came from. Manual edits are kept.
- [x] Tests use recorded fixtures or a mocked HTTP layer and never call the real network.
- [ ] `docker compose build` verified after the change.

**Delivered.**

- ECB Data Portal client (`backend/app/ecb.py`, series `EXR.D.USD.EUR.SP00.A`) with the TARGET
  closing-day calendar, and a cached lookup with business-day fallback
  (`backend/app/exchange_rates.py`, table `exchange_rate`).
- The legal rule for which day applies, with sources, in
  `backend/app/fiscal/currency_conversion.py`: the *Fatura-Recibo* amount uses the day IVA becomes
  chargeable (CIVA art. 49.º n.º 1 with art. 8.º n.º 1), and the IRS income uses the payment day
  (CIRS art. 23.º n.º 1 al. b), with n.º 3 for the fallback).
- Payouts therefore store two rate pairs (document and IRS) and where each rate came from
  (`payout_rate_provenance`). Existing databases are upgraded at start-up.
- See the README section *Exchange rates (ECB)* for details.

<details>
<summary>Agent prompt (original)</summary>

> In this repo (FastAPI backend in `backend/`, React/TS frontend in `frontend/`), add automatic
> ECB reference-rate lookup for foreign-currency payouts. Read the current ECB Data Portal API
> docs first. Add a cached `ExchangeRate` table and a `GET /api/exchange-rates` endpoint. For
> non-publication days, fall back to the previous business day and say so in the response. Map
> upstream failures to 502. Wire it into `frontend/src/pages/Payouts.tsx` so the rate auto-fills
> but stays editable and shows its source and date. Find and cite the Portuguese rule for which
> date's rate applies to invoices in foreign currency. Mock all HTTP in tests. Keep pytest, ruff,
> mypy --strict, vitest, eslint and the build green.

</details>

#### 2. Stripe payout CSV import

**Status:** 📋 Planned · **Area:** Backend + UI, parsing · **Depends on:** 1 ✅

**Goal.** Instead of typing every weekly payout, import the Stripe Dashboard *Payouts* CSV
export. Show a preview, skip duplicates, and convert currencies.

**Acceptance criteria**

- [ ] `POST /api/payouts/import` accepts a CSV upload and returns a preview: rows to create, rows
  skipped as duplicates, and rows rejected with reasons. Nothing is written until a confirm call
  with the preview token.
- [ ] Duplicates are detected by the Stripe payout id (`po_…`), stored in a new unique column.
- [ ] Amounts in Stripe's minor units or decimal formats both parse correctly. Non-USD/EUR
  currencies are rejected with a clear reason.
- [ ] Rates come from the ECB lookup (`lookup_exchange_rate` in `backend/app/exchange_rates.py`),
  with both the document and IRS pairs and their provenance. Rows whose lookup fails are flagged
  for a manual rate instead of failing the import.
- [ ] The frontend has an upload → preview table → confirm flow that is keyboard accessible.
- [ ] Upload size and row count are limited. Malformed CSVs return 422, never 500.
- [ ] Tests use realistic fixture CSVs, including BOM, `;` vs `,`, and quoted fields.

**Notes.** Payout gross and fees: decide whether the invoiced amount is the gross charge or the
net payout, and document it. Invoices should normally show the amount billed to the client, not
the amount after Stripe fees. Use the standard `csv` module and Pydantic validation, not a
hand-written parser.

<details>
<summary>Agent prompt</summary>

> Add a Stripe payouts CSV import to PT Tax Assistant. Look up the current column layout of
> Stripe's Payouts export in the Stripe docs. Build a two-step preview/confirm API under
> `/api/payouts/import`, deduplicate on the Stripe payout id (add a unique column), validate
> every row with Pydantic, and enforce size and row limits. Reuse the ECB lookup in
> `backend/app/exchange_rates.py` for rates. Add an accessible upload/preview/confirm UI in the
> Payouts page. Document whether the gross charge or the net payout is the invoice amount and
> why. Cover the edge cases with fixture CSVs. Keep all checks green.

</details>

#### 10. Invoice lifecycle tracker

**Status:** 📋 Planned · **Area:** Full stack · **Depends on:** 13

**Goal.** Payouts store an optional invoice number, but nothing enforces that every payout was
invoiced on time. Track the invoice lifecycle and flag gaps.

**Acceptance criteria**

- [ ] Payouts can be edited in the UI (the `PUT` endpoint already exists), including the invoice
  number and issue date, through an "I issued this invoice" flow from the invoice helper.
- [ ] Invoice numbers are validated against the Portal format (`FR <series>/<n>`). Gaps and
  duplicates in the sequence are reported.
- [ ] The dashboard shows a "not yet invoiced" count with how overdue each one is, based on the
  legal issuing deadline.
- [ ] Optionally, each un-invoiced payout gets a CalDAV reminder (reusing `calendar_sync.py`).
- [ ] Backend and frontend tests cover the state transitions.

**Notes.** Find the legal deadline for issuing a fatura-recibo (CIVA art. 36.º and the rules for
*recibos verdes*). Don't guess it. Setting the invoice date can change which day's rate applies
to the document amount (see item 1), so editing it should offer to refresh the rate.

<details>
<summary>Agent prompt</summary>

> Add an invoice lifecycle to PT Tax Assistant: payout editing in the UI, a "mark as invoiced"
> flow from the invoice helper, invoice-number validation, gap and duplicate detection, and
> overdue alerts on the dashboard based on the legal issuing deadline (research CIVA art. 36.º
> and cite it). Optionally push reminders through `backend/app/calendar_sync.py`. Test the state
> machine on both sides.

</details>

#### 16. VAT regime monitor and invoice legal wording review

**Status:** 🔬 Research · **Area:** Domain research · **Depends on:** —

**Goal.** The VAT exemption reason defaults to the user-provided "Artigo 6.º, n.º 7, al. a) do
CIVA" with code `M99`. For B2B services to a non-EU business, the usual basis is art. 6.º n.º 6
al. a) *a contrario*. Confirm the right wording and code for each client type, and track the
Art. 53.º small-business threshold.

**Acceptance criteria**

- [ ] The client profile has a type (business or consumer, and location). The invoice helper
  picks the legally correct exemption wording and SAF-T exemption code for each, with citations.
- [ ] A VAT monitor computes year-to-date turnover relevant to Art. 53.º and warns at 75% and
  100% of the threshold. Deadlines switch regime when the user confirms.
- [ ] `PTTAX_VAT_REGIME` defaults are reviewed. The quarterly IVA deadline guides are checked
  against the current CIVA art. 41.º.
- [ ] Tests for each client type and the threshold transitions.

**Notes.** This is a research-heavy item. Use the official CIVA text and AT's list of exemption
codes (*Códigos de motivo de isenção*). Include a note recommending the user confirm with a
*contabilista certificado*.

<details>
<summary>Agent prompt</summary>

> Review and fix VAT handling in PT Tax Assistant. Using the official CIVA text (arts. 6.º, 41.º,
> 53.º) and AT's list of VAT exemption reason codes, decide the correct invoice wording and code
> for B2B and B2C clients outside the EU, add a client-type setting, and make
> `backend/app/fiscal/invoice_text.py` choose accordingly. Add an Art. 53.º threshold monitor
> with warnings and regime-dependent deadlines. Cite every rule and test each branch.

</details>

---

### M3 · Tax accuracy

#### 3. Multi-year and regional fiscal parameters

**Status:** 🔬 Research · **Area:** Domain research · **Depends on:** —

**Goal.** `parameters.py` only has 2026 mainland values. Add 2025, prepare 2027, and support the
Azores and Madeira rate tables. Also show where each number comes from.

**Acceptance criteria**

- [ ] `FISCAL_PARAMETERS` has 2025 and 2026, each value with a citation to the diploma that set
  it. A 2027 entry is added only if the values are published.
- [ ] A `region` (mainland / Açores / Madeira) setting changes the IRS bracket table.
- [ ] `GET /api/fiscal-parameters?year=` returns the values together with their sources. The
  frontend shows a "Fiscal parameters" panel with the sources.
- [ ] Parametrised tests check at least one official worked example per year, e.g. the AT
  simulator or the official average rate column (*taxa média*) at every bracket boundary.
- [ ] Any year without parameters still returns 422 with a helpful message.

**Notes.** IRS rates changed during 2025 (and possibly during 2026), so check which table applies
to *annual settlement* for each income year. Withholding tables are a separate thing. Search
results at the time of writing disagreed on the 2026 values, so use the official CIRS
consolidated text on `info.portaldasfinancas.gov.pt` and *Diário da República*.

<details>
<summary>Agent prompt</summary>

> Extend `backend/app/fiscal/parameters.py` to support several years and the Azores and Madeira
> IRS tables. Research the official values for 2025 and 2026 (CIRS art. 68.º and regional
> diplomas, IAS portarias, art. 25.º specific deduction) only from official sources (Portal das
> Finanças CIRS text, Diário da República). Cite each value. Move sources into structured data
> that the API exposes. Add a region setting and a parameters/sources panel in the frontend.
> Validate each year against the official average-rate column at every bracket boundary with
> parametrised tests.

</details>

#### 5. Business-day adjustment of deadlines

**Status:** 🔬 Research · **Area:** Domain + calendar · **Depends on:** —

**Goal.** Deadlines that fall on a weekend or a Portuguese public holiday are generated on the
nominal date. Shift them according to the legal rule for each obligation, and show both dates.

**Acceptance criteria**

- [ ] A pure function computes Portuguese national holidays for any year, including Easter-based
  ones (Good Friday, Corpus Christi).
- [ ] Each `Deadline` has `nominal_due` and `effective_due`, with a per-obligation rule saying
  whether it moves to the next business day.
- [ ] Calendar events use `effective_due`, and the description mentions the shift.
- [ ] Tests cover known years: 2026-01-31 is a Saturday, and so is 2026-10-31.

**Notes.** Prefer the maintained `holidays` package (country `PT`) over hand-rolled Easter maths
if it covers the needed holidays. (The Easter calculation in `backend/app/ecb.py` is for the ECB's
TARGET calendar, which is a different set of days.) The legal rule differs by obligation: CPPT
art. 20.º and Código Civil art. 279.º for tax deadlines, and the Segurança Social rules for SS.
Research and cite each one.

<details>
<summary>Agent prompt</summary>

> Add business-day adjustment to `backend/app/fiscal/deadlines.py`. Use the `holidays` package
> for Portuguese national holidays (check its docs), find and cite the legal rule for each
> deadline type (CPPT art. 20.º / CC art. 279.º for AT, the relevant rule for Segurança Social),
> and add `nominal_due` and `effective_due`. Update CalDAV rendering and the Calendar page to
> show shifts. Add tests for weekend and holiday cases in 2026 and 2027.

</details>

#### 6. The 15% expense-justification rule

**Status:** 🔬 Research · **Area:** Domain + UI · **Depends on:** 13

**Goal.** Under CIRS art. 31.º n.º 13, the 0.75 coefficient assumes 15% of gross services income
is justified by expenses (the standard €4,104 deduction plus e-Fatura activity expenses and other
listed items). Any shortfall is added to the taxable base. The estimator currently ignores this,
so it can understate IRS.

**Acceptance criteria**

- [ ] A new expense ledger (CRUD API and UI) records activity expenses by category, with the
  e-Fatura activity-expense flag.
- [ ] `estimate_irs` takes justified expenses and returns the required amount, the justified
  amount, the shortfall, and the adjusted taxable base.
- [ ] The dashboard warns when the year-to-date shortfall is above zero and shows how much more
  needs justifying.
- [ ] Tests cover: no shortfall, a partial shortfall, and income low enough that the standard
  deduction covers everything.

**Notes.** Read the current wording of art. 31.º n.os 13–15 carefully: which items count, how the
€4,104 standard deduction interacts, and how mixed-use expenses are capped at 25%. Cite the
paragraph numbers.

<details>
<summary>Agent prompt</summary>

> Implement the CIRS art. 31.º n.º 13 expense-justification rule in PT Tax Assistant. Read the
> official article text first and summarise which items count before coding. Add an `Expense`
> model, CRUD endpoints and a page. Extend `backend/app/fiscal/irs.py` so the simplified-regime
> base includes any shortfall. Surface it on the dashboard and the estimator. Test the boundary
> cases with figures you compute by hand from the law.

</details>

#### 7. Start-of-activity reductions and IRS Jovem

**Status:** 🔬 Research · **Area:** Domain + UI · **Depends on:** 3

**Goal.** Support the reduced coefficient in the first years of activity (CIRS art. 31.º n.º 10)
and the IRS Jovem exemption (art. 12.º-B) as optional profile settings in the estimator.

**Acceptance criteria**

- [ ] The profile records the activity start date, year of birth or first year of work, and
  whether IRS Jovem has already been used.
- [ ] `estimate_irs` applies the right reductions per year, and the result lists each one
  applied.
- [ ] The UI explains why a reduction does or doesn't apply.
- [ ] Tests cover every year of eligibility and the transitions between them.

**Notes.** IRS Jovem was rewritten in the OE 2025 (age ≤ 35, up to 10 years, an exemption
schedule, and a cap tied to IAS). Check the version in force for each income year.

<details>
<summary>Agent prompt</summary>

> Add start-of-activity coefficient reductions (CIRS art. 31.º n.º 10) and IRS Jovem
> (art. 12.º-B, as in force each year) to PT Tax Assistant. Research the current official text,
> add profile fields (settings or DB), apply the reductions in `backend/app/fiscal/irs.py` with an
> itemised breakdown, expose them in the Estimator page, and write year-by-year eligibility tests.

</details>

#### 8. Annual IRS settlement simulation

**Status:** 🔬 Research · **Area:** Domain + UI · **Depends on:** 3

**Goal.** The estimator stops at gross tax (*coleta*). Simulate the real annual settlement:
salary withholding already paid, deductions from the tax (*deduções à coleta*), the solidarity
surcharge, and the final refund or amount payable.

**Acceptance criteria**

- [ ] The user enters or derives the salary withholding using the official monthly withholding
  tables (Despacho) for their situation.
- [ ] Deductions supported: general family expenses, health, education, rent, VAT on invoices,
  with their legal caps. The overall cap by income level (art. 78.º n.º 7) is applied.
- [ ] The solidarity surcharge (art. 68.º-A) is applied above its thresholds.
- [ ] The result shows liquidated tax, credits, and refund or payment. Results are within ±1 € of
  the AT simulator for 3 documented scenarios, saved as test fixtures.

**Notes.** Withholding tables are formula-based since 2023 (marginal rate and amount to
subtract). Model them as data per year. Keep this separate from the "freelance impact" figure on
the dashboard.

<details>
<summary>Agent prompt</summary>

> Build an annual IRS settlement simulator into PT Tax Assistant. Using official sources only
> (CIRS arts. 68.º-A, 78.º–78.º-E, 99.º-C and the year's withholding Despacho), model withholding
> on salary, deductions with caps, the solidarity surcharge, and the final refund or amount due.
> Add an endpoint and an Estimator sub-section. Write three scenario tests whose expected values
> you derive step by step in the test docstrings.

</details>

#### 9. Complete Social Security model

**Status:** 🔬 Research · **Area:** Domain + UI · **Depends on:** —

**Goal.** The SS estimator handles the 4×IAS exemption for people who also have employment. It
does not handle the 12-month exemption at the start of activity, the optional ±25% adjustment of
relevant income, the minimum contribution, or the income-date basis. It also doesn't give the
monthly values to type into the quarterly declaration.

**Acceptance criteria**

- [ ] The profile records the activity start date. Contributions are zero during the initial
  exemption, as defined in the code.
- [ ] The user can pick an adjustment from −25% to +25% in 5% steps, and it is applied to the
  base.
- [ ] The quarterly declaration helper lists each month's services income exactly as SS Direta
  asks for it, with copy buttons.
- [ ] The dashboard shows a monthly payment schedule (amount, due date) for the year.
- [ ] Tests check each rule against worked examples from the official SS practical guide.

**Notes.** Verify against the current Código Contributivo (arts. 157.º, 162.º–168.º) and the
official *Guia Prático — Trabalhadores Independentes*. Also verify the assumption in
`social_security.py` that only the excess over 4×IAS is charged. The quarterly declaration is
pre-filled by AT from the invoices issued, i.e. the document amounts, while the estimator uses the
IRS amounts (see item 1). Decide which one the helper shows and say why.

<details>
<summary>Agent prompt</summary>

> Complete the Segurança Social model in `backend/app/fiscal/social_security.py`. Using the
> current Código Contributivo and the official ISS practical guide, verify the existing 4×IAS
> logic and add the first-12-months exemption, the ±25% adjustment, the minimum contribution if
> applicable, a per-month declaration helper (with copy fields in the UI), and a monthly payment
> schedule on the dashboard. Cite articles and test against the guide's examples.

</details>

---

### M4 · Reporting and experience

#### 4. Scheduled CalDAV sync with state and stale-event cleanup

**Status:** 📋 Planned · **Area:** Background jobs · **Depends on:** 13

**Goal.** Sync currently only runs from a button or the CLI. Add a scheduled background sync that
records its history, retries on failure, and removes events this app created that are no longer
generated (for example after changing the VAT regime).

**Acceptance criteria**

- [ ] An in-container scheduler (or a separate compose service) syncs on a configurable cron
  (default daily), for the current year and for the next year from 1 December onwards.
- [ ] A `calendar_sync_runs` table records start, end, pushed, deleted, failed, and error text.
  `GET /api/calendar/status` returns the last run. The Calendar page shows it.
- [ ] Events whose UID ends in `@pt-tax-assistant` but are no longer in the generated set are
  deleted. Events created by anything else are never touched (tested against a fake CalDAV
  calendar).
- [ ] Transient network errors retry with exponential backoff. Auth errors (401/403) do not retry
  and surface clearly.
- [ ] Two syncs can't run at the same time, whether triggered by the scheduler or the button.

**Notes.** Prefer a maintained scheduler library (e.g. APScheduler) or a simple supercronic
sidecar over a hand-rolled loop. Use a library for retries (e.g. `tenacity`). caldav 3.x API:
`calendar.search(...)` and `get_object_by_uid`. Check the caldav docs for the version in
`uv.lock`.

<details>
<summary>Agent prompt</summary>

> Implement scheduled, stateful Nextcloud CalDAV sync for PT Tax Assistant. Pick a maintained
> scheduler and retry library, verify their APIs against official docs, and justify the choice.
> Persist sync runs, expose them in `/api/calendar/status` and the Calendar page, prevent
> concurrent runs, and delete stale events this app owns (UID suffix `@pt-tax-assistant`) without
> touching anything else. Write tests against an in-memory fake calendar. Update the Dockerfile or
> compose file if a sidecar is needed.

</details>

#### 14. Accountant export

**Status:** 📋 Planned · **Area:** Full stack · **Depends on:** —

**Goal.** At year end the accountant needs a summary: payouts with invoice numbers and rates,
quarterly totals, SS declarations, and the IRS estimate. Generate it as CSV, XLSX and a one-page
PDF.

**Acceptance criteria**

- [ ] `GET /api/exports/{year}.csv|.xlsx|.pdf` returns correct files with PT number formatting in
  the human-readable outputs.
- [ ] The XLSX has sheets for payouts, monthly totals, quarterly SS, and the IRS summary, using
  real numeric cells (not text).
- [ ] Payout rows include both the document and the IRS rate pairs, their ECB days, and whether
  each rate was taken from the ECB or entered manually.
- [ ] The PDF includes the compliance disclaimer and the fiscal parameter sources.
- [ ] Download buttons on the Dashboard. Tests open the generated files and check their contents.

**Notes.** Use maintained libraries (e.g. openpyxl, a PDF library such as WeasyPrint or
ReportLab). Note the image-size impact in the Dockerfile.

<details>
<summary>Agent prompt</summary>

> Add yearly accountant exports (CSV, XLSX, PDF) to PT Tax Assistant using maintained libraries.
> Reuse `build_year_overview` from `backend/app/fiscal/ledger.py`. Store numbers as numeric
> cells, include both rate pairs with their provenance, the parameter sources and the disclaimer,
> add download buttons on the Dashboard, and test by parsing the generated files. Keep the Docker
> image building.

</details>

#### 15. Dashboard charts and year-end projection

**Status:** 📋 Planned · **Area:** Frontend · **Depends on:** —

**Goal.** The dashboard is all tables. Add accessible charts and a year-end projection that
warns when the projected income crosses into a higher IRS bracket or an SS threshold.

**Acceptance criteria**

- [ ] A monthly bar chart of gross vs savings target, and a cumulative line of obligations vs
  savings pool.
- [ ] The projection uses year-to-date run-rate (and optionally a user-entered expected income),
  and shows the projected IRS impact, the marginal bracket, and the quarters where SS kicks in.
- [ ] Charts work in light and dark mode, have text alternatives or data-table fallbacks, and
  work by keyboard.
- [ ] Tests cover the projection maths (backend) and render the charts (frontend).

**Notes.** Prefer a maintained chart library (e.g. Recharts). Put the projection logic in
`backend/app/fiscal/`, not in React.

<details>
<summary>Agent prompt</summary>

> Upgrade the PT Tax Assistant dashboard with accessible charts (pick a maintained React chart
> library and justify it) and a year-end projection computed in a new pure backend function next
> to `ledger.py`. Warn when the projection crosses an IRS bracket or the 4×IAS SS threshold.
> Support light and dark themes and provide table fallbacks. Test both layers.

</details>

#### 18. Portuguese / English internationalisation

**Status:** 📋 Planned · **Area:** Frontend · **Depends on:** —

**Goal.** The UI mixes English labels with Portuguese legal terms. Add full PT-PT and EN
translations. Legal strings that are pasted into the Portal stay in Portuguese whatever the
language.

**Acceptance criteria**

- [ ] All UI strings come from translation catalogues. A language switcher remembers the choice.
- [ ] Number and date formatting follows the selected locale. Portal copy fields always use PT
  formatting.
- [ ] Calendar event guides can be generated in either language (a setting).
- [ ] A test fails if any catalogue key is missing in either language.

**Notes.** Use a maintained i18n library (e.g. react-i18next) on the frontend. On the backend,
keep guide texts as data, not inline f-strings. The exchange-rate notes and legal-basis texts
returned by `/api/exchange-rates` are English today and need the same treatment.

<details>
<summary>Agent prompt</summary>

> Internationalise PT Tax Assistant into PT-PT and EN using a maintained i18n library. Move all
> UI strings into catalogues, add a persisted language switcher, keep Portal copy-paste fields in
> Portuguese with PT formatting, and make the CalDAV guide texts in
> `backend/app/fiscal/deadlines.py` available in both languages via a setting. Add a
> catalogue-completeness test.

</details>
