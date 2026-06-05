import Link from "next/link";
import { api, fmtUSD, fmtShares, fmtSignedShares, FilerDetail, Changes } from "@/lib/api";
import { ActionPill } from "@/components/ActionPill";

export default async function FilerPage({ params }: { params: { cik: string } }) {
  let detail: FilerDetail | null = null;
  let changes: Changes | null = null;
  let err: string | null = null;
  try {
    [detail, changes] = await Promise.all([
      api.filer(params.cik),
      api.changes(params.cik).catch(() => null),
    ]);
  } catch (e) {
    err = String(e);
  }

  if (err || !detail) {
    return (
      <div className="card">
        <Link href="/" className="text-accent text-sm">
          ← back
        </Link>
        <p className="mt-3 text-neg">Could not load filer {params.cik}: {err}</p>
        <p className="text-muted text-sm mt-2">
          It may not be ingested yet. Try{" "}
          <code className="text-accent">POST /filings/ingest/{params.cik}</code>.
        </p>
      </div>
    );
  }

  const { filer, holdings, total_value, position_count, period_of_report } = detail;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-accent text-sm">
          ← back
        </Link>
        <div className="flex flex-wrap items-baseline gap-3 mt-2">
          <h1 className="text-2xl font-bold">{filer.name}</h1>
          <span className="pill bg-edge text-muted">{filer.kind}</span>
          <span className="text-xs text-muted">CIK {filer.cik}</span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Portfolio value" value={fmtUSD(total_value)} />
        <Stat label="Positions" value={String(position_count)} />
        <Stat label="As of" value={period_of_report ?? "—"} />
      </div>

      {changes && changes.changes.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-1">
            Changes this quarter
            <span className="text-muted text-xs font-normal ml-2">
              {changes.prev_period} → {changes.period}
            </span>
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Move</th>
                  <th className="th">Security</th>
                  <th className="th text-right">Δ Shares</th>
                  <th className="th text-right">Δ Value</th>
                  <th className="th text-right">Δ %</th>
                </tr>
              </thead>
              <tbody>
                {changes.changes.slice(0, 40).map((c, i) => (
                  <tr key={i}>
                    <td className="td"><ActionPill action={c.action} /></td>
                    <td className="td">{c.security.name}</td>
                    <td className={`td text-right ${c.shares_delta >= 0 ? "text-pos" : "text-neg"}`}>
                      {fmtSignedShares(c.shares_delta)}
                    </td>
                    <td className={`td text-right ${c.value_delta >= 0 ? "text-pos" : "text-neg"}`}>
                      {fmtUSD(c.value_delta)}
                    </td>
                    <td className="td text-right text-muted">
                      {c.pct_change == null ? "—" : `${c.pct_change.toFixed(1)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card">
        <h2 className="font-semibold mb-1">Portfolio</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Security</th>
                <th className="th text-right">Shares</th>
                <th className="th text-right">Value</th>
                <th className="th text-right">% Port.</th>
                <th className="th">Type</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h, i) => (
                <tr key={i}>
                  <td className="td">
                    {h.security.cusip ? (
                      <Link
                        href={`/security/${h.security.cusip}`}
                        className="hover:text-accent"
                      >
                        {h.security.name}
                      </Link>
                    ) : (
                      h.security.name
                    )}
                  </td>
                  <td className="td text-right">{fmtShares(h.shares)}</td>
                  <td className="td text-right">{fmtUSD(h.value)}</td>
                  <td className="td text-right text-muted">
                    {h.pct_of_portfolio?.toFixed(2) ?? "—"}%
                  </td>
                  <td className="td">
                    {h.put_call ? (
                      <span className="pill bg-amber-500/15 text-amber-400">{h.put_call}</span>
                    ) : (
                      <span className="text-muted text-xs">{h.sh_prn_type}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <div className="text-xs text-muted uppercase tracking-wide">{label}</div>
      <div className="text-xl font-semibold mt-1">{value}</div>
    </div>
  );
}
