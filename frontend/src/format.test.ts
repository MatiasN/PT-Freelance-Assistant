import { formatEur, previewEurAmount } from "./format";

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
