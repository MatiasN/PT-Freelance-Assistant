import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { Payouts } from "./Payouts";
import type { Payout } from "../api";
import {
  createdPayout,
  payoutWithTwoRates,
  usdRateFriday,
  usdRateInvoiceFirst,
  usdRateSaturdayFallback,
} from "../test/fixtures";
import { type FetchHandler, mockFetch } from "../test/mockFetch";
import { setupUser } from "../test/user";

/** Backend stand-in: empty payout list, ECB rates keyed by requested date, 502 on demand. */
interface BackendOptions {
  ecbDown?: boolean;
  payouts?: Payout[];
  /** Status for POST /api/payouts (default 201). */
  createStatus?: number;
  listStatus?: number;
  deleteStatus?: number;
}

const INVOICE_FIELDS = [
  { portal_label: "Valor base (EUR)", value: "1.000,00", hint: "" },
  { portal_label: "NIF do adquirente", value: "", hint: "Foreign client: leave empty." },
];

function backend(options: BackendOptions = {}): FetchHandler {
  return ({ method, url }) => {
    if (url.pathname === "/api/payouts" && method === "GET") {
      if (options.listStatus) {
        return { status: options.listStatus, body: { detail: "database is locked" } };
      }
      return { status: 200, body: options.payouts ?? [] };
    }
    if (url.pathname === "/api/payouts" && method === "POST") {
      if (options.createStatus && options.createStatus >= 400) {
        return { status: options.createStatus, body: { detail: "EUR payouts must use 1" } };
      }
      return { status: 201, body: createdPayout };
    }
    if (/^\/api\/payouts\/\d+$/.test(url.pathname) && method === "DELETE") {
      if (options.deleteStatus && options.deleteStatus >= 400) {
        return { status: options.deleteStatus, body: { detail: "Payout not found" } };
      }
      return { status: 204 };
    }
    if (/^\/api\/payouts\/\d+\/invoice-fields$/.test(url.pathname)) {
      return { status: 200, body: INVOICE_FIELDS };
    }
    if (url.pathname === "/api/exchange-rates") {
      if (options.ecbDown) {
        return {
          status: 502,
          body: { detail: "ECB Data Portal unavailable: ECB Data Portal answered HTTP 503" },
        };
      }
      const payoutDate = url.searchParams.get("payout_date");
      const invoiceDate = url.searchParams.get("invoice_issued_on");
      if (invoiceDate && payoutDate && invoiceDate < payoutDate) {
        return { status: 200, body: { ...usdRateInvoiceFirst, payout_date: payoutDate } };
      }
      const rate = payoutDate === "2026-03-07" ? usdRateSaturdayFallback : usdRateFriday;
      return {
        status: 200,
        body: { ...rate, payout_date: payoutDate, requested_date: payoutDate },
      };
    }
    return { status: 404, body: { detail: "Not found" } };
  };
}

function rateInput(): HTMLInputElement {
  return screen.getByLabelText(/^(Exchange rate|Fatura-Recibo rate) \(USD per 1 EUR\)/);
}

function irsRateInput(): HTMLInputElement {
  return screen.getByLabelText(/^IRS rate \(USD per 1 EUR, payout date\)/);
}

function setInvoiceDate(value: string) {
  fireEvent.change(screen.getByLabelText("Invoice issued on (optional)"), { target: { value } });
}

/** The source paragraph that starts with the given bold label ("Rate:", "IRS rate (payout date):"). */
function rateLine(label: string): HTMLElement {
  const paragraph = screen.getByText(label, { selector: "strong" }).closest("p");
  if (!paragraph) {
    throw new Error(`No paragraph for ${label}`);
  }
  return paragraph;
}

function postedBody(requests: ReturnType<typeof mockFetch>) {
  return requests.find((request) => request.method === "POST")?.body as Record<string, unknown>;
}

