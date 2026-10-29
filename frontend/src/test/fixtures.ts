import type { ExchangeRate, Payout, RateLookup, RateProvenance } from "../api";

const LEGAL_BASIS =
  "CIVA art. 49.º n.º 1 (rate of the day the tax becomes chargeable) with art. 8.º n.º 1: " +
  "al. c) payment received before the invoice -> day of receipt; al. a) invoice issued first " +
  "-> invoice date. CIRS art. 23.º n.º 1 al. b): income from abroad is converted on the day " +
  "it was paid or made available; n.º 3: without a quotation for that day, the last previous " +
  "quotation applies.";

export const PAYOUT_DATE_NOTE =
  "Payment received on 2026-03-06: IVA became chargeable on receipt (CIVA art. 8.º n.º 1 " +
  "al. c)), and CIRS art. 23.º n.º 1 al. b) converts income on the day it was paid or made " +
  "available, so both rules point to the payout date.";

const fridayLookup: RateLookup = {
  requested_date: "2026-03-06",
  rate_date: "2026-03-06",
  currency_per_eur: "1.081700",
  is_fallback: false,
  fallback_reason: null,
  note: "ECB euro foreign exchange reference rate for 2026-03-06.",
  fetched_at: "2026-03-06T16:05:00Z",
  from_cache: false,
};

const saturdayLookup: RateLookup = {
  ...fridayLookup,
  requested_date: "2026-03-07",
  is_fallback: true,
  fallback_reason: "weekend",
  note:
    "The ECB does not publish reference rates on weekends (Saturday 2026-03-07). Using the " +
    "latest previous ECB business day, 2026-03-06, as CIRS art. 23.º n.º 3 prescribes " +
    "(última cotação anterior).",
  from_cache: true,
};

/** Real ECB value for 2 March 2026 (from the captured Data Portal answer). */
const mondayLookup: RateLookup = {
  ...fridayLookup,
  requested_date: "2026-03-02",
  rate_date: "2026-03-02",
  currency_per_eur: "1.169800",
  note: "ECB euro foreign exchange reference rate for 2026-03-02.",
};

export const usdRateFriday: ExchangeRate = {
  ...fridayLookup,
  currency: "USD",
  payout_date: "2026-03-06",
  invoice_issued_on: null,
  conversion_basis: "payout_date",
  conversion_note: PAYOUT_DATE_NOTE,
  irs: fridayLookup,
  rates_differ: false,
  source: "European Central Bank — euro foreign exchange reference rates (ECB Data Portal, EXR)",
  source_url: "https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A",
  legal_basis: LEGAL_BASIS,
};

export const usdRateSaturdayFallback: ExchangeRate = {
  ...usdRateFriday,
  ...saturdayLookup,
  payout_date: "2026-03-07",
  irs: saturdayLookup,
};

/** Invoice issued Monday 2 March, payout arrived Friday 6 March: the invoice day applies. */
export const usdRateInvoiceFirst: ExchangeRate = {
  ...usdRateFriday,
  ...mondayLookup,
  invoice_issued_on: "2026-03-02",
  conversion_basis: "invoice_date",
  irs: fridayLookup,
  rates_differ: true,
  conversion_note:
    "The invoice was issued on 2026-03-02, before the payout of 2026-03-06: IVA became " +
    "chargeable on the invoice date (CIVA art. 8.º n.º 1 al. a)), so the document is " +
    "converted at that day's rate (CIVA art. 49.º n.º 1). For IRS, CIRS art. 23.º n.º 1 " +
    "al. b) uses the day the income was paid (2026-03-06); tell your accountant if the two " +
    "amounts differ.",
};

export const ecbProvenanceFriday: RateProvenance = {
  source: "ecb",
  requested_date: "2026-03-06",
  ecb_rate_date: "2026-03-06",
  ecb_currency_per_eur: "1.081700",
  is_fallback: false,
  fallback_reason: null,
  fetched_at: "2026-03-06T16:05:00Z",
};

export const createdPayout: Payout = {
  id: 7,
  payout_date: "2026-03-06",
  currency: "USD",
  original_amount: "1081.70",
  currency_per_eur: "1.081700",
  rate_date: "2026-03-06",
  rate_provenance: ecbProvenanceFriday,
  irs_currency_per_eur: "1.081700",
  irs_rate_date: "2026-03-06",
  irs_rate_provenance: ecbProvenanceFriday,
  client_name: null,
  notes: null,
  invoice_number: null,
  invoice_issued_on: null,
  eur_amount: "1000.00",
  irs_eur_amount: "1000.00",
  created_at: "2026-03-06T17:00:00Z",
};

/** Invoice of 2 March converted at that day's rate; IRS income at the 6 March rate. */
export const payoutWithTwoRates: Payout = {
  ...createdPayout,
  id: 8,
  original_amount: "1169.80",
  currency_per_eur: "1.169800",
  rate_date: "2026-03-02",
  rate_provenance: {
    ...ecbProvenanceFriday,
    requested_date: "2026-03-02",
    ecb_rate_date: "2026-03-02",
    ecb_currency_per_eur: "1.169800",
  },
  eur_amount: "1000.00",
  irs_currency_per_eur: "1.081700",
  irs_rate_date: "2026-03-06",
  irs_rate_provenance: ecbProvenanceFriday,
  irs_eur_amount: "1081.45",
  invoice_number: "FR 2026/11",
  invoice_issued_on: "2026-03-02",
};
