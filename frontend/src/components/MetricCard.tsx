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
          ? "border-[#FFD400]/40 bg-[#121210] shadow-[0_0_24px_rgba(255,212,0,0.08)]"
          : "border-[#222222] bg-[#0c0c0c] hover:border-[#383838]"
      } ${onClick ? "cursor-pointer active:scale-[0.99]" : ""}`}
    >
      {/* Accent energy bar on top */}
      {accent && (
        <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-[#FFD400] to-transparent opacity-80" />
      )}

      {/* Inner Machined Core (Double-Bezel) */}
      <div
        className={`flex h-full min-h-[120px] flex-col justify-between rounded-xl border p-4 transition-colors ${
          accent
            ? "border-[#FFD400]/15 bg-[#161510]"
            : "border-[#1A1A1A] bg-[#121212] group-hover:bg-[#151515]"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-sans text-[0.72rem] font-medium tracking-[0.06em] uppercase text-[#8A8A8A]">
            {label}
          </span>
          {icon && (
            <div
              className={`flex h-7 w-7 items-center justify-center rounded-lg border text-sm transition-transform duration-300 group-hover:scale-105 ${
                accent
                  ? "border-[#FFD400]/30 bg-[#FFD400]/10 text-[#FFD400]"
                  : "border-[#262626] bg-[#1A1A1A] text-[#8A8A8A] group-hover:text-white"
              }`}
            >
              {icon}
            </div>
          )}
        </div>

        <div className="my-2 flex items-baseline gap-1.5">
          <span
            className={`font-mono text-2xl font-bold tracking-tight md:text-3xl ${
              accent ? "text-[#FFD400]" : "text-white"
            }`}
          >
            {value}
          </span>
          {unit && (
            <span className="font-mono text-xs font-medium text-[#8A8A8A]">
              {unit}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between text-[0.72rem] text-[#8A8A8A]">
          {note && <span className="truncate">{note}</span>}
          {trend && (
            <span
              className={`font-mono text-[0.68rem] font-semibold ${
                trend.isPositive ? "text-[#22C55E]" : "text-[#EF4444]"
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
