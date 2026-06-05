import Link from "next/link";
import { API_BASE, fmtUSD, fmtShares, Filer } from "@/lib/api";

interface Holder {
  filer: Filer;
  shares: number;
  value: number;
  period_of_report: string | null;
}

export default async function SecurityPage({ params }: { params: { cusip: string } }) {
  let holders: Holder[] = [];
  let err: string | null = null;
  try {
    const res = await fetch(`${API_BASE}/securities/${params.cusip}/holders`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`${res.status}`);
    holders = await res.json();
  } catch (e) {
    err = String(e);
  }

  return (
    <div className="space-y-4">
      <Link href="/" className="text-accent text-sm">
        ← back
      </Link>
      <h1 className="text-2xl font-bold">
        Holders of <span className="font-mono text-accent">{params.cusip}</span>
      </h1>

      {err && <p className="text-muted text-sm">No holders found for this CUSIP yet.</p>}

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
