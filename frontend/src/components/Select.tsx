import React, { useState, useRef, useEffect, useId, useMemo } from "react";
import {
  CaretDown,
  Check,
  MagnifyingGlass,
  X,
} from "@phosphor-icons/react";

export interface SelectOption<T = string> {
  value: T;
  label: string;
  description?: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  disabled?: boolean;
}

export interface SelectProps<T extends string | number = string> {
  /** Currently selected value */
  value: T;
  /** Callback fired when a value is selected */
  onChange: (value: T) => void;
  /** List of selectable options */
  options: SelectOption<T>[];
  /** Placeholder when nothing is selected */
  placeholder?: string;
  /** Optional inline label or prefix (e.g. "Cobertura", "Status") */
  label?: string;
  /** Size variant */
  size?: "sm" | "md";
  /** Whether to enable searchable input inside the popover */
  searchable?: boolean;
  /** Disabled state */
  disabled?: boolean;
  /** Additional container classes */
  className?: string;
  /** Additional trigger button classes */
  buttonClassName?: string;
  /** Additional menu popover classes */
  menuClassName?: string;
  /** Preferred popover alignment */
  align?: "left" | "right" | "auto";
  /** Optional ID for accessibility */
  id?: string;
  /** Accessibility label */
  "aria-label"?: string;
}

