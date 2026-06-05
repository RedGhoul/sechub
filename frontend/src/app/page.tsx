import { LiveFeed } from "@/components/LiveFeed";
import { FilerSearch } from "@/components/FilerSearch";

export default function Home() {
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight">
          What the big money is filing
        </h1>
        <p className="text-muted text-sm mt-1">
          13F holdings, insider trades, activist stakes, and fund portfolios —
          pulled straight from SEC EDGAR.
        </p>
      </section>

      <div className="grid gap-6 md:grid-cols-[1.4fr_1fr]">
        <LiveFeed />
        <FilerSearch />
      </div>
    </div>
  );
}
