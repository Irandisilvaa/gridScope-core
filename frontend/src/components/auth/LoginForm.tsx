import React, { useState } from "react";
import {
  EnvelopeSimple,
  Lock,
  Eye,
  EyeSlash,
  ArrowRight,
  CircleNotch,
  WarningCircle,
  ShieldCheck,
  UserCheck,
} from "@phosphor-icons/react";
import type { LoginCredentials, UserProfile } from "../../types/auth";
import { authService } from "../../lib/authService";

interface LoginFormProps {
  onSuccess: (user: UserProfile) => void;
  onSwitchToRegister: () => void;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onSuccess, onSwitchToRegister }) => {
  const [credentials, setCredentials] = useState<LoginCredentials>({
    email: "",
    password: "",
    rememberMe: true,
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsLoading(true);

    try {
      const res = await authService.login(credentials);
      if (res.success && res.user) {
        onSuccess(res.user);
      } else {
        setErrorMessage(res.error || "Falha na autenticação. Verifique suas credenciais.");
      }
    } catch {
      setErrorMessage("Erro de comunicação com o serviço de segurança.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickFill = (email: string) => {
    setCredentials((prev) => ({
      ...prev,
      email,
      password: "password123@",
    }));
    setErrorMessage(null);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {errorMessage && (
        <div className="flex items-start gap-2.5 rounded-xl border border-[#EF4444]/40 bg-[#EF4444]/10 p-3 text-xs text-[#EF4444] animate-fadeIn">
          <WarningCircle size={16} className="shrink-0 mt-0.5 text-[#EF4444]" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Field: E-mail / ID Técnico */}
      <div>
        <label className="mb-1.5 block font-mono text-[0.7rem] uppercase tracking-wider text-[#A0A0A0]">
          E-mail Corporativo ou ID Técnico
        </label>
        <div className="relative">
          <EnvelopeSimple
            size={18}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#777777]"
          />
          <input
            type="text"
            required
            autoComplete="username"
            value={credentials.email}
            onChange={(e) => setCredentials({ ...credentials, email: e.target.value })}
            placeholder="ex: operador@gridscope.com ou OP-4821"
            className="w-full rounded-xl border border-[#2B2B2B] bg-[#121212] py-2.5 pl-10 pr-4 font-mono text-xs text-white placeholder:text-[#555555] transition-colors focus:border-[#FFD400] focus:outline-none focus:ring-1 focus:ring-[#FFD400]/40"
          />
        </div>
      </div>

      {/* Field: Senha */}
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <label className="font-mono text-[0.7rem] uppercase tracking-wider text-[#A0A0A0]">
            Senha de Acesso
          </label>
          <button
            type="button"
            onClick={() =>
              alert(
                "Em ambiente operacional, a redefinição de chave de acesso deve ser solicitada à Superintendência de Segurança da Informação (TI/COI)."
              )
            }
            className="font-mono text-[0.68rem] text-[#FFD400]/80 transition-colors hover:text-[#FFD400] hover:underline"
          >
            Esqueceu a chave?
          </button>
        </div>
        <div className="relative">
          <Lock
            size={18}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#777777]"
          />
          <input
            type={showPassword ? "text" : "password"}
            required
            autoComplete="current-password"
            value={credentials.password}
            onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
            placeholder="••••••••••••"
            className="w-full rounded-xl border border-[#2B2B2B] bg-[#121212] py-2.5 pl-10 pr-10 font-mono text-xs text-white placeholder:text-[#555555] transition-colors focus:border-[#FFD400] focus:outline-none focus:ring-1 focus:ring-[#FFD400]/40"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#777777] transition-colors hover:text-white"
            title={showPassword ? "Ocultar senha" : "Ver senha"}
          >
            {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </div>

      {/* Remember Me Option */}
      <div className="flex items-center justify-between pt-1">
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={credentials.rememberMe}
            onChange={(e) => setCredentials({ ...credentials, rememberMe: e.target.checked })}
            className="h-4 w-4 rounded border-[#333333] bg-[#141414] text-[#FFD400] focus:ring-[#FFD400] focus:ring-offset-0 accent-[#FFD400]"
          />
          <span className="font-mono text-[0.72rem] text-[#8A8A8A]">
            Manter sessão ativa neste terminal
          </span>
        </label>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isLoading}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#FFD400] py-3 font-display text-xs font-bold text-black shadow-[0_0_20px_rgba(255,212,0,0.3)] transition-all hover:bg-[#ffe033] hover:shadow-[0_0_25px_rgba(255,212,0,0.45)] active:scale-[0.99] disabled:opacity-50"
      >
        {isLoading ? (
          <>
            <CircleNotch size={16} className="animate-spin text-black" />
            <span>Validando Credenciais Operacionais...</span>
          </>
        ) : (
          <>
            <span>Acessar Plataforma GridScope</span>
            <ArrowRight size={16} weight="bold" />
          </>
        )}
      </button>

      {/* Quick Demo Operator Logins */}
      <div className="pt-2">
        <span className="block font-mono text-[0.65rem] uppercase tracking-wider text-[#666666] text-center mb-2">
          Atalhos de Acesso Rápido (Demonstração)
        </span>
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => handleQuickFill("operador@gridscope.com")}
            className="flex flex-col items-center gap-1 rounded-lg border border-[#222222] bg-[#101010] p-2 text-center transition-colors hover:border-[#FFD400]/40 hover:bg-[#181818]"
          >
            <UserCheck size={14} className="text-[#FFD400]" />
            <span className="font-mono text-[0.65rem] text-[#CCCCCC]">Operador</span>
            <span className="font-mono text-[0.55rem] text-[#777777]">Proteção</span>
          </button>

          <button
            type="button"
            onClick={() => handleQuickFill("analista@gridscope.com")}
            className="flex flex-col items-center gap-1 rounded-lg border border-[#222222] bg-[#101010] p-2 text-center transition-colors hover:border-[#FFD400]/40 hover:bg-[#181818]"
          >
            <ShieldCheck size={14} className="text-[#3B82F6]" />
            <span className="font-mono text-[0.65rem] text-[#CCCCCC]">Analista</span>
            <span className="font-mono text-[0.55rem] text-[#777777]">Planejamento</span>
          </button>

          <button
            type="button"
            onClick={() => handleQuickFill("admin@gridscope.com")}
            className="flex flex-col items-center gap-1 rounded-lg border border-[#222222] bg-[#101010] p-2 text-center transition-colors hover:border-[#FFD400]/40 hover:bg-[#181818]"
          >
            <ShieldCheck size={14} className="text-[#22C55E]" />
            <span className="font-mono text-[0.65rem] text-[#CCCCCC]">Supervisão</span>
            <span className="font-mono text-[0.55rem] text-[#777777]">ONS Master</span>
          </button>
        </div>
      </div>

      {/* Switch to Register */}
      <div className="pt-2 text-center font-mono text-xs text-[#8A8A8A]">
        Novo operador do sistema?{" "}
        <button
          type="button"
          onClick={onSwitchToRegister}
          className="font-bold text-[#FFD400] transition-colors hover:underline"
        >
          Criar cadastro operacional
        </button>
      </div>
    </form>
  );
};
