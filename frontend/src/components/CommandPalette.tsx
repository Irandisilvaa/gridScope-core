import React, { useEffect, useState, useRef } from "react";
import type { Substation } from "../lib/api";
import { StatusPill } from "./StatusPill";
import {
  MagnifyingGlass,
  Lightning,
  X,
  Buildings,
  CaretRight,
  ArrowsVertical,
} from "@phosphor-icons/react";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  substations: Substation[];
  onSelectSubstation: (id: string) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  substations,
  onSelectSubstation,
}) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery("");
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (isOpen) onClose();
        else setQuery("");
      }
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const filtered = substations.filter((s) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      s.subestacao.toLowerCase().includes(q) ||
      s.id_tecnico.includes(q) ||
      s.metricas_rede.nivel_criticidade_gd.toLowerCase().includes(q)
    );
  });

  const handleKeyDownNav = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filtered.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(1, filtered.length));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      e.preventDefault();
      onSelectSubstation(filtered[selectedIndex].id_tecnico);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl rounded-2xl border border-[#2F2F2F] bg-[#0A0A0A] shadow-2xl overflow-hidden double-bezel"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDownNav}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 border-b border-[#202020] bg-[#0F0F0F] px-4 py-3.5">
          <MagnifyingGlass size={18} className="text-[#FFD400]" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Buscar por subestação, ID técnico ou status... (Ex: SUBESTA1, 3029)"
            className="flex-1 bg-transparent text-sm font-mono text-white placeholder:text-[#666666] outline-none"
          />
          <kbd className="hidden sm:inline-block rounded border border-[#2B2B2B] bg-[#141414] px-1.5 py-0.5 font-mono text-[0.65rem] text-[#8A8A8A]">
            ESC
          </kbd>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-[#8A8A8A] hover:text-white"
          >
            <X size={16} />
          </button>
        </div>

        {/* Results Stream */}
        <div className="max-h-80 overflow-y-auto divide-y divide-[#181818] p-2">
          {filtered.length > 0 ? (
            filtered.map((sub, idx) => {
              const isSelected = idx === selectedIndex;
              const cleanName = sub.subestacao.split(" (ID:")[0];

              return (
                <div
                  key={sub.id_tecnico}
                  onClick={() => {
                    onSelectSubstation(sub.id_tecnico);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex cursor-pointer items-center justify-between rounded-xl px-3.5 py-2.5 transition-colors ${
                    isSelected ? "bg-[#FFD400]/10 text-white" : "hover:bg-[#141414] text-[#CCCCCC]"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`flex h-8 w-8 items-center justify-center rounded-lg border text-sm ${
                        isSelected
                          ? "border-[#FFD400]/40 bg-[#FFD400]/20 text-[#FFD400]"
                          : "border-[#222222] bg-[#121212] text-[#8A8A8A]"
                      }`}
                    >
                      <Lightning size={16} weight={isSelected ? "fill" : "regular"} />
                    </span>
                    <div>
                      <strong className={`block font-display text-xs ${isSelected ? "text-[#FFD400]" : "text-white"}`}>
                        {cleanName}
                      </strong>
                      <span className="font-mono text-[0.68rem] text-[#8A8A8A]">
                        ID: {sub.id_tecnico} · {sub.metricas_rede.total_clientes} clientes
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs font-semibold text-[#FFD400]">
                      {sub.geracao_distribuida.potencia_total_kw.toFixed(1)} kW
                    </span>
                    <StatusPill
                      label={sub.metricas_rede.nivel_criticidade_gd}
                      size="sm"
                    />
                    <CaretRight
                      size={14}
                      className={isSelected ? "text-[#FFD400]" : "text-transparent"}
                    />
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-8 text-center font-mono text-xs text-[#8A8A8A]">
              Nenhum ativo encontrado para "{query}".
            </div>
          )}
        </div>

        {/* Footer Navigation Hints */}
        <div className="flex items-center justify-between border-t border-[#1C1C1C] bg-[#0A0A0A] px-4 py-2 font-mono text-[0.66rem] text-[#777777]">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-[#2B2B2B] bg-[#141414] px-1 py-0.5">↑</kbd>
              <kbd className="rounded border border-[#2B2B2B] bg-[#141414] px-1 py-0.5">↓</kbd>
              Navegar
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-[#2B2B2B] bg-[#141414] px-1 py-0.5">Enter</kbd>
              Selecionar
            </span>
          </div>
          <span>{filtered.length} Ativos Encontrados</span>
        </div>
      </div>
    </div>
  );
};
