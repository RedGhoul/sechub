# Prompt: Complete Frontend Redesign of SecHub

Copy everything below this line into a Claude design session.

---

You are redesigning the entire frontend of **SecHub**, a real-time SEC filing
intelligence app. You have full creative freedom over the visual design and
information architecture, within the constraints listed at the end. This is a
**complete redesign**, not a restyle — rethink layout, navigation, typography,
color, component structure, and interaction patterns from scratch.

## What the product is

SecHub ingests filings from SEC EDGAR the moment they're published and shows
who bought or sold what. It tracks:

- **13F-HR** — quarterly institutional portfolios (hedge funds, asset
  managers): holdings, share counts, values, put/call options, voting
  authority, and quarter-over-quarter changes (NEW / ADD / TRIM / EXIT / HOLD).
- **Forms 3/4/5** — insider buys and sells by officers, directors, and 10%
  owners: date, price, shares, shares owned after, acquired/disposed.
- **SC 13D/13G** — activist and >5% beneficial-ownership stakes.
- **NPORT-P** — monthly mutual fund / ETF holdings.

The audience is investors, analysts, and researchers. They care about **data
density, scannability, and speed** — this is a Bloomberg-adjacent tool, not a
marketing site. Numbers are the content: large dollar values, share counts,
percentage changes, dates, CUSIPs, tickers.

## Current state (what you're replacing)

- **Stack:** Next.js 14 App Router, React 18, TypeScript (strict), Tailwind
  CSS 3, Vitest + Testing Library. No component library, no icon library, no
  charts, no fonts beyond the system stack. Frontend lives in `frontend/`,
  pages in `frontend/src/app/`, components in `frontend/src/components/`,
  API client and types in `frontend/src/lib/api.ts`.
- **Pages (4):**
  - `/` — live feed of recent filings (client component polling every 30s,
    filterable by form type) plus a debounced filer search box.
  - `/filer/[cik]` — filer detail: stat cards (portfolio value, positions,
    as-of date), a quarter selector, and up to 7 bespoke tables (changes this
    quarter, 13F holdings, fund holdings, 13D/13G stakes, insider trades,
    filing history).
  - `/filing/[id]` — filing metadata with links out to EDGAR.
  - `/security/[cusip]` — institutional holders of a given security.
- **Current look:** dark-only, hand-rolled palette (`ink #0b0f17` background,
  `panel #121826` cards, `accent #4f8cff` blue, green/red for gains/losses,
  amber for insider forms, fuchsia for activist forms), three CSS component
  classes (`.card`, `.pill`, `.th/.td`), raw HTML tables, sticky header with
  a "SecHub" wordmark, no nav, no charts, no skeletons, minimal mobile
  support (tables horizontally scroll).

## Known weaknesses to fix (not just carry over)

1. Seven bespoke table implementations — build **one reusable, typed table
   component** (column defs, alignment, numeric formatting, empty states).
2. **Accessibility is poor:** no input labels, no ARIA landmarks, no
   `scope="col"`, no visible focus styles, and red/green is the *only*
   signal for direction — add icons/symbols so colorblind users aren't lost.
3. **No loading or error states** — design skeletons for the feed and tables,
   and an error pattern with retry.
4. **Silent truncation** — lists are sliced to 40–50 rows with no indication;
   design pagination or "show more" affordances.
5. **Mobile is an afterthought** — design how dense tables degrade on small
   screens (card collapse, column priority, or sticky first column — your
   call, but it must be deliberate).
6. **No data visualization** — this app is begging for it. At minimum design:
   a portfolio-composition view (top holdings as bars or treemap), a
   quarter-over-quarter value sparkline/trend on the filer page, and visual
   weight for the changes table (e.g., bar-scaled % deltas). Prefer a small,
   tree-shakeable approach (e.g., lightweight SVG components or a minimal
   chart lib) over heavyweight charting suites.

## Design direction

- Keep it a **dark-first, data-dense financial terminal aesthetic**, but make
  it feel designed rather than default: establish a real type scale, use
  tabular figures everywhere numbers align, pick an intentional font pairing
  (a quality sans for UI plus a mono for tickers/CIKs/accession numbers), and
  define design tokens (color, spacing, radius, typography) in
  `tailwind.config.ts` as the single source of truth.
- Add a **light mode** driven by `prefers-color-scheme` with a manual toggle;
  both themes come from the same token set.
- Preserve and strengthen the **semantic color language** users already get:
  green = buy/add, red = sell/trim, with distinct hues per form family
  (13F vs insider vs activist vs fund). Pills/badges stay, but as one
  consistent component.
- The **live feed is the heartbeat of the product** — design it to feel live:
  subtle entrance animation for new filings, a clear "live" indicator,
  relative timestamps, and prominent form-type filtering.
- Navigation: the app currently has none beyond the wordmark. Design a proper
  header with global search (filers *and* tickers), and clear cross-linking
  paths: filer → holding → security → other holders → their filers.
- Empty/null values ("—") and zero-result states deserve real design, not
  placeholder dashes alone.

## Hard constraints

- **Stay on the existing stack:** Next.js 14 App Router + React 18 +
  TypeScript + Tailwind. Server components for data pages, client components
  only where interactivity demands it (feed polling, search, theme toggle,
  period selector). Do not introduce a different framework or a heavy UI kit
  (no MUI/Chakra/Bootstrap); small headless utilities (e.g., Radix
  primitives) are acceptable if justified.
- **Do not change the backend or API contract.** All data comes from the
  existing FastAPI REST API via `frontend/src/lib/api.ts` — keep its types
  and functions as the data layer (you may refactor it, e.g., into hooks,
  but not change endpoints or response shapes).
- **Keep all four routes and every piece of data they currently display.**
  You may reorganize, group, tab, or progressively disclose — but no data
  regression.
- Keep EDGAR attribution links and the footer's "not investment advice"
  disclaimer present.
- Maintain or improve performance: no client-side rendering of pages that
  are currently server-rendered, and keep the JS bundle lean.
- Keep the existing Vitest setup working; update tests to match the new
  components and add tests for the new shared table and pill components.

## Deliverables

1. A short written **design rationale** (in the PR description or a
   `docs/DESIGN.md`): the type scale, token system, theme approach, and the
   mobile strategy for tables.
2. The **implemented redesign**: all pages, the shared component library
   (table, pill/badge, stat card, skeleton, empty state, page header,
   search), theme toggle, and the new visualizations.
3. Updated tests passing (`npm test` in `frontend/`).
4. Screenshots (or a screen recording) of every route in both themes at
   desktop and mobile widths.

Work iteratively: tokens and layout shell first, then the shared components,
then page by page (home → filer → security → filing), verifying in the
browser as you go.
