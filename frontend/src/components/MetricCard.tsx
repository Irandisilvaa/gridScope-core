type MetricCardProps = {
  label: string;
  value: string;
  note?: string;
};

export function MetricCard({ label, value, note }: MetricCardProps) {
  return (
    <article className="flex min-h-[124px] flex-col justify-between rounded-lg border border-white/10 bg-[#0d202c]/70 p-[18px]">
      <span className="text-xs text-[#8ea4a7]">{label}</span>
      <strong className="mt-[18px] text-[clamp(1.25rem,2.1vw,1.8rem)] font-semibold tracking-[-0.04em] text-[#eef6f3]">{value}</strong>
      {note ? <span className="text-xs text-[#577277]">{note}</span> : null}
    </article>
  );
}
