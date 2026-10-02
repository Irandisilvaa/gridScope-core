import React, { useEffect, useRef, useState } from "react";
import { CaretDown, IdentificationBadge, SignOut, User } from "@phosphor-icons/react";
import type { UserProfile } from "../../types/auth";

interface OperatorBadgeProps {
  user: UserProfile | null;
  onOpenAuth: () => void;
  onLogout: () => void;
}

export const OperatorBadge: React.FC<OperatorBadgeProps> = ({ user, onOpenAuth, onLogout }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    };
    if (menuOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  if (!user) {
    return (
      <button
        type="button"
        onClick={onOpenAuth}
        className="flex items-center gap-2 rounded-xl border border-grid-yellow/40 bg-grid-yellow/10 px-3.5 py-2 font-mono text-xs font-bold text-grid-yellow transition-all hover:border-grid-yellow hover:bg-grid-yellow/20 active:scale-95"
      >
        <User size={15} weight="bold" />
        <span>Entrar</span>
      </button>
    );
  }

  const roleLabel = user.role === "admin" ? "Admin Geral" : "Operador GridScope";

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setMenuOpen((open) => !open)}
        className="flex items-center gap-2 rounded-xl border border-grid-border-card bg-grid-surface-raised px-3 py-1.5 transition-all hover:border-grid-yellow active:scale-95"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-grid-yellow/30 bg-grid-yellow/15 text-grid-yellow">
          <IdentificationBadge size={16} />
        </div>
        <div className="text-left">
          <span className="block max-w-[130px] truncate font-mono text-[0.68rem] font-bold leading-none text-white">{user.name}</span>
          <span className="mt-0.5 block font-mono text-[0.6rem] text-grid-gray-muted">{roleLabel}</span>
        </div>
        <CaretDown size={12} className={`text-grid-gray-muted transition-transform ${menuOpen ? "rotate-180" : ""}`} />
      </button>

      {menuOpen && (
        <div className="absolute right-0 top-full z-50 mt-2 w-64 rounded-xl border border-grid-surface-border bg-grid-surface p-3 text-xs shadow-2xl animate-fadeIn">
          <div className="mb-2 border-b border-grid-border-subtle pb-2.5">
            <div className="truncate font-display font-semibold text-white">{user.name}</div>
            <div className="truncate font-mono text-[0.68rem] text-grid-gray">{user.email}</div>
            <div className="mt-1 flex items-center gap-1 font-mono text-[0.65rem] text-status-success">
              <span className="h-1.5 w-1.5 rounded-full bg-status-success" />
              <span>Sessão autenticada</span>
            </div>
          </div>
          <div className="space-y-1">
            <div className="flex items-center justify-between px-2 py-1 font-mono text-[0.65rem] text-grid-gray-muted">
              <span>Perfil:</span>
              <span className="text-grid-gray-subtle">{roleLabel}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                onLogout();
              }}
              className="mt-2 flex w-full items-center gap-2 rounded-lg border border-status-danger/30 bg-status-danger/10 px-2.5 py-1.5 font-mono text-xs text-status-danger transition-colors hover:bg-status-danger/20"
            >
              <SignOut size={14} />
              <span>Encerrar sessão</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
