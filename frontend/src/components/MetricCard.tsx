import React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  note?: string;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  icon?: React.ReactNode;
  accent?: boolean;
  onClick?: () => void;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit,
  note,
  trend,
  icon,
  accent = false,
  onClick,
}) => {
  return (
    <article
      onClick={onClick}
      className={`group relative overflow-hidden rounded-2xl border p-1 transition-all duration-300 ${
        accent
          ? "border-grid-yellow/40 bg-grid-surface-raised yellow-border-glow"
          : "border-grid-graphite-light bg-grid-surface hover:border-grid-border-strong"
      } ${onClick ? "cursor-pointer active:scale-[0.99]" : ""}`}
    >
      {/* Accent energy bar on top */}
      {accent && (
        <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-grid-yellow to-transparent opacity-80" />
      )}

      {/* Inner Machined Core (Double-Bezel) */}
      <div
        className={`flex h-full min-h-[120px] flex-col justify-between rounded-xl border p-4 transition-colors ${
          accent
            ? "border-grid-yellow/15 bg-grid-surface-raised"
            : "border-grid-border-subtle bg-grid-surface-raised group-hover:bg-grid-surface-elevated"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-sans text-[0.72rem] font-medium tracking-[0.06em] uppercase text-grid-gray">
            {label}
          </span>
          {icon && (
            <div
              className={`flex h-7 w-7 items-center justify-center rounded-lg border text-sm transition-transform duration-300 group-hover:scale-105 ${
                accent
                  ? "border-grid-yellow/30 bg-grid-yellow/10 text-grid-yellow"
                  : "border-grid-border bg-grid-graphite text-grid-gray group-hover:text-white"
              }`}
            >
              {icon}
            </div>
          )}
        </div>

        <div className="my-2 flex items-baseline gap-1.5">
          <span
            className={`font-mono text-2xl font-bold tracking-tight md:text-3xl ${
              accent ? "text-grid-yellow" : "text-white"
            }`}
          >
            {value}
          </span>
          {unit && (
            <span className="font-mono text-xs font-medium text-grid-gray">
              {unit}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between text-[0.72rem] text-grid-gray">
          {note && <span className="truncate">{note}</span>}
          {trend && (
            <span
              className={`font-mono text-[0.68rem] font-semibold ${
                trend.isPositive ? "text-status-success" : "text-status-danger"
              }`}
            >
              {trend.value}
            </span>
          )}
        </div>
      </div>
    </article>
  );
};