function setPayoutDate(value: string) {
  fireEvent.change(screen.getByLabelText("Payout date"), { target: { value } });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

it("auto-fills the ECB rate for the payout date and shows the source and rate date", async () => {
  const requests = mockFetch(backend());
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-06");

  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));

  // The form first looks up today's date, then the date the user picked.
  const lookup = requests.findLast((request) => request.url.pathname === "/api/exchange-rates");
  expect(lookup?.url.searchParams.get("currency")).toBe("USD");
  expect(lookup?.url.searchParams.get("payout_date")).toBe("2026-03-06");
  expect(lookup?.url.searchParams.has("invoice_issued_on")).toBe(false);

  const source = rateLine("Rate:");
  expect(source).toHaveTextContent("auto-filled from the ECB");
  expect(source).toHaveTextContent("06/03/2026");
  expect(source).toHaveTextContent("1.0817 USD/EUR");
  expect(screen.getByRole("link", { name: "ECB euro reference rates" })).toHaveAttribute(
    "href",
    usdRateFriday.source_url,
  );
  expect(screen.getByText(/Rate day:/)).toHaveTextContent("06/03/2026 (payout date)");
  expect(screen.getByText(/Rate day:/)).toHaveTextContent("CIVA art. 8.º n.º 1 al. c)");
  expect(screen.getByText(/Rate day:/)).toHaveTextContent("CIRS art. 23.º n.º 1 al. b)");
  expect(screen.getByText(/^CIVA art\. 49\.º n\.º 1/)).toBeInTheDocument(); // legal basis
});

it("uses the invoice date when the invoice was issued before the payout", async () => {
  const requests = mockFetch(backend());
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-06");
  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));

  setInvoiceDate("2026-03-02");

  await waitFor(() => expect(rateInput()).toHaveValue(1.1698));
  const lookup = requests.findLast((request) => request.url.pathname === "/api/exchange-rates");
  expect(lookup?.url.searchParams.get("payout_date")).toBe("2026-03-06");
  expect(lookup?.url.searchParams.get("invoice_issued_on")).toBe("2026-03-02");
  const rateDay = screen.getByText(/Rate day:/);
  expect(rateDay).toHaveTextContent("02/03/2026 (invoice date)");
  expect(rateDay).toHaveTextContent("CIVA art. 8.º n.º 1 al. a)");
  expect(rateDay).toHaveTextContent("tell your accountant");
});

describe("invoice issued before the payout: two rates", () => {
  it("shows the Fatura-Recibo rate and the IRS rate with both EUR amounts", async () => {
    const user = setupUser();
    mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    setInvoiceDate("2026-03-02");
    await user.type(screen.getByLabelText("Amount (USD)"), "1169.8");

    await waitFor(() => expect(rateInput()).toHaveValue(1.1698)); // invoice day, CIVA
    expect(irsRateInput()).toHaveValue(1.0817); // payout day, CIRS

    expect(screen.getByText(/Fatura-Recibo EUR amount:/)).toHaveTextContent(/1\s?000,00/);
    expect(screen.getByText(/IRS income EUR amount:/)).toHaveTextContent(/1\s?081,45/);
    expect(rateLine("Fatura-Recibo rate:")).toHaveTextContent("02/03/2026");
    expect(rateLine("Fatura-Recibo rate:")).toHaveTextContent("1.1698 USD/EUR");
    expect(rateLine("IRS rate (payout date):")).toHaveTextContent("06/03/2026");
    expect(rateLine("IRS rate (payout date):")).toHaveTextContent("1.0817 USD/EUR");
  });

  it("submits both pairs with their ECB rate days", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    setInvoiceDate("2026-03-02");
    await waitFor(() => expect(irsRateInput()).toHaveValue(1.0817));

    await user.type(screen.getByLabelText("Amount (USD)"), "1169.8");
    await user.click(screen.getByRole("button", { name: "Add payout" }));

    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        currency_per_eur: "1.1698",
        rate_date: "2026-03-02",
        irs_currency_per_eur: "1.0817",
        irs_rate_date: "2026-03-06",
        invoice_issued_on: "2026-03-02",
      }),
    );
  });

  it("lets the IRS rate be edited on its own and drops its ECB day", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    setInvoiceDate("2026-03-02");
    await waitFor(() => expect(irsRateInput()).toHaveValue(1.0817));
    await user.type(screen.getByLabelText("Amount (USD)"), "1169.8");

    await user.clear(irsRateInput());
    await user.type(irsRateInput(), "1.09");

    expect(rateInput()).toHaveValue(1.1698); // document rate untouched
    expect(rateLine("IRS rate (payout date):")).toHaveTextContent("entered manually");
    expect(rateLine("Fatura-Recibo rate:")).toHaveTextContent("auto-filled");
    expect(screen.getByText(/Fatura-Recibo EUR amount:/)).toHaveTextContent(/1\s?000,00/);
    expect(screen.getByText(/IRS income EUR amount:/)).toHaveTextContent(/1\s?073,21/);

    await user.click(screen.getByRole("button", { name: "Use ECB rate" })); // only the IRS one
    expect(irsRateInput()).toHaveValue(1.0817);
    expect(screen.queryByRole("button", { name: "Use ECB rate" })).not.toBeInTheDocument();

    await user.clear(irsRateInput());
    await user.type(irsRateInput(), "1.09");
    await user.click(screen.getByRole("button", { name: "Add payout" }));
    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        currency_per_eur: "1.1698",
        rate_date: "2026-03-02",
        irs_currency_per_eur: "1.09",
        irs_rate_date: null,
      }),
    );
  });

  it("goes back to a single rate when the invoice date is cleared", async () => {
    mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    setInvoiceDate("2026-03-02");
    await waitFor(() => expect(irsRateInput()).toHaveValue(1.0817));

    setInvoiceDate("");

    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
    expect(screen.queryByLabelText(/^IRS rate/)).not.toBeInTheDocument();
    expect(screen.queryByText(/IRS income EUR amount:/)).not.toBeInTheDocument();
  });
});

