import React, { useEffect } from "react";
import { LockKey, ShieldCheck, X } from "@phosphor-icons/react";
import { BrandSymbol } from "../BrandLogo";
import type { UserProfile } from "../../types/auth";
import { LoginForm } from "./LoginForm";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthenticated: (user: UserProfile) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onAuthenticated }) => {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-md animate-fadeIn"
      onClick={onClose}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        className="relative max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-grid-border bg-grid-surface p-6 shadow-2xl sm:p-8"
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-lg border border-grid-surface-border bg-grid-surface-elevated text-grid-gray transition-colors hover:border-grid-yellow hover:text-white"
          title="Fechar (Esc)"
        >
          <X size={16} />
        </button>

        <div className="flex flex-col items-center text-center">
          <BrandSymbol size={44} animated />
          <div className="mt-2.5 flex items-center gap-1.5 font-mono text-[0.68rem] font-bold uppercase tracking-[0.2em] text-grid-yellow">
            <LockKey size={13} weight="bold" />
            <span>CENTRO DE CONTROLE OPERACIONAL</span>
          </div>
          <h2 id="auth-modal-title" className="mt-1 font-display text-xl font-bold tracking-tight text-white sm:text-2xl">
            Acesso à Estação GridScope
          </h2>
          <p className="mt-1 font-mono text-xs text-grid-gray-muted">
            Autenticação criptografada de operadores e engenheiros de rede
          </p>
        </div>

        <div className="mt-6">
          <LoginForm onSuccess={onAuthenticated} />
        </div>

        <div className="mt-6 border-t border-grid-border-subtle pt-4 text-center">
          <div className="flex items-center justify-center gap-2 font-mono text-[0.62rem] text-grid-gray-dim">
            <ShieldCheck size={14} className="text-grid-yellow" />
            <span>ACESSO CONTROLADO · SESSÕES AUDITÁVEIS</span>
          </div>
          <div className="mt-1 font-mono text-[0.58rem] text-grid-gray-dark">
            Usuários são provisionados exclusivamente por administradores.
          </div>
        </div>
      </div>
    </div>
  );
};
