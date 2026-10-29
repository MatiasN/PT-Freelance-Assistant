import { ApiError, api, irsRateDiffers } from "./api";
import { createdPayout, payoutWithTwoRates, usdRateFriday } from "./test/fixtures";
import { type RecordedRequest, mockFetch } from "./test/mockFetch";

afterEach(() => {
  vi.unstubAllGlobals();
});

function only(requests: RecordedRequest[]): RecordedRequest {
  expect(requests).toHaveLength(1);
  return requests[0]!;
}

describe("api.exchangeRate", () => {
  it("requests the rate for a currency and payout date", async () => {
    const requests = mockFetch(() => ({ status: 200, body: usdRateFriday }));

    const rate = await api.exchangeRate("USD", "2026-03-06", null);

    expect(rate).toEqual(usdRateFriday);
    const request = only(requests);
    expect(request.method).toBe("GET");
    expect(request.url.pathname).toBe("/api/exchange-rates");
    expect(request.url.searchParams.get("currency")).toBe("USD");
    expect(request.url.searchParams.get("payout_date")).toBe("2026-03-06");
    expect(request.url.searchParams.has("invoice_issued_on")).toBe(false);
  });

  it("sends the invoice date when the invoice is already issued", async () => {
    const requests = mockFetch(() => ({ status: 200, body: usdRateFriday }));

    await api.exchangeRate("USD", "2026-03-06", "2026-03-02");

    expect(only(requests).url.searchParams.get("invoice_issued_on")).toBe("2026-03-02");
  });

  it("surfaces the 502 detail when the ECB is unavailable", async () => {
    mockFetch(() => ({
      status: 502,
      body: { detail: "ECB Data Portal unavailable: ECB Data Portal answered HTTP 503" },
    }));

    const error = await api
      .exchangeRate("USD", "2026-03-06", null)
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(502);
    expect((error as ApiError).message).toContain("ECB Data Portal unavailable");
  });
});

describe("payout endpoints", () => {
  it("lists payouts of a year", async () => {
    const requests = mockFetch(() => ({ status: 200, body: [createdPayout] }));

    expect(await api.listPayouts(2026)).toEqual([createdPayout]);
    const request = only(requests);
    expect(request.method).toBe("GET");
    expect(request.url.pathname).toBe("/api/payouts");
    expect(request.url.searchParams.get("year")).toBe("2026");
  });

  it("creates a payout with a JSON body", async () => {
    const requests = mockFetch(() => ({ status: 201, body: createdPayout }));
    const input = { ...createdPayout, currency_per_eur: "1.0817", rate_date: null };

    expect(await api.createPayout(input)).toEqual(createdPayout);
    const request = only(requests);
    expect(request.method).toBe("POST");
    expect(request.url.pathname).toBe("/api/payouts");
    expect(request.body).toEqual(input);
    expect(request.headers.get("Content-Type")).toBe("application/json");
  });

  it("updates a payout by id", async () => {
    const requests = mockFetch(() => ({ status: 200, body: createdPayout }));

    await api.updatePayout(7, createdPayout);

    const request = only(requests);
    expect(request.method).toBe("PUT");
    expect(request.url.pathname).toBe("/api/payouts/7");
    expect(request.body).toMatchObject({ payout_date: "2026-03-06" });
  });

  it("deletes a payout and resolves with nothing on 204", async () => {
    const requests = mockFetch(() => ({ status: 204 }));

    await expect(api.deletePayout(7)).resolves.toBeUndefined();
    const request = only(requests);
    expect(request.method).toBe("DELETE");
    expect(request.url.pathname).toBe("/api/payouts/7");
  });

  it("fetches the Portal das Finanças fields of a payout", async () => {
    const fields = [{ portal_label: "Valor base (EUR)", value: "1.000,00", hint: "" }];
    const requests = mockFetch(() => ({ status: 200, body: fields }));

    expect(await api.invoiceFields(7)).toEqual(fields);
    expect(only(requests).url.pathname).toBe("/api/payouts/7/invoice-fields");
  });
});

