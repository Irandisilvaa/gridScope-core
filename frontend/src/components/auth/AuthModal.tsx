import React, { useState, useEffect } from "react";
import { X, ShieldCheck, LockKey } from "@phosphor-icons/react";
import { BrandSymbol } from "../BrandLogo";
import type { AuthMode, UserProfile } from "../../types/auth";
import { LoginForm } from "./LoginForm";
import { RegisterForm } from "./RegisterForm";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthenticated: (user: UserProfile) => void;
  initialMode?: AuthMode;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onAuthenticated,
  initialMode = "login",
}) => {
  const [mode, setMode] = useState<AuthMode>(initialMode);

  // Sync mode if initialMode changes
  useEffect(() => {
    setMode(initialMode);
  }, [initialMode, isOpen]);

  // Trap Escape key
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

  const handleSuccess = (user: UserProfile) => {
    onAuthenticated(user);
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fadeIn"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-lg rounded-2xl border border-[#262626] bg-[#0A0A0A] p-6 sm:p-8 shadow-[0_0_50px_rgba(0,0,0,0.9)] max-h-[92vh] overflow-y-auto"
        style={{
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.85), 0 0 40px rgba(255, 212, 0, 0.08)",
        }}
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-lg border border-[#242424] bg-[#141414] text-[#8A8A8A] transition-colors hover:border-[#FFD400] hover:text-white"
          title="Fechar (Esc)"
        >
          <X size={16} />
        </button>

        {/* Modal Brand Header */}
        <div className="flex flex-col items-center text-center">
          <div className="flex items-center justify-center">
            <BrandSymbol size={44} animated />
          </div>

          <div className="mt-2.5 flex items-center gap-1.5 font-mono text-[0.68rem] font-bold uppercase tracking-[0.2em] text-[#FFD400]">
            <LockKey size={13} weight="bold" />
            <span>CENTRO DE CONTROLE OPERACIONAL</span>
          </div>

          <h2
            id="auth-modal-title"
            className="mt-1 font-display text-xl font-bold tracking-tight text-white sm:text-2xl"
          >
            {mode === "login" ? "Acesso à Estação GridScope" : "Cadastro de Novo Operador"}
          </h2>

          <p className="mt-1 font-mono text-xs text-[#777777]">
            {mode === "login"
              ? "Autenticação criptografada de operadores e engenheiros de rede"
              : "Habilitação técnica com auditoria de conformidade regulatória"}
          </p>
        </div>

        {/* Tab Switcher: Entrar vs Criar Cadastro */}
        <div className="mt-6 mb-5 grid grid-cols-2 rounded-xl border border-[#222222] bg-[#101010] p-1">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`rounded-lg py-2 font-display text-xs font-semibold transition-all ${
              mode === "login"
                ? "bg-[#FFD400] text-black shadow-[0_0_12px_rgba(255,212,0,0.35)]"
                : "text-[#8A8A8A] hover:text-white"
            }`}
          >
            Entrar (Login)
          </button>

          <button
            type="button"
            onClick={() => setMode("register")}
            className={`rounded-lg py-2 font-display text-xs font-semibold transition-all ${
              mode === "register"
                ? "bg-[#FFD400] text-black shadow-[0_0_12px_rgba(255,212,0,0.35)]"
                : "text-[#8A8A8A] hover:text-white"
            }`}
          >
            Criar Cadastro
          </button>
        </div>

        {/* Dynamic Form Area */}
        <div className="mt-2">
          {mode === "login" ? (
            <LoginForm
              onSuccess={handleSuccess}
              onSwitchToRegister={() => setMode("register")}
            />
          ) : (
            <RegisterForm
              onSuccess={handleSuccess}
              onSwitchToLogin={() => setMode("login")}
            />
          )}
        </div>

        {/* Security & Regulatory Compliance Footer */}
        <div className="mt-6 border-t border-[#1C1C1C] pt-4 text-center">
          <div className="flex items-center justify-center gap-2 font-mono text-[0.62rem] text-[#666666]">
            <ShieldCheck size={14} className="text-[#FFD400]" />
            <span>CRIPTOGRAFIA AES-256 · PADRÃO DE AUDITORIA NERC-CIP / ONS</span>
          </div>
          <div className="mt-1 font-mono text-[0.58rem] text-[#444444]">
            GridScope Security Gateway v2.4 · Todos os acessos são registrados e correlacionados
          </div>
        </div>
      </div>
    </div>
  );
};
