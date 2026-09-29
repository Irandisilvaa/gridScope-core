type StatusPillProps = {
  label: string;
  tone?: "good" | "warn" | "muted";
};

export function StatusPill({ label, tone = "muted" }: StatusPillProps) {
  const toneClasses = {
    good: "border-[#6fe7d2]/30 bg-[#6fe7d2]/[0.08] text-[#6fe7d2]",
    warn: "border-[#ffc857]/35 bg-[#ffc857]/[0.08] text-[#ffc857]",
    muted: "border-white/10 bg-white/[0.04] text-[#8ea4a7]",
  };

  return (
    <span className={`inline-flex w-fit items-center whitespace-nowrap rounded-full border px-2 py-1 text-[0.66rem] font-bold tracking-[0.03em] ${toneClasses[tone]}`}>
      {label}
    </span>
  );
}
