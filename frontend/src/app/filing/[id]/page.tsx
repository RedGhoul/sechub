import Link from "next/link";
import { api, Filing } from "@/lib/api";
import { FormPill } from "@/components/ActionPill";

export default async function FilingPage({ params }: { params: { id: string } }) {
  let filing: Filing | null = null;
  let err: string | null = null;
  try {
    filing = await api.filing(Number(params.id));
  } catch (e) {
    err = String(e);
  }

  if (err || !filing) {
    return (
      <div className="card">
        <Link href="/" className="text-accent text-sm">
          ← back
        </Link>
        <p className="mt-3 text-neg">Could not load filing {params.id}: {err}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Link href="/" className="text-accent text-sm">
        ← back
      </Link>
      <div className="flex flex-wrap items-baseline gap-3">
        <FormPill form={filing.form_type} />
        <h1 className="text-2xl font-bold">
          <Link href={`/filer/${filing.filer.cik}`} className="hover:text-accent">
            {filing.filer.name}
          </Link>
        </h1>
        <span className="pill bg-edge text-muted">{filing.filer.kind}</span>
      </div>

      <div className="card">
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
          <Field label="Form type" value={filing.form_type} />
          <Field label="Filed" value={filing.filed_at} />
          <Field label="Period of report" value={filing.period_of_report ?? "—"} />
          <Field label="Accession no." value={filing.accession_no} mono />
          <Field label="Filer CIK" value={filing.filer.cik} mono />
        </dl>
        <div className="mt-4 flex gap-4 text-sm">
          <Link href={`/filer/${filing.filer.cik}`} className="text-accent">
            View filer →
          </Link>
          <a
            href={filing.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-muted hover:text-accent"
          >
            View on EDGAR ↗
          </a>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-muted uppercase tracking-wide">{label}</dt>
      <dd className={`mt-0.5 ${mono ? "font-mono text-sm" : ""}`}>{value}</dd>
    </div>
  );
}