it("sends the same pair twice when the invoice is not earlier than the payout", async () => {
  const user = setupUser();
  const requests = mockFetch(backend());
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-06");
  setInvoiceDate("2026-03-09");
  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
  expect(screen.queryByLabelText(/^IRS rate/)).not.toBeInTheDocument();

  await user.type(screen.getByLabelText("Amount (USD)"), "1085");
  await user.click(screen.getByRole("button", { name: "Add payout" }));

  await waitFor(() =>
    expect(postedBody(requests)).toMatchObject({
      currency_per_eur: "1.0817",
      rate_date: "2026-03-06",
      irs_currency_per_eur: "1.0817",
      irs_rate_date: "2026-03-06",
    }),
  );
});

it("sends unit rates for EUR payouts", async () => {
  const user = setupUser();
  const requests = mockFetch(backend());
  render(<Payouts year={2026} />);

  await user.selectOptions(screen.getByLabelText("Currency"), "EUR");
  await user.type(screen.getByLabelText("Amount (EUR)"), "250");
  await user.click(screen.getByRole("button", { name: "Add payout" }));

  await waitFor(() =>
    expect(postedBody(requests)).toMatchObject({
      currency: "EUR",
      currency_per_eur: "1",
      rate_date: null,
      irs_currency_per_eur: "1",
      irs_rate_date: null,
    }),
  );
});

describe("rate provenance", () => {
  const ecbFriday = {
    source: "ecb",
    requested_date: "2026-03-06",
    ecb_rate_date: "2026-03-06",
    ecb_currency_per_eur: "1.081700",
    is_fallback: false,
    fallback_reason: null,
    fetched_at: "2026-03-06T16:05:00Z",
  };

  it("records an ECB-sourced rate for both pairs when nothing was edited", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
    await user.type(screen.getByLabelText("Amount (USD)"), "1085");
    await user.click(screen.getByRole("button", { name: "Add payout" }));

    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        rate_provenance: ecbFriday,
        irs_rate_provenance: ecbFriday,
      }),
    );
  });

  it("records a manual rate together with what the ECB said", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-07"); // Saturday: ECB falls back to Friday
    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
    await user.clear(rateInput());
    await user.type(rateInput(), "1.08");
    await user.type(screen.getByLabelText("Amount (USD)"), "1080");
    await user.click(screen.getByRole("button", { name: "Add payout" }));

    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        currency_per_eur: "1.08",
        rate_date: null,
        rate_provenance: {
          ...ecbFriday,
          source: "manual",
          requested_date: "2026-03-07",
          is_fallback: true,
          fallback_reason: "weekend",
        },
      }),
    );
  });

  it("records a manual rate without evidence when the ECB was unavailable", async () => {
    const user = setupUser();
    const requests = mockFetch(backend({ ecbDown: true }));
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    await screen.findByRole("alert");
    await user.type(rateInput(), "1.085");
    await user.type(screen.getByLabelText("Amount (USD)"), "1085");
    await user.click(screen.getByRole("button", { name: "Add payout" }));

    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        rate_provenance: {
          source: "manual",
          requested_date: null,
          ecb_rate_date: null,
          ecb_currency_per_eur: null,
          is_fallback: null,
          fallback_reason: null,
          fetched_at: null,
        },
      }),
    );
  });

  it("records separate provenance per pair when the invoice precedes the payout", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    setInvoiceDate("2026-03-02");
    await waitFor(() => expect(irsRateInput()).toHaveValue(1.0817));
    await user.clear(irsRateInput());
    await user.type(irsRateInput(), "1.09");
    await user.type(screen.getByLabelText("Amount (USD)"), "1169.8");
    await user.click(screen.getByRole("button", { name: "Add payout" }));

    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        rate_provenance: {
          source: "ecb",
          requested_date: "2026-03-02",
          ecb_rate_date: "2026-03-02",
          ecb_currency_per_eur: "1.169800",
        },
        irs_rate_provenance: { ...ecbFriday, source: "manual" },
      }),
    );
  });

  it("sends no provenance for EUR payouts", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    await user.selectOptions(screen.getByLabelText("Currency"), "EUR");
    await user.type(screen.getByLabelText("Amount (EUR)"), "250");
    await user.click(screen.getByRole("button", { name: "Add payout" }));

    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        rate_provenance: null,
        irs_rate_provenance: null,
      }),
    );
  });
});

