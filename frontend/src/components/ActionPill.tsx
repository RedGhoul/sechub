const STYLES: Record<string, string> = {
  NEW: "bg-pos/15 text-pos",
  ADD: "bg-pos/10 text-pos",
  TRIM: "bg-neg/10 text-neg",
  EXIT: "bg-neg/15 text-neg",
  HOLD: "bg-edge text-muted",
};

export function ActionPill({ action }: { action: string }) {
  return <span className={`pill ${STYLES[action] ?? "bg-edge text-muted"}`}>{action}</span>;
}

const FORM_STYLES: Record<string, string> = {
  "13F-HR": "bg-accent/15 text-accent",
  "4": "bg-amber-500/15 text-amber-400",
  "3": "bg-amber-500/15 text-amber-400",
  "5": "bg-amber-500/15 text-amber-400",
};

// 13D (active/activist) and 13G (passive) get distinct accents from each other
// and from the neutral fallback.
const SCHEDULE_STYLES: Record<string, string> = {
  "13D": "bg-fuchsia-500/15 text-fuchsia-400",
  "13G": "bg-sky-500/15 text-sky-400",
};

export function FormPill({ form }: { form: string }) {
  const key = form.startsWith("SC 13D") ? "13D" : form.startsWith("SC 13G") ? "13G" : form;
  const style = FORM_STYLES[form] ?? SCHEDULE_STYLES[key] ?? "bg-edge text-muted";
  return <span className={`pill ${style}`}>{form}</span>;
}

export function RolePill({ label }: { label: string }) {
  return <span className="pill bg-edge text-muted">{label}</span>;
}
