import React, { useEffect } from "react";
import type { Substation, Territories } from "../lib/api";
import { TerritoryMap } from "./TerritoryMap";
import { X, GlobeHemisphereWest } from "@phosphor-icons/react";

/**
 * Interface Segregation Principle (ISP):
 * Minimal, strongly typed contract for the modal presentation layer.
 */
export interface TerritoryMapModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: Territories;
  substations?: Substation[];
  selectedId?: string | null;
  onSelectSubstation?: (id: string) => void;
}

/**
 * TerritoryMapModal
 * 
 * Follows Single Responsibility Principle (SRP):
 * Manages full-screen modal lifecycle, backdrop, keyboard ESC trap, and edge-to-edge layout.
 */
export const TerritoryMapModal: React.FC<TerritoryMapModalProps> = ({
  isOpen,
  onClose,
  data,
  substations = [],
  selectedId = null,
  onSelectSubstation,
}) => {
  // Keyboard shortcut: ESC closes modal
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="territory-map-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/90 backdrop-blur-xl animate-in fade-in duration-200"
      onClick={onClose}
    >
      {/* Modal Dialog Body (Nearly full-screen size: 97vw x 94vh) */}
      <div
        className="relative flex flex-col w-full max-w-[97vw] h-[94vh] rounded-3xl border border-[#2B2B2B] bg-[#070707] shadow-2xl double-bezel overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Top Header Bar */}
        <div className="flex items-center justify-between border-b border-[#1C1C1C] bg-[#0D0D0D] px-5 py-3 text-xs shrink-0">
          <div className="flex items-center gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#FFD400]/15 text-[#FFD400]">
              <GlobeHemisphereWest size={16} weight="bold" />
            </span>
            <div>
              <h2
                id="territory-map-modal-title"
                className="font-display text-sm font-bold text-white tracking-wide uppercase"
              >
                Mapeamento Territorial Geoespacial · Vista Expandida
              </h2>
              <span className="font-mono text-[0.66rem] text-[#8A8A8A]">
                Aracaju / Sergipe · {data.features.length} Polígonos de Cobertura Conformal
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-[#2A2A2A] bg-[#141414] px-3 py-1 font-mono text-[0.68rem] text-[#A0A0A0]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#FFD400]" />
              <span>Modo Alta Resolução</span>
            </span>

            {/* Prominent Close Button */}
            <button
              type="button"
              onClick={onClose}
              className="flex items-center gap-1.5 rounded-xl border border-[#2B2B2B] bg-[#161616] px-3 py-1.5 font-mono text-xs font-semibold text-[#CCCCCC] transition-colors hover:border-[#FFD400] hover:bg-[#FFD400] hover:text-black"
              title="Fechar Vista Expandida (Esc)"
            >
              <span>Fechar</span>
              <X size={14} weight="bold" />
            </button>
          </div>
        </div>

        {/* Modal Content Area: Full Height Interactive Map */}
        <div className="relative flex-1 min-h-0 w-full overflow-hidden bg-[#050505]">
          <TerritoryMap
            data={data}
            substations={substations}
            selectedId={selectedId}
            onSelectSubstation={onSelectSubstation}
            isModalView={true}
            onCloseModal={onClose}
          />
        </div>
      </div>
    </div>
  );
};
