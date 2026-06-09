// Typed client for the SecHub API. Mirrors backend/app/schemas.py.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface Filer {
  id: number;
  cik: string;
  name: string;
  kind: string;
  latest_filing_at: string | null;
}

export interface Security {
  id: number;
  cusip: string | null;
  name: string;
  ticker: string | null;
}

export interface Holding {
  security: Security;
  value: number;
  shares: number;
  sh_prn_type: string;
  put_call: string | null;
  investment_discretion: string | null;
  voting_sole: number;
  voting_shared: number;
  voting_none: number;
  pct_of_portfolio: number | null;
}

export interface FilerDetail {
  filer: Filer;
  period_of_report: string | null;
  total_value: number;
  position_count: number;
  holdings: Holding[];
}

export interface HoldingChange {
  security: Security;
  action: "NEW" | "ADD" | "TRIM" | "EXIT" | "HOLD";
  shares_delta: number;
  value_delta: number;
  pct_change: number | null;
}

export interface Changes {
  filer: Filer;
  period: string | null;
  prev_period: string | null;
  changes: HoldingChange[];
}

export interface Filing {
  id: number;
  accession_no: string;
  form_type: string;
  filed_at: string;
  period_of_report: string | null;
  source_url: string;
  filer: Filer;
}

export interface Period {
  period: string;
  total_value: number;
  position_count: number;
}

export interface FundHolding {
  security: Security;
  value: number;
  balance: number | null;
  pct_of_net_assets: number | null;
}

export interface Stake {
  filer: Filer;
  security: Security;
  form_type: string;
  percent_of_class: number | null;
  shares: number | null;
  event_date: string | null;
  is_activist: boolean;
}

export interface InsiderTxn {
  security: Security;
  insider_name: string;
  insider_title: string | null;
  is_director: boolean;
  is_officer: boolean;
  is_ten_pct_owner: boolean;
  txn_date: string | null;
  txn_code: string | null;
  is_derivative: boolean;
  security_title: string | null;
  shares: number | null;
  price: number | null;
  acquired_disposed: string | null;
  shares_owned_after: number | null;
}

export interface Holder {
  filer: Filer;
  shares: number;
  value: number;
  period_of_report: string | null;
}

export interface IssuerActivity {
  securities: Security[];
  insider_txns: InsiderTxn[];
  stakes_in: Stake[];
  top_holders: Holder[];
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  filers: (q = "", kind = "") =>
    get<Filer[]>(`/filers?q=${encodeURIComponent(q)}&kind=${kind}`),
  filer: (cik: string, period?: string) =>
    get<FilerDetail>(`/filers/${cik}${period ? `?period=${period}` : ""}`),
  periods: (cik: string) => get<Period[]>(`/filers/${cik}/periods`),
  changes: (cik: string, period?: string) =>
    get<Changes>(`/filers/${cik}/changes${period ? `?period=${period}` : ""}`),
  fundHoldings: (cik: string, period?: string) =>
    get<FundHolding[]>(`/filers/${cik}/fund-holdings${period ? `?period=${period}` : ""}`),
  stakesHeld: (cik: string) => get<Stake[]>(`/filers/${cik}/stakes-held`),
  issuerActivity: (cik: string) => get<IssuerActivity>(`/filers/${cik}/issuer-activity`),
  feed: (form = "", limit = 50) =>
    get<Filing[]>(`/filings?limit=${limit}${form ? `&form=${encodeURIComponent(form)}` : ""}`),
  filing: (id: number) => get<Filing>(`/filings/${id}`),
  security: (cusip: string) => get<Security>(`/securities/${cusip}`),
  securityHolders: (cusip: string) => get<Holder[]>(`/securities/${cusip}/holders`),
};

// --- formatting helpers ---

export function fmtUSD(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

export function fmtShares(n: number): string {
  return n.toLocaleString("en-US");
}

export function fmtSignedShares(n: number): string {
  const s = n.toLocaleString("en-US");
  return n > 0 ? `+${s}` : s;
}
