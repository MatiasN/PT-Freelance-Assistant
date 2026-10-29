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
