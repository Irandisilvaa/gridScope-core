import React, { useState } from "react";
import { ArrowRight, CircleNotch, EnvelopeSimple, Eye, EyeSlash, Lock, WarningCircle } from "@phosphor-icons/react";
import type { LoginCredentials, UserProfile } from "../../types/auth";
import { authService } from "../../lib/authService";

interface LoginFormProps {
  onSuccess: (user: UserProfile) => void;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onSuccess }) => {
  const [credentials, setCredentials] = useState<LoginCredentials>({ email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const result = await authService.login(credentials);
      if (result.success && result.user) {
        onSuccess(result.user);
      } else {
        setErrorMessage(result.error || "Falha na autenticação. Verifique suas credenciais.");
      }
    } catch {
      setErrorMessage("Erro de comunicação com o serviço de segurança.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {errorMessage && (
        <div className="flex items-start gap-2.5 rounded-xl border border-status-danger/40 bg-status-danger/10 p-3 text-xs text-status-danger animate-fadeIn">
          <WarningCircle size={16} className="mt-0.5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <div>
        <label className="mb-1.5 block font-mono text-[0.7rem] uppercase tracking-wider text-grid-gray-light">E-mail Corporativo</label>
        <div className="relative">
          <EnvelopeSimple size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-grid-gray-muted" />
          <input
            type="email"
            required
            autoComplete="email"
            value={credentials.email}
            onChange={(event) => setCredentials({ ...credentials, email: event.target.value })}
            placeholder="operador@distribuidora.com.br"
            className="w-full rounded-xl border border-grid-border-card bg-grid-surface-raised py-2.5 pl-10 pr-4 font-mono text-xs text-grid-white placeholder:text-grid-gray-dim transition-colors focus:border-grid-yellow focus:outline-none focus:ring-1 focus:ring-grid-yellow/40"
          />
        </div>
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <label className="font-mono text-[0.7rem] uppercase tracking-wider text-grid-gray-light">Senha de Acesso</label>
          <span className="font-mono text-[0.68rem] text-grid-gray-dim">Redefinição pelo administrador</span>
        </div>
        <div className="relative">
          <Lock size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-grid-gray-muted" />
          <input
            type={showPassword ? "text" : "password"}
            required
            autoComplete="current-password"
            value={credentials.password}
            onChange={(event) => setCredentials({ ...credentials, password: event.target.value })}
            placeholder="••••••••••••"
            className="w-full rounded-xl border border-grid-border-card bg-grid-surface-raised py-2.5 pl-10 pr-10 font-mono text-xs text-grid-white placeholder:text-grid-gray-dim transition-colors focus:border-grid-yellow focus:outline-none focus:ring-1 focus:ring-grid-yellow/40"
          />
          <button
            type="button"
            onClick={() => setShowPassword((visible) => !visible)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-grid-gray-muted transition-colors hover:text-white"
            title={showPassword ? "Ocultar senha" : "Ver senha"}
          >
            {showPassword ? <EyeSlash size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-grid-yellow py-3 font-display text-xs font-bold text-black energy-glow transition-all hover:bg-grid-yellow-hover disabled:opacity-50"
      >
        {isLoading ? (
          <>
            <CircleNotch size={16} className="animate-spin" />
            <span>Validando credenciais...</span>
          </>
        ) : (
          <>
            <span>Acessar Plataforma GridScope</span>
            <ArrowRight size={16} weight="bold" />
          </>
        )}
      </button>

      <p className="pt-2 text-center font-mono text-[0.68rem] leading-relaxed text-grid-gray-dim">
        O acesso é provisionado exclusivamente por um administrador do GridScope.
      </p>
    </form>
  );
};
