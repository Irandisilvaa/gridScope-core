import React, { useState, useRef, useEffect, useId } from "react";
import {
  Calendar as CalendarIcon,
  CaretLeft,
  CaretRight,
  CaretDown,
  ArrowCounterClockwise,
  Check,
} from "@phosphor-icons/react";

export interface DatePickerProps {
  /** Selected date in "YYYY-MM-DD" ISO format */
  value?: string;
  /** Callback fired when a date is picked, returning "YYYY-MM-DD" */
  onChange: (date: string) => void;
  /** Minimum selectable date "YYYY-MM-DD" */
  minDate?: string;
  /** Maximum selectable date "YYYY-MM-DD" */
  maxDate?: string;
  /** Optional placeholder when no date is selected */
  placeholder?: string;
  /** Optional label displayed before or above the input */
  label?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Custom wrapper class */
  className?: string;
  /** Preferred popover alignment */
  align?: "left" | "right" | "auto";
  /** Size variant */
  size?: "sm" | "md";
  /** Whether to show quick shortcut buttons like 'Hoje' and 'Ontem' */
  showShortcuts?: boolean;
  /** ID for accessibility */
  id?: string;
}

const MONTH_NAMES = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

const WEEKDAY_NAMES = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

/**
 * Parses YYYY-MM-DD string into year, month (0-indexed), day
 * Avoids JavaScript timezone offset bugs with UTC vs local midnight.
 */
function parseDateParts(dateStr?: string): { year: number; month: number; day: number } | null {
  if (!dateStr || typeof dateStr !== "string") return null;
  const parts = dateStr.trim().split("-");
  if (parts.length !== 3) return null;
  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10) - 1;
  const day = parseInt(parts[2], 10);
  if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
  return { year, month, day };
}

