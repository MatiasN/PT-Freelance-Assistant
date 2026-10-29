import { type FormEvent, useCallback, useState } from "react";

import { type Currency, type PayoutInput, api } from "../api";
import { CopyField } from "../components/CopyField";
import { Status } from "../components/Status";
import { formatDate, formatEur, previewEurAmount } from "../format";
import { useApi } from "../useApi";

function emptyForm(): PayoutInput {
  return {
    payout_date: new Date().toISOString().slice(0, 10),
    currency: "USD",
    original_amount: "",
    currency_per_eur: "",
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

export function Payouts({ year }: { year: number }) {
  const load = useCallback(() => api.listPayouts(year), [year]);
  const { data: payouts, error, loading, reload } = useApi(load);
  const [form, setForm] = useState<PayoutInput>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const eurPreview =
    form.currency === "EUR"
      ? previewEurAmount(form.original_amount, "1")
      : previewEurAmount(form.original_amount, form.currency_per_eur);

  function update<K extends keyof PayoutInput>(key: K, value: PayoutInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function changeCurrency(currency: Currency) {
    setForm((current) => ({
      ...current,
      currency,
      currency_per_eur: currency === "EUR" ? "1" : "",
    }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      const created = await api.createPayout(form);
      setForm(emptyForm());
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
            onChange={(event) => update("payout_date", event.target.value)}
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
            ECB rate ({form.currency} per 1 EUR)
            <input
              type="number"
              required
              min="0.000001"
              step="0.000001"
              inputMode="decimal"
              value={form.currency_per_eur}
              onChange={(event) => update("currency_per_eur", event.target.value)}
            />
          </label>
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
        <p aria-live="polite">EUR amount: {eurPreview ? formatEur(eurPreview) : "—"}</p>
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
                <td>{formatEur(payout.eur_amount)}</td>
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
