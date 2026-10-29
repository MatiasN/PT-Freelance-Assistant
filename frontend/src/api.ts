export type Money = string;
export type Currency = "EUR" | "USD";

export type RateSource = "manual" | "ecb";

/** Where a stored rate came from, plus the ECB evidence for that day either way. */
export interface RateProvenance {
  source: RateSource;
  requested_date: string | null;
  ecb_rate_date: string | null;
  ecb_currency_per_eur: Money | null;
  is_fallback: boolean | null;
  fallback_reason: FallbackReason | null;
  fetched_at: string | null;
}

export interface PayoutInput {
  payout_date: string;
  currency: Currency;
  original_amount: Money;
  /** Rate for the Fatura-Recibo amount (CIVA art. 49.º day: invoice date if it precedes the payout). */
  currency_per_eur: Money;
  rate_date: string | null;
  rate_provenance: RateProvenance | null;
  /** Rate of the payment day (CIRS art. 23.º), used for the IRS income. */
  irs_currency_per_eur: Money | null;
  irs_rate_date: string | null;
  irs_rate_provenance: RateProvenance | null;
  client_name: string | null;
  notes: string | null;
  invoice_number: string | null;
  invoice_issued_on: string | null;
}

export interface Payout extends PayoutInput {
  id: number;
  eur_amount: Money;
  irs_currency_per_eur: Money;
  irs_eur_amount: Money;
  created_at: string;
}

/** The stored IRS pair differs from the document pair (another day or another rate). */
export function irsRateDiffers(payout: Payout): boolean {
  return (
    payout.irs_eur_amount !== payout.eur_amount ||
    payout.irs_currency_per_eur !== payout.currency_per_eur ||
    payout.irs_rate_date !== payout.rate_date
  );
}

export type FallbackReason =
  | "weekend"
  | "target_holiday"
  | "not_yet_published"
  | "no_rate_published";

export type ConversionBasis = "payout_date" | "invoice_date";

export interface RateLookup {
  /** Day asked for. */
  requested_date: string;
  /** ECB business day the rate belongs to; differs from requested_date on a fallback. */
  rate_date: string;
  currency_per_eur: Money;
  is_fallback: boolean;
  fallback_reason: FallbackReason | null;
  note: string;
  fetched_at: string;
  from_cache: boolean;
}

/** Top level: the Fatura-Recibo rate (CIVA art. 49.º with art. 8.º n.º 1). `irs`: the
 * payment-day rate (CIRS art. 23.º). They are the same lookup unless the invoice was issued
 * before the payout. */
export interface ExchangeRate extends RateLookup {
  currency: Currency;
  payout_date: string;
  invoice_issued_on: string | null;
  conversion_basis: ConversionBasis;
  conversion_note: string;
  irs: RateLookup;
  rates_differ: boolean;
  source: string;
  source_url: string;
  legal_basis: string;
}

export interface PortalField {
  portal_label: string;
  value: string;
  hint: string;
}

export interface BracketSlice {
  lower_limit: Money;
  upper_limit: Money | null;
  rate: Money;
  taxable_in_bracket: Money;
  tax: Money;
}

export interface ProgressiveTax {
  taxable_income: Money;
  total_tax: Money;
  marginal_rate: Money;
  effective_rate: Money;
  slices: BracketSlice[];
}

export interface IrsEstimate {
  year: number;
  employment_gross: Money;
  employment_specific_deduction: Money;
  employment_net_income: Money;
  freelance_gross: Money;
  simplified_regime_coefficient: Money;
  freelance_taxable_income: Money;
  tax_without_freelance: ProgressiveTax;
  tax_with_freelance: ProgressiveTax;
  freelance_tax_impact: Money;
  freelance_effective_rate: Money;
}

export interface QuarterlySocialSecurity {
  year: number;
  quarter: number;
  services_income: Money;
  relevant_income: Money;
  monthly_average_relevant_income: Money;
  exempt_threshold: Money;
  monthly_contribution_base: Money;
  monthly_contribution: Money;
  quarterly_contribution: Money;
  declaration_deadline: string;
  contribution_months: string[];
}

export interface PeriodTotal {
  label: string;
  gross: Money;
  savings_target: Money;
}

export interface YearOverview {
  year: number;
  gross: Money;
  savings_pool_rate: Money;
  savings_target: Money;
  irs: IrsEstimate;
  social_security_quarters: QuarterlySocialSecurity[];
  social_security_total: Money;
  estimated_obligations: Money;
  expected_net: Money;
  savings_gap: Money;
  monthly: PeriodTotal[];
  weekly: PeriodTotal[];
}

export interface Deadline {
  key: string;
  kind: string;
  title: string;
  due: string;
  guide_markdown: string;
  links: { title: string; url: string }[];
  repeat_every_days: number | null;
}

export interface CalendarStatus {
  configured: boolean;
  calendar_url: string;
}

export interface SyncReport {
  calendar_url: string;
  pushed: number;
  failed: string[];
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = body.detail;
      if (typeof detail === "string") {
        return detail;
      }
      if (Array.isArray(detail)) {
        return detail.map((issue: { msg?: string }) => issue.msg ?? "Invalid value").join("; ");
      }
    }
  } catch {
    // Non-JSON error body: fall back to the status text below.
  }
  return response.statusText || `Request failed with status ${response.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  fiscalYears: () => request<number[]>("/api/fiscal-parameters/years"),
  listPayouts: (year: number) => request<Payout[]>(`/api/payouts?year=${year}`),
  createPayout: (payout: PayoutInput) =>
    request<Payout>("/api/payouts", { method: "POST", body: JSON.stringify(payout) }),
  updatePayout: (id: number, payout: PayoutInput) =>
    request<Payout>(`/api/payouts/${id}`, { method: "PUT", body: JSON.stringify(payout) }),
  deletePayout: (id: number) => request<void>(`/api/payouts/${id}`, { method: "DELETE" }),
  invoiceFields: (id: number) => request<PortalField[]>(`/api/payouts/${id}/invoice-fields`),
  exchangeRate: (currency: Currency, payoutDate: string, invoiceIssuedOn: string | null) =>
    request<ExchangeRate>(
      `/api/exchange-rates?${new URLSearchParams({
        currency,
        payout_date: payoutDate,
        ...(invoiceIssuedOn ? { invoice_issued_on: invoiceIssuedOn } : {}),
      })}`,
    ),
  dashboard: (year: number) => request<YearOverview>(`/api/dashboard?year=${year}`),
  irsEstimate: (year: number, freelanceGross: string, employmentGross: string) =>
    request<IrsEstimate>(
      `/api/estimates/irs?${new URLSearchParams({
        year: String(year),
        freelance_gross: freelanceGross,
        employment_gross: employmentGross,
      })}`,
    ),
  socialSecurityEstimate: (year: number, quarter: number, servicesIncome: string) =>
    request<QuarterlySocialSecurity>(
      `/api/estimates/social-security?${new URLSearchParams({
        year: String(year),
        quarter: String(quarter),
        services_income: servicesIncome,
      })}`,
    ),
  deadlines: (year: number) => request<Deadline[]>(`/api/calendar/deadlines?year=${year}`),
  calendarStatus: () => request<CalendarStatus>("/api/calendar/status"),
  syncCalendar: (year: number) =>
    request<SyncReport>(`/api/calendar/sync?year=${year}`, { method: "POST" }),
};
