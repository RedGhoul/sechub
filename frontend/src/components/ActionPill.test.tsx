import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ActionPill, FormPill } from "./ActionPill";

describe("ActionPill", () => {
  it("renders the action label", () => {
    render(<ActionPill action="NEW" />);
    expect(screen.getByText("NEW")).toBeInTheDocument();
  });

  it("applies the action-specific style classes", () => {
    render(<ActionPill action="EXIT" />);
    const pill = screen.getByText("EXIT");
    expect(pill).toHaveClass("pill", "bg-neg/15", "text-neg");
  });

  it("falls back to a neutral style for unknown actions", () => {
    render(<ActionPill action="WAT" />);
    const pill = screen.getByText("WAT");
    expect(pill).toHaveClass("bg-edge", "text-muted");
  });
});

describe("FormPill", () => {
  it("renders the form type and a known style", () => {
    render(<FormPill form="13F-HR" />);
    const pill = screen.getByText("13F-HR");
    expect(pill).toHaveClass("pill", "bg-accent/15", "text-accent");
  });

  it("styles SC 13D filings with the activist (fuchsia) accent", () => {
    render(<FormPill form="SC 13D" />);
    const pill = screen.getByText("SC 13D");
    expect(pill).toHaveClass("bg-fuchsia-500/15", "text-fuchsia-400");
  });

  it("treats SC 13D/A amendments like a 13D", () => {
    render(<FormPill form="SC 13D/A" />);
    const pill = screen.getByText("SC 13D/A");
    expect(pill).toHaveClass("bg-fuchsia-500/15", "text-fuchsia-400");
  });

  it("groups insider forms (3/4/5) under the amber style", () => {
    render(<FormPill form="4" />);
    expect(screen.getByText("4")).toHaveClass("bg-amber-500/15", "text-amber-400");
  });

  it("falls back to a neutral style for unmapped forms", () => {
    render(<FormPill form="NPORT-P" />);
    expect(screen.getByText("NPORT-P")).toHaveClass("bg-edge", "text-muted");
  });
});
