"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, Filer } from "@/lib/api";

export function FilerSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Filer[]>([]);

  useEffect(() => {
    let active = true;
    const t = setTimeout(() => {
      api
        .filers(q)
        .then((r) => active && setResults(r))
        .catch(() => active && setResults([]));
    }, 200);
    // `active` invalidates an in-flight request when q changes or we unmount, so
    // a slow response for an older query can't overwrite newer results.
    return () => {
      active = false;
      clearTimeout(t);
    };
  }, [q]);

  return (
    <div className="card">
      <h2 className="font-semibold mb-3">Filers</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const cik = q.replace(/\D/g, "");
          if (cik) router.push(`/filer/${cik}`);
        }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name, or enter a CIK…"
          className="w-full rounded-lg bg-ink border border-edge px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </form>
      <ul className="mt-3 divide-y divide-edge">
        {results.map((f) => (
          <li key={f.id} className="py-2 flex items-center gap-2">
            <span className="pill bg-edge text-muted">{f.kind}</span>
            <Link href={`/filer/${f.cik}`} className="flex-1 truncate hover:text-accent">
              {f.name}
            </Link>
            <span className="text-xs text-muted">{f.latest_filing_at ?? "—"}</span>
          </li>
        ))}
        {results.length === 0 && (
          <li className="py-2 text-sm text-muted">No matching filers ingested yet.</li>
        )}
      </ul>
    </div>
  );
}