describe("payout table", () => {
  it("shows where each stored rate came from, and nothing for older rows", async () => {
    mockFetch(
      backend({
        payouts: [
          createdPayout,
          {
            ...createdPayout,
            id: 9,
            invoice_number: "MANUAL",
            currency_per_eur: "1.080000",
            rate_date: null,
            rate_provenance: { ...createdPayout.rate_provenance!, source: "manual" },
          },
          { ...createdPayout, id: 10, invoice_number: "OLD", rate_provenance: null, irs_rate_provenance: null },
        ],
      }),
    );
    render(<Payouts year={2026} />);

    const rows = await screen.findAllByRole("row");
    expect(rows.find((row) => row.textContent?.includes("Not issued"))).toHaveTextContent(
      "Rate: ECB rate of 06/03/2026",
    );
    expect(rows.find((row) => row.textContent?.includes("MANUAL"))).toHaveTextContent(
      "Rate: manual (ECB was 1.0817 on 06/03/2026)",
    );
    expect(rows.find((row) => row.textContent?.includes("OLD"))).not.toHaveTextContent("Rate:");
  });


  it("shows the IRS amount next to the Fatura-Recibo amount when they differ", async () => {
    mockFetch(backend({ payouts: [payoutWithTwoRates, createdPayout] }));
    render(<Payouts year={2026} />);

    const rows = await screen.findAllByRole("row");
    const twoRates = rows.find((row) => row.textContent?.includes("FR 2026/11"));
    expect(twoRates).toHaveTextContent(/1\s?000,00\s?€/);
    expect(twoRates).toHaveTextContent("Fatura-Recibo (rate of 02/03/2026)");
    expect(twoRates).toHaveTextContent(/IRS income: 1\s?081,45\s?€ \(rate of 06\/03\/2026\)/);

    const single = rows.find((row) => row.textContent?.includes("Not issued"));
    expect(single).toHaveTextContent(/1\s?000,00\s?€/);
    expect(single).not.toHaveTextContent("IRS income");
  });

  it("shows the manual IRS rate when no ECB day is stored", async () => {
    mockFetch(
      backend({
        payouts: [{ ...payoutWithTwoRates, irs_rate_date: null, irs_currency_per_eur: "1.090000" }],
      }),
    );
    render(<Payouts year={2026} />);

    const row = (await screen.findAllByRole("row"))[1];
    expect(row).toHaveTextContent(/IRS income: 1\s?081,45\s?€ \(rate 1\.09\)/);
  });
});

it("submits the invoice fields with the payout", async () => {
  const user = setupUser();
  const requests = mockFetch(backend());
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-06");
  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));

  await user.type(screen.getByLabelText("Invoice number (optional)"), "FR 2026/12");
  fireEvent.change(screen.getByLabelText("Invoice issued on (optional)"), {
    target: { value: "2026-03-09" },
  });
  await user.type(screen.getByLabelText("Amount (USD)"), "1085");
  await user.click(screen.getByRole("button", { name: "Add payout" }));

  await waitFor(() => {
    const created = requests.find((request) => request.method === "POST");
    expect(created?.body).toMatchObject({
      invoice_number: "FR 2026/12",
      invoice_issued_on: "2026-03-09",
      currency_per_eur: "1.0817",
    });
  });
});

