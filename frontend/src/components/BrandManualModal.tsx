import React, { useState } from "react";
import { BrandLogo, BrandSymbol } from "./BrandLogo";
import {
  X,
  Copy,
  Check,
  Lightning,
  Sparkle,
  ShieldCheck,
  Warning,
  Eye,
} from "@phosphor-icons/react";

interface BrandManualModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const BrandManualModal: React.FC<BrandManualModalProps> = ({ isOpen, onClose }) => {
  const [copiedHex, setCopiedHex] = useState<string | null>(null);

  if (!isOpen) return null;

  const copyHex = (hex: string) => {
    navigator.clipboard.writeText(hex);
    setCopiedHex(hex);
    setTimeout(() => setCopiedHex(null), 2000);
  };

  const institutionalColors = [
    { name: "Amarelo GridScope", hex: "#FFD400", role: "Energia, destaque e inovação" },
    { name: "Preto GridScope", hex: "#050505", role: "Base, sofisticação e tecnologia" },
    { name: "Branco", hex: "#FFFFFF", role: "Contraste máximo e legibilidade" },
    { name: "Grafite", hex: "#181818", role: "Estrutura e equilíbrio" },
    { name: "Cinza Técnico", hex: "#8A8A8A", role: "Metadados e informações de apoio" },
  ];

