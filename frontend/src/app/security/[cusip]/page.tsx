import Link from "next/link";
import { api, fmtUSD, fmtShares, Holder, Security } from "@/lib/api";

export default async function SecurityPage({ params }: { params: { cusip: string } }) {
  // Independent requests — fetch them together rather than in series.
  const [security, holders]: [Security | null, Holder[]] = await Promise.all([
    api.security(params.cusip).catch(() => null),
    api.securityHolders(params.cusip).catch(() => []),
  ]);

  return (
    <div className="space-y-4">
      <Link href="/" className="text-accent text-sm">
        ← back
      </Link>
      <div className="flex flex-wrap items-baseline gap-3">
        <h1 className="text-2xl font-bold">
          {security ? security.name : "Holders"}
        </h1>
        {security?.ticker && (
          <span className="pill bg-edge text-muted font-mono">{security.ticker}</span>
        )}
        <span className="font-mono text-sm text-accent">{params.cusip}</span>
      </div>

      {holders.length === 0 && (
        <p className="text-muted text-sm">No holders found for this CUSIP yet.</p>
      )}

      {holders.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Institution</th>
                <th className="th text-right">Shares</th>
                <th className="th text-right">Value</th>
                <th className="th text-right">As of</th>
              </tr>
            </thead>
            <tbody>
              {holders.map((h) => (
                <tr key={h.filer.id}>
                  <td className="td">
                    <Link href={`/filer/${h.filer.cik}`} className="hover:text-accent">
                      {h.filer.name}
                    </Link>
                  </td>
                  <td className="td text-right">{fmtShares(h.shares)}</td>
                  <td className="td text-right">{fmtUSD(h.value)}</td>
                  <td className="td text-right text-muted">{h.period_of_report ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