it("explains a fallback to the previous business day", async () => {
  mockFetch(backend());
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-07");

  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));

  expect(screen.getByText(/does not publish reference rates on weekends/)).toBeInTheDocument();
  expect(rateLine("Rate:")).toHaveTextContent("06/03/2026");
});

it("keeps a manually edited rate and can return to the ECB rate", async () => {
  const user = setupUser();
  mockFetch(backend());
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-06");
  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));

  await user.clear(rateInput());
  await user.type(rateInput(), "1.1");

  expect(rateInput()).toHaveValue(1.1);
  expect(rateLine("Rate:")).toHaveTextContent("entered manually");
  expect(rateLine("Rate:")).toHaveTextContent("1.0817 USD/EUR");

  await user.click(screen.getByRole("button", { name: "Use ECB rate" }));

  expect(rateInput()).toHaveValue(1.0817);
  expect(screen.queryByRole("button", { name: "Use ECB rate" })).not.toBeInTheDocument();
});

it("re-applies the ECB rate when the payout date changes after a manual edit", async () => {
  const user = setupUser();
  mockFetch(backend());
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-06");
  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
  await user.clear(rateInput());
  await user.type(rateInput(), "1.2");

  setPayoutDate("2026-03-07");

  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
  expect(rateLine("Rate:")).toHaveTextContent("auto-filled from the ECB");
});

it("leaves the rate editable and reports the error when the ECB is unavailable", async () => {
  const user = setupUser();
  mockFetch(backend({ ecbDown: true }));
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-06");

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("ECB Data Portal unavailable");
  expect(rateInput()).toHaveValue(null);

  await user.type(rateInput(), "1.085");
  await user.type(screen.getByLabelText("Amount (USD)"), "1085");

  expect(screen.getByText(/EUR amount:/)).toHaveTextContent(/1\s?000,00/);
});

it("submits the effective rate with the payout", async () => {
  const user = setupUser();
  const requests = mockFetch(backend());
  render(<Payouts year={2026} />);
  setPayoutDate("2026-03-06");
  await waitFor(() => expect(rateInput()).toHaveValue(1.0817));

  await user.type(screen.getByLabelText("Amount (USD)"), "1085");
  await user.click(screen.getByRole("button", { name: "Add payout" }));

  await waitFor(() => {
    const created = requests.find((request) => request.method === "POST");
    expect(created?.body).toMatchObject({
      payout_date: "2026-03-06",
      currency: "USD",
      original_amount: "1085",
      currency_per_eur: "1.0817",
    });
  });
});

it("does not look up a rate for EUR payouts", async () => {
  const user = setupUser();
  const requests = mockFetch(backend());
  render(<Payouts year={2026} />);

  await user.selectOptions(screen.getByLabelText("Currency"), "EUR");
  await user.type(screen.getByLabelText("Amount (EUR)"), "250");

  expect(screen.queryByLabelText(/per 1 EUR/)).not.toBeInTheDocument();
  expect(screen.getByText(/EUR amount:/)).toHaveTextContent(/250,00/);
  await waitFor(() => expect(screen.getByText(/No payouts recorded/)).toBeInTheDocument());
  const lookups = requests.filter((request) => request.url.pathname === "/api/exchange-rates");
  expect(lookups.every((request) => request.url.searchParams.get("currency") === "USD")).toBe(
    true,
  );
});

describe("invoice helper", () => {
  it("opens the Portal das Finanças fields for the created payout", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
    await user.type(screen.getByLabelText("Amount (USD)"), "1085");

    await user.click(screen.getByRole("button", { name: "Add payout" }));

    const helper = await screen.findByRole("region", {
      name: "Portal das Finanças — Fatura-Recibo",
    });
    expect(await within(helper).findByText("Valor base (EUR)")).toBeInTheDocument();
    expect(helper).toHaveTextContent("1.000,00");
    expect(helper).toHaveTextContent("Foreign client: leave empty.");
    expect(
      requests.some((request) => request.url.pathname === "/api/payouts/7/invoice-fields"),
    ).toBe(true);
    // the form was reset for the next payout
    expect(screen.getByLabelText("Amount (USD)")).toHaveValue(null);
  });

  it("opens for a listed payout and marks its row as selected", async () => {
    const user = setupUser();
    mockFetch(backend({ payouts: [createdPayout, payoutWithTwoRates] }));
    render(<Payouts year={2026} />);
    const rows = await screen.findAllByRole("row");
    const row = rows.find((candidate) => candidate.textContent?.includes("FR 2026/11"))!;

    await user.click(within(row).getByRole("button", { name: "Invoice text" }));

    expect(row).toHaveAttribute("aria-selected", "true");
    const helper = await screen.findByRole("region", {
      name: "Portal das Finanças — Fatura-Recibo",
    });
    expect(await within(helper).findByText("Valor base (EUR)")).toBeInTheDocument();
  });

  it("shows the API error inside the helper", async () => {
    const user = setupUser();
    mockFetch((request) =>
      request.url.pathname.endsWith("/invoice-fields")
        ? { status: 404, body: { detail: "Payout not found" } }
        : backend({ payouts: [createdPayout] })(request),
    );
    render(<Payouts year={2026} />);
    await user.click(await screen.findByRole("button", { name: "Invoice text" }));

    const helper = await screen.findByRole("region", {
      name: "Portal das Finanças — Fatura-Recibo",
    });
    expect(await within(helper).findByRole("alert")).toHaveTextContent("Payout not found");
  });
});

