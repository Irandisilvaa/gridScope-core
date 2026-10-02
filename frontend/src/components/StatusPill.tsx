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
      border: "border-status-success/30",
      bg: "bg-status-success/10",
      text: "text-status-success",
      dot: "bg-status-success shadow-[0_0_8px_var(--color-status-success)]",
    },
    critical: {
      border: "border-status-danger/40",
      bg: "bg-status-danger/15",
      text: "text-status-danger",
      dot: "bg-status-danger shadow-[0_0_8px_var(--color-status-danger)] animate-pulse",
    },
    attention: {
      border: "border-status-warning/40",
      bg: "bg-status-warning/15",
      text: "text-status-warning",
      dot: "bg-status-warning shadow-[0_0_8px_var(--color-status-warning)]",
    },
    warning: {
      border: "border-status-warning/40",
      bg: "bg-status-warning/15",
      text: "text-status-warning",
      dot: "bg-status-warning",
    },
    info: {
      border: "border-status-info/35",
      bg: "bg-status-info/10",
      text: "text-status-info",
      dot: "bg-status-info",
    },
    yellow: {
      border: "border-grid-yellow/40",
      bg: "bg-grid-yellow/12",
      text: "text-grid-yellow",
      dot: "bg-grid-yellow shadow-[0_0_8px_var(--color-grid-yellow)]",
    },
    muted: {
      border: "border-grid-border",
      bg: "bg-grid-graphite",
      text: "text-grid-gray",
      dot: "bg-grid-gray",
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
