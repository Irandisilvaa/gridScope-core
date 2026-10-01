import React, { useState } from "react";
import {
  User,
  EnvelopeSimple,
  Briefcase,
  Lock,
  Eye,
  EyeSlash,
  ArrowRight,
  CircleNotch,
  WarningCircle,
  Buildings,
} from "@phosphor-icons/react";
import type { OperatorRole, RegisterCredentials, UserProfile } from "../../types/auth";
import { authService } from "../../lib/authService";
import { PasswordStrengthMeter } from "./PasswordStrengthMeter";

interface RegisterFormProps {
  onSuccess: (user: UserProfile) => void;
  onSwitchToLogin: () => void;
}

export const RegisterForm: React.FC<RegisterFormProps> = ({ onSuccess, onSwitchToLogin }) => {
  const [credentials, setCredentials] = useState<RegisterCredentials>({
    name: "",
    email: "",
    department: "",
    role: "engineer",
    password: "",
    confirmPassword: "",
    acceptTerms: false,
  });

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (credentials.password !== credentials.confirmPassword) {
      setErrorMessage("A confirmação de senha não corresponde à senha informada.");
      return;
    }

    if (!credentials.acceptTerms) {
      setErrorMessage("É obrigatório concordar com o protocolo de conformidade NERC-CIP / ONS.");
      return;
    }

    setIsLoading(true);

    try {
      const res = await authService.register(credentials);
      if (res.success && res.user) {
        onSuccess(res.user);
      } else {
        setErrorMessage(res.error || "Não foi possível completar o cadastro.");
      }
    } catch {
      setErrorMessage("Erro de comunicação com o serviço de segurança.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3.5">
      {errorMessage && (
        <div className="flex items-start gap-2.5 rounded-xl border border-[#EF4444]/40 bg-[#EF4444]/10 p-3 text-xs text-[#EF4444] animate-fadeIn">
          <WarningCircle size={16} className="shrink-0 mt-0.5 text-[#EF4444]" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Field: Nome Completo */}
      <div>
        <label className="mb-1 block font-mono text-[0.68rem] uppercase tracking-wider text-[#A0A0A0]">
          Nome Completo do Operador
        </label>
        <div className="relative">
          <User
            size={16}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#777777]"
          />
          <input
            type="text"
            required
            value={credentials.name}
            onChange={(e) => setCredentials({ ...credentials, name: e.target.value })}
            placeholder="ex: Dr. Carlos Eduardo Mendonça"
            className="w-full rounded-xl border border-[#2B2B2B] bg-[#121212] py-2 pl-9 pr-4 font-mono text-xs text-white placeholder:text-[#555555] transition-colors focus:border-[#FFD400] focus:outline-none focus:ring-1 focus:ring-[#FFD400]/40"
          />
        </div>
      </div>

      {/* Field: E-mail Corporativo */}
      <div>
        <label className="mb-1 block font-mono text-[0.68rem] uppercase tracking-wider text-[#A0A0A0]">
          E-mail Corporativo
        </label>
        <div className="relative">
          <EnvelopeSimple
            size={16}
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[#777777]"
          />
          <input
            type="email"
            required
            value={credentials.email}
            onChange={(e) => setCredentials({ ...credentials, email: e.target.value })}
            placeholder="carlos.mendonca@distribuidora.com.br"
            className="w-full rounded-xl border border-[#2B2B2B] bg-[#121212] py-2 pl-9 pr-4 font-mono text-xs text-white placeholder:text-[#555555] transition-colors focus:border-[#FFD400] focus:outline-none focus:ring-1 focus:ring-[#FFD400]/40"
          />
        </div>
      </div>

      {/* Row: Role & Department */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div>
          <label className="mb-1 block font-mono text-[0.68rem] uppercase tracking-wider text-[#A0A0A0]">
            Perfil Operacional
          </label>
          <div className="relative">
            <Briefcase
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#777777]"
            />
            <select
              value={credentials.role}
              onChange={(e) =>
                setCredentials({ ...credentials, role: e.target.value as OperatorRole })
              }
              className="w-full rounded-xl border border-[#2B2B2B] bg-[#121212] py-2 pl-8 pr-3 font-mono text-xs text-white transition-colors focus:border-[#FFD400] focus:outline-none focus:ring-1 focus:ring-[#FFD400]/40"
            >
              <option value="engineer">Engenheiro de Operação</option>
              <option value="analyst">Analista de GD / Rede</option>
              <option value="operator">Operador de Despacho</option>
              <option value="admin">Administrador Geral</option>
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block font-mono text-[0.68rem] uppercase tracking-wider text-[#A0A0A0]">
            Setor / Gerência
          </label>
          <div className="relative">
            <Buildings
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#777777]"
            />
            <input
              type="text"
              required
              value={credentials.department}
              onChange={(e) => setCredentials({ ...credentials, department: e.target.value })}
              placeholder="ex: COI / Planejamento"
              className="w-full rounded-xl border border-[#2B2B2B] bg-[#121212] py-2 pl-8 pr-3 font-mono text-xs text-white placeholder:text-[#555555] transition-colors focus:border-[#FFD400] focus:outline-none focus:ring-1 focus:ring-[#FFD400]/40"
            />
          </div>
        </div>
      </div>

      {/* Row: Password & Confirm */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div>
          <label className="mb-1 block font-mono text-[0.68rem] uppercase tracking-wider text-[#A0A0A0]">
            Senha de Acesso
          </label>
          <div className="relative">
            <Lock
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#777777]"
            />
            <input
              type={showPassword ? "text" : "password"}
              required
              value={credentials.password}
              onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
              placeholder="Mín. 8 caracteres"
              className="w-full rounded-xl border border-[#2B2B2B] bg-[#121212] py-2 pl-8 pr-8 font-mono text-xs text-white placeholder:text-[#555555] transition-colors focus:border-[#FFD400] focus:outline-none focus:ring-1 focus:ring-[#FFD400]/40"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#777777] transition-colors hover:text-white"
            >
              {showPassword ? <EyeSlash size={14} /> : <Eye size={14} />}
            </button>
          </div>
        </div>

        <div>
          <label className="mb-1 block font-mono text-[0.68rem] uppercase tracking-wider text-[#A0A0A0]">
            Confirmar Senha
          </label>
          <div className="relative">
            <Lock
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#777777]"
            />
            <input
              type={showConfirmPassword ? "text" : "password"}
              required
              value={credentials.confirmPassword}
              onChange={(e) => setCredentials({ ...credentials, confirmPassword: e.target.value })}
              placeholder="Repita a senha"
              className="w-full rounded-xl border border-[#2B2B2B] bg-[#121212] py-2 pl-8 pr-8 font-mono text-xs text-white placeholder:text-[#555555] transition-colors focus:border-[#FFD400] focus:outline-none focus:ring-1 focus:ring-[#FFD400]/40"
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#777777] transition-colors hover:text-white"
            >
              {showConfirmPassword ? <EyeSlash size={14} /> : <Eye size={14} />}
            </button>
          </div>
        </div>
      </div>

      {/* Password Strength Feedback */}
      <PasswordStrengthMeter password={credentials.password} />

      {/* Accept Terms */}
      <div className="pt-1">
        <label className="flex items-start gap-2.5 cursor-pointer select-none">
          <input
            type="checkbox"
            required
            checked={credentials.acceptTerms}
            onChange={(e) => setCredentials({ ...credentials, acceptTerms: e.target.checked })}
            className="mt-0.5 h-4 w-4 rounded border-[#333333] bg-[#141414] text-[#FFD400] focus:ring-[#FFD400] focus:ring-offset-0 accent-[#FFD400]"
          />
          <span className="font-mono text-[0.68rem] leading-relaxed text-[#8A8A8A]">
            Declaro responsabilidade técnica e concordância com os termos de sigilo e auditoria
            operacional da rede elétrica (Resolução Normativa ANEEL / ONS).
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
            <span>Processando Cadastro Operacional...</span>
          </>
        ) : (
          <>
            <span>Cadastrar Operador no GridScope</span>
            <ArrowRight size={16} weight="bold" />
          </>
        )}
      </button>

      {/* Switch to Login */}
      <div className="pt-1 text-center font-mono text-xs text-[#8A8A8A]">
        Já possui credencial ativa?{" "}
        <button
          type="button"
          onClick={onSwitchToLogin}
          className="font-bold text-[#FFD400] transition-colors hover:underline"
        >
          Fazer login
        </button>
      </div>
    </form>
  );
};
