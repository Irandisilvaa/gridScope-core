type StatusPillProps = {
  label: string;
  tone?: "good" | "warn" | "muted";
};

export function StatusPill({ label, tone = "muted" }: StatusPillProps) {
  return <span className={`status-pill status-pill--${tone}`}>{label}</span>;
}