/** Formats year, month (0-indexed), day into "YYYY-MM-DD" */
function toDateString(year: number, month: number, day: number): string {
  const y = year.toString().padStart(4, "0");
  const m = (month + 1).toString().padStart(2, "0");
  const d = day.toString().padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Formats "YYYY-MM-DD" into Brazilian format "DD/MM/YYYY" */
function formatDisplayDate(dateStr?: string): string {
  const parsed = parseDateParts(dateStr);
  if (!parsed) return "";
  const d = parsed.day.toString().padStart(2, "0");
  const m = (parsed.month + 1).toString().padStart(2, "0");
  return `${d}/${m}/${parsed.year}`;
}

/** Gets today in "YYYY-MM-DD" format using local timezone */
function getTodayString(): string {
  const now = new Date();
  return toDateString(now.getFullYear(), now.getMonth(), now.getDate());
}

/** Gets yesterday in "YYYY-MM-DD" format */
function getYesterdayString(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return toDateString(d.getFullYear(), d.getMonth(), d.getDate());
}

export const DatePicker: React.FC<DatePickerProps> = ({
  value,
  onChange,
  minDate,
  maxDate,
  placeholder = "Selecione uma data",
  label,
  disabled = false,
  className = "",
  align = "auto",
  size = "md",
  showShortcuts = true,
  id: customId,
}) => {
  const autoId = useId();
  const id = customId || autoId;
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [resolvedAlign, setResolvedAlign] = useState<"left" | "right">("left");

  // Current view month & year in the calendar
  const parsedValue = parseDateParts(value);
  const todayParts = parseDateParts(getTodayString())!;

  const [viewYear, setViewYear] = useState<number>(
    parsedValue ? parsedValue.year : todayParts.year
  );
  const [viewMonth, setViewMonth] = useState<number>(
    parsedValue ? parsedValue.month : todayParts.month
  );

  // Selector mode: "days" | "months" | "years"
  const [viewMode, setViewMode] = useState<"days" | "months" | "years">("days");

  // Keep view aligned when value changes from outside
  useEffect(() => {
    if (parsedValue) {
      setViewYear(parsedValue.year);
      setViewMonth(parsedValue.month);
    }
  }, [value]);

  // Handle click outside to close popover
  useEffect(() => {
    if (!isOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setViewMode("days");
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
        setViewMode("days");
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  // Compute popover alignment to avoid overflowing viewport
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;
    if (align === "left" || align === "right") {
      setResolvedAlign(align);
      return;
    }
    const rect = containerRef.current.getBoundingClientRect();
    const spaceOnRight = window.innerWidth - rect.left;
    if (spaceOnRight < 320 && rect.right > 320) {
      setResolvedAlign("right");
    } else {
      setResolvedAlign("left");
    }
  }, [isOpen, align]);

  // Navigate months
  const handlePrevMonth = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
  };

  const handleNextMonth = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
  };

  // Select day
  const handleSelectDay = (year: number, month: number, day: number) => {
    const formatted = toDateString(year, month, day);
    onChange(formatted);
    setIsOpen(false);
    setViewMode("days");
  };

  // Quick shortcuts
  const selectToday = (e: React.MouseEvent) => {
    e.stopPropagation();
    const today = getTodayString();
    onChange(today);
    const parsed = parseDateParts(today)!;
    setViewYear(parsed.year);
    setViewMonth(parsed.month);
    setIsOpen(false);
  };

  const selectYesterday = (e: React.MouseEvent) => {
    e.stopPropagation();
    const yesterday = getYesterdayString();
    onChange(yesterday);
    const parsed = parseDateParts(yesterday)!;
    setViewYear(parsed.year);
    setViewMonth(parsed.month);
    setIsOpen(false);
  };

  // Check if date is disabled
  const isDateDisabled = (year: number, month: number, day: number) => {
    const currentStr = toDateString(year, month, day);
    if (minDate && currentStr < minDate) return true;
    if (maxDate && currentStr > maxDate) return true;
    return false;
  };

  // Calculate days for the calendar grid
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const daysInPrevMonth = new Date(viewYear, viewMonth, 0).getDate();
  const firstDayOfWeek = new Date(viewYear, viewMonth, 1).getDay(); // 0 = Sunday

  const daysGrid: Array<{
    day: number;
    month: number;
    year: number;
    isCurrentMonth: boolean;
  }> = [];

  // Previous month trailing days
  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const d = daysInPrevMonth - i;
    const m = viewMonth === 0 ? 11 : viewMonth - 1;
    const y = viewMonth === 0 ? viewYear - 1 : viewYear;
    daysGrid.push({ day: d, month: m, year: y, isCurrentMonth: false });
  }

  // Current month days
  for (let d = 1; d <= daysInMonth; d++) {
    daysGrid.push({ day: d, month: viewMonth, year: viewYear, isCurrentMonth: true });
  }

  // Next month leading days (fill to 35 or 42 cells)
  const remainingCells = 42 - daysGrid.length >= 7 ? 35 - daysGrid.length : 42 - daysGrid.length;
  for (let d = 1; d <= remainingCells; d++) {
    const m = viewMonth === 11 ? 0 : viewMonth + 1;
    const y = viewMonth === 11 ? viewYear + 1 : viewYear;
    daysGrid.push({ day: d, month: m, year: y, isCurrentMonth: false });
  }

  // Years list for year picker mode (decade range around viewYear)
  const startYear = Math.floor(viewYear / 12) * 12;
  const yearsList = Array.from({ length: 12 }, (_, i) => startYear + i);

  const sizeClasses =
    size === "sm"
      ? "px-2.5 py-1.5 text-[0.72rem] min-h-[30px]"
      : "px-3 py-2 text-xs min-h-[38px]";

  return (
    <div
      ref={containerRef}
      className={`relative inline-block select-none ${className}`}
    >
      {label && (
        <label
          htmlFor={id}
          className="mb-1 block font-mono text-[0.68rem] font-medium uppercase tracking-wider text-grid-gray"
        >
          {label}
        </label>
      )}

      {/* Trigger Button */}
      <button
        id={id}
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen((prev) => !prev)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        className={`group flex items-center justify-between gap-2.5 rounded-xl border border-grid-border-card bg-grid-surface-elevated font-mono text-white transition-all duration-150 hover:border-grid-border-strong focus:border-grid-yellow focus:outline-none focus:ring-1 focus:ring-grid-yellow active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 ${sizeClasses}`}
      >
        <div className="flex items-center gap-2">
          <CalendarIcon
            size={size === "sm" ? 14 : 16}
            className={`transition-colors ${
              isOpen ? "text-grid-yellow" : "text-grid-yellow/80 group-hover:text-grid-yellow"
            }`}
          />
          <span
            className={
              value
                ? "font-medium text-white"
                : "text-grid-gray-dim font-normal"
            }
          >
            {value ? formatDisplayDate(value) : placeholder}
          </span>
        </div>

        <CaretDown
          size={13}
          className={`text-grid-gray transition-transform duration-200 ${
            isOpen ? "rotate-180 text-grid-yellow" : "group-hover:text-white"
          }`}
        />
      </button>

      {/* Calendar Dropdown Popover */}
      {isOpen && (
        <div
          ref={dropdownRef}
          role="dialog"
          aria-label="Calendário seletor de data"
          className={`absolute top-full mt-1.5 z-50 w-72 rounded-2xl border border-grid-border-card bg-grid-surface p-3.5 shadow-2xl backdrop-blur-md animate-in fade-in zoom-in-95 duration-150 ${
            resolvedAlign === "right" ? "right-0" : "left-0"
          }`}
          style={{
            boxShadow:
              "0 20px 25px -5px rgba(0, 0, 0, 0.7), 0 8px 10px -6px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.05)",
          }}
        >
          {/* Header with Month/Year Navigation */}
          <div className="flex items-center justify-between pb-3 border-b border-grid-border-subtle">
            <button
              type="button"
              onClick={handlePrevMonth}
              className="flex h-7 w-7 items-center justify-center rounded-lg border border-grid-border bg-grid-surface-raised text-grid-gray transition-colors hover:border-grid-border-strong hover:text-white active:scale-95"
              aria-label="Mês anterior"
            >
              <CaretLeft size={14} />
            </button>

            {/* Month/Year toggle */}
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() =>
                  setViewMode((prev) => (prev === "months" ? "days" : "months"))
                }
                className="rounded-md px-1.5 py-0.5 font-display text-xs font-semibold text-white transition-colors hover:bg-grid-surface-raised hover:text-grid-yellow"
              >
                {MONTH_NAMES[viewMonth]}
              </button>
              <button
                type="button"
                onClick={() =>
                  setViewMode((prev) => (prev === "years" ? "days" : "years"))
                }
                className="rounded-md px-1.5 py-0.5 font-mono text-xs font-semibold text-grid-gray-light transition-colors hover:bg-grid-surface-raised hover:text-grid-yellow"
              >
                {viewYear}
              </button>
            </div>

            <button
              type="button"
              onClick={handleNextMonth}
              className="flex h-7 w-7 items-center justify-center rounded-lg border border-grid-border bg-grid-surface-raised text-grid-gray transition-colors hover:border-grid-border-strong hover:text-white active:scale-95"
              aria-label="Próximo mês"
            >
              <CaretRight size={14} />
            </button>
          </div>

          {/* Body: Months View */}
          {viewMode === "months" && (
            <div className="grid grid-cols-3 gap-1.5 py-3">
              {MONTH_NAMES.map((name, idx) => {
                const isSelectedMonth =
                  parsedValue &&
                  parsedValue.year === viewYear &&
                  parsedValue.month === idx;
                const isCurrentMonth =
                  todayParts.year === viewYear && todayParts.month === idx;

                return (
                  <button
                    key={name}
                    type="button"
                    onClick={() => {
                      setViewMonth(idx);
                      setViewMode("days");
                    }}
                    className={`rounded-lg px-2 py-2 text-center font-mono text-xs transition-colors ${
                      isSelectedMonth
                        ? "bg-grid-yellow font-bold text-black shadow-[0_0_10px_rgba(255,212,0,0.3)]"
                        : isCurrentMonth
                        ? "border border-grid-yellow/40 bg-grid-yellow/10 font-medium text-grid-yellow"
                        : "text-grid-gray-light hover:bg-grid-surface-raised hover:text-white"
                    }`}
                  >
                    {name.slice(0, 3)}
                  </button>
                );
              })}
            </div>
          )}

          {/* Body: Years View */}
          {viewMode === "years" && (
            <div className="space-y-2 py-3">
              <div className="flex items-center justify-between px-1 text-[0.68rem] font-mono text-grid-gray">
                <button
                  type="button"
                  onClick={() => setViewYear((y) => y - 12)}
                  className="hover:text-white"
                >
                  &larr; Anteriores
                </button>
                <span>
                  {yearsList[0]} - {yearsList[yearsList.length - 1]}
                </span>
                <button
                  type="button"
                  onClick={() => setViewYear((y) => y + 12)}
                  className="hover:text-white"
                >
                  Próximos &rarr;
                </button>
              </div>
              <div className="grid grid-cols-3 gap-1.5">
                {yearsList.map((yr) => {
                  const isSelectedYear =
                    parsedValue && parsedValue.year === yr;
                  const isCurrentYear = todayParts.year === yr;

                  return (
                    <button
                      key={yr}
                      type="button"
                      onClick={() => {
                        setViewYear(yr);
                        setViewMode("months");
                      }}
                      className={`rounded-lg px-2 py-2 text-center font-mono text-xs transition-colors ${
                        isSelectedYear
                          ? "bg-grid-yellow font-bold text-black shadow-[0_0_10px_rgba(255,212,0,0.3)]"
                          : isCurrentYear
                          ? "border border-grid-yellow/40 bg-grid-yellow/10 font-medium text-grid-yellow"
                          : "text-grid-gray-light hover:bg-grid-surface-raised hover:text-white"
                      }`}
                    >
                      {yr}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Body: Days View */}
          {viewMode === "days" && (
            <div className="pt-2">
              {/* Day of Week Headers */}
              <div className="grid grid-cols-7 gap-1 text-center font-mono text-[0.65rem] font-bold uppercase tracking-wider text-grid-gray-muted mb-1.5">
                {WEEKDAY_NAMES.map((wkd) => (
                  <div key={wkd} className="py-1">
                    {wkd}
                  </div>
                ))}
              </div>

              {/* Day Cells Grid */}
              <div className="grid grid-cols-7 gap-1">
                {daysGrid.map((item, idx) => {
                  const isSelected =
                    parsedValue &&
                    parsedValue.year === item.year &&
                    parsedValue.month === item.month &&
                    parsedValue.day === item.day;

                  const isToday =
                    todayParts.year === item.year &&
                    todayParts.month === item.month &&
                    todayParts.day === item.day;

                  const disabledDay = isDateDisabled(
                    item.year,
                    item.month,
                    item.day
                  );

                  return (
                    <button
                      key={idx}
                      type="button"
                      disabled={disabledDay}
                      onClick={() =>
                        handleSelectDay(item.year, item.month, item.day)
                      }
                      className={`group relative flex h-8 w-8 items-center justify-center rounded-lg font-mono text-xs transition-all duration-100 ${
                        disabledDay
                          ? "cursor-not-allowed text-grid-gray-dark opacity-30"
                          : isSelected
                          ? "bg-grid-yellow font-bold text-black shadow-[0_0_12px_rgba(255,212,0,0.35)] scale-105"
                          : isToday
                          ? "border border-grid-yellow/60 bg-grid-yellow/10 font-bold text-grid-yellow hover:bg-grid-yellow/20"
                          : item.isCurrentMonth
                          ? "text-grid-gray-subtle hover:bg-grid-surface-raised hover:text-white"
                          : "text-grid-gray-dark hover:bg-grid-surface-raised/50 hover:text-grid-gray-muted"
                      }`}
                    >
                      {item.day}
                      {/* Subtle indicator dot for today if not selected */}
                      {isToday && !isSelected && (
                        <span className="absolute bottom-1 h-1 w-1 rounded-full bg-grid-yellow" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Footer Shortcuts */}
          {showShortcuts && (
            <div className="mt-3 flex items-center justify-between border-t border-grid-border-subtle pt-2.5 font-mono text-[0.7rem]">
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={selectToday}
                  className="rounded-md border border-grid-border-card bg-grid-surface-raised px-2 py-1 text-grid-gray-light transition-colors hover:border-grid-yellow/50 hover:text-grid-yellow"
                >
                  Hoje
                </button>
                <button
                  type="button"
                  onClick={selectYesterday}
                  className="rounded-md border border-grid-border-card bg-grid-surface-raised px-2 py-1 text-grid-gray-light transition-colors hover:border-grid-yellow/50 hover:text-grid-yellow"
                >
                  Ontem
                </button>
              </div>

              {value && (
                <div className="flex items-center gap-1 text-[0.66rem] text-grid-gray">
                  <Check size={12} className="text-status-success" />
                  <span>{formatDisplayDate(value)}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
