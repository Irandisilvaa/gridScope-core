import React from "react";
import { Check, DotOutline } from "@phosphor-icons/react";
import { authService } from "../../lib/authService";

interface PasswordStrengthMeterProps {
  password: string;
}

export const PasswordStrengthMeter: React.FC<PasswordStrengthMeterProps> = ({ password }) => {
  if (!password) return null;

  const strength = authService.checkPasswordStrength(password);

  return (
    <div className="mt-2 space-y-2 rounded-xl border border-[#222222] bg-[#0E0E0E] p-3 text-xs">
      <div className="flex items-center justify-between font-mono text-[0.68rem]">
        <span className="text-[#8A8A8A]">Segurança da Credencial:</span>
        <span style={{ color: strength.color }} className="font-bold">
          {strength.label}
        </span>
      </div>

      {/* Segmented Strength Bar */}
      <div className="grid grid-cols-4 gap-1.5">
        {[0, 1, 2, 3].map((step) => {
          const active = step < strength.score;
          return (
            <div
              key={step}
              className="h-1.5 rounded-full transition-all duration-300"
              style={{
                backgroundColor: active ? strength.color : "#222222",
                boxShadow: active ? `0 0 6px ${strength.color}40` : "none",
              }}
            />
          );
        })}
      </div>

      {/* Validation Checklist */}
      <div className="grid grid-cols-2 gap-1.5 pt-1">
        {strength.rules.map((rule) => (
          <div
            key={rule.id}
            className={`flex items-center gap-1.5 font-mono text-[0.65rem] transition-colors ${
              rule.passed ? "text-[#22C55E]" : "text-[#666666]"
            }`}
          >
            {rule.passed ? (
              <Check size={12} weight="bold" className="shrink-0 text-[#22C55E]" />
            ) : (
              <DotOutline size={12} weight="fill" className="shrink-0 text-[#444444]" />
            )}
            <span>{rule.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
