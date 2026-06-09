"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Filing } from "@/lib/api";
import { FormPill } from "./ActionPill";

const FORMS = ["", "13F-HR", "4", "SC 13D", "SC 13G", "NPORT-P"];
const LABELS: Record<string, string> = {
  "": "All",
  "13F-HR": "13F",
  "4": "Insider",
  "SC 13D": "13D",
  "SC 13G": "13G",
  "NPORT-P": "Fund",
};

export function LiveFeed() {
  const [form, setForm] = useState("");
  const [filings, setFilings] = useState<Filing[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = () =>
      api
        .feed(form, 40)
        .then((f) => active && (setFilings(f), setError(null)))
        .catch((e) => active && setError(String(e)));
    load();
    // Poll so new filings surface "as soon as they come out".
    const t = setInterval(load, 30_000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [form]);

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">Live filing feed</h2>
        <div className="flex gap-1">
          {FORMS.map((f) => (
            <button
              key={f}
              onClick={() => setForm(f)}
              className={`pill ${form === f ? "bg-accent text-white" : "bg-edge text-muted"}`}
            >
              {LABELS[f]}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-neg text-sm">Could not reach API: {error}</p>}
      {!error && filings.length === 0 && (
        <p className="text-muted text-sm">
          No filings yet. Ingest some via the API, e.g.{" "}
          <code className="text-accent">POST /filings/ingest/0001067983</code>.
        </p>
      )}

      <ul className="divide-y divide-edge">
        {filings.map((f) => (
          <li key={f.id} className="py-2 flex items-center gap-3">
            <FormPill form={f.form_type} />
            <Link href={`/filer/${f.filer.cik}`} className="flex-1 truncate hover:text-accent">
              {f.filer.name}
            </Link>
            <span className="text-xs text-muted whitespace-nowrap">{f.filed_at}</span>
            <Link
              href={`/filing/${f.id}`}
              className="text-xs text-muted hover:text-accent whitespace-nowrap"
            >
              details
            </Link>
            <a
              href={f.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-muted hover:text-accent"
            >
              EDGAR ↗
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
