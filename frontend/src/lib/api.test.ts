import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  API_BASE,
  api,
  fmtShares,
  fmtSignedShares,
  fmtUSD,
  type Filer,
} from "./api";

describe("fmtUSD", () => {
  it("formats billions with two decimals", () => {
    expect(fmtUSD(2_500_000_000)).toBe("$2.50B");
  });

  it("formats millions with two decimals", () => {
    expect(fmtUSD(1_230_000)).toBe("$1.23M");
  });

  it("formats thousands with one decimal", () => {
    expect(fmtUSD(4_500)).toBe("$4.5K");
  });

  it("formats small amounts as whole dollars", () => {
    expect(fmtUSD(750)).toBe("$750");
  });

  it("uses the magnitude (not the sign) to pick the unit", () => {
    // abs() drives the threshold, but the value keeps its sign.
    expect(fmtUSD(-2_000_000_000)).toBe("$-2.00B");
  });

  it("handles exact boundaries", () => {
    expect(fmtUSD(1e9)).toBe("$1.00B");
    expect(fmtUSD(1e6)).toBe("$1.00M");
    expect(fmtUSD(1e3)).toBe("$1.0K");
  });
});

describe("fmtShares", () => {
  it("groups thousands with commas", () => {
    expect(fmtShares(1_234_567)).toBe("1,234,567");
  });

  it("leaves small numbers unchanged", () => {
    expect(fmtShares(42)).toBe("42");
  });
});

describe("fmtSignedShares", () => {
  it("prefixes positive values with a plus", () => {
    expect(fmtSignedShares(1_000)).toBe("+1,000");
  });

  it("keeps the native minus sign for negatives", () => {
    expect(fmtSignedShares(-2_500)).toBe("-2,500");
  });

  it("does not prefix zero", () => {
    expect(fmtSignedShares(0)).toBe("0");
  });
});

describe("api client", () => {
  const sample: Filer[] = [
    { id: 1, cik: "0001067983", name: "Berkshire", kind: "institution", latest_filing_at: null },
  ];

  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => sample,
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function calledUrl(): string {
    return fetchMock.mock.calls[0][0] as string;
  }

  it("requests filers with url-encoded query params", async () => {
    await api.filers("Bridgewater & Co", "institution");
    expect(calledUrl()).toBe(
      `${API_BASE}/filers?q=Bridgewater%20%26%20Co&kind=institution`,
    );
  });

  it("defaults filer search params to empty strings", async () => {
    await api.filers();
    expect(calledUrl()).toBe(`${API_BASE}/filers?q=&kind=`);
  });

  it("omits the period query when none is given", async () => {
    await api.filer("0001067983");
    expect(calledUrl()).toBe(`${API_BASE}/filers/0001067983`);
  });

  it("appends the period query when provided", async () => {
    await api.filer("0001067983", "2024-03-31");
    expect(calledUrl()).toBe(`${API_BASE}/filers/0001067983?period=2024-03-31`);
  });

  it("builds the changes path with an optional period", async () => {
    await api.changes("0001067983");
    expect(calledUrl()).toBe(`${API_BASE}/filers/0001067983/changes`);

    fetchMock.mockClear();
    await api.changes("0001067983", "2024-03-31");
    expect(calledUrl()).toBe(
      `${API_BASE}/filers/0001067983/changes?period=2024-03-31`,
    );
  });

  it("builds the feed path with limit and optional form filter", async () => {
    await api.feed();
    expect(calledUrl()).toBe(`${API_BASE}/filings?limit=50`);

    fetchMock.mockClear();
    await api.feed("SC 13D", 10);
    expect(calledUrl()).toBe(`${API_BASE}/filings?limit=10&form=SC%2013D`);
  });

  it("builds the filing detail path from a numeric id", async () => {
    await api.filing(5);
    expect(calledUrl()).toBe(`${API_BASE}/filings/5`);
  });

  it("builds the security detail and holders paths", async () => {
    await api.security("037833100");
    expect(calledUrl()).toBe(`${API_BASE}/securities/037833100`);

    fetchMock.mockClear();
    await api.securityHolders("037833100");
    expect(calledUrl()).toBe(`${API_BASE}/securities/037833100/holders`);
  });

  it("sends requests with no-store caching", async () => {
    await api.periods("0001067983");
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/filers/0001067983/periods`,
      { cache: "no-store" },
    );
  });

  it("parses and returns the JSON body", async () => {
    const out = await api.filers();
    expect(out).toEqual(sample);
  });

  it("throws with status text on a non-ok response", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({}),
    });
    await expect(api.filer("0000000000")).rejects.toThrow("404 Not Found");
  });
});
