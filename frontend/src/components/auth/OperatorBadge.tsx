import React, { useState, useRef, useEffect } from "react";
import { User, SignOut, ShieldCheck, CaretDown, IdentificationBadge } from "@phosphor-icons/react";
import type { UserProfile } from "../../types/auth";

interface OperatorBadgeProps {
  user: UserProfile | null;
  onOpenAuth: () => void;
  onLogout: () => void;
}

export const OperatorBadge: React.FC<OperatorBadgeProps> = ({ user, onOpenAuth, onLogout }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  if (!user) {
    return (
      <button
        type="button"
        onClick={onOpenAuth}
        className="flex items-center gap-2 rounded-xl border border-[#FFD400]/40 bg-[#FFD400]/10 px-3.5 py-2 font-mono text-xs font-bold text-[#FFD400] transition-all hover:bg-[#FFD400]/20 hover:border-[#FFD400] active:scale-95 shadow-[0_0_12px_rgba(255,212,0,0.15)]"
      >
        <User size={15} weight="bold" />
        <span>Entrar / Cadastrar</span>
      </button>
    );
  }

  const roleLabels: Record<string, string> = {
    admin: "Admin Geral",
    engineer: "Eng. Operação",
    analyst: "Analista GD",
    operator: "Operador Despacho",
  };

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setMenuOpen(!menuOpen)}
        className="flex items-center gap-2 rounded-xl border border-[#2B2B2B] bg-[#121212] px-3 py-1.5 transition-all hover:border-[#FFD400] active:scale-95"
      >
        {/* Operator Status Pill */}
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#FFD400]/15 text-[#FFD400] font-mono text-xs font-bold border border-[#FFD400]/30">
          <IdentificationBadge size={16} />
        </div>

        <div className="text-left">
          <div className="flex items-center gap-1.5 font-mono text-[0.68rem] leading-none">
            <span className="font-bold text-white truncate max-w-[110px]">{user.name.split(" ")[0]}</span>
            <span className="rounded bg-[#FFD400]/20 px-1 py-0.2 text-[0.6rem] font-bold text-[#FFD400]">
              {user.technicalId}
            </span>
          </div>
          <span className="font-mono text-[0.6rem] text-[#777777] block mt-0.5">
            {roleLabels[user.role] || user.role}
          </span>
        </div>

        <CaretDown size={12} className={`text-[#777777] transition-transform ${menuOpen ? "rotate-180" : ""}`} />
      </button>

      {/* Operator Dropdown Menu */}
      {menuOpen && (
        <div className="absolute right-0 top-full mt-2 w-64 rounded-xl border border-[#242424] bg-[#0E0E0E] p-3 shadow-2xl z-50 animate-fadeIn text-xs">
          <div className="border-b border-[#1E1E1E] pb-2.5 mb-2">
            <div className="font-display font-semibold text-white truncate">{user.name}</div>
            <div className="font-mono text-[0.68rem] text-[#8A8A8A] truncate">{user.email}</div>
            <div className="mt-1 flex items-center gap-1 text-[0.65rem] text-[#22C55E]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#22C55E]" />
              <span>Sessão Autenticada · {user.department}</span>
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between py-1 px-2 font-mono text-[0.65rem] text-[#777777]">
              <span>ID Técnico:</span>
              <span className="text-[#FFD400] font-bold">{user.technicalId}</span>
            </div>

            <div className="flex items-center justify-between py-1 px-2 font-mono text-[0.65rem] text-[#777777]">
              <span>Nível de Acesso:</span>
              <span className="text-[#CCCCCC]">{roleLabels[user.role]}</span>
            </div>

            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onLogout();
              }}
              className="mt-2 flex w-full items-center gap-2 rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-2.5 py-1.5 font-mono text-xs text-[#EF4444] transition-colors hover:bg-[#EF4444]/20"
            >
              <SignOut size={14} />
              <span>Encerrar Sessão Operacional</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
