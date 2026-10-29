import { type FormEvent, useCallback, useState } from "react";

import {
  type Currency,
  type ExchangeRate,
  type PayoutInput,
  type RateLookup,
  type RateProvenance,
  api,
  irsRateDiffers,
} from "../api";
import { CopyField } from "../components/CopyField";
import { Status } from "../components/Status";
import {
  describeProvenance,
  formatDate,
  formatEur,
  previewEurAmount,
  trimDecimal,
} from "../format";
import { type ApiState, useApi } from "../useApi";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function emptyForm(): PayoutInput {
  return {
    payout_date: new Date().toISOString().slice(0, 10),
    currency: "USD",
    original_amount: "",
    currency_per_eur: "",
    rate_date: null,
    rate_provenance: null,
    irs_currency_per_eur: null,
    irs_rate_date: null,
    irs_rate_provenance: null,
    client_name: null,
    notes: null,
    invoice_number: null,
    invoice_issued_on: null,
  };
}

function InvoiceHelper({ payoutId }: { payoutId: number }) {
  const load = useCallback(() => api.invoiceFields(payoutId), [payoutId]);
  const { data: fields, error, loading } = useApi(load);

  return (
    <section aria-labelledby="invoice-helper-title" className="panel">
      <h3 id="invoice-helper-title">Portal das Finanças — Fatura-Recibo</h3>
      <p>
        Copy each value into <em>Faturas e Recibos Verdes → Emitir</em>. This app never logs in
        to the Portal for you.
      </p>
      <Status loading={loading} error={error} />
      {fields && (
        <dl>
          {fields.map((field) => (
            <CopyField key={field.portal_label} field={field} />
          ))}
        </dl>
      )}
    </section>
  );
}

function provenanceOf(lookup: RateLookup | null, overridden: boolean): RateProvenance {
  return {
    source: overridden ? "manual" : "ecb",
    requested_date: lookup?.requested_date ?? null,
    ecb_rate_date: lookup?.rate_date ?? null,
    ecb_currency_per_eur: lookup?.currency_per_eur ?? null,
    is_fallback: lookup?.is_fallback ?? null,
    fallback_reason: lookup?.fallback_reason ?? null,
    fetched_at: lookup?.fetched_at ?? null,
  };
}

function RateLine({
  label,
  rate,
  currency,
  overridden,
  onUseEcbRate,
}: {
  label: string;
  rate: RateLookup;
  currency: Currency;
  overridden: boolean;
  onUseEcbRate: () => void;
}) {
  return (
    <div className={rate.is_fallback ? "warning" : undefined}>
      <p>
        <strong>{label}:</strong>{" "}
        {overridden ? "entered manually" : "auto-filled from the ECB"} — ECB reference rate for{" "}
        {formatDate(rate.rate_date)} ({trimDecimal(rate.currency_per_eur)} {currency}/EUR
        {rate.from_cache ? ", cached locally" : ""}).
        {overridden && (
          <>
            {" "}
            <button type="button" onClick={onUseEcbRate}>
              Use ECB rate
            </button>
          </>
        )}
      </p>
      {rate.is_fallback && <p>{rate.note}</p>}
    </div>
  );
}

function RateSource({
  lookup,
  currency,
  documentOverridden,
  irsOverridden,
  onUseEcbRate,
  onUseEcbIrsRate,
}: {
  lookup: ApiState<ExchangeRate | null>;
  currency: Currency;
  documentOverridden: boolean;
  irsOverridden: boolean;
  onUseEcbRate: () => void;
  onUseEcbIrsRate: () => void;
}) {
  if (lookup.error) {
    return (
      <p role="alert" className="error">
        ECB rate unavailable: {lookup.error}. Enter the rate manually (source: your own lookup).
      </p>
    );
  }
  if (lookup.loading) {
    return (
      <p className="note" aria-live="polite">
        Looking up the ECB reference rate…
      </p>
    );
  }
  const rate = lookup.data;
  if (!rate) {
    return null;
  }
  return (
    <div className="note rate-source" aria-live="polite">
      <p>
        Source:{" "}
        <a href={rate.source_url} target="_blank" rel="noreferrer">
          ECB euro reference rates
        </a>
        . Rate day: {formatDate(rate.requested_date)} (
        {rate.conversion_basis === "invoice_date" ? "invoice date" : "payout date"}).{" "}
        {rate.conversion_note}
      </p>
      <RateLine
        label={rate.rates_differ ? "Fatura-Recibo rate" : "Rate"}
        rate={rate}
        currency={currency}
        overridden={documentOverridden}
        onUseEcbRate={onUseEcbRate}
      />
      {rate.rates_differ && (
        <RateLine
          label="IRS rate (payout date)"
          rate={rate.irs}
          currency={currency}
          overridden={irsOverridden}
          onUseEcbRate={onUseEcbIrsRate}
        />
      )}
      <small>{rate.legal_basis}</small>
    </div>
  );
}