describe("deleting a payout", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("asks for confirmation and does nothing when declined", async () => {
    const user = setupUser();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const requests = mockFetch(backend({ payouts: [createdPayout] }));
    render(<Payouts year={2026} />);

    await user.click(await screen.findByRole("button", { name: "Delete" }));

    expect(window.confirm).toHaveBeenCalledWith("Delete this payout?");
    expect(requests.some((request) => request.method === "DELETE")).toBe(false);
  });

  it("deletes, closes the helper of that payout and reloads the list", async () => {
    const user = setupUser();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let deleted = false;
    const requests = mockFetch((request) => {
      if (request.method === "DELETE") {
        deleted = true;
      }
      return backend({ payouts: deleted ? [] : [createdPayout] })(request);
    });
    render(<Payouts year={2026} />);
    await user.click(await screen.findByRole("button", { name: "Invoice text" }));
    await screen.findByRole("region", { name: "Portal das Finanças — Fatura-Recibo" });

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(screen.getByText(/No payouts recorded/)).toBeInTheDocument());
    expect(
      screen.queryByRole("region", { name: "Portal das Finanças — Fatura-Recibo" }),
    ).not.toBeInTheDocument();
    const request = requests.find((candidate) => candidate.method === "DELETE");
    expect(request?.url.pathname).toBe("/api/payouts/7");
  });

  it("keeps another payout's helper open", async () => {
    const user = setupUser();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockFetch(backend({ payouts: [createdPayout, payoutWithTwoRates] }));
    render(<Payouts year={2026} />);
    const rows = await screen.findAllByRole("row");
    const first = rows.find((row) => row.textContent?.includes("Not issued"))!;
    const second = rows.find((row) => row.textContent?.includes("FR 2026/11"))!;
    await user.click(within(second).getByRole("button", { name: "Invoice text" }));

    await user.click(within(first).getByRole("button", { name: "Delete" }));

    expect(
      await screen.findByRole("region", { name: "Portal das Finanças — Fatura-Recibo" }),
    ).toBeInTheDocument();
  });

  it("reports a failed delete", async () => {
    const user = setupUser();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockFetch(backend({ payouts: [createdPayout], deleteStatus: 404 }));
    render(<Payouts year={2026} />);

    await user.click(await screen.findByRole("button", { name: "Delete" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Payout not found");
  });
});

describe("form errors and optional fields", () => {
  it("shows the API error when saving fails and keeps the form", async () => {
    const user = setupUser();
    mockFetch(backend({ createStatus: 422 }));
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
    await user.type(screen.getByLabelText("Amount (USD)"), "1085");

    await user.click(screen.getByRole("button", { name: "Add payout" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("EUR payouts must use 1");
    expect(screen.getByLabelText("Amount (USD)")).toHaveValue(1085);
    expect(screen.getByRole("button", { name: "Add payout" })).toBeEnabled();
  });

  it("shows the list error", async () => {
    mockFetch(backend({ listStatus: 500 }));
    render(<Payouts year={2026} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("database is locked");
  });

  it("sends client, notes and invoice number, and null when cleared", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
    await user.type(screen.getByLabelText("Client (optional)"), "ACME Inc.");
    await user.type(screen.getByLabelText("Notes"), "March retainer");
    await user.type(screen.getByLabelText("Invoice number (optional)"), "FR 2026/12");
    await user.clear(screen.getByLabelText("Notes"));
    await user.type(screen.getByLabelText("Amount (USD)"), "1085");

    await user.click(screen.getByRole("button", { name: "Add payout" }));

    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        client_name: "ACME Inc.",
        notes: null,
        invoice_number: "FR 2026/12",
      }),
    );
  });

  it("shows no rate source while the payout date is incomplete", async () => {
    mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));

    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    setPayoutDate("");

    await waitFor(() => expect(rateInput()).toHaveValue(null));
    expect(screen.queryByText(/Source:/)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Payout date")).toHaveValue("");
    expect(consoleError).not.toHaveBeenCalled(); // stays a controlled input
    consoleError.mockRestore();
  });

  it("shows the IRS line with a manual rate and no provenance", async () => {
    mockFetch(
      backend({
        payouts: [
          {
            ...payoutWithTwoRates,
            rate_date: null,
            rate_provenance: null,
            irs_rate_date: null,
            irs_rate_provenance: null,
            irs_currency_per_eur: "1.090000",
          },
        ],
      }),
    );
    render(<Payouts year={2026} />);

    const row = (await screen.findAllByRole("row"))[1];
    expect(row).toHaveTextContent(/Fatura-Recibo\. IRS income: 1\s?081,45\s?€ \(rate 1\.09\)FR/);
    expect(row).not.toHaveTextContent("Rate:");
  });
});