  const functionalColors = [
    { name: "Sucesso", hex: "#22C55E", role: "Operação normal e estabilidade" },
    { name: "Atenção / Crítico", hex: "#EF4444", role: "Nível crítico de GD ou erro" },
    { name: "Alerta", hex: "#F59E0B", role: "Avisos e inspeções pendentes" },
    { name: "Informação", hex: "#3B82F6", role: "Dados e sincronizações ativas" },
    { name: "Destaque Telemetria", hex: "#8B5CF6", role: "Clusters e segmentos avançados" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto bg-black/85 backdrop-blur-md">
      <div className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-3xl border border-[#2B2B2B] bg-[#0A0A0A] p-6 shadow-2xl text-white double-bezel">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#202020] pb-4">
          <div className="flex items-center gap-3">
            <BrandLogo variant="symbol" size="sm" />
            <div>
              <h2 className="font-display text-xl font-bold">Manual de Marca & Design System</h2>
              <span className="font-mono text-xs text-[#8A8A8A]">
                GridScope v1.0 · Diretrizes Oficiais de Identidade
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#2A2A2A] bg-[#141414] text-[#8A8A8A] transition-colors hover:border-[#FFD400] hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Content */}
        <div className="space-y-8 py-6 text-sm">
          {/* Section 1: Essência e Conceito */}
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Sparkle size={18} className="text-[#FFD400]" />
              <h3 className="font-display text-base font-semibold text-white">
                01. Essência & Conceito Central
              </h3>
            </div>
            <p className="leading-relaxed text-[#A0A0A0]">
              A <strong className="text-white">GridScope</strong> une <em className="text-[#FFD400] not-italic font-medium">Grid</em> (rede/sistema elétrico) e <em className="text-white not-italic font-medium">Scope</em> (observar, analisar e compreender). Seu propósito é transformar dados do setor elétrico em inteligência preditiva para decisões precisas e uma transição energética equilibrada.
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 pt-2">
              <div className="rounded-xl border border-[#222222] bg-[#121212] p-3 text-center">
                <span className="block font-mono text-[0.66rem] text-[#8A8A8A]">ASSINATURA</span>
                <strong className="mt-1 block font-display text-xs text-[#FFD400]">
                  Dados. Equilíbrio. Futuro.
                </strong>
              </div>
              <div className="rounded-xl border border-[#222222] bg-[#121212] p-3 text-center">
                <span className="block font-mono text-[0.66rem] text-[#8A8A8A]">PERSONALIDADE</span>
                <strong className="mt-1 block font-display text-xs text-white">
                  Tecnológica & Analítica
                </strong>
              </div>
              <div className="rounded-xl border border-[#222222] bg-[#121212] p-3 text-center">
                <span className="block font-mono text-[0.66rem] text-[#8A8A8A]">TOM DE VOZ</span>
                <strong className="mt-1 block font-display text-xs text-white">
                  Técnico · Claro · Confiável
                </strong>
              </div>
              <div className="rounded-xl border border-[#222222] bg-[#121212] p-3 text-center">
                <span className="block font-mono text-[0.66rem] text-[#8A8A8A]">FLUXO NARRATIVO</span>
                <strong className="mt-1 block font-mono text-[0.68rem] text-[#FFD400]">
                  DADOS → FUTURO
                </strong>
              </div>
            </div>
          </section>

          {/* Section 2: O Símbolo e Logotipo */}
          <section className="space-y-4 border-t border-[#202020] pt-6">
            <div className="flex items-center gap-2">
              <Lightning size={18} className="text-[#FFD400]" />
              <h3 className="font-display text-base font-semibold text-white">
                02. Construção do Logotipo & Versões
              </h3>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Principal Fundo Escuro */}
              <div className="rounded-2xl border border-[#2A2A2A] bg-[#050505] p-5 text-center">
                <span className="mb-4 block font-mono text-[0.68rem] uppercase tracking-wider text-[#8A8A8A]">
                  Versão Principal (Fundo Escuro)
                </span>
                <div className="py-4">
                  <BrandLogo variant="full" size="lg" />
                </div>
                <p className="text-[0.72rem] text-[#8A8A8A]">
                  Grid em #FFD400, Scope em Branco com Símbolo Integrado.
                </p>
              </div>

              {/* Versão Positiva (Fundo Claro) */}
              <div className="rounded-2xl border border-[#CCCCCC] bg-[#FFFFFF] p-5 text-center text-black">
                <span className="mb-4 block font-mono text-[0.68rem] uppercase tracking-wider text-[#666666]">
                  Versão Positiva (Fundo Claro)
                </span>
                <div className="py-4 flex items-center justify-center">
                  <div className="inline-flex flex-col select-none">
                    <div className="flex items-center text-3xl leading-none">
                      <span className="font-display font-extrabold text-[#050505]">Grid</span>
                      <span className="font-display font-bold text-[#050505]">Sc</span>
                      <span className="mx-1">
                        <svg width="26" height="26" viewBox="0 0 100 100" fill="none">
                          <circle cx="50" cy="50" r="42" stroke="#050505" strokeWidth="6" strokeDasharray="3 3" />
                          <path d="M 54,16 L 33,52 L 50,52 L 44,84 L 68,48 L 50,48 Z" fill="#FFD400" />
                        </svg>
                      </span>
                      <span className="font-display font-bold text-[#050505]">pe</span>
                    </div>
                    <span className="font-sans font-medium text-[0.66rem] uppercase tracking-[0.24em] text-[#666666] mt-1 text-center">
                      Dados. Equilíbrio. Futuro.
                    </span>
                  </div>
                </div>
                <p className="text-[0.72rem] text-[#666666]">
                  Grid e Scope em Preto com raio em destaque Amarelo.
                </p>
              </div>
            </div>
          </section>

          {/* Section 3: Paleta Institucional e Funcional */}
          <section className="space-y-4 border-t border-[#202020] pt-6">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#FFD400]" />
              <h3 className="font-display text-base font-semibold text-white">
                03. Paleta de Cores Oficial
              </h3>
            </div>

            <div>
              <span className="font-mono text-xs uppercase tracking-wider text-[#8A8A8A]">
                Cores Institucionais
              </span>
              <div className="mt-2 grid grid-cols-2 sm:grid-cols-5 gap-3">
                {institutionalColors.map((c) => (
                  <div
                    key={c.hex}
                    onClick={() => copyHex(c.hex)}
                    className="group cursor-pointer rounded-xl border border-[#222222] bg-[#121212] p-2.5 transition-all hover:border-[#FFD400]/50"
                  >
                    <div
                      className="h-10 w-full rounded-lg border border-white/10"
                      style={{ backgroundColor: c.hex }}
                    />
                    <strong className="mt-2 block truncate font-display text-xs text-white">
                      {c.name}
                    </strong>
                    <div className="flex items-center justify-between mt-1">
                      <span className="font-mono text-[0.72rem] text-[#FFD400]">{c.hex}</span>
                      {copiedHex === c.hex ? (
                        <Check size={12} className="text-[#22C55E]" />
                      ) : (
                        <Copy size={12} className="text-[#8A8A8A] opacity-0 group-hover:opacity-100" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2">
              <span className="font-mono text-xs uppercase tracking-wider text-[#8A8A8A]">
                Cores Funcionais (UI, Gráficos & Indicadores)
              </span>
              <div className="mt-2 grid grid-cols-2 sm:grid-cols-5 gap-3">
                {functionalColors.map((c) => (
                  <div
                    key={c.hex}
                    onClick={() => copyHex(c.hex)}
                    className="group cursor-pointer rounded-xl border border-[#222222] bg-[#121212] p-2.5 transition-all hover:border-[#FFD400]/50"
                  >
                    <div
                      className="h-8 w-full rounded-lg border border-white/10"
                      style={{ backgroundColor: c.hex }}
                    />
                    <strong className="mt-2 block truncate font-display text-xs text-white">
                      {c.name}
                    </strong>
                    <div className="flex items-center justify-between mt-1">
                      <span className="font-mono text-[0.72rem] text-[#8A8A8A]">{c.hex}</span>
                      {copiedHex === c.hex ? (
                        <Check size={12} className="text-[#22C55E]" />
                      ) : (
                        <Copy size={12} className="text-[#8A8A8A] opacity-0 group-hover:opacity-100" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Section 4: Tipografia */}
          <section className="space-y-4 border-t border-[#202020] pt-6">
            <div className="flex items-center gap-2">
              <Eye size={18} className="text-[#FFD400]" />
              <h3 className="font-display text-base font-semibold text-white">
                04. Sistema Tipográfico
              </h3>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-[#222222] bg-[#121212] p-4">
                <span className="font-mono text-[0.68rem] text-[#FFD400]">TÍTULOS E IDENTIDADE</span>
                <strong className="mt-1 block font-display text-lg text-white">Sora</strong>
                <p className="mt-2 text-xs text-[#8A8A8A]">
                  Geométrica, moderna e robusta. Utilizada em títulos, destaques e números macro.
                </p>
              </div>

              <div className="rounded-xl border border-[#222222] bg-[#121212] p-4">
                <span className="font-mono text-[0.68rem] text-[#FFD400]">INTERFACE E CORPO</span>
                <strong className="mt-1 block font-sans text-lg text-white">Inter</strong>
                <p className="mt-2 text-xs text-[#8A8A8A]">
                  Alta legibilidade em telas técnicas, relatórios e textos de navegação.
                </p>
              </div>

              <div className="rounded-xl border border-[#222222] bg-[#121212] p-4">
                <span className="font-mono text-[0.68rem] text-[#FFD400]">DADOS E TELEMETRIA</span>
                <strong className="mt-1 block font-mono text-lg text-white">JetBrains Mono</strong>
                <p className="mt-2 text-xs text-[#8A8A8A]">
                  Figuras tabulares, coordenadas, IDs técnicos, grandezas elétricas e tabelas.
                </p>
              </div>
            </div>
          </section>

          {/* Section 5: Usos Incorretos */}
          <section className="space-y-3 border-t border-[#202020] pt-6">
            <div className="flex items-center gap-2">
              <Warning size={18} className="text-[#EF4444]" />
              <h3 className="font-display text-base font-semibold text-white">
                05. Usos Incorretos Proibidos
              </h3>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-[#8A8A8A]">
              <div className="rounded-lg border border-[#331111] bg-[#1A0A0A] p-2.5">
                ❌ Não distorcer ou esticar
              </div>
              <div className="rounded-lg border border-[#331111] bg-[#1A0A0A] p-2.5">
                ❌ Não alterar cores arbitrariamente
              </div>
              <div className="rounded-lg border border-[#331111] bg-[#1A0A0A] p-2.5">
                ❌ Não aplicar sombras 3D ou contornos
              </div>
              <div className="rounded-lg border border-[#331111] bg-[#1A0A0A] p-2.5">
                ❌ Não reposicionar o raio
              </div>
            </div>
          </section>
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-[#202020] pt-4">
          <span className="font-mono text-xs text-[#8A8A8A]">
            Manual oficial integrado ao frontend
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-[#FFD400] bg-[#FFD400] px-5 py-2 text-xs font-bold text-black transition-colors hover:bg-[#FFE033]"
          >
            Entendido
          </button>
        </div>
      </div>
    </div>
  );
};