export function Payouts({ year }: { year: number }) {
  const load = useCallback(() => api.listPayouts(year), [year]);
  const { data: payouts, error, loading, reload } = useApi(load);
  const [form, setForm] = useState<PayoutInput>(emptyForm);
  // null: follow the ECB lookup; a string: the user typed their own rate.
  const [rateOverride, setRateOverride] = useState<string | null>(null);
  const [irsRateOverride, setIrsRateOverride] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const currency = form.currency;
  const lookupDate =
    currency !== "EUR" && ISO_DATE.test(form.payout_date) ? form.payout_date : null;
  const invoiceDate =
    form.invoice_issued_on && ISO_DATE.test(form.invoice_issued_on)
      ? form.invoice_issued_on
      : null;
  // Invoice issued before the payout: the Fatura-Recibo converts on the invoice day (CIVA
  // art. 8.º n.º 1 al. a) + 49.º) while IRS income converts on the payout day (CIRS art. 23.º).
  const twoRates = lookupDate !== null && invoiceDate !== null && invoiceDate < lookupDate;
  const loadRate = useCallback(
    () =>
      lookupDate ? api.exchangeRate(currency, lookupDate, invoiceDate) : Promise.resolve(null),
    [currency, lookupDate, invoiceDate],
  );
  const rateLookup = useApi(loadRate);
  const ecbRate = !rateLookup.loading && rateLookup.data ? rateLookup.data : null;
  const ecbRateValue = ecbRate ? trimDecimal(ecbRate.currency_per_eur) : "";
  const ecbIrsRateValue = ecbRate ? trimDecimal(ecbRate.irs.currency_per_eur) : "";
  const effectiveRate = currency === "EUR" ? "1" : (rateOverride ?? ecbRateValue);
  const effectiveIrsRate = twoRates ? (irsRateOverride ?? ecbIrsRateValue) : effectiveRate;

  const eurPreview = previewEurAmount(form.original_amount, effectiveRate);
  const irsPreview = previewEurAmount(form.original_amount, effectiveIrsRate);

  function update<K extends keyof PayoutInput>(key: K, value: PayoutInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function resetOverrides() {
    setRateOverride(null);
    setIrsRateOverride(null);
  }

  function changeDate(key: "payout_date" | "invoice_issued_on", value: string) {
    resetOverrides();
    if (key === "payout_date") {
      update("payout_date", value); // required field: stays a (possibly empty) string
    } else {
      update("invoice_issued_on", value || null);
    }
  }

  function changeCurrency(currency: Currency) {
    resetOverrides();
    setForm((current) => ({ ...current, currency, currency_per_eur: "" }));
  }

  function payload(): PayoutInput {
    if (currency === "EUR") {
      return {
        ...form,
        currency_per_eur: "1",
        rate_date: null,
        rate_provenance: null,
        irs_currency_per_eur: "1",
        irs_rate_date: null,
        irs_rate_provenance: null,
      };
    }
    const documentOverridden = rateOverride !== null;
    const rateDate = !documentOverridden && ecbRate ? ecbRate.rate_date : null;
    const rateProvenance = provenanceOf(ecbRate, documentOverridden);
    if (!twoRates) {
      return {
        ...form,
        currency_per_eur: effectiveRate,
        rate_date: rateDate,
        rate_provenance: rateProvenance,
        irs_currency_per_eur: effectiveIrsRate,
        irs_rate_date: rateDate,
        irs_rate_provenance: rateProvenance,
      };
    }
    const irsOverridden = irsRateOverride !== null;
    return {
      ...form,
      currency_per_eur: effectiveRate,
      rate_date: rateDate,
      rate_provenance: rateProvenance,
      irs_currency_per_eur: effectiveIrsRate,
      irs_rate_date: !irsOverridden && ecbRate ? ecbRate.irs.rate_date : null,
      irs_rate_provenance: provenanceOf(ecbRate?.irs ?? null, irsOverridden),
    };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      const created = await api.createPayout(payload());
      setForm(emptyForm());
      resetOverrides();
      setSelectedId(created.id);
      reload();
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Could not save payout");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: number) {
    if (!window.confirm("Delete this payout?")) {
      return;
    }
    try {
      await api.deletePayout(id);
      if (selectedId === id) {
        setSelectedId(null);
      }
      reload();
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Could not delete payout");
    }
  }

  return (
    <section aria-labelledby="payouts-title">
      <h2 id="payouts-title">Stripe payouts & invoice helper</h2>

      <form onSubmit={submit} className="panel payout-form">
        <label>
          Payout date
          <input
            type="date"
            required
            value={form.payout_date}
            onChange={(event) => changeDate("payout_date", event.target.value)}
          />
        </label>
        <label>
          Currency
          <select
            value={form.currency}
            onChange={(event) => changeCurrency(event.target.value as Currency)}
          >
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </select>
        </label>
        <label>
          Amount ({form.currency})
          <input
            type="number"
            required
            min="0.01"
            step="0.01"
            inputMode="decimal"
            value={form.original_amount}
            onChange={(event) => update("original_amount", event.target.value)}
          />
        </label>
        {form.currency !== "EUR" && (
          <label>
            {twoRates ? "Fatura-Recibo rate" : "Exchange rate"} ({form.currency} per 1 EUR)
            <input
              type="number"
              required
              min="0.000001"
              step="0.000001"
              inputMode="decimal"
              value={effectiveRate}
              onChange={(event) => setRateOverride(event.target.value)}
            />
          </label>
        )}
        {form.currency !== "EUR" && twoRates && (
          <label>
            IRS rate ({form.currency} per 1 EUR, payout date)
            <input
              type="number"
              required
              min="0.000001"
              step="0.000001"
              inputMode="decimal"
              value={effectiveIrsRate}
              onChange={(event) => setIrsRateOverride(event.target.value)}
            />
          </label>
        )}
        {form.currency !== "EUR" && (
          <RateSource
            lookup={rateLookup}
            currency={form.currency}
            documentOverridden={rateOverride !== null}
            irsOverridden={irsRateOverride !== null}
            onUseEcbRate={() => setRateOverride(null)}
            onUseEcbIrsRate={() => setIrsRateOverride(null)}
          />
        )}
        <label>
          Client (optional)
          <input
            type="text"
            maxLength={200}
            value={form.client_name ?? ""}
            onChange={(event) => update("client_name", event.target.value || null)}
          />
        </label>
        <label>
          Notes
          <input
            type="text"
            maxLength={2000}
            value={form.notes ?? ""}
            onChange={(event) => update("notes", event.target.value || null)}
          />
        </label>
        <label>
          Invoice number (optional)
          <input
            type="text"
            maxLength={50}
            value={form.invoice_number ?? ""}
            onChange={(event) => update("invoice_number", event.target.value || null)}
          />
        </label>
        <label>
          Invoice issued on (optional)
          <input
            type="date"
            value={form.invoice_issued_on ?? ""}
            onChange={(event) => changeDate("invoice_issued_on", event.target.value)}
          />
        </label>
        <p aria-live="polite">
          {twoRates ? "Fatura-Recibo EUR amount" : "EUR amount"}:{" "}
          {eurPreview ? formatEur(eurPreview) : "—"}
        </p>
        {twoRates && (
          <p aria-live="polite">IRS income EUR amount: {irsPreview ? formatEur(irsPreview) : "—"}</p>
        )}
        {formError && (
          <p role="alert" className="error">
            {formError}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? "Saving…" : "Add payout"}
        </button>
      </form>

      <Status loading={loading} error={error} />
      {payouts && payouts.length === 0 && <p>No payouts recorded for {year}.</p>}
      {payouts && payouts.length > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Original</th>
              <th scope="col">EUR</th>
              <th scope="col">Invoice</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {payouts.map((payout) => (
              <tr key={payout.id} aria-selected={payout.id === selectedId}>
                <th scope="row">{formatDate(payout.payout_date)}</th>
                <td>
                  {payout.currency} {payout.original_amount}
                </td>
                <td>
                  {formatEur(payout.eur_amount)}
                  {describeProvenance(payout.rate_provenance) && (
                    <small className="irs-amount">
                      Rate: {describeProvenance(payout.rate_provenance)}
                    </small>
                  )}
                  {irsRateDiffers(payout) && (
                    <small className="irs-amount">
                      Fatura-Recibo
                      {payout.rate_date ? ` (rate of ${formatDate(payout.rate_date)})` : ""}.
                      IRS income: {formatEur(payout.irs_eur_amount)}
                      {payout.irs_rate_date
                        ? ` (rate of ${formatDate(payout.irs_rate_date)})`
                        : ` (rate ${trimDecimal(payout.irs_currency_per_eur)})`}
                      {describeProvenance(payout.irs_rate_provenance)
                        ? ` — ${describeProvenance(payout.irs_rate_provenance)}`
                        : ""}
                    </small>
                  )}
                </td>
                <td>{payout.invoice_number ?? "Not issued"}</td>
                <td className="actions">
                  <button type="button" onClick={() => setSelectedId(payout.id)}>
                    Invoice text
                  </button>
                  <button type="button" onClick={() => remove(payout.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selectedId !== null && <InvoiceHelper payoutId={selectedId} />}
    </section>
  );
}