describe("unexpected failures", () => {
  /** fetch itself blowing up with something that is not an Error. */
  function backendThatThrows(on: (request: { method: string; url: URL }) => boolean) {
    return (request: Parameters<FetchHandler>[0]) => {
      if (on(request)) {
        throw "socket hang up";
      }
      return backend({ payouts: [createdPayout] })(request);
    };
  }

  it("falls back to a generic message when saving throws a non-Error", async () => {
    const user = setupUser();
    mockFetch(backendThatThrows(({ method }) => method === "POST"));
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
    await user.type(screen.getByLabelText("Amount (USD)"), "1085");

    await user.click(screen.getByRole("button", { name: "Add payout" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save payout");
  });

  it("falls back to a generic message when deleting throws a non-Error", async () => {
    const user = setupUser();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockFetch(backendThatThrows(({ method }) => method === "DELETE"));
    render(<Payouts year={2026} />);

    await user.click(await screen.findByRole("button", { name: "Delete" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not delete payout");
    vi.restoreAllMocks();
  });

  it("shows 'Unexpected error' when loading the list throws a non-Error", async () => {
    mockFetch(
      backendThatThrows(({ method, url }) => method === "GET" && url.pathname === "/api/payouts"),
    );
    render(<Payouts year={2026} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unexpected error");
  });

  it("records manual provenance without evidence for both pairs when the ECB is down", async () => {
    const user = setupUser();
    const requests = mockFetch(backend({ ecbDown: true }));
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    setInvoiceDate("2026-03-02");
    await screen.findByRole("alert");
    await user.type(rateInput(), "1.17");
    await user.type(irsRateInput(), "1.08");
    await user.type(screen.getByLabelText("Amount (USD)"), "1170");

    await user.click(screen.getByRole("button", { name: "Add payout" }));

    const noEvidence = {
      source: "manual",
      requested_date: null,
      ecb_rate_date: null,
      ecb_currency_per_eur: null,
      is_fallback: null,
      fallback_reason: null,
      fetched_at: null,
    };
    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({
        currency_per_eur: "1.17",
        rate_date: null,
        rate_provenance: noEvidence,
        irs_currency_per_eur: "1.08",
        irs_rate_date: null,
        irs_rate_provenance: noEvidence,
      }),
    );
  });

  it("sends null for optional text fields that were typed and then cleared", async () => {
    const user = setupUser();
    const requests = mockFetch(backend());
    render(<Payouts year={2026} />);
    setPayoutDate("2026-03-06");
    await waitFor(() => expect(rateInput()).toHaveValue(1.0817));
    for (const label of ["Client (optional)", "Invoice number (optional)"]) {
      await user.type(screen.getByLabelText(label), "x");
      await user.clear(screen.getByLabelText(label));
    }
    await user.type(screen.getByLabelText("Amount (USD)"), "1085");

    await user.click(screen.getByRole("button", { name: "Add payout" }));

    await waitFor(() =>
      expect(postedBody(requests)).toMatchObject({ client_name: null, invoice_number: null }),
    );
  });
});
