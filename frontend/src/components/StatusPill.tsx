import React from "react";

export type StatusTone = "normal" | "attention" | "critical" | "warning" | "info" | "yellow" | "muted";

interface StatusPillProps {
  label: string;
  tone?: StatusTone;
  size?: "sm" | "md";
  showDot?: boolean;
}

export const StatusPill: React.FC<StatusPillProps> = ({
  label,
  tone = "muted",
  size = "md",
  showDot = true,
}) => {
  const normalized = label.toUpperCase();

  // Determine tone automatically if generic string passed
  let resolvedTone = tone;
  if (tone === "muted") {
    if (normalized.includes("NORMAL") || normalized.includes("BOM") || normalized.includes("PUBLICAD")) {
      resolvedTone = "normal";
    } else if (normalized.includes("CRÍT") || normalized.includes("CRITIC")) {
      resolvedTone = "critical";
    } else if (normalized.includes("ATEN") || normalized.includes("MÉD")) {
      resolvedTone = "attention";
    } else if (normalized.includes("ALERT") || normalized.includes("WARN")) {
      resolvedTone = "warning";
    } else if (normalized.includes("INFO") || normalized.includes("DISTRIB")) {
      resolvedTone = "info";
    }
  }

  const toneConfig: Record<StatusTone, { border: string; bg: string; text: string; dot: string }> = {
    normal: {
      border: "border-[#22C55E]/30",
      bg: "bg-[#22C55E]/10",
      text: "text-[#22C55E]",
      dot: "bg-[#22C55E] shadow-[0_0_8px_rgba(34,197,94,0.6)]",
    },
    critical: {
      border: "border-[#EF4444]/40",
      bg: "bg-[#EF4444]/15",
      text: "text-[#EF4444]",
      dot: "bg-[#EF4444] shadow-[0_0_8px_rgba(239,68,68,0.7)] animate-pulse",
    },
    attention: {
      border: "border-[#F59E0B]/40",
      bg: "bg-[#F59E0B]/12",
      text: "text-[#F59E0B]",
      dot: "bg-[#F59E0B] shadow-[0_0_8px_rgba(245,158,11,0.6)]",
    },
    warning: {
      border: "border-[#F59E0B]/40",
      bg: "bg-[#F59E0B]/12",
      text: "text-[#F59E0B]",
      dot: "bg-[#F59E0B]",
    },
    info: {
      border: "border-[#3B82F6]/35",
      bg: "bg-[#3B82F6]/10",
      text: "text-[#3B82F6]",
      dot: "bg-[#3B82F6]",
    },
    yellow: {
      border: "border-[#FFD400]/40",
      bg: "bg-[#FFD400]/12",
      text: "text-[#FFD400]",
      dot: "bg-[#FFD400] shadow-[0_0_8px_rgba(255,212,0,0.8)]",
    },
    muted: {
      border: "border-[#262626]",
      bg: "bg-[#181818]",
      text: "text-[#8A8A8A]",
      dot: "bg-[#8A8A8A]",
    },
  };

  const current = toneConfig[resolvedTone] || toneConfig.muted;
  const padding = size === "sm" ? "px-2 py-0.5 text-[0.65rem]" : "px-2.5 py-1 text-[0.72rem]";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-mono font-medium uppercase tracking-[0.08em] transition-all duration-200 ${padding} ${current.border} ${current.bg} ${current.text}`}
    >
      {showDot && (
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${current.dot}`}
          aria-hidden="true"
        />
      )}
      <span>{label}</span>
    </span>
  );
};