describe("estimate, parameter and calendar endpoints", () => {
  it.each([
    ["fiscalYears", () => api.fiscalYears(), "GET", "/api/fiscal-parameters/years", {}],
    ["dashboard", () => api.dashboard(2026), "GET", "/api/dashboard", { year: "2026" }],
    [
      "irsEstimate",
      () => api.irsEstimate(2026, "10000", "42000"),
      "GET",
      "/api/estimates/irs",
      { year: "2026", freelance_gross: "10000", employment_gross: "42000" },
    ],
    [
      "socialSecurityEstimate",
      () => api.socialSecurityEstimate(2026, 2, "3000"),
      "GET",
      "/api/estimates/social-security",
      { year: "2026", quarter: "2", services_income: "3000" },
    ],
    ["deadlines", () => api.deadlines(2026), "GET", "/api/calendar/deadlines", { year: "2026" }],
    ["calendarStatus", () => api.calendarStatus(), "GET", "/api/calendar/status", {}],
    ["syncCalendar", () => api.syncCalendar(2026), "POST", "/api/calendar/sync", { year: "2026" }],
  ])("%s hits %s %s", async (_name, call, method, path, params) => {
    const payload = { ok: true };
    const requests = mockFetch(() => ({ status: 200, body: payload }));

    expect(await call()).toEqual(payload);
    const request = only(requests);
    expect(request.method).toBe(method);
    expect(request.url.pathname).toBe(path);
    expect(Object.fromEntries(request.url.searchParams)).toEqual(params);
  });
});

describe("error mapping", () => {
  it("uses a string detail", async () => {
    mockFetch(() => ({ status: 404, body: { detail: "Payout not found" } }));

    await expect(api.invoiceFields(999)).rejects.toMatchObject({
      status: 404,
      message: "Payout not found",
    });
  });

  it("joins FastAPI validation issues, with a placeholder for issues without a message", async () => {
    mockFetch(() => ({
      status: 422,
      body: { detail: [{ msg: "Input should be greater than 0" }, { loc: ["body", "x"] }] },
    }));

    await expect(api.createPayout(createdPayout)).rejects.toMatchObject({
      message: "Input should be greater than 0; Invalid value",
    });
  });

  it("falls back to the status text when the detail has an unknown shape", async () => {
    mockFetch(() => ({ status: 500, statusText: "Internal Server Error", body: { detail: 42 } }));

    await expect(api.fiscalYears()).rejects.toMatchObject({ message: "Internal Server Error" });
  });

  it("falls back to the status text when the body has no detail", async () => {
    mockFetch(() => ({ status: 503, statusText: "Service Unavailable", body: "busy" }));

    await expect(api.fiscalYears()).rejects.toMatchObject({ message: "Service Unavailable" });
  });

  it("falls back to the status code when the body is not JSON and there is no status text", async () => {
    mockFetch(() => ({ status: 502, body: new Error("Unexpected token <") }));

    await expect(api.fiscalYears()).rejects.toMatchObject({
      status: 502,
      message: "Request failed with status 502",
    });
  });

  it("is an Error with the HTTP status attached", () => {
    const error = new ApiError(418, "teapot");

    expect(error).toBeInstanceOf(Error);
    expect(error.status).toBe(418);
    expect(error.message).toBe("teapot");
  });
});

describe("irsRateDiffers", () => {
  it("is false when both pairs are identical", () => {
    expect(irsRateDiffers(createdPayout)).toBe(false);
  });

  it("is true when the amount, the rate or the rate day differ", () => {
    expect(irsRateDiffers(payoutWithTwoRates)).toBe(true);
    expect(irsRateDiffers({ ...createdPayout, irs_currency_per_eur: "1.090000" })).toBe(true);
    expect(irsRateDiffers({ ...createdPayout, irs_rate_date: null })).toBe(true);
  });
});