export function Select<T extends string | number = string>({
  value,
  onChange,
  options,
  placeholder = "Selecione...",
  label,
  size = "md",
  searchable,
  disabled = false,
  className = "",
  buttonClassName = "",
  menuClassName = "",
  align = "auto",
  id: customId,
  "aria-label": ariaLabel,
}: SelectProps<T>): React.ReactElement {
  const autoId = useId();
  const id = customId || autoId;
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [resolvedAlign, setResolvedAlign] = useState<"left" | "right">("left");

  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Automatically enable search if more than 7 options unless explicitly specified false
  const isSearchable = searchable ?? options.length >= 8;

  // Find currently selected option
  const selectedOption = useMemo(
    () => options.find((opt) => opt.value === value),
    [options, value]
  );

  // Filter options based on search query
  const filteredOptions = useMemo(() => {
    if (!searchQuery.trim()) return options;
    const query = searchQuery.toLowerCase().trim();
    return options.filter((opt) => {
      const matchLabel = opt.label.toLowerCase().includes(query);
      const matchDesc = opt.description?.toLowerCase().includes(query);
      return matchLabel || matchDesc;
    });
  }, [options, searchQuery]);

  // Click outside and keydown listeners
  useEffect(() => {
    if (!isOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setSearchQuery("");
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
        setSearchQuery("");
      }
    }

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  // Auto focus search input when opened
  useEffect(() => {
    if (isOpen) {
      setHighlightedIndex(
        filteredOptions.findIndex((opt) => opt.value === value)
      );
      if (isSearchable) {
        const timer = setTimeout(() => {
          searchInputRef.current?.focus();
        }, 50);
        return () => clearTimeout(timer);
      }
    } else {
      setSearchQuery("");
    }
  }, [isOpen, isSearchable, value]);

  // Calculate alignment to avoid overflowing viewport
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;
    if (align === "left" || align === "right") {
      setResolvedAlign(align);
      return;
    }
    const rect = containerRef.current.getBoundingClientRect();
    const spaceOnRight = window.innerWidth - rect.left;
    if (spaceOnRight < 240 && rect.right > 240) {
      setResolvedAlign("right");
    } else {
      setResolvedAlign("left");
    }
  }, [isOpen, align]);

  // Keyboard navigation within list
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;

    if (!isOpen) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((prev) => {
        const next = prev < filteredOptions.length - 1 ? prev + 1 : 0;
        scrollOptionIntoView(next);
        return next;
      });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((prev) => {
        const next = prev > 0 ? prev - 1 : filteredOptions.length - 1;
        scrollOptionIntoView(next);
        return next;
      });
    } else if (e.key === "Enter" && highlightedIndex >= 0) {
      e.preventDefault();
      const option = filteredOptions[highlightedIndex];
      if (option && !option.disabled) {
        onChange(option.value);
        setIsOpen(false);
        setSearchQuery("");
      }
    } else if (e.key === "Tab") {
      setIsOpen(false);
      setSearchQuery("");
    }
  };

  const scrollOptionIntoView = (index: number) => {
    if (!listRef.current) return;
    const items = listRef.current.querySelectorAll<HTMLButtonElement>("[data-select-option]");
    const target = items[index];
    if (target) {
      target.scrollIntoView({ block: "nearest" });
    }
  };

  const handleSelect = (option: SelectOption<T>) => {
    if (option.disabled) return;
    onChange(option.value);
    setIsOpen(false);
    setSearchQuery("");
  };

  const sizeClasses =
    size === "sm"
      ? "px-2.5 py-1 text-[0.72rem] min-h-[28px] rounded-lg"
      : "px-3 py-2 text-xs min-h-[38px] rounded-xl";

  return (
    <div
      ref={containerRef}
      className={`relative inline-block select-none ${className}`}
      onKeyDown={handleKeyDown}
    >
      {/* Trigger Button */}
      <button
        id={id}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={ariaLabel || label || placeholder}
        onClick={() => !disabled && setIsOpen((prev) => !prev)}
        className={`group flex w-full items-center justify-between gap-2 border border-grid-border-card bg-grid-surface-raised font-mono text-white transition-all duration-150 hover:border-grid-border-strong focus:border-grid-yellow focus:outline-none focus:ring-1 focus:ring-grid-yellow active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 ${sizeClasses} ${buttonClassName}`}
      >
        <div className="flex min-w-0 items-center gap-2 truncate">
          {label && (
            <span className="shrink-0 text-grid-gray font-normal">
              {label}
            </span>
          )}

          {selectedOption?.icon && (
            <span className="shrink-0 text-grid-yellow">
              {selectedOption.icon}
            </span>
          )}

          {selectedOption?.badge && (
            <span className="shrink-0">{selectedOption.badge}</span>
          )}

          <span
            className={`truncate ${
              selectedOption
                ? "font-medium text-white"
                : "font-normal text-grid-gray-dim"
            }`}
          >
            {selectedOption ? selectedOption.label : placeholder}
          </span>
        </div>

        <CaretDown
          size={size === "sm" ? 12 : 14}
          className={`shrink-0 text-grid-gray transition-transform duration-200 ${
            isOpen ? "rotate-180 text-grid-yellow" : "group-hover:text-white"
          }`}
        />
      </button>

      {/* Dropdown Menu Popover */}
      {isOpen && (
        <div
          role="listbox"
          aria-label={ariaLabel || label || placeholder}
          className={`absolute top-full mt-1.5 z-50 min-w-full rounded-xl border border-grid-border-card bg-grid-surface shadow-2xl backdrop-blur-md animate-in fade-in zoom-in-95 duration-150 overflow-hidden ${
            resolvedAlign === "right" ? "right-0" : "left-0"
          } ${menuClassName}`}
          style={{
            minWidth: "max(100%, 190px)",
            boxShadow:
              "0 20px 25px -5px rgba(0, 0, 0, 0.7), 0 8px 10px -6px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.05)",
          }}
        >
          {/* Optional Search Input */}
          {isSearchable && (
            <div className="border-b border-grid-border-subtle p-2">
              <div className="relative flex items-center">
                <MagnifyingGlass
                  size={13}
                  className="absolute left-2.5 text-grid-gray"
                />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filtrar..."
                  className="w-full rounded-lg border border-grid-border bg-grid-surface-raised py-1.5 pl-7 pr-7 font-mono text-[0.72rem] text-white placeholder:text-grid-gray-dim outline-none focus:border-grid-yellow"
                  onClick={(e) => e.stopPropagation()}
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSearchQuery("");
                      searchInputRef.current?.focus();
                    }}
                    className="absolute right-2 text-grid-gray hover:text-white"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Options List */}
          <div
            ref={listRef}
            className="max-h-56 overflow-y-auto p-1 font-mono text-xs"
          >
            {filteredOptions.length === 0 ? (
              <div className="py-3 px-3 text-center text-[0.72rem] text-grid-gray">
                Nenhum resultado
              </div>
            ) : (
              filteredOptions.map((option, index) => {
                const isSelected = option.value === value;
                const isHighlighted = index === highlightedIndex;

                return (
                  <button
                    key={String(option.value)}
                    type="button"
                    data-select-option
                    disabled={option.disabled}
                    onClick={() => handleSelect(option)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    role="option"
                    aria-selected={isSelected}
                    className={`group flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left transition-colors duration-100 ${
                      option.disabled
                        ? "cursor-not-allowed text-grid-gray-dark opacity-40"
                        : isSelected
                        ? "bg-grid-yellow/15 text-grid-yellow font-medium"
                        : isHighlighted
                        ? "bg-grid-graphite-light text-white"
                        : "text-grid-gray-subtle hover:bg-grid-surface-raised hover:text-white"
                    }`}
                  >
                    <div className="flex min-w-0 items-center gap-2 truncate">
                      {option.icon && (
                        <span className="shrink-0 text-grid-yellow">
                          {option.icon}
                        </span>
                      )}
                      {option.badge && (
                        <span className="shrink-0">{option.badge}</span>
                      )}
                      <div className="truncate">
                        <span className="block truncate">{option.label}</span>
                        {option.description && (
                          <span className="block text-[0.65rem] text-grid-gray truncate">
                            {option.description}
                          </span>
                        )}
                      </div>
                    </div>

                    {isSelected && (
                      <Check
                        size={13}
                        weight="bold"
                        className="shrink-0 text-grid-yellow"
                      />
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
