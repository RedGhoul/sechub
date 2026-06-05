import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "SecHub — SEC filings tracker",
  description: "Hedge fund & institutional SEC filings, as soon as they drop.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-edge bg-panel/60 backdrop-blur sticky top-0 z-10">
          <div className="mx-auto max-w-6xl px-5 py-3 flex items-center gap-3">
            <Link href="/" className="text-lg font-bold tracking-tight">
              Sec<span className="text-accent">Hub</span>
            </Link>
            <span className="text-xs text-muted">institutional &amp; insider filings</span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-5 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-5 py-8 text-xs text-muted">
          Data from SEC EDGAR. Informational only — not investment advice.
        </footer>
      </body>
    </html>
  );
}
