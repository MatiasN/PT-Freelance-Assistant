import type { RateProvenance } from "./api";

const eurFormatter = new Intl.NumberFormat("pt-PT", { style: "currency", currency: "EUR" });
const percentFormatter = new Intl.NumberFormat("pt-PT", {
  style: "percent",
  maximumFractionDigits: 2,
});
const dateFormatter = new Intl.DateTimeFormat("pt-PT", { dateStyle: "medium", timeZone: "UTC" });

export function formatEur(amount: string): string {
  return eurFormatter.format(Number(amount));
}

export function formatPercent(rate: string): string {
  return percentFormatter.format(Number(rate));
}

export function formatDate(isoDate: string): string {
  return dateFormatter.format(new Date(`${isoDate}T00:00:00Z`));
}

export function previewEurAmount(originalAmount: string, currencyPerEur: string): string | null {
  const amount = Number(originalAmount);
  const rate = Number(currencyPerEur);
  if (!Number.isFinite(amount) || !Number.isFinite(rate) || amount <= 0 || rate <= 0) {
    return null;
  }
  return (Math.round((amount / rate) * 100) / 100).toFixed(2);
}

/** "1.081700" → "1.0817" (the API serialises rates with six decimals). */
export function trimDecimal(value: string): string {
  if (!/^-?\d+\.\d+$/.test(value)) {
    return value;
  }
  return value.replace(/\.?0+$/, "");
}

/** Short description for the payouts table; null when nothing was recorded (older rows). */
export function describeProvenance(provenance: RateProvenance | null): string | null {
  if (!provenance) {
    return null;
  }
  const ecbDay = provenance.ecb_rate_date ? formatDate(provenance.ecb_rate_date) : null;
  if (provenance.source === "ecb") {
    const fallback =
      provenance.is_fallback && provenance.requested_date
        ? ` (fallback for ${formatDate(provenance.requested_date)})`
        : "";
    return `ECB rate of ${ecbDay ?? "unknown day"}${fallback}`;
  }
  if (provenance.ecb_currency_per_eur && ecbDay) {
    return `manual (ECB was ${trimDecimal(provenance.ecb_currency_per_eur)} on ${ecbDay})`;
  }
  return "manual (no ECB lookup)";
}

