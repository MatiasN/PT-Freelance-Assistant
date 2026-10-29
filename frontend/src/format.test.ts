import {
  describeProvenance,
  formatDate,
  formatEur,
  formatPercent,
  previewEurAmount,
  trimDecimal,
} from "./format";
import { ecbProvenanceFriday } from "./test/fixtures";

describe("previewEurAmount", () => {
  it("converts using the ECB convention (units per EUR)", () => {
    expect(previewEurAmount("1085", "1.085")).toBe("1000.00");
  });

  it("returns null for incomplete input", () => {
    expect(previewEurAmount("", "1.08")).toBeNull();
    expect(previewEurAmount("100", "0")).toBeNull();
  });
});

describe("formatEur", () => {
  it("uses Portuguese formatting", () => {
    expect(formatEur("1234.5")).toMatch(/1\s?234,50\s?€/);
  });
});

describe("trimDecimal", () => {
  it("drops trailing zeros from API decimals", () => {
    expect(trimDecimal("1.081700")).toBe("1.0817");
    expect(trimDecimal("1.000000")).toBe("1");
    expect(trimDecimal("162.35")).toBe("162.35");
  });

  it("leaves integers and non-numbers untouched", () => {
    expect(trimDecimal("100")).toBe("100");
    expect(trimDecimal("")).toBe("");
    expect(trimDecimal("abc")).toBe("abc");
  });
});

describe("describeProvenance", () => {
  it("describes an ECB rate, with its fallback day when there was one", () => {
    expect(describeProvenance(ecbProvenanceFriday)).toBe("ECB rate of 06/03/2026");
    expect(
      describeProvenance({
        ...ecbProvenanceFriday,
        requested_date: "2026-03-07",
        is_fallback: true,
        fallback_reason: "weekend",
      }),
    ).toBe("ECB rate of 06/03/2026 (fallback for 07/03/2026)");
  });

  it("keeps the ECB evidence next to a manual rate", () => {
    expect(describeProvenance({ ...ecbProvenanceFriday, source: "manual" })).toBe(
      "manual (ECB was 1.0817 on 06/03/2026)",
    );
    expect(
      describeProvenance({
        source: "manual",
        requested_date: "2026-03-06",
        ecb_rate_date: null,
        ecb_currency_per_eur: null,
        is_fallback: null,
        fallback_reason: null,
        fetched_at: null,
      }),
    ).toBe("manual (no ECB lookup)");
  });

  it("copes with an ECB provenance that lacks the rate day", () => {
    expect(describeProvenance({ ...ecbProvenanceFriday, ecb_rate_date: null })).toBe(
      "ECB rate of unknown day",
    );
  });

  it("is silent for payouts recorded before provenance existed", () => {
    expect(describeProvenance(null)).toBeNull();
  });
});

describe("formatPercent and formatDate", () => {
  it("formats a rate as a Portuguese percentage", () => {
    expect(formatPercent("0.25")).toMatch(/^25\s?%$/);
    expect(formatPercent("0.214")).toMatch(/^21,4\s?%$/);
  });

  it("formats ISO dates as dd/mm/yyyy regardless of the local time zone", () => {
    expect(formatDate("2026-03-06")).toBe("06/03/2026");
    expect(formatDate("2026-12-31")).toBe("31/12/2026");
  });
});
