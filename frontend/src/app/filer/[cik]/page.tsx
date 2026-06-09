import Link from "next/link";
import {
  api,
  fmtUSD,
  fmtShares,
  fmtSignedShares,
  FilerDetail,
  Changes,
  Period,
  FundHolding,
  Stake,
  IssuerActivity,
  Security,
} from "@/lib/api";
import { ActionPill, FormPill, RolePill } from "@/components/ActionPill";

export default async function FilerPage({
  params,
  searchParams,
}: {
  params: { cik: string };
  searchParams: { period?: string };
}) {
  const { cik } = params;
  const period = searchParams.period;

  let detail: FilerDetail | null = null;
  let err: string | null = null;
  try {
    detail = await api.filer(cik, period);
  } catch (e) {
    err = String(e);
  }

  if (err || !detail) {
    return (
      <div className="card">
        <Link href="/" className="text-accent text-sm">
          ← back
        </Link>
        <p className="mt-3 text-neg">Could not load entity {cik}: {err}</p>
        <p className="text-muted text-sm mt-2">
          It may not be ingested yet. Try{" "}
          <code className="text-accent">POST /filings/ingest/{cik}</code> or run the
          historical backfill.
        </p>
      </div>
    );
  }

  // The investor side and the company side load independently; any one being
  // empty just hides its section rather than failing the page.
  const [periods, changes, funds, stakesHeld, issuer]: [
    Period[],
    Changes | null,
    FundHolding[],
    Stake[],
    IssuerActivity | null
  ] = await Promise.all([
    api.periods(cik).catch(() => []),
    api.changes(cik, period).catch(() => null),
    api.fundHoldings(cik, period).catch(() => []),
    api.stakesHeld(cik).catch(() => []),
    api.issuerActivity(cik).catch(() => null),
  ]);

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

      {periods.length > 0 && (
        <PeriodSelector cik={cik} periods={periods} active={period_of_report} />
      )}

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

      {holdings.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-1">Portfolio (13F)</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Security</th>
                  <th className="th text-right">Shares</th>
                  <th className="th text-right">Value</th>
                  <th className="th text-right">% Port.</th>
                  <th className="th" title="Sole / Shared / None voting authority">
                    Voting (S/Sh/N)
                  </th>
                  <th className="th">Disc.</th>
                  <th className="th">Type</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((h, i) => (
                  <tr key={i}>
                    <td className="td">
                      {h.security.cusip ? (
                        <Link href={`/security/${h.security.cusip}`} className="hover:text-accent">
                          <SecurityName security={h.security} />
                        </Link>
                      ) : (
                        <SecurityName security={h.security} />
                      )}
                    </td>
                    <td className="td text-right">{fmtShares(h.shares)}</td>
                    <td className="td text-right">{fmtUSD(h.value)}</td>
                    <td className="td text-right text-muted">
                      {h.pct_of_portfolio?.toFixed(2) ?? "—"}%
                    </td>
                    <td className="td text-muted text-xs whitespace-nowrap">
                      {fmtShares(h.voting_sole)} / {fmtShares(h.voting_shared)} /{" "}
                      {fmtShares(h.voting_none)}
                    </td>
                    <td className="td text-muted text-xs">{h.investment_discretion ?? "—"}</td>
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
      )}

      {funds.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-1">Fund holdings (N-PORT)</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Security</th>
                  <th className="th text-right">Balance</th>
                  <th className="th text-right">Value</th>
                  <th className="th text-right">% Net assets</th>
                </tr>
              </thead>
              <tbody>
                {funds.map((h, i) => (
                  <tr key={i}>
                    <td className="td"><SecurityName security={h.security} /></td>
                    <td className="td text-right">{h.balance == null ? "—" : fmtShares(h.balance)}</td>
                    <td className="td text-right">{fmtUSD(h.value)}</td>
                    <td className="td text-right text-muted">
                      {h.pct_of_net_assets == null ? "—" : `${h.pct_of_net_assets.toFixed(2)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {stakesHeld.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-1">Stakes held (13D/13G)</h2>
          <p className="text-muted text-xs mb-2">&gt;5% positions this entity holds in other companies.</p>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Company</th>
                  <th className="th">Type</th>
                  <th className="th text-right">% of class</th>
                  <th className="th text-right">Shares</th>
                  <th className="th text-right">As of</th>
                </tr>
              </thead>
              <tbody>
                {stakesHeld.map((s, i) => (
                  <tr key={i}>
                    <td className="td"><SecurityName security={s.security} /></td>
                    <td className="td">
                      <FormPill form={s.form_type} />
                      {s.is_activist && (
                        <span className="pill bg-fuchsia-500/15 text-fuchsia-400 ml-1">activist</span>
                      )}
                    </td>
                    <td className="td text-right">
                      {s.percent_of_class == null ? "—" : `${s.percent_of_class.toFixed(2)}%`}
                    </td>
                    <td className="td text-right">{s.shares == null ? "—" : fmtShares(s.shares)}</td>
                    <td className="td text-right text-muted">{s.event_date ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {issuer && issuer.insider_txns.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-1">Insider trades (Form 3/4/5)</h2>
          <p className="text-muted text-xs mb-2">Transactions by insiders in this company&apos;s stock.</p>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Date</th>
                  <th className="th">Insider</th>
                  <th className="th">Security</th>
                  <th className="th">Code</th>
                  <th className="th text-right">Shares</th>
                  <th className="th text-right">Owned after</th>
                  <th className="th text-right">Price</th>
                  <th className="th">A/D</th>
                </tr>
              </thead>
              <tbody>
                {issuer.insider_txns.slice(0, 50).map((t, i) => (
                  <tr key={i}>
                    <td className="td text-muted">{t.txn_date ?? "—"}</td>
                    <td className="td">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span>{t.insider_name}</span>
                        {t.insider_title && (
                          <span className="text-muted text-xs">({t.insider_title})</span>
                        )}
                        {t.is_director && <RolePill label="Dir" />}
                        {t.is_officer && <RolePill label="Officer" />}
                        {t.is_ten_pct_owner && <RolePill label="10%" />}
                      </div>
                    </td>
                    <td className="td text-muted text-xs">{t.security_title ?? "—"}</td>
                    <td className="td">
                      <span>{t.txn_code ?? "—"}</span>
                      {t.is_derivative && (
                        <span className="pill bg-edge text-muted ml-1">deriv</span>
                      )}
                    </td>
                    <td className="td text-right">{t.shares == null ? "—" : fmtShares(t.shares)}</td>
                    <td className="td text-right text-muted">
                      {t.shares_owned_after == null ? "—" : fmtShares(t.shares_owned_after)}
                    </td>
                    <td className="td text-right">{t.price == null ? "—" : `$${t.price.toFixed(2)}`}</td>
                    <td className={`td ${t.acquired_disposed === "A" ? "text-pos" : t.acquired_disposed === "D" ? "text-neg" : "text-muted"}`}>
                      {t.acquired_disposed ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {issuer && issuer.stakes_in.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-1">Activist & 5%+ stakes in this company</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Holder</th>
                  <th className="th">Type</th>
                  <th className="th text-right">% of class</th>
                  <th className="th text-right">Shares</th>
                  <th className="th text-right">As of</th>
                </tr>
              </thead>
              <tbody>
                {issuer.stakes_in.map((s, i) => (
                  <tr key={i}>
                    <td className="td">
                      <Link href={`/filer/${s.filer.cik}`} className="hover:text-accent">
                        {s.filer.name}
                      </Link>
                    </td>
                    <td className="td">
                      <FormPill form={s.form_type} />
                      {s.is_activist && (
                        <span className="pill bg-fuchsia-500/15 text-fuchsia-400 ml-1">activist</span>
                      )}
                    </td>
                    <td className="td text-right">
                      {s.percent_of_class == null ? "—" : `${s.percent_of_class.toFixed(2)}%`}
                    </td>
                    <td className="td text-right">{s.shares == null ? "—" : fmtShares(s.shares)}</td>
                    <td className="td text-right text-muted">{s.event_date ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {issuer && issuer.top_holders.length > 0 && (
        <section className="card">
          <h2 className="font-semibold mb-1">Institutional holders of this company</h2>
          <div className="overflow-x-auto">
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
                {issuer.top_holders.map((h, i) => (
                  <tr key={i}>
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
        </section>
      )}
    </div>
  );
}

function PeriodSelector({
  cik,
  periods,
  active,
}: {
  cik: string;
  periods: Period[];
  active: string | null;
}) {
  return (
    <div className="card">
      <div className="text-xs text-muted uppercase tracking-wide mb-2">13F history</div>
      <div className="flex flex-wrap gap-2">
        {periods.map((p) => {
          const isActive = p.period === active;
          return (
            <Link
              key={p.period}
              href={`/filer/${cik}?period=${p.period}`}
              className={`pill ${isActive ? "bg-accent/20 text-accent" : "bg-edge text-muted hover:text-accent"}`}
              title={`${p.position_count} positions · ${fmtUSD(p.total_value)}`}
            >
              {p.period}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function SecurityName({ security }: { security: Security }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {security.name}
      {security.ticker && (
        <span className="pill bg-edge text-muted font-mono text-xs">{security.ticker}</span>
      )}
    </span>
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
